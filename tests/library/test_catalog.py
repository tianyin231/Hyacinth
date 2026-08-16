import os
from datetime import UTC, datetime
from pathlib import Path

from hyacinth.library.catalog import discover_imported_workbooks
from hyacinth.versioning import ImportedWorkbook, MetadataStore, VersionRecord


def test_discovery_returns_only_complete_published_workbooks(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    complete = library_root / "files" / "file-complete"
    original = complete / "original" / "销售报表.xlsx"
    working = complete / "working" / "current.xlsx"
    original.parent.mkdir(parents=True)
    working.parent.mkdir(parents=True)
    original.write_bytes(b"original")
    working.write_bytes(b"working")
    incomplete = library_root / "files" / "file-incomplete" / "original"
    incomplete.mkdir(parents=True)
    (incomplete / "未完成.xlsx").write_bytes(b"partial")

    records = discover_imported_workbooks(library_root)

    assert len(records) == 1
    assert records[0].file_id == "file-complete"
    assert records[0].display_name == "销售报表.xlsx"
    assert records[0].original_path == original
    assert records[0].working_path == working
    assert records[0].root_version is None


def test_discovery_orders_newest_published_directory_first(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    for file_id, timestamp in (("a-old", 1), ("z-new", 2)):
        directory = library_root / "files" / file_id
        original = directory / "original" / f"{file_id}.xlsx"
        working = directory / "working" / "current.xlsx"
        original.parent.mkdir(parents=True)
        working.parent.mkdir(parents=True)
        original.write_bytes(b"original")
        working.write_bytes(b"working")
        os.utime(directory, (timestamp, timestamp))

    records = discover_imported_workbooks(library_root)

    assert [record.file_id for record in records] == ["z-new", "a-old"]


def test_discovery_prefers_sqlite_metadata_and_root_version(tmp_path: Path) -> None:
    directory = tmp_path / "files" / "file-1"
    version = VersionRecord(
        version_id="version-1",
        file_id="file-1",
        parent_version_id=None,
        name="导入原始文件",
        created_at=datetime(2026, 8, 15, tzinfo=UTC),
        operation="import",
        engine=None,
        snapshot_path=directory / "versions" / "version-1" / "snapshot.xlsx",
        content_hash="a" * 64,
    )
    record = ImportedWorkbook(
        "file-1",
        "销售.xlsx",
        directory / "original" / "销售.xlsx",
        directory / "working" / "current.xlsx",
        version,
        version.created_at,
    )
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    version.snapshot_path.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"working")
    version.snapshot_path.write_bytes(b"snapshot")
    MetadataStore(tmp_path).record_import(record)

    assert discover_imported_workbooks(tmp_path) == (record,)


def test_discovery_does_not_return_metadata_without_published_files(tmp_path: Path) -> None:
    directory = tmp_path / "files" / "missing"
    version = VersionRecord(
        version_id="version-missing",
        file_id="missing",
        parent_version_id=None,
        name="导入原始文件",
        created_at=datetime(2026, 8, 15, tzinfo=UTC),
        operation="import",
        engine=None,
        snapshot_path=directory / "versions" / "version-missing" / "snapshot.xlsx",
        content_hash="a" * 64,
    )
    MetadataStore(tmp_path).record_import(
        ImportedWorkbook(
            "missing",
            "缺失.xlsx",
            directory / "original" / "缺失.xlsx",
            directory / "working" / "current.xlsx",
            version,
        )
    )

    assert discover_imported_workbooks(tmp_path) == ()
