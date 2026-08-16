"""表格入口（右键菜单/功能区条）触发处理功能的端到端测试。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTableView
from pytestqt.qtbot import QtBot

from hyacinth.app import HyacinthMainWindow
from hyacinth.excel.contracts import EngineName
from hyacinth.library import ImportedWorkbook
from hyacinth.preview import BUILD_PREVIEW_INDEX_OPERATION, run_preview_index_task
from hyacinth.processing import (
    APPLY_FIND_REPLACE_PREVIEW_OPERATION,
    APPLY_TRIM_PREVIEW_OPERATION,
    FIND_REPLACE_PREVIEW_OPERATION,
    SORT_PREVIEW_OPERATION,
    TRIM_PREVIEW_OPERATION,
    run_apply_find_replace_preview_task,
    run_apply_trim_preview_task,
    run_find_replace_preview_task,
    run_trim_preview_task,
)
from hyacinth.tasks import TaskEvent, TaskRequest, TaskState
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


def _last_request(queue: FakeApplicationTaskQueue, operation: str) -> TaskRequest:
    return [request for request in queue.submitted if request.operation == operation][-1]


def _push_success(
    queue: FakeApplicationTaskQueue,
    request: TaskRequest,
    result: object,
    engine: EngineName | None = None,
) -> None:
    queue.push_event(
        TaskEvent(
            request.task_id,
            TaskState.SUCCEEDED,
            request.name,
            request.file_id,
            engine,
            result=result,
        )
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
) -> tuple[Path, FakeApplicationTaskQueue, HyacinthMainWindow]:
    from hyacinth.app import create_main_window

    library_root = tmp_path / "library"
    _seed_file(library_root, rows)
    task_queue = FakeApplicationTaskQueue([])
    window = create_main_window(task_queue=task_queue, library_root=library_root)
    qtbot.addWidget(window)
    window.show()
    preview_request = _preview_request_of(task_queue)
    preview = run_preview_index_task(preview_request, PreviewTaskContext())
    _push_success(task_queue, preview_request, preview)
    table = _child(window, QTableView, "preview-table")
    qtbot.waitUntil(lambda: table.model() is not None, timeout=2000)
    return library_root, task_queue, window


def _head_record(library_root: Path) -> VersionRecord | None:
    return MetadataStore(library_root).get_workbook("file-1").head_version


def _wait_second_preview_request(qtbot: QtBot, queue: FakeApplicationTaskQueue) -> None:
    qtbot.waitUntil(
        lambda: (
            len(
                [
                    request
                    for request in queue.submitted
                    if request.operation == BUILD_PREVIEW_INDEX_OPERATION
                ]
            )
            >= 2
        ),
        timeout=2000,
    )


def test_trim_from_table_context_menu_creates_version(qtbot: QtBot, tmp_path: Path) -> None:
    library_root, task_queue, window = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["  苹果  ", 3], [" 香蕉 ", 2]],
    )

    # 表格右键菜单“清除首尾空格…”最终以选中列触发一步处理
    window._one_step_processing("trim", [0])

    trim_request = _last_request(task_queue, TRIM_PREVIEW_OPERATION)
    assert trim_request.payload["key_columns"] == [0]
    result = run_trim_preview_task(trim_request, PreviewTaskContext())
    assert len(result.trimmed_cells) == 2
    _push_success(task_queue, trim_request, result)
    _wait_second_preview_request(qtbot, task_queue)

    temporary_request = _last_request(task_queue, BUILD_PREVIEW_INDEX_OPERATION)
    temporary_preview = run_preview_index_task(temporary_request, PreviewTaskContext())
    _push_success(task_queue, temporary_request, temporary_preview)
    qtbot.waitUntil(
        lambda: "将清理 2 个单元格" in _child(window, QLabel, "banner-message").text(),
        timeout=2000,
    )

    # 预览就绪后“查看明细”可用，并展示修改前后内容
    details_button = _child(window, QPushButton, "banner-details-button")
    assert details_button.isEnabled()
    qtbot.mouseClick(details_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    from PySide6.QtWidgets import QTableView as DetailsTable

    details_table = _child(window, DetailsTable, "processing-details-table")
    assert details_table.model() is not None
    assert details_table.model().rowCount() == 2
    assert "苹果" in str(details_table.model().data(details_table.model().index(0, 2)))

    qtbot.mouseClick(_child(window, QPushButton, "banner-apply-button"), Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    apply_request = _last_request(task_queue, APPLY_TRIM_PREVIEW_OPERATION)
    _push_success(
        task_queue,
        apply_request,
        run_apply_trim_preview_task(apply_request, PreviewTaskContext()),
        EngineName.PYTHON,
    )

    qtbot.waitUntil(lambda: _head_record(library_root) is not None, timeout=2000)
    head = _head_record(library_root)
    assert head is not None
    assert head.version_id != "version-1"
    assert head.operation == "trim-whitespace"


def test_temporary_preview_supports_manual_edits_on_apply(qtbot: QtBot, tmp_path: Path) -> None:
    """需求第 17 节：临时结果上可继续单元格编辑，统一随应用生成版本。"""
    from openpyxl import load_workbook
    from PySide6.QtCore import Qt

    library_root, task_queue, window = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["  苹果  ", 3], [" 香蕉 ", 2]],
    )
    window._one_step_processing("trim", [0])
    trim_request = _last_request(task_queue, TRIM_PREVIEW_OPERATION)
    _push_success(
        task_queue, trim_request, run_trim_preview_task(trim_request, PreviewTaskContext())
    )
    _wait_second_preview_request(qtbot, task_queue)
    temporary_request = _last_request(task_queue, BUILD_PREVIEW_INDEX_OPERATION)
    temporary_preview = run_preview_index_task(temporary_request, PreviewTaskContext())
    _push_success(task_queue, temporary_request, temporary_preview)

    table = _child(window, QTableView, "preview-table")
    qtbot.waitUntil(lambda: table.model() is not None, timeout=2000)
    # 临时结果进入可编辑状态，编辑值先落在编辑会话中
    model = table.model()
    assert model is not None
    assert model.flags(model.index(1, 0)) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(model.index(1, 0), "苹果·已编辑", Qt.ItemDataRole.EditRole)
    edits = window._workbook_preview.pending_edits()
    assert len(edits) == 1
    assert (edits[0].sheet_name, edits[0].row, edits[0].column) == ("数据", 1, 0)

    qtbot.mouseClick(_child(window, QPushButton, "banner-apply-button"), Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    apply_request = _last_request(task_queue, APPLY_TRIM_PREVIEW_OPERATION)
    assert apply_request.payload["edits"] == [
        {"sheet_name": "数据", "row": 1, "column": 0, "value": "苹果·已编辑"}
    ]
    applied = run_apply_trim_preview_task(apply_request, PreviewTaskContext())
    _push_success(task_queue, apply_request, applied, EngineName.PYTHON)

    qtbot.waitUntil(lambda: _head_record(library_root) is not None, timeout=2000)
    head = _head_record(library_root)
    assert head is not None and head.version_id != "version-1"
    # 等应用成功事件处理完毕（丢弃临时结果并清空编辑会话）后再检查状态
    qtbot.waitUntil(lambda: window._processing_result is None, timeout=2000)
    workbook = load_workbook(head.snapshot_path)
    try:
        assert workbook["数据"]["A2"].value == "苹果·已编辑"
    finally:
        workbook.close()
    # 应用成功后编辑会话清空，不再污染后续预览
    assert window._workbook_preview.pending_edits() == ()


def test_find_replace_only_and_apply_flow(qtbot: QtBot, tmp_path: Path) -> None:
    library_root, task_queue, window = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["Apple 销售", 3], ["apple pie", 5]],
    )
    window._open_find_replace_dialog()
    parameters: dict[str, object] = {
        "all_sheets": False,
        "mode": "values",
        "find_text": "apple",
        "replace_text": "橙子",
        "match_case": False,
        "whole_cell": False,
        "trim_whitespace": False,
    }

    window._submit_find_replace_preview("数据", {**parameters, "replace_all": False})
    find_request = _last_request(task_queue, FIND_REPLACE_PREVIEW_OPERATION)
    find_result = run_find_replace_preview_task(find_request, PreviewTaskContext())
    assert find_result.preview_path is None
    _push_success(task_queue, find_request, find_result)
    qtbot.waitUntil(
        lambda: "找到 2 处匹配" in _child(window, QLabel, "find-dialog-status").text(),
        timeout=2000,
    )

    window._submit_find_replace_preview("数据", {**parameters, "replace_all": True})
    replace_request = next(
        request
        for request in task_queue.submitted
        if request.operation == FIND_REPLACE_PREVIEW_OPERATION
        and request.payload.get("replace_all")
    )
    replace_result = run_find_replace_preview_task(replace_request, PreviewTaskContext())
    assert replace_result.preview_path is not None
    _push_success(task_queue, replace_request, replace_result)
    _wait_second_preview_request(qtbot, task_queue)

    temporary_request = _last_request(task_queue, BUILD_PREVIEW_INDEX_OPERATION)
    temporary_preview = run_preview_index_task(temporary_request, PreviewTaskContext())
    _push_success(task_queue, temporary_request, temporary_preview)

    apply_button = _child(window, QPushButton, "banner-apply-button")
    qtbot.waitUntil(apply_button.isEnabled, timeout=2000)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    apply_request = _last_request(task_queue, APPLY_FIND_REPLACE_PREVIEW_OPERATION)
    _push_success(
        task_queue,
        apply_request,
        run_apply_find_replace_preview_task(apply_request, PreviewTaskContext()),
        EngineName.PYTHON,
    )

    def _head_operation() -> str:
        head = _head_record(library_root)
        return head.operation if head is not None else ""

    qtbot.waitUntil(
        lambda: _head_operation() == "find-replace",
        timeout=2000,
    )


def test_editor_bar_sort_and_entry(qtbot: QtBot, tmp_path: Path) -> None:
    _library_root, task_queue, window = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["b", 2], ["a", 1]],
    )

    # 无进行中任务时功能区条入口可用
    qtbot.mouseClick(
        _child(window, QPushButton, "bar-find-replace-button"), Qt.MouseButton.LeftButton
    )  # type: ignore[no-untyped-call]
    dialog = window._find_dialog
    assert dialog is not None
    assert dialog.isVisible()
    dialog.close()

    table = _child(window, QTableView, "preview-table")
    table.selectColumn(0)

    qtbot.mouseClick(_child(window, QPushButton, "bar-sort-asc-button"), Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    sort_request = task_queue.submitted[-1]
    assert sort_request.operation == SORT_PREVIEW_OPERATION
    sort_keys = sort_request.payload["sort_keys"]
    assert isinstance(sort_keys, list) and isinstance(sort_keys[0], dict)
    assert sort_keys[0]["column_index"] == 0
    assert sort_keys[0]["direction"] == "asc"
    # 处理预览进行中当前预览被清空，功能区条入口应禁用，避免误触发错误提示
    assert not _child(window, QPushButton, "bar-find-replace-button").isEnabled()


def test_grid_shows_data_margin_and_select_all_is_safe(qtbot: QtBot, tmp_path: Path) -> None:
    _library_root, _task_queue, window = _ready_window(
        qtbot,
        tmp_path,
        [["名称", "数量"], ["苹果", 3], ["香蕉", 2]],
    )
    table = _child(window, QTableView, "preview-table")
    model = table.model()
    assert model is not None
    # 数据 3 行 2 列 + 编辑余量 32 行 4 列，不再生成百万行逻辑网格
    assert model.rowCount() == 3 + 32
    assert model.columnCount() == 2 + 4

    table.selectAll()
    selected = table.selectionModel().selectedIndexes()
    # 全选只选数据区域，不会选中余量，更不会触碰百万行
    assert len(selected) == 3 * 2
