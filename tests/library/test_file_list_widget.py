from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QLabel, QListWidget
from pytestqt.qtbot import QtBot

from hyacinth.library import ImportedWorkbook
from hyacinth.library.widget import FileLibraryWidget


def _record(file_id: str, name: str, root: Path) -> ImportedWorkbook:
    return ImportedWorkbook(
        file_id=file_id,
        display_name=name,
        original_path=root / file_id / "original" / name,
        working_path=root / file_id / "working" / "current.xlsx",
    )


def test_file_library_widget_selects_newest_file(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    widget = FileLibraryWidget()
    qtbot.addWidget(widget)
    file_list = widget.findChild(QListWidget, "library-file-list")
    assert file_list is not None

    widget.add_workbook(_record("file-1", "库存.xlsx", tmp_path))
    selected = QSignalSpy(widget.workbook_selected)
    widget.add_workbook(_record("file-2", "销售.xls", tmp_path))

    assert file_list.count() == 2
    assert file_list.item(0).text() == "销售.xls"
    assert file_list.item(0).data(Qt.ItemDataRole.UserRole) == "file-2"
    assert file_list.currentRow() == 0
    assert widget.current_workbook() == _record("file-2", "销售.xls", tmp_path)
    assert selected.count() == 1
    assert selected.at(0)[0] == widget.current_workbook()


def test_file_search_filters_highlights_and_restores(qtbot: QtBot, tmp_path: Path) -> None:
    widget = FileLibraryWidget()
    qtbot.addWidget(widget)
    widget.add_workbook(_record("file-1", "库存.xlsx", tmp_path))
    widget.add_workbook(_record("file-2", "销售.xls", tmp_path))
    file_list = widget.findChild(QListWidget, "library-file-list")
    assert file_list is not None

    # 打开搜索：标题原位切换为输入框（需求第 27 节）
    widget.open_search()
    assert not widget._title.isVisibleTo(widget)
    assert widget._search_input.isVisibleTo(widget)

    widget._search_input.setText("销售")
    widget._apply_filter()
    assert not file_list.isRowHidden(0)
    assert file_list.isRowHidden(1)
    item = file_list.item(0)
    assert item is not None
    entry = file_list.itemWidget(item)
    assert isinstance(entry, QLabel)
    assert "<span" in entry.text()  # 高亮匹配文字
    assert not widget._no_match_label.isVisibleTo(widget)

    widget._search_input.setText("xlsx")
    widget._apply_filter()
    assert file_list.isRowHidden(0)  # 销售.xls 后缀不匹配
    assert not file_list.isRowHidden(1)
    assert not widget._no_match_label.isVisibleTo(widget)

    widget._search_input.setText("zzz")
    widget._apply_filter()
    assert widget._no_match_label.isVisibleTo(widget)

    # Esc 关闭：清空关键词并恢复完整列表（真实按键路径）
    QTest.keyClick(widget._search_input, Qt.Key.Key_Escape)
    assert not file_list.isRowHidden(0)
    assert not file_list.isRowHidden(1)
    assert widget._title.isVisibleTo(widget)
    assert not widget._search_input.isVisibleTo(widget)
