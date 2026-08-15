import time
from pathlib import Path

from openpyxl import Workbook

from hyacinth.preview import (
    BUILD_PREVIEW_INDEX_OPERATION,
    WorkbookPreview,
    preview_task_handlers,
)
from hyacinth.tasks import TaskEvent, TaskQueue, TaskRequest, TaskState


def test_preview_index_runs_in_persistent_worker(tmp_path: Path) -> None:
    working = tmp_path / "current.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = "后台读取"
    workbook.save(working)
    workbook.close()
    index_path = tmp_path / "preview.sqlite"
    task_queue = TaskQueue(preview_task_handlers())
    request = TaskRequest(
        task_id="preview-worker",
        name="加载工作簿预览",
        file_id="file-1",
        engine=None,
        operation=BUILD_PREVIEW_INDEX_OPERATION,
        payload={"working_path": str(working), "index_path": str(index_path)},
    )
    try:
        task_queue.submit(request)
        events = _collect_until_succeeded(task_queue)
    finally:
        assert task_queue.shutdown(timeout=1.0) is True

    succeeded = next(event for event in events if event.state is TaskState.SUCCEEDED)
    assert isinstance(succeeded.result, WorkbookPreview)
    assert succeeded.result.index_path == index_path
    assert index_path.is_file()


def _collect_until_succeeded(task_queue: TaskQueue) -> list[TaskEvent]:
    events: list[TaskEvent] = []
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        events.extend(task_queue.poll_events())
        if any(event.state is TaskState.SUCCEEDED for event in events):
            return events
        time.sleep(0.01)
    raise AssertionError(f"等待预览任务超时：{events!r}")
