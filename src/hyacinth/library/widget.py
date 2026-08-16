from collections.abc import Iterable

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from hyacinth.versioning import ImportedWorkbook


class _FileList(QListWidget):
    delete_key_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self.delete_key_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class FileLibraryWidget(QFrame):
    workbook_selected = Signal(object)
    workbook_delete_requested = Signal(object)

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

        self._empty_label = QLabel("暂无文件\n从上方“导入文件”开始\n支持 XLSX 和 XLS", self)
        self._empty_label.setObjectName("library-empty-state")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)

        self._file_list = _FileList(self)
        self._file_list.setObjectName("library-file-list")
        self._file_list.setAccessibleName("已上传文件列表")
        self._file_list.setAlternatingRowColors(False)
        self._file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_list.customContextMenuRequested.connect(self._show_context_menu)
        self._file_list.delete_key_requested.connect(self._request_delete_current)
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

    def restore_workbook(self, record: ImportedWorkbook) -> None:
        imported_at = record.imported_at
        if imported_at is None:
            self._insert_restored_item(record, self._file_list.count())
            return
        row = 0
        while row < self._file_list.count():
            item = self._file_list.item(row)
            existing = item.data(int(Qt.ItemDataRole.UserRole) + 1) if item is not None else None
            if (
                isinstance(existing, ImportedWorkbook)
                and existing.imported_at is not None
                and existing.imported_at < imported_at
            ):
                break
            row += 1
        self._insert_restored_item(record, row)

    def current_workbook(self) -> ImportedWorkbook | None:
        item = self._file_list.currentItem()
        if item is None:
            return None
        record = item.data(int(Qt.ItemDataRole.UserRole) + 1)
        return record if isinstance(record, ImportedWorkbook) else None

    def replace_workbook(self, record: ImportedWorkbook) -> None:
        for row in range(self._file_list.count()):
            item = self._file_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) != record.file_id:
                continue
            item.setText(record.display_name)
            item.setData(int(Qt.ItemDataRole.UserRole) + 1, record)
            item.setToolTip(record.display_name)
            return
        self.add_workbook(record)

    def remove_workbook(self, file_id: str) -> None:
        for row in range(self._file_list.count()):
            item = self._file_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) != file_id:
                continue
            self._file_list.takeItem(row)
            break
        if self._file_list.count() == 0:
            self._empty_label.setVisible(True)

    def select_workbook(self, file_id: str) -> None:
        self._file_list.blockSignals(True)
        try:
            for row in range(self._file_list.count()):
                item = self._file_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == file_id:
                    self._file_list.setCurrentItem(item)
                    return
        finally:
            self._file_list.blockSignals(False)

    def _insert_restored_item(self, record: ImportedWorkbook, row: int) -> None:
        item = QListWidgetItem(record.display_name)
        item.setData(Qt.ItemDataRole.UserRole, record.file_id)
        item.setData(int(Qt.ItemDataRole.UserRole) + 1, record)
        item.setToolTip(record.display_name)
        item.setSizeHint(QSize(0, 40))
        self._file_list.insertItem(row, item)
        self._empty_label.setVisible(False)

    def _show_context_menu(self, position: QPoint) -> None:
        item = self._file_list.itemAt(position)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("删除文件")
        delete_action.triggered.connect(lambda: self._request_delete_current())
        menu.exec(self._file_list.mapToGlobal(position))

    def _request_delete_current(self) -> None:
        record = self.current_workbook()
        if record is not None:
            self.workbook_delete_requested.emit(record)

    def _emit_selected_workbook(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            return
        record = current.data(int(Qt.ItemDataRole.UserRole) + 1)
        if isinstance(record, ImportedWorkbook):
            self.workbook_selected.emit(record)
