import json
import os
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from hyacinth.excel.contracts import EngineName
from hyacinth.versioning.models import (
    ImportedWorkbook,
    VersionDeletionPlan,
    VersionLayout,
    VersionRecord,
)

DATABASE_NAME = "library.sqlite3"
MANIFEST_NAME = "manifest.json"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    working_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    head_version_id TEXT NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS versions (
    version_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
    parent_version_id TEXT REFERENCES versions(version_id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    operation TEXT NOT NULL,
    engine TEXT,
    snapshot_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS versions_file_id ON versions(file_id);
CREATE TABLE IF NOT EXISTS version_layouts (
    version_id TEXT PRIMARY KEY REFERENCES versions(version_id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    fixed INTEGER NOT NULL DEFAULT 1
);
"""


class MetadataStore:
    def __init__(self, library_root: Path) -> None:
        self._library_root = library_root
        self._database_path = library_root / DATABASE_NAME

    @property
    def database_path(self) -> Path:
        return self._database_path

    def record_import(self, record: ImportedWorkbook) -> None:
        version = record.root_version
        if version is None:
            raise ValueError("导入记录缺少根版本")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO files (
                    file_id, display_name, original_path, working_path,
                    imported_at, head_version_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.file_id,
                    record.display_name,
                    self._relative(record.original_path),
                    self._relative(record.working_path),
                    version.created_at.isoformat(),
                    version.version_id,
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO versions (
                    version_id, file_id, parent_version_id, name, created_at,
                    operation, engine, snapshot_path, content_hash, parameters_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.version_id,
                    version.file_id,
                    version.parent_version_id,
                    version.name,
                    version.created_at.isoformat(),
                    version.operation,
                    version.engine.value if version.engine is not None else None,
                    self._relative(version.snapshot_path),
                    version.content_hash,
                    version.parameters_json,
                ),
            )

    def record_child_version(
        self,
        version: VersionRecord,
        expected_parent_version_id: str,
    ) -> None:
        if version.parent_version_id != expected_parent_version_id:
            raise ValueError("子版本的父版本与预期 HEAD 不一致")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO versions (
                    version_id, file_id, parent_version_id, name, created_at,
                    operation, engine, snapshot_path, content_hash, parameters_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.version_id,
                    version.file_id,
                    version.parent_version_id,
                    version.name,
                    version.created_at.isoformat(),
                    version.operation,
                    version.engine.value if version.engine is not None else None,
                    self._relative(version.snapshot_path),
                    version.content_hash,
                    version.parameters_json,
                ),
            )
            updated = connection.execute(
                """
                UPDATE files
                SET head_version_id = ?
                WHERE file_id = ? AND head_version_id = ?
                """,
                (version.version_id, version.file_id, expected_parent_version_id),
            )
            if updated.rowcount != 1:
                raise ValueError("当前 HEAD 已变化，请重新生成预览")

    def list_workbooks(self) -> tuple[ImportedWorkbook, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    f.file_id, f.display_name, f.original_path, f.working_path,
                    v.version_id, v.parent_version_id, v.name, v.created_at,
                    v.operation, v.engine, v.snapshot_path, v.content_hash
                    , v.parameters_json, v.deleted_at,
                    f.imported_at, f.deleted_at
                FROM files AS f
                JOIN versions AS v ON v.version_id = f.head_version_id
                WHERE f.deleted_at IS NULL
                ORDER BY f.imported_at DESC
                """
            ).fetchall()
        return tuple(self._workbook_from_row(row) for row in rows)

    def list_deleted_files(self) -> tuple[ImportedWorkbook, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    f.file_id, f.display_name, f.original_path, f.working_path,
                    v.version_id, v.parent_version_id, v.name, v.created_at,
                    v.operation, v.engine, v.snapshot_path, v.content_hash
                    , v.parameters_json, v.deleted_at,
                    f.imported_at, f.deleted_at
                FROM files AS f
                JOIN versions AS v ON v.version_id = f.head_version_id
                WHERE f.deleted_at IS NOT NULL
                ORDER BY f.deleted_at DESC
                """
            ).fetchall()
        return tuple(self._workbook_from_row(row) for row in rows)

    def get_deleted_file(self, file_id: str) -> ImportedWorkbook:
        records = {record.file_id: record for record in self.list_deleted_files()}
        try:
            return records[file_id]
        except KeyError as error:
            raise ValueError(f"回收站中找不到文件记录：{file_id}") from error

    def soft_delete_file(
        self,
        file_id: str,
        expected_head_version_id: str,
        *,
        deleted_at: datetime | None = None,
    ) -> ImportedWorkbook:
        timestamp = deleted_at or datetime.now().astimezone()
        with self._connection() as connection:
            updated = connection.execute(
                """
                UPDATE files SET deleted_at = ?
                WHERE file_id = ? AND head_version_id = ? AND deleted_at IS NULL
                """,
                (timestamp.isoformat(), file_id, expected_head_version_id),
            )
            if updated.rowcount != 1:
                raise ValueError("文件不存在、已删除或当前工作版本已变化，请刷新文件列表")
        return self.get_deleted_file(file_id)

    def restore_file(self, file_id: str) -> ImportedWorkbook:
        with self._connection() as connection:
            updated = connection.execute(
                """
                UPDATE files SET deleted_at = NULL
                WHERE file_id = ? AND deleted_at IS NOT NULL
                """,
                (file_id,),
            )
            if updated.rowcount != 1:
                raise ValueError(f"文件未删除或不存在：{file_id}")
        return self.get_workbook(file_id)

    def purge_file_records(self, file_id: str) -> None:
        with self._connection() as connection:
            deleted = connection.execute(
                "SELECT 1 FROM files WHERE file_id = ? AND deleted_at IS NOT NULL",
                (file_id,),
            ).fetchone()
            if deleted is None:
                raise ValueError(f"只有回收站中的文件才能永久删除：{file_id}")
            connection.execute("DELETE FROM files WHERE file_id = ?", (file_id,))

    def get_workbook(self, file_id: str) -> ImportedWorkbook:
        records = {record.file_id: record for record in self.list_workbooks()}
        try:
            return records[file_id]
        except KeyError as error:
            raise ValueError(f"找不到文件记录：{file_id}") from error

    def list_versions(self, file_id: str) -> tuple[VersionRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT version_id, file_id, parent_version_id, name, created_at,
                       operation, engine, snapshot_path, content_hash, parameters_json,
                       deleted_at
                FROM versions
                WHERE file_id = ?
                ORDER BY created_at, version_id
                """,
                (file_id,),
            ).fetchall()
        return tuple(self._version_from_row(row) for row in rows)

    def get_version(self, file_id: str, version_id: str) -> VersionRecord:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT version_id, file_id, parent_version_id, name, created_at,
                       operation, engine, snapshot_path, content_hash, parameters_json,
                       deleted_at
                FROM versions
                WHERE file_id = ? AND version_id = ?
                """,
                (file_id, version_id),
            ).fetchone()
        if row is None:
            raise ValueError(f"找不到版本记录：{version_id}")
        return self._version_from_row(row)

    def switch_head(
        self,
        file_id: str,
        version_id: str,
        expected_head_version_id: str,
    ) -> VersionRecord:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT version_id, file_id, parent_version_id, name, created_at,
                       operation, engine, snapshot_path, content_hash, parameters_json,
                       deleted_at
                FROM versions
                WHERE file_id = ? AND version_id = ? AND deleted_at IS NULL
                """,
                (file_id, version_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"找不到版本记录：{version_id}")
            updated = connection.execute(
                """
                UPDATE files
                SET head_version_id = ?
                WHERE file_id = ? AND head_version_id = ?
                """,
                (version_id, file_id, expected_head_version_id),
            )
            if updated.rowcount != 1:
                raise ValueError("当前 HEAD 已变化，请刷新版本树")
        return self._version_from_row(row)

    def plan_version_deletion(self, file_id: str, version_id: str) -> VersionDeletionPlan:
        with self._connection() as connection:
            return self._plan_version_deletion(connection, file_id, version_id)

    def soft_delete_version(
        self,
        file_id: str,
        version_id: str,
        expected_head_version_id: str,
        replacement_version_id: str | None = None,
        *,
        deleted_at: datetime | None = None,
    ) -> tuple[VersionRecord, VersionRecord | None]:
        with self._connection() as connection:
            plan = self._plan_version_deletion(connection, file_id, version_id)
            if plan.current_head_version_id != expected_head_version_id:
                raise ValueError("当前 HEAD 已变化，请刷新版本树")
            replacement: VersionRecord | None = None
            if plan.requires_head_switch:
                candidate_ids = {candidate.version_id for candidate in plan.replacement_candidates}
                if replacement_version_id is None:
                    if len(plan.replacement_candidates) != 1:
                        raise ValueError("删除当前 HEAD 前请选择新的工作版本")
                    replacement = plan.replacement_candidates[0]
                else:
                    if replacement_version_id not in candidate_ids:
                        raise ValueError("所选的新 HEAD 不是可用的相邻版本")
                    replacement = next(
                        candidate
                        for candidate in plan.replacement_candidates
                        if candidate.version_id == replacement_version_id
                    )
                updated = connection.execute(
                    """
                    UPDATE files SET head_version_id = ?
                    WHERE file_id = ? AND head_version_id = ?
                    """,
                    (replacement.version_id, file_id, expected_head_version_id),
                )
                if updated.rowcount != 1:
                    raise ValueError("当前 HEAD 已变化，请刷新版本树")
            timestamp = deleted_at or datetime.now().astimezone()
            updated = connection.execute(
                """
                UPDATE versions SET deleted_at = ?
                WHERE file_id = ? AND version_id = ? AND deleted_at IS NULL
                """,
                (timestamp.isoformat(), file_id, version_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"版本已删除或不存在：{version_id}")
        return self.get_version(file_id, version_id), replacement

    def restore_version(self, file_id: str, version_id: str) -> VersionRecord:
        with self._connection() as connection:
            updated = connection.execute(
                """
                UPDATE versions SET deleted_at = NULL
                WHERE file_id = ? AND version_id = ? AND deleted_at IS NOT NULL
                """,
                (file_id, version_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"版本未删除或不存在：{version_id}")
        return self.get_version(file_id, version_id)

    def list_version_layouts(self, file_id: str) -> dict[str, VersionLayout]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT l.version_id, l.x, l.y, l.fixed
                FROM version_layouts AS l
                JOIN versions AS v ON v.version_id = l.version_id
                WHERE v.file_id = ?
                """,
                (file_id,),
            ).fetchall()
        return {
            str(version_id): VersionLayout(float(x), float(y), bool(fixed))
            for version_id, x, y, fixed in rows
        }

    def save_version_layout(
        self,
        file_id: str,
        version_id: str,
        x: float,
        y: float,
        *,
        fixed: bool,
    ) -> None:
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM versions WHERE file_id = ? AND version_id = ?",
                (file_id, version_id),
            ).fetchone()
            if exists is None:
                raise ValueError(f"找不到文件中的版本记录：{version_id}")
            connection.execute(
                """
                INSERT INTO version_layouts (version_id, x, y, fixed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(version_id) DO UPDATE SET
                    x = excluded.x,
                    y = excluded.y,
                    fixed = excluded.fixed
                """,
                (version_id, x, y, int(fixed)),
            )

    def _plan_version_deletion(
        self,
        connection: sqlite3.Connection,
        file_id: str,
        version_id: str,
    ) -> VersionDeletionPlan:
        rows = connection.execute(
            """
            SELECT version_id, file_id, parent_version_id, name, created_at,
                   operation, engine, snapshot_path, content_hash, parameters_json,
                   deleted_at
            FROM versions WHERE file_id = ? ORDER BY created_at, version_id
            """,
            (file_id,),
        ).fetchall()
        records = {record.version_id: record for record in map(self._version_from_row, rows)}
        target = records.get(version_id)
        if target is None:
            raise ValueError(f"找不到版本记录：{version_id}")
        if target.deleted_at is not None:
            raise ValueError("该版本已删除")
        active = [record for record in records.values() if record.deleted_at is None]
        if len(active) == 1:
            raise ValueError("文件只剩一个可用版本，不能删除；请删除整个文件记录")
        head_row = connection.execute(
            "SELECT head_version_id FROM files WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if head_row is None:
            raise ValueError(f"找不到文件记录：{file_id}")
        head_id = str(head_row[0])
        candidates: tuple[VersionRecord, ...] = ()
        if version_id == head_id:
            ancestor_id = target.parent_version_id
            while ancestor_id is not None:
                ancestor = records.get(ancestor_id)
                if ancestor is None:
                    break
                if ancestor.deleted_at is None:
                    candidates = (ancestor,)
                    break
                ancestor_id = ancestor.parent_version_id
            if not candidates:
                children: dict[str, list[VersionRecord]] = {}
                for record in records.values():
                    if record.parent_version_id is not None:
                        children.setdefault(record.parent_version_id, []).append(record)
                frontier = list(children.get(version_id, ()))
                found: list[VersionRecord] = []
                while frontier:
                    candidate = frontier.pop(0)
                    if candidate.deleted_at is None:
                        found.append(candidate)
                    else:
                        frontier.extend(children.get(candidate.version_id, ()))
                candidates = tuple(found)
            if not candidates:
                raise ValueError("当前 HEAD 没有可切换的父版本或子版本")
        return VersionDeletionPlan(target, head_id, candidates)

    def reconcile_manifests(self) -> int:
        recovered = 0
        files_root = self._library_root / "files"
        if not files_root.is_dir():
            return 0
        candidates: list[ImportedWorkbook] = []
        for manifest in files_root.glob(f"*/versions/*/{MANIFEST_NAME}"):
            try:
                record = read_recovery_manifest(manifest, self._library_root)
                version = record.root_version
                if version is None:
                    continue
                if (
                    not record.original_path.is_file()
                    or not record.working_path.is_file()
                    or not version.snapshot_path.is_file()
                    or _content_hash(version.snapshot_path) != version.content_hash
                ):
                    continue
                candidates.append(record)
            except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
                continue
        candidates.sort(
            key=lambda record: (
                record.head_version.created_at.timestamp()
                if record.head_version is not None
                else 0.0
            )
        )
        for record in candidates:
            version = record.head_version
            if version is None:
                continue
            try:
                current = self.get_workbook(record.file_id)
            except ValueError:
                if version.parent_version_id is not None:
                    continue
                self.record_import(record)
                recovered += 1
                continue
            current_head = current.head_version
            if current_head is None:
                continue
            if current_head.version_id == version.version_id:
                if _content_hash(current.working_path) != version.content_hash:
                    _atomic_copy(version.snapshot_path, current.working_path)
                    recovered += 1
                continue
            try:
                self.get_version(record.file_id, version.version_id)
            except ValueError:
                pass
            else:
                continue
            if version.parent_version_id != current_head.version_id:
                continue
            _atomic_copy(version.snapshot_path, current.working_path)
            self.record_child_version(version, current_head.version_id)
            recovered += 1
        return recovered

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._library_root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            _ensure_schema(connection)
            with connection:
                yield connection
        finally:
            connection.close()

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._library_root).as_posix()

    def _workbook_from_row(self, row: tuple[object, ...]) -> ImportedWorkbook:
        engine_value = row[9]
        engine = EngineName(str(engine_value)) if engine_value is not None else None
        version = VersionRecord(
            version_id=str(row[4]),
            file_id=str(row[0]),
            parent_version_id=str(row[5]) if row[5] is not None else None,
            name=str(row[6]),
            created_at=_parse_datetime(row[7]),
            operation=str(row[8]),
            engine=engine,
            snapshot_path=self._library_root / str(row[10]),
            content_hash=str(row[11]),
            parameters_json=str(row[12]),
            deleted_at=_parse_optional_datetime(row[13]),
        )
        return ImportedWorkbook(
            file_id=str(row[0]),
            display_name=str(row[1]),
            original_path=self._library_root / str(row[2]),
            working_path=self._library_root / str(row[3]),
            root_version=version,
            imported_at=_parse_optional_datetime(row[14]),
            deleted_at=_parse_optional_datetime(row[15]),
        )

    def _version_from_row(self, row: tuple[object, ...]) -> VersionRecord:
        engine_value = row[6]
        return VersionRecord(
            version_id=str(row[0]),
            file_id=str(row[1]),
            parent_version_id=str(row[2]) if row[2] is not None else None,
            name=str(row[3]),
            created_at=_parse_datetime(row[4]),
            operation=str(row[5]),
            engine=EngineName(str(engine_value)) if engine_value is not None else None,
            snapshot_path=self._library_root / str(row[7]),
            content_hash=str(row[8]),
            parameters_json=str(row[9]),
            deleted_at=_parse_optional_datetime(row[10]),
        )


def write_recovery_manifest(
    manifest_path: Path,
    library_root: Path,
    record: ImportedWorkbook,
) -> None:
    version = record.root_version
    if version is None:
        raise ValueError("导入记录缺少根版本")
    payload = {
        "schema_version": 1,
        "file": {
            "file_id": record.file_id,
            "display_name": record.display_name,
            "original_path": record.original_path.relative_to(library_root).as_posix(),
            "working_path": record.working_path.relative_to(library_root).as_posix(),
            "head_version_id": version.version_id,
        },
        "version": {
            "version_id": version.version_id,
            "file_id": version.file_id,
            "parent_version_id": version.parent_version_id,
            "name": version.name,
            "created_at": version.created_at.isoformat(),
            "operation": version.operation,
            "engine": version.engine.value if version.engine is not None else None,
            "snapshot_path": version.snapshot_path.relative_to(library_root).as_posix(),
            "content_hash": version.content_hash,
            "parameters_json": version.parameters_json,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_recovery_manifest(manifest_path: Path, library_root: Path) -> ImportedWorkbook:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload["schema_version"] != 1:
        raise ValueError("不支持的恢复清单版本")
    file_data = payload["file"]
    version_data = payload["version"]
    engine_value = version_data["engine"]
    version = VersionRecord(
        version_id=str(version_data["version_id"]),
        file_id=str(version_data["file_id"]),
        parent_version_id=(
            str(version_data["parent_version_id"])
            if version_data["parent_version_id"] is not None
            else None
        ),
        name=str(version_data["name"]),
        created_at=_parse_datetime(version_data["created_at"]),
        operation=str(version_data["operation"]),
        engine=EngineName(str(engine_value)) if engine_value is not None else None,
        snapshot_path=library_root / str(version_data["snapshot_path"]),
        content_hash=str(version_data["content_hash"]),
        parameters_json=str(version_data.get("parameters_json", "{}")),
    )
    if file_data["head_version_id"] != version.version_id:
        raise ValueError("恢复清单的 HEAD 与根版本不一致")
    if file_data["file_id"] != version.file_id:
        raise ValueError("恢复清单的文件 ID 不一致")
    return ImportedWorkbook(
        file_id=str(file_data["file_id"]),
        display_name=str(file_data["display_name"]),
        original_path=library_root / str(file_data["original_path"]),
        working_path=library_root / str(file_data["working_path"]),
        root_version=version,
    )


def _parse_datetime(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_optional_datetime(value: object) -> datetime | None:
    return None if value is None else _parse_datetime(value)


def _content_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(_SCHEMA)
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(versions)")}
    if "parameters_json" not in columns:
        connection.execute(
            "ALTER TABLE versions ADD COLUMN parameters_json TEXT NOT NULL DEFAULT '{}'"
        )
    if "deleted_at" not in columns:
        connection.execute("ALTER TABLE versions ADD COLUMN deleted_at TEXT")
    file_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(files)")}
    if "deleted_at" not in file_columns:
        connection.execute("ALTER TABLE files ADD COLUMN deleted_at TEXT")


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.recovery.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
