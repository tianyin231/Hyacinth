from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QListWidget
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
