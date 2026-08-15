import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from hyacinth.excel.contracts import EngineName
from hyacinth.versioning.models import ImportedWorkbook, VersionRecord

DATABASE_NAME = "library.sqlite3"
MANIFEST_NAME = "manifest.json"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    working_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    head_version_id TEXT NOT NULL
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
    content_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS versions_file_id ON versions(file_id);
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
                    operation, engine, snapshot_path, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def list_workbooks(self) -> tuple[ImportedWorkbook, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    f.file_id, f.display_name, f.original_path, f.working_path,
                    v.version_id, v.parent_version_id, v.name, v.created_at,
                    v.operation, v.engine, v.snapshot_path, v.content_hash
                FROM files AS f
                JOIN versions AS v ON v.version_id = f.head_version_id
                ORDER BY f.imported_at DESC
                """
            ).fetchall()
        return tuple(self._workbook_from_row(row) for row in rows)

    def reconcile_manifests(self) -> int:
        known_ids = {record.file_id for record in self.list_workbooks()}
        recovered = 0
        files_root = self._library_root / "files"
        if not files_root.is_dir():
            return 0
        for manifest in files_root.glob(f"*/versions/*/{MANIFEST_NAME}"):
            try:
                record = read_recovery_manifest(manifest, self._library_root)
                version = record.root_version
                if version is None or record.file_id in known_ids:
                    continue
                if (
                    not record.original_path.is_file()
                    or not record.working_path.is_file()
                    or not version.snapshot_path.is_file()
                    or _content_hash(version.snapshot_path) != version.content_hash
                ):
                    continue
                self.record_import(record)
            except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
                continue
            known_ids.add(record.file_id)
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
            connection.executescript(_SCHEMA)
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
        )
        return ImportedWorkbook(
            file_id=str(row[0]),
            display_name=str(row[1]),
            original_path=self._library_root / str(row[2]),
            working_path=self._library_root / str(row[3]),
            root_version=version,
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


def _content_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
