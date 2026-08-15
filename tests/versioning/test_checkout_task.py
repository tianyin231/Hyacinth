import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskEvent, TaskQueue, TaskRequest, TaskState
from hyacinth.versioning import (
    CHECKOUT_VERSION_OPERATION,
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    checkout_version_handlers,
    checkout_version_task,
    run_checkout_version_task,
)


class RecordingContext:
    def __init__(self) -> None:
        self.committed = False
        self.critical_messages: list[str] = []

    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def set_engine(self, engine: EngineName) -> None:
        assert engine is EngineName.PYTHON

    def commit(self) -> None:
        self.committed = True

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        self.critical_messages.append(message)
        yield


def _seed_branch(root: Path) -> tuple[ImportedWorkbook, VersionRecord, VersionRecord]:
    directory = root / "files/file-1"
    original = directory / "original/销售.xlsx"
    working = directory / "working/current.xlsx"
    root_snapshot = directory / "versions/version-1/snapshot.xlsx"
    child_snapshot = directory / "versions/version-2/snapshot.xlsx"
    for path, content in (
        (original, b"original"),
        (working, b"child"),
        (root_snapshot, b"root"),
        (child_snapshot, b"child"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    root_version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "import",
        None,
        root_snapshot,
        sha256(b"root").hexdigest(),
    )
    child_version = VersionRecord(
        "version-2",
        "file-1",
        "version-1",
        "多列排序",
        datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        child_snapshot,
        sha256(b"child").hexdigest(),
    )
    record = ImportedWorkbook("file-1", "销售.xlsx", original, working, root_version)
    store = MetadataStore(root)
    store.record_import(record)
    store.record_child_version(child_version, root_version.version_id)
    return record, root_version, child_version


def _request(root: Path) -> TaskRequest:
    return TaskRequest(
        "checkout-1",
        "从导入原始文件继续",
        "file-1",
        None,
        CHECKOUT_VERSION_OPERATION,
        {
            "library_root": str(root),
            "version_id": "version-1",
            "expected_head_version_id": "version-2",
        },
    )


def test_checkout_handler_is_registered() -> None:
    assert checkout_version_handlers() == {
        CHECKOUT_VERSION_OPERATION: checkout_version_task,
    }


def test_checkout_switches_head_and_working_copy_without_removing_branch(tmp_path: Path) -> None:
    record, root_version, child_version = _seed_branch(tmp_path)
    context = RecordingContext()

    result = run_checkout_version_task(_request(tmp_path), context)

    assert result.head_version == root_version
    assert record.working_path.read_bytes() == b"root"
    assert MetadataStore(tmp_path).list_versions("file-1") == (root_version, child_version)
    assert context.committed
    assert context.critical_messages == ["正在安全切换当前工作版本"]


def test_checkout_rejects_corrupt_snapshot_without_moving_head(tmp_path: Path) -> None:
    record, _root_version, child_version = _seed_branch(tmp_path)
    target = tmp_path / "files/file-1/versions/version-1/snapshot.xlsx"
    target.write_bytes(b"corrupt")

    with pytest.raises(ValueError, match="哈希"):
        run_checkout_version_task(_request(tmp_path), RecordingContext())

    assert MetadataStore(tmp_path).get_workbook("file-1").head_version == child_version
    assert record.working_path.read_bytes() == b"child"


def test_task_queue_checks_out_version_in_worker_process(tmp_path: Path) -> None:
    _seed_branch(tmp_path)
    queue = TaskQueue(checkout_version_handlers())
    try:
        queue.submit(_request(tmp_path))
        events: list[TaskEvent] = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            events.extend(queue.poll_events())
            if any(event.state in {TaskState.SUCCEEDED, TaskState.FAILED} for event in events):
                break
            time.sleep(0.01)

        succeeded = [event for event in events if event.state is TaskState.SUCCEEDED]
        assert len(succeeded) == 1, [(event.state, event.message) for event in events]
        result = succeeded[0].result
        assert isinstance(result, ImportedWorkbook)
        assert result.head_version is not None
        assert result.head_version.version_id == "version-1"
    finally:
        assert queue.shutdown(timeout=5.0) is True
