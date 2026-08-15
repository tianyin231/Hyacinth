from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QPushButton
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


def test_file_library_widget_requests_import_and_selects_newest_file(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    widget = FileLibraryWidget()
    qtbot.addWidget(widget)
    button = widget.findChild(QPushButton, "library-import-button")
    file_list = widget.findChild(QListWidget, "library-file-list")
    assert button is not None
    assert file_list is not None
    assert button.minimumHeight() >= 44

    with qtbot.waitSignal(widget.import_requested, timeout=500):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    widget.add_workbook(_record("file-1", "库存.xlsx", tmp_path))
    widget.add_workbook(_record("file-2", "销售.xls", tmp_path))

    assert file_list.count() == 2
    assert file_list.item(0).text() == "销售.xls"
    assert file_list.item(0).data(Qt.ItemDataRole.UserRole) == "file-2"
    assert file_list.currentRow() == 0
