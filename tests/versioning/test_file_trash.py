import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from hyacinth.tasks import TaskEvent, TaskQueue, TaskRequest, TaskState
from hyacinth.versioning import (
    PURGE_FILE_OPERATION,
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    purge_file_handlers,
    run_purge_file_task,
)


class PurgeContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return


def _seed_library(root: Path) -> ImportedWorkbook:
    directory = root / "files/file-1"
    original = directory / "original/销售报表.xlsx"
    working = directory / "working/current.xlsx"
    snapshot = directory / "versions/version-1/snapshot.xlsx"
    for path, content in (
        (original, b"original-xlsx"),
        (working, b"root-xlsx"),
        (snapshot, b"root-xlsx"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 16, 8, 0, tzinfo=UTC),
        "import",
        None,
        snapshot,
        sha256(snapshot.read_bytes()).hexdigest(),
    )
    record = ImportedWorkbook(
        "file-1",
        "销售报表.xlsx",
        original,
        working,
        version,
        datetime(2026, 8, 16, 8, 0, tzinfo=UTC),
    )
    MetadataStore(root).record_import(record)
    return record


def _purge_request(root: Path) -> TaskRequest:
    return TaskRequest(
        task_id="task-1",
        name="永久删除 销售报表.xlsx",
        file_id="file-1",
        engine=None,
        operation=PURGE_FILE_OPERATION,
        payload={"library_root": str(root)},
    )


def test_soft_delete_file_moves_record_to_trash_and_back(tmp_path: Path) -> None:
    root = tmp_path / "library"
    record = _seed_library(root)
    assert record.head_version is not None
    store = MetadataStore(root)

    deleted = store.soft_delete_file(record.file_id, record.head_version.version_id)

    assert deleted.deleted_at is not None
    assert record.file_id not in {item.file_id for item in store.list_workbooks()}
    assert [item.file_id for item in store.list_deleted_files()] == [record.file_id]
    assert (root / "files/file-1/versions/version-1/snapshot.xlsx").is_file()

    restored = store.restore_file(record.file_id)

    assert restored.deleted_at is None
    assert restored.imported_at == record.imported_at
    assert [item.file_id for item in store.list_workbooks()] == [record.file_id]
    assert store.list_deleted_files() == ()


def test_soft_delete_file_rejects_stale_head_missing_and_double_delete(
    tmp_path: Path,
) -> None:
    root = tmp_path / "library"
    record = _seed_library(root)
    assert record.head_version is not None
    store = MetadataStore(root)
    head_id = record.head_version.version_id

    with pytest.raises(ValueError):
        store.soft_delete_file(record.file_id, "other-head")
    with pytest.raises(ValueError):
        store.soft_delete_file("missing-file", head_id)

    store.soft_delete_file(record.file_id, head_id)

    with pytest.raises(ValueError):
        store.soft_delete_file(record.file_id, head_id)
    with pytest.raises(ValueError):
        store.restore_file("missing-file")


def test_purge_file_task_removes_directory_and_records(tmp_path: Path) -> None:
    root = tmp_path / "library"
    record = _seed_library(root)
    assert record.head_version is not None
    store = MetadataStore(root)
    store.soft_delete_file(record.file_id, record.head_version.version_id)

    result = run_purge_file_task(_purge_request(root), PurgeContext())

    assert result.file_id == record.file_id
    assert result.display_name == record.display_name
    assert not (root / "files/file-1").exists()
    assert not list((root / "files").glob(".purge-*"))
    assert store.list_deleted_files() == ()


def test_purge_file_task_requires_soft_deleted_record(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _seed_library(root)

    with pytest.raises(ValueError):
        run_purge_file_task(_purge_request(root), PurgeContext())

    assert (root / "files/file-1/versions/version-1/snapshot.xlsx").is_file()


def test_purge_file_handlers_register_operation() -> None:
    assert set(purge_file_handlers()) == {PURGE_FILE_OPERATION}


def test_real_task_queue_purges_file(tmp_path: Path) -> None:
    root = tmp_path / "library"
    record = _seed_library(root)
    assert record.head_version is not None
    MetadataStore(root).soft_delete_file(record.file_id, record.head_version.version_id)
    queue = TaskQueue(purge_file_handlers())
    request = TaskRequest(
        task_id="purge-task",
        name="永久删除 销售报表.xlsx",
        file_id=record.file_id,
        engine=None,
        operation=PURGE_FILE_OPERATION,
        payload={"library_root": str(root)},
    )
    final_states = {TaskState.SUCCEEDED, TaskState.FAILED}
    events: list[TaskEvent] = []
    try:
        queue.submit(request)
        for _ in range(200):
            events.extend(queue.poll_events())
            terminal = [event for event in events if event.task_id == request.task_id]
            if terminal and terminal[-1].state in final_states:
                break
            time.sleep(0.01)
    finally:
        queue.shutdown()

    final = [event for event in events if event.task_id == request.task_id][-1]
    assert final.state is TaskState.SUCCEEDED
    assert not (root / "files/file-1").exists()
