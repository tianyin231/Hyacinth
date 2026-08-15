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
