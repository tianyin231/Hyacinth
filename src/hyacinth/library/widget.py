from collections.abc import Iterable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hyacinth.library.import_task import ImportedWorkbook


class FileLibraryWidget(QFrame):
    import_requested = Signal()
    workbook_selected = Signal(object)

    def __init__(
        self,
        records: Iterable[ImportedWorkbook] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("file-library")
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)

        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 6)
        title = QLabel("已上传文件", self)
        title.setObjectName("library-title")
        header.addWidget(title)
        header.addStretch()

        import_button = QPushButton("导入文件", self)
        import_button.setObjectName("library-import-button")
        import_button.setAccessibleName("导入 Excel 文件")
        import_button.setMinimumHeight(44)
        import_button.clicked.connect(self.import_requested)
        header.addWidget(import_button)

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
        layout.addLayout(header)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._file_list, 1)

        self.setStyleSheet(
            """
            QFrame#file-library {
                background: #f7f8fa;
                border-right: 1px solid #dfe3e8;
            }
            QLabel#library-title {
                color: #343a45;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#library-empty-state {
                color: #68717e;
                padding: 28px 12px;
            }
            QPushButton#library-import-button {
                color: white;
                background: #0f6cbd;
                border: 1px solid #0f6cbd;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 600;
            }
            QPushButton#library-import-button:hover { background: #115ea3; }
            QPushButton#library-import-button:pressed { background: #0c3b5e; }
            QPushButton#library-import-button:focus {
                border: 2px solid #063b66;
            }
            QListWidget#library-file-list {
                color: #343a45;
                background: transparent;
                border: 0;
                padding: 6px;
                outline: 0;
            }
            QListWidget#library-file-list::item {
                border-radius: 5px;
                padding: 0 9px;
            }
            QListWidget#library-file-list::item:selected {
                color: #20242b;
                background: #e5f2fb;
                border-left: 2px solid #0f6cbd;
            }
            QListWidget#library-file-list:focus {
                border: 2px solid #0f6cbd;
            }
            """
        )

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
