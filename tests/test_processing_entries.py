"""表格入口（右键菜单）触发新处理功能的端到端测试。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from PySide6.QtWidgets import QComboBox, QLabel, QListWidget
from pytestqt.qtbot import QtBot

from hyacinth.app import HyacinthMainWindow
from hyacinth.excel.contracts import EngineName
from hyacinth.library import ImportedWorkbook
from hyacinth.preview import BUILD_PREVIEW_INDEX_OPERATION, run_preview_index_task
from hyacinth.processing import (
    APPLY_FIND_REPLACE_PREVIEW_OPERATION,
    APPLY_TRIM_PREVIEW_OPERATION,
    FIND_REPLACE_PREVIEW_OPERATION,
    TRIM_PREVIEW_OPERATION,
    run_apply_find_replace_preview_task,
    run_apply_trim_preview_task,
    run_find_replace_preview_task,
    run_trim_preview_task,
)
from hyacinth.tasks import TaskEvent, TaskRequest, TaskState
from hyacinth.ui import FunctionPanel
from hyacinth.versioning import MetadataStore, VersionRecord


class FakeApplicationTaskQueue:
    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.submitted: list[TaskRequest] = []

    def submit(self, request: TaskRequest) -> None:
        self.submitted.append(request)

    def push_event(self, event: Any) -> None:
        self._events.append(event)

    def poll_events(self) -> tuple[Any, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def cancel(self, task_id: str) -> bool:
        return True

    def shutdown(self, timeout: float = 1.0) -> bool:
        return True


class PreviewTaskContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def set_engine(self, engine: EngineName) -> None:
        return

    def commit(self) -> None:
        return

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


def _child(parent: object, child_type: type, name: str) -> Any:
    from PySide6.QtCore import QObject

    child = QObject.findChild(parent, child_type, name)  # type: ignore[arg-type]
    assert child is not None
    return child


def _preview_request_of(queue: FakeApplicationTaskQueue) -> TaskRequest:
    return next(
        request for request in queue.submitted if request.operation == BUILD_PREVIEW_INDEX_OPERATION
    )


def _seed_file(library_root: Path, rows: list[list[object]]) -> None:
    directory = library_root / "files/file-1"
    original = directory / "original/数据.xlsx"
    working = directory / "working/current.xlsx"
    snapshot = directory / "versions/version-1/snapshot.xlsx"
    for path in (original, working, snapshot):
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "数据"
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        workbook.close()
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
        "数据.xlsx",
        original,
        working,
        version,
        datetime(2026, 8, 16, 8, 0, tzinfo=UTC),
    )
    MetadataStore(library_root).record_import(record)


def _ready_window(
    qtbot: QtBot, tmp_path: Path, rows: list[list[object]]
) -> tuple[Path, FakeApplicationTaskQueue, HyacinthMainWindow, FunctionPanel]:
    from hyacinth.app import create_main_window

    library_root = tmp_path / "library"
    _seed_file(library_root, rows)
    task_queue = FakeApplicationTaskQueue([])
    window = create_main_window(task_queue=task_queue, library_root=library_root)
    qtbot.addWidget(window)
    window.show()
    preview_request = _preview_request_of(task_queue)
    preview = run_preview_index_task(preview_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            preview_request.task_id,
            TaskState.SUCCEEDED,
            preview_request.name,
            preview_request.file_id,
            None,
            result=preview,
        )
    )
    qtbot.waitUntil(
        lambda: _child(window, QListWidget, "trim-key-columns").count() > 0, timeout=2000
    )
    function_panel = window.findChild(FunctionPanel, "function-panel")
    assert function_panel is not None
    return library_root, task_queue, window, function_panel


def test_trim_from_table_context_menu_creates_version(qtbot: QtBot, tmp_path: Path) -> None:
    library_root, task_queue, window, function_panel = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["  苹果  ", 3], [" 香蕉 ", 2]],
    )

    window._open_processing_entry("trim", [0])

    operation = _child(window, QComboBox, "processing-operation")
    assert operation.currentData() == "trim"
    trim_columns = _child(window, QListWidget, "trim-key-columns")
    assert trim_columns.selectedItems()

    function_panel.trim_preview_requested.emit(
        "数据", {"key_columns": [0], "collapse_spaces": False}
    )

    trim_request = task_queue.submitted[-1]
    assert trim_request.operation == TRIM_PREVIEW_OPERATION
    result = run_trim_preview_task(trim_request, PreviewTaskContext())
    assert len(result.trimmed_cells) == 2
    task_queue.push_event(
        TaskEvent(
            trim_request.task_id,
            TaskState.SUCCEEDED,
            trim_request.name,
            trim_request.file_id,
            None,
            result=result,
        )
    )
    qtbot.waitUntil(
        lambda: (
            len([r for r in task_queue.submitted if r.operation == BUILD_PREVIEW_INDEX_OPERATION])
            >= 2
        ),
        timeout=2000,
    )
    temporary_request = [
        r for r in task_queue.submitted if r.operation == BUILD_PREVIEW_INDEX_OPERATION
    ][-1]
    temporary_preview = run_preview_index_task(temporary_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            temporary_request.task_id,
            TaskState.SUCCEEDED,
            temporary_request.name,
            temporary_request.file_id,
            None,
            result=temporary_preview,
        )
    )
    qtbot.waitUntil(
        lambda: "将清理 2 个单元格" in _child(window, QLabel, "sort-state").text(),
        timeout=2000,
    )

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    qtbot.mouseClick(
        _child(window, QPushButton, "function-apply-button"), Qt.MouseButton.LeftButton
    )  # type: ignore[no-untyped-call]
    apply_request = next(
        request
        for request in task_queue.submitted
        if request.operation == APPLY_TRIM_PREVIEW_OPERATION
    )
    task_queue.push_event(
        TaskEvent(
            apply_request.task_id,
            TaskState.SUCCEEDED,
            apply_request.name,
            apply_request.file_id,
            EngineName.PYTHON,
            result=run_apply_trim_preview_task(apply_request, PreviewTaskContext()),
        )
    )

    def _head_id() -> str:
        head = MetadataStore(library_root).get_workbook("file-1").head_version
        return head.version_id if head is not None else ""

    qtbot.waitUntil(lambda: _head_id() != "version-1", timeout=2000)
    head = MetadataStore(library_root).get_workbook("file-1").head_version
    assert head is not None and head.operation == "trim-whitespace"


def test_find_replace_only_and_apply_flow(qtbot: QtBot, tmp_path: Path) -> None:
    library_root, task_queue, window, function_panel = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["Apple 销售", 3], ["apple pie", 5]],
    )

    function_panel.find_replace_requested.emit(
        "数据",
        {
            "all_sheets": False,
            "mode": "values",
            "find_text": "apple",
            "replace_text": "橙子",
            "match_case": False,
            "whole_cell": False,
            "trim_whitespace": False,
            "replace_all": False,
        },
    )
    find_request = task_queue.submitted[-1]
    assert find_request.operation == FIND_REPLACE_PREVIEW_OPERATION
    find_result = run_find_replace_preview_task(find_request, PreviewTaskContext())
    assert find_result.preview_path is None
    task_queue.push_event(
        TaskEvent(
            find_request.task_id,
            TaskState.SUCCEEDED,
            find_request.name,
            find_request.file_id,
            None,
            result=find_result,
        )
    )
    qtbot.waitUntil(
        lambda: "找到 2 处匹配" in _child(window, QLabel, "find-result").text(),
        timeout=2000,
    )

    function_panel.find_replace_requested.emit(
        "数据",
        {
            "all_sheets": False,
            "mode": "values",
            "find_text": "apple",
            "replace_text": "橙子",
            "match_case": False,
            "whole_cell": False,
            "trim_whitespace": False,
            "replace_all": True,
        },
    )
    qtbot.waitUntil(
        lambda: any(
            r.operation == FIND_REPLACE_PREVIEW_OPERATION and r.payload.get("replace_all")
            for r in task_queue.submitted
        ),
        timeout=2000,
    )
    replace_request = next(
        r
        for r in task_queue.submitted
        if r.operation == FIND_REPLACE_PREVIEW_OPERATION and r.payload.get("replace_all")
    )
    replace_result = run_find_replace_preview_task(replace_request, PreviewTaskContext())
    assert replace_result.preview_path is not None
    task_queue.push_event(
        TaskEvent(
            replace_request.task_id,
            TaskState.SUCCEEDED,
            replace_request.name,
            replace_request.file_id,
            None,
            result=replace_result,
        )
    )
    replace_request = next(
        r
        for r in task_queue.submitted
        if r.operation == FIND_REPLACE_PREVIEW_OPERATION and r.payload.get("replace_all")
    )
    replace_result = run_find_replace_preview_task(replace_request, PreviewTaskContext())
    assert replace_result.preview_path is not None
    task_queue.push_event(
        TaskEvent(
            replace_request.task_id,
            TaskState.SUCCEEDED,
            replace_request.name,
            replace_request.file_id,
            None,
            result=replace_result,
        )
    )
    qtbot.waitUntil(
        lambda: (
            len([r for r in task_queue.submitted if r.operation == BUILD_PREVIEW_INDEX_OPERATION])
            >= 2
        ),
        timeout=2000,
    )
    temporary_request = [
        r for r in task_queue.submitted if r.operation == BUILD_PREVIEW_INDEX_OPERATION
    ][-1]
    temporary_preview = run_preview_index_task(temporary_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            temporary_request.task_id,
            TaskState.SUCCEEDED,
            temporary_request.name,
            temporary_request.file_id,
            None,
            result=temporary_preview,
        )
    )
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    apply_button = _child(window, QPushButton, "function-apply-button")
    qtbot.waitUntil(apply_button.isEnabled, timeout=2000)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    apply_request = next(
        request
        for request in task_queue.submitted
        if request.operation == APPLY_FIND_REPLACE_PREVIEW_OPERATION
    )
    task_queue.push_event(
        TaskEvent(
            apply_request.task_id,
            TaskState.SUCCEEDED,
            apply_request.name,
            apply_request.file_id,
            EngineName.PYTHON,
            result=run_apply_find_replace_preview_task(apply_request, PreviewTaskContext()),
        )
    )

    def _head_operation() -> str:
        head = MetadataStore(library_root).get_workbook("file-1").head_version
        return head.operation if head is not None else ""

    qtbot.waitUntil(
        lambda: _head_operation() == "find-replace",
        timeout=2000,
    )
