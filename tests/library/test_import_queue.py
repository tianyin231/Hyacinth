import time
from pathlib import Path

from openpyxl import Workbook

from hyacinth.library.import_task import (
    IMPORT_WORKBOOK_OPERATION,
    ImportedWorkbook,
    import_task_handlers,
    import_workbook_task,
)
from hyacinth.tasks import TaskEvent, TaskQueue, TaskRequest, TaskState


def test_import_handler_is_registered() -> None:
    assert import_task_handlers() == {IMPORT_WORKBOOK_OPERATION: import_workbook_task}


def test_task_queue_runs_xlsx_import(tmp_path: Path) -> None:
    source = tmp_path / "销售报表.xlsx"
    workbook = Workbook()
    workbook.save(source)
    workbook.close()
    library_root = tmp_path / "library"
    queue = TaskQueue(import_task_handlers())
    try:
        queue.submit(
            TaskRequest(
                task_id="queued-import",
                name="导入工作簿",
                file_id="file-queued",
                engine=None,
                operation=IMPORT_WORKBOOK_OPERATION,
                payload={
                    "source_path": str(source),
                    "library_root": str(library_root),
                },
            )
        )
        events: list[TaskEvent] = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            events.extend(queue.poll_events())
            if any(event.state in {TaskState.SUCCEEDED, TaskState.FAILED} for event in events):
                break
            time.sleep(0.01)

        succeeded = [event for event in events if event.state is TaskState.SUCCEEDED]
        terminal_evidence = [
            (event.state, event.message)
            for event in events
            if event.state in {TaskState.SUCCEEDED, TaskState.FAILED}
        ]
        assert len(succeeded) == 1, terminal_evidence
        assert isinstance(succeeded[0].result, ImportedWorkbook)
        assert succeeded[0].result.working_path.exists()
    finally:
        assert queue.shutdown(timeout=5.0) is True
