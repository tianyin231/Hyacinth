from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTabBar, QTableView
from pytestqt.qtbot import QtBot

from hyacinth.tasks import TaskRequest


class PreviewTaskContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def commit(self) -> None:
        return

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


class CountingGridSource:
    row_count = 1_048_576
    column_count = 256

    def __init__(self) -> None:
        self.read_count = 0

    def value_at(self, row: int, column: int) -> object:
        self.read_count += 1
        return ""

    def set_value(self, row: int, column: int, value: object) -> None:
        raise AssertionError("只读表格不应写入数据源")


def _preview(tmp_path: Path):  # type: ignore[no-untyped-def]
    from hyacinth.preview import run_preview_index_task

    working = tmp_path / "current.xlsx"
    workbook = Workbook()
    sales = workbook.active
    assert sales is not None
    sales.title = "销售"
    sales["A1"] = "一月"
    inventory = workbook.create_sheet("库存")
    inventory["B2"] = 42
    workbook.save(working)
    workbook.close()
    index_path = tmp_path / "preview.sqlite"
    request = TaskRequest(
        task_id="preview-1",
        name="加载预览",
        file_id="file-1",
        engine=None,
        operation="build-preview-index",
        payload={"working_path": str(working), "index_path": str(index_path)},
    )
    return run_preview_index_task(request, PreviewTaskContext())


def test_preview_widget_shows_sheet_tabs_and_switches_grid(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.preview import WorkbookPreviewWidget

    preview = _preview(tmp_path)
    widget = WorkbookPreviewWidget()
    qtbot.addWidget(widget)
    widget.show_preview(preview)
    widget.show()
    tabs = widget.findChild(QTabBar, "preview-sheet-tabs")
    table = widget.findChild(QTableView, "preview-table")
    assert tabs is not None
    assert table is not None

    assert [tabs.tabText(index) for index in range(tabs.count())] == ["销售", "库存"]
    assert table.model().data(table.model().index(0, 0)) == "一月"
    assert table.editTriggers() == QTableView.EditTrigger.NoEditTriggers
    assert tabs.minimumHeight() >= 34

    tabs.setCurrentIndex(1)

    assert table.model().data(table.model().index(1, 1)) == "42"
    assert tabs.focusPolicy() is Qt.FocusPolicy.StrongFocus

    widget.set_loading("另一份.xlsx")

    assert table.model() is None


def test_preview_widget_has_stable_loading_and_error_states(qtbot: QtBot) -> None:
    from hyacinth.preview import WorkbookPreviewWidget

    widget = WorkbookPreviewWidget()
    qtbot.addWidget(widget)
    state = widget.findChild(QLabel, "preview-state")
    import_button = widget.findChild(QPushButton, "preview-import-button")
    assert state is not None
    assert import_button is not None

    with qtbot.waitSignal(widget.import_requested):
        qtbot.mouseClick(import_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    widget.set_loading("销售.xlsx")
    assert state.text() == "正在加载 销售.xlsx…"
    assert import_button.isHidden()

    widget.set_error("工作簿损坏")
    assert state.text() == "无法加载预览\n工作簿损坏"
    assert not import_button.isHidden()


def test_read_only_table_does_not_scan_million_rows_for_typed_text(qtbot: QtBot) -> None:
    from hyacinth.grid.model import WorkbookTableModel
    from hyacinth.preview.widget import ReadOnlyWorkbookTableView

    source = CountingGridSource()
    table = ReadOnlyWorkbookTableView()
    qtbot.addWidget(table)
    model = WorkbookTableModel(source, table, editable=False)
    table.setModel(model)
    table.setCurrentIndex(model.index(0, 0))

    table.keyboardSearch("不存在的内容")

    assert source.read_count == 0


def test_preview_widget_edits_head_cells_and_supports_undo_redo(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.preview import WorkbookPreviewWidget

    preview = _preview(tmp_path)
    widget = WorkbookPreviewWidget()
    qtbot.addWidget(widget)
    widget.show_preview(preview, editable=True)
    table = widget.findChild(QTableView, "preview-table")
    assert table is not None
    model = table.model()
    assert model is not None
    cell = model.index(0, 0)

    assert model.setData(cell, "二月", Qt.ItemDataRole.EditRole)
    assert model.data(cell) == "二月"
    assert widget.pending_edits()[0].sheet_name == "销售"
    assert widget.pending_edits()[0].value == "二月"
    assert table.editTriggers() != QTableView.EditTrigger.NoEditTriggers

    widget.undo()
    assert model.data(cell) == "一月"
    assert widget.pending_edits() == ()
    widget.redo()
    assert model.data(cell) == "二月"


def test_formula_bar_tracks_current_cell_and_submits_text(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.preview import WorkbookPreviewWidget

    preview = _preview(tmp_path)
    widget = WorkbookPreviewWidget()
    qtbot.addWidget(widget)
    events: list[tuple[str, str]] = []
    widget.current_cell_changed.connect(lambda name, content: events.append((name, content)))
    editable_modes: list[bool] = []
    widget.edit_mode_changed.connect(editable_modes.append)

    widget.show_preview(preview, editable=True)

    # 模型上屏即报告首个单元格；内容为原始值（公式优先）
    assert events[-1] == ("A1", "一月")
    assert editable_modes[-1] is True
    table = widget.findChild(QTableView, "preview-table")
    assert table is not None
    model = table.model()
    assert model is not None
    table.setCurrentIndex(model.index(1, 1))

    assert events[-1] == ("B2", "")
    table.setCurrentIndex(model.index(0, 0))

    # 公式栏提交走与表格编辑相同的链路：编辑会话 + 撤销 + 脏计数
    widget.submit_cell_text("二月")
    assert model.data(model.index(0, 0)) == "二月"
    assert widget.pending_edits()[0].value == "二月"
    # 当前单元格内容变化后公式栏同步刷新
    assert events[-1] == ("A1", "二月")
    widget.undo()
    assert events[-1] == ("A1", "一月")

    # 只读模式：模式信号翻转，提交不产生编辑
    widget.show_preview(preview, editable=False)
    assert editable_modes[-1] is False
    readonly_model = table.model()
    assert readonly_model is not None and readonly_model is not model
    table.setCurrentIndex(readonly_model.index(0, 0))
    widget.submit_cell_text("不应写入")
    assert widget.pending_edits() == ()

    widget.clear_preview()
    assert events[-1] == ("", "")
