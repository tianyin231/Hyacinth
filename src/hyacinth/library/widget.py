from collections.abc import Iterable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hyacinth.versioning import ImportedWorkbook


class FileLibraryWidget(QFrame):
    workbook_selected = Signal(object)

    def __init__(
        self,
        records: Iterable[ImportedWorkbook] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("file-library")
        self.setMinimumSize(230, 150)

        header = QFrame(self)
        header.setObjectName("panel-header")
        header.setFixedHeight(38)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(11, 0, 9, 0)
        title = QLabel("已上传文件", self)
        title.setProperty("class", "panel-title")
        header_layout.addWidget(title)

        self._empty_label = QLabel("还没有导入文件", self)
        self._empty_label.setObjectName("library-empty-state")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._file_list = QListWidget(self)
        self._file_list.setObjectName("library-file-list")
        self._file_list.setAccessibleName("已上传文件列表")
        self._file_list.setAlternatingRowColors(False)
        self._file_list.currentItemChanged.connect(self._emit_selected_workbook)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._file_list, 1)

        for record in reversed(tuple(records)):
            self.add_workbook(record)

    def add_workbook(self, record: ImportedWorkbook) -> None:
        item = QListWidgetItem(record.display_name)
        item.setData(Qt.ItemDataRole.UserRole, record.file_id)
        item.setData(int(Qt.ItemDataRole.UserRole) + 1, record)
        item.setToolTip(record.display_name)
        item.setSizeHint(QSize(0, 40))
        self._file_list.insertItem(0, item)
        self._file_list.setCurrentItem(item)
        self._empty_label.setVisible(False)

    def current_workbook(self) -> ImportedWorkbook | None:
        item = self._file_list.currentItem()
        if item is None:
            return None
        record = item.data(int(Qt.ItemDataRole.UserRole) + 1)
        return record if isinstance(record, ImportedWorkbook) else None

    def _emit_selected_workbook(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        record = current.data(int(Qt.ItemDataRole.UserRole) + 1)
        if isinstance(record, ImportedWorkbook):
            self.workbook_selected.emit(record)
