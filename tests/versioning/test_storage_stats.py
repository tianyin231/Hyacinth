from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from hyacinth.tasks import TaskRequest
from hyacinth.versioning import (
    VERSION_STORAGE_STATS_OPERATION,
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    VersionStorageStats,
    run_version_storage_stats_task,
    version_storage_stats_handlers,
)


class StorageStatsContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def commit(self) -> None:
        return

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


def _seed_versions(root: Path) -> tuple[ImportedWorkbook, VersionRecord, VersionRecord]:
    directory = root / "files/file-1"
    original = directory / "original/销售报表.xlsx"
    working = directory / "working/current.xlsx"
    root_snapshot = directory / "versions/version-1/snapshot.xlsx"
    child_snapshot = directory / "versions/version-2/snapshot.xlsx"
    shared_snapshot = directory / "versions/version-3/snapshot.xlsx"
    for path, content in (
        (original, b"original-xlsx"),
        (working, b"child-xlsx"),
        (root_snapshot, b"root-content-40-bytes-padding-padding-pad!"),
        (child_snapshot, b"child-content-32-bytes-padding!!"),
        (shared_snapshot, b"shared-content-30-bytes-padd!"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    root_version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 16, 8, 0, tzinfo=UTC),
        "import",
        None,
        root_snapshot,
        sha256(root_snapshot.read_bytes()).hexdigest(),
    )
    child_version = VersionRecord(
        "version-2",
        "file-1",
        root_version.version_id,
        "多列排序",
        datetime(2026, 8, 16, 9, 0, tzinfo=UTC),
        "sort",
        None,
        child_snapshot,
        sha256(child_snapshot.read_bytes()).hexdigest(),
    )
    record = ImportedWorkbook("file-1", "销售报表.xlsx", original, working, root_version)
    store = MetadataStore(root)
    store.record_import(record)
    store.record_child_version(child_version, root_version.version_id)
    return record, root_version, child_version


def _request(root: Path, preview_version_id: str | None) -> TaskRequest:
    return TaskRequest(
        task_id="task-1",
        name="统计版本占用",
        file_id="file-1",
        engine=None,
        operation=VERSION_STORAGE_STATS_OPERATION,
        payload={
            "library_root": str(root),
            "preview_version_id": preview_version_id,
        },
    )


def test_storage_stats_sums_unique_snapshot_sizes_and_previewed_version(
    tmp_path: Path,
) -> None:
    root = tmp_path / "library"
    _record, root_version, child_version = _seed_versions(root)
    shared_snapshot = root / "files/file-1/versions/version-3/snapshot.xlsx"
    store = MetadataStore(root)
    shared_version = VersionRecord(
        "version-3",
        "file-1",
        child_version.version_id,
        "手动编辑",
        datetime(2026, 8, 16, 10, 0, tzinfo=UTC),
        "manual-edit",
        None,
        shared_snapshot,
        sha256(shared_snapshot.read_bytes()).hexdigest(),
    )
    store.record_child_version(shared_version, child_version.version_id)

    result = run_version_storage_stats_task(
        _request(root, child_version.version_id), StorageStatsContext()
    )

    expected_total = (
        root_version.snapshot_path.stat().st_size
        + child_version.snapshot_path.stat().st_size
        + shared_snapshot.stat().st_size
    )
    assert result == VersionStorageStats(
        total_bytes=expected_total,
        preview_bytes=child_version.snapshot_path.stat().st_size,
    )


def test_storage_stats_without_preview_version_reports_zero_preview(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _record, root_version, _child = _seed_versions(root)

    result = run_version_storage_stats_task(_request(root, None), StorageStatsContext())

    assert result.preview_bytes == 0
    assert result.total_bytes > 0


def test_storage_stats_counts_shared_snapshot_once(tmp_path: Path) -> None:
    root = tmp_path / "library"
    record, root_version, child_version = _seed_versions(root)
    store = MetadataStore(root)
    twin = VersionRecord(
        "version-2-twin",
        "file-1",
        child_version.version_id,
        "手动编辑",
        datetime(2026, 8, 16, 11, 0, tzinfo=UTC),
        "manual-edit",
        None,
        child_version.snapshot_path,
        child_version.content_hash,
    )
    store.record_child_version(twin, child_version.version_id)
    twin_only = run_version_storage_stats_task(
        _request(root, twin.version_id), StorageStatsContext()
    )
    child_only = run_version_storage_stats_task(
        _request(root, child_version.version_id), StorageStatsContext()
    )

    assert twin_only.total_bytes == child_only.total_bytes
    assert twin_only.total_bytes == (
        root_version.snapshot_path.stat().st_size + child_version.snapshot_path.stat().st_size
    )


def test_storage_stats_ignores_missing_snapshot_files(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _record, root_version, child_version = _seed_versions(root)
    child_version.snapshot_path.unlink()

    result = run_version_storage_stats_task(
        _request(root, child_version.version_id), StorageStatsContext()
    )

    assert result == VersionStorageStats(
        total_bytes=root_version.snapshot_path.stat().st_size,
        preview_bytes=0,
    )


def test_storage_stats_handlers_register_operation() -> None:
    handlers = version_storage_stats_handlers()

    assert set(handlers) == {VERSION_STORAGE_STATS_OPERATION}
