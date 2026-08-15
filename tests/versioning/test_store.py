import json
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from hyacinth.excel.contracts import EngineName
from hyacinth.versioning import (
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    write_recovery_manifest,
)


def _record(root: Path) -> ImportedWorkbook:
    original = root / "files" / "file-1" / "original" / "销售.xls"
    working = root / "files" / "file-1" / "working" / "current.xlsx"
    snapshot = root / "files" / "file-1" / "versions" / "version-1" / "snapshot.xlsx"
    version = VersionRecord(
        version_id="version-1",
        file_id="file-1",
        parent_version_id=None,
        name="导入原始文件",
        created_at=datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        operation="import",
        engine=EngineName.COM,
        snapshot_path=snapshot,
        content_hash=sha256(b"snapshot").hexdigest(),
    )
    return ImportedWorkbook("file-1", "销售.xls", original, working, version)


def test_metadata_store_persists_root_version_and_head_with_relative_paths(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)

    store.record_import(record)

    assert store.list_workbooks() == (record,)
    with sqlite3.connect(tmp_path / "library.sqlite3") as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        stored_path = connection.execute(
            "SELECT snapshot_path FROM versions WHERE version_id = ?",
            ("version-1",),
        ).fetchone()[0]
        head = connection.execute(
            "SELECT head_version_id FROM files WHERE file_id = ?",
            ("file-1",),
        ).fetchone()[0]

    assert stored_path == "files/file-1/versions/version-1/snapshot.xlsx"
    assert head == "version-1"


def test_recovery_manifest_can_rebuild_missing_database_record(tmp_path: Path) -> None:
    record = _record(tmp_path)
    version = record.root_version
    assert version is not None
    manifest = version.snapshot_path.parent / "manifest.json"
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    manifest.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"working")
    version.snapshot_path.write_bytes(b"snapshot")
    write_recovery_manifest(manifest, tmp_path, record)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    store = MetadataStore(tmp_path)
    assert store.list_workbooks() == ()

    assert store.reconcile_manifests() == 1
    assert store.list_workbooks() == (record,)
    assert payload["schema_version"] == 1
    assert payload["file"]["head_version_id"] == "version-1"
    assert payload["version"]["parent_version_id"] is None


def test_reconcile_skips_unreadable_or_corrupt_manifests(tmp_path: Path) -> None:
    record = _record(tmp_path)
    version = record.root_version
    assert version is not None
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"working")
    version.snapshot_path.parent.mkdir(parents=True)
    version.snapshot_path.write_bytes(b"corrupt snapshot")
    write_recovery_manifest(version.snapshot_path.parent / "manifest.json", tmp_path, record)

    unreadable_manifest = (
        tmp_path / "files" / "unreadable" / "versions" / "version-2" / "manifest.json"
    )
    unreadable_manifest.mkdir(parents=True)

    store = MetadataStore(tmp_path)
    assert store.reconcile_manifests() == 0
    assert store.list_workbooks() == ()
