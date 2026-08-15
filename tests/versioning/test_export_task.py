import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskEvent, TaskQueue, TaskRequest, TaskState
from hyacinth.versioning import (
    EXPORT_VERSION_OPERATION,
    ExportedVersion,
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    export_version_handlers,
    export_version_task,
    run_export_version_task,
    suggested_export_filename,
)


class ExportContext:
    def __init__(self) -> None:
        self.committed = False

    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def commit(self) -> None:
        self.committed = True

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


def _seed_versions(root: Path) -> tuple[ImportedWorkbook, VersionRecord, VersionRecord]:
    directory = root / "files/file-1"
    original = directory / "original/销售:报表.xls"
    working = directory / "working/current.xlsx"
    root_snapshot = directory / "versions/version-1/snapshot.xlsx"
    child_snapshot = directory / "versions/version-2/snapshot.xlsx"
    for path, content in (
        (original, b"original-xls"),
        (working, b"child-xlsx"),
        (root_snapshot, b"root-xlsx"),
        (child_snapshot, b"child-xlsx"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    root_version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入/原始文件",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "import",
        None,
        root_snapshot,
        sha256(root_snapshot.read_bytes()).hexdigest(),
    )
    record = ImportedWorkbook("file-1", "销售:报表.xls", original, working, root_version)
    store = MetadataStore(root)
    store.record_import(record)
    child = VersionRecord(
        "version-2",
        "file-1",
        root_version.version_id,
        "手动*编辑",
        datetime(2026, 8, 15, 9, 30, tzinfo=UTC),
        "manual-edit",
        EngineName.PYTHON,
        child_snapshot,
        sha256(child_snapshot.read_bytes()).hexdigest(),
    )
    store.record_child_version(child, root_version.version_id)
    return store.get_workbook(record.file_id), root_version, child


def _request(root: Path, version_id: str, downloads: Path) -> TaskRequest:
    return TaskRequest(
        task_id=f"export-{version_id}",
        name="导出版本",
        file_id="file-1",
        engine=None,
        operation=EXPORT_VERSION_OPERATION,
        payload={
            "library_root": str(root),
            "version_id": version_id,
            "destination_directory": str(downloads),
        },
    )


def test_export_handler_is_registered() -> None:
    assert export_version_handlers() == {EXPORT_VERSION_OPERATION: export_version_task}


def test_root_export_preserves_original_format_and_sanitizes_name(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _record, root_version, _child = _seed_versions(root)
    context = ExportContext()

    result = run_export_version_task(_request(root, root_version.version_id, tmp_path), context)

    assert result.path.suffix == ".xls"
    assert result.path.read_bytes() == b"original-xls"
    assert ":" not in result.path.name
    assert "/" not in result.path.name
    assert context.committed


def test_child_export_is_xlsx_and_never_overwrites_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "library"
    record, _root_version, child = _seed_versions(root)
    expected_name = suggested_export_filename(
        record.display_name,
        child.name,
        child.created_at.astimezone().strftime("%Y%m%d-%H%M%S"),
        ".xlsx",
    )
    existing = tmp_path / expected_name
    existing.write_bytes(b"keep-me")

    result = run_export_version_task(_request(root, child.version_id, tmp_path), ExportContext())

    assert existing.read_bytes() == b"keep-me"
    assert result.path.name == f"{existing.stem}(1).xlsx"
    assert result.path.read_bytes() == b"child-xlsx"


def test_task_queue_exports_version_in_worker_process(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _record, _root_version, child = _seed_versions(root)
    queue = TaskQueue(export_version_handlers())
    try:
        queue.submit(_request(root, child.version_id, tmp_path / "downloads"))
        events: list[TaskEvent] = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            events.extend(queue.poll_events())
            if any(event.state in {TaskState.SUCCEEDED, TaskState.FAILED} for event in events):
                break
            time.sleep(0.01)

        succeeded = [event for event in events if event.state is TaskState.SUCCEEDED]
        assert len(succeeded) == 1, [(event.state, event.message) for event in events]
        assert isinstance(succeeded[0].result, ExportedVersion)
        assert succeeded[0].result.path.read_bytes() == b"child-xlsx"
    finally:
        assert queue.shutdown(timeout=5.0) is True
