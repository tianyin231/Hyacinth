from collections.abc import Iterable

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hyacinth.ui.function_panel import highlight_match
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
        self._search_open = False
        self._query = ""

        header = QFrame(self)
        header.setObjectName("panel-header")
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(11, 0, 9, 0)
        header_layout.setSpacing(4)
        self._title = QLabel("已上传文件", self)
        self._title.setProperty("class", "panel-title")
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._search_toggle = QPushButton(self)
        self._search_toggle.setObjectName("library-search-toggle")
        self._search_toggle.setFixedSize(26, 24)
        self._search_toggle.setText("🔍")
        self._search_toggle.setToolTip("搜索文件 (Ctrl+F)")
        self._search_toggle.setAccessibleName("搜索文件")
        self._search_toggle.clicked.connect(self._toggle_search)
        # 搜索态：标题原位切换为输入框 + 关闭按钮（需求第 27 节）。
        self._search_input = QLineEdit(self)
        self._search_input.setObjectName("library-search-input")
        self._search_input.setPlaceholderText("搜索文件…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setVisible(False)
        self._search_close = QPushButton("✕", self)
        self._search_close.setObjectName("library-search-close")
        self._search_close.setFixedSize(26, 24)
        self._search_close.setToolTip("关闭搜索 (Esc)")
        self._search_close.setVisible(False)
        self._search_close.clicked.connect(self.close_search)
        # 约 150ms 延迟实时过滤；Esc 关闭搜索（需求第 27 节）。
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(150)
        self._search_debounce.timeout.connect(self._apply_filter)
        self._search_input.textChanged.connect(lambda _text: self._search_debounce.start())
        header_layout.addWidget(self._title)
        header_layout.addWidget(self._search_input, 1)
        header_layout.addWidget(self._search_close)
        header_layout.addWidget(self._search_toggle)

        self._empty_label = QLabel("暂无文件\n从上方“导入文件”开始\n支持 XLSX 和 XLS", self)
        self._empty_label.setObjectName("library-empty-state")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._no_match_label = QLabel("没有匹配的文件", self)
        self._no_match_label.setObjectName("library-empty-state")
        self._no_match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_match_label.setVisible(False)

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
        layout.addWidget(self._no_match_label)
        layout.addWidget(self._file_list, 1)

        for record in reversed(tuple(records)):
            self.add_workbook(record)

    # ── 文件搜索（需求第 27 节）──────────────────────────────────────

    def open_search(self) -> None:
        if not self._search_open:
            self._search_open = True
            self._title.setVisible(False)
            self._search_input.setVisible(True)
            self._search_close.setVisible(True)
        self._search_input.setFocus()

    def close_search(self) -> None:
        """关闭搜索：清空关键词、恢复标题与完整列表（需求第 27 节）。"""
        self._search_open = False
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._search_input.setVisible(False)
        self._search_close.setVisible(False)
        self._title.setVisible(True)
        self._apply_filter()

    def _toggle_search(self) -> None:
        if self._search_open:
            self.close_search()
        else:
            self.open_search()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Esc 在文件列表区域任意位置都能退出搜索（需求第 27 节）。
        if self._search_open and event.key() == Qt.Key.Key_Escape:
            self.close_search()
            event.accept()
            return
        super().keyPressEvent(event)

    def _apply_filter(self) -> None:
        self._query = self._search_input.text().strip()
        visible = 0
        for row in range(self._file_list.count()):
            item = self._file_list.item(row)
            record = self._record_of(item)
            matched = self._query == "" or self._record_matches(record)
            self._file_list.setRowHidden(row, not matched)
            if matched:
                visible += 1
            self._update_item_widget(item, record, matched)
        has_files = self._file_list.count() > 0
        self._no_match_label.setVisible(has_files and visible == 0)
        self._empty_label.setVisible(not has_files)

    def _record_matches(self, record: ImportedWorkbook | None) -> bool:
        if record is None:
            return False
        query = self._query.lower()
        fields = [record.display_name, record.original_path.suffix.lstrip(".")]
        if record.imported_at is not None:
            fields.append(record.imported_at.astimezone().strftime("%Y-%m-%d %H:%M"))
        head = record.head_version
        if head is not None and head.note:
            fields.append(head.note)
        return any(query in field.lower() for field in fields)

    def _update_item_widget(
        self,
        item: QListWidgetItem | None,
        record: ImportedWorkbook | None,
        matched: bool,
    ) -> None:
        if item is None:
            return
        self._file_list.removeItemWidget(item)
        if self._query and matched and record is not None:
            label = QLabel(self._file_list)
            label.setProperty("class", "library-file-entry")
            # 显式富文本：高亮匹配文字（需求第 27 节）。
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setText(highlight_match(record.display_name, self._query))
            self._file_list.setItemWidget(item, label)

    def _record_of(self, item: QListWidgetItem | None) -> ImportedWorkbook | None:
        if item is None:
            return None
        record = item.data(int(Qt.ItemDataRole.UserRole) + 1)
        return record if isinstance(record, ImportedWorkbook) else None

    def add_workbook(self, record: ImportedWorkbook) -> None:
        item = QListWidgetItem(record.display_name)
        item.setData(Qt.ItemDataRole.UserRole, record.file_id)
        item.setData(int(Qt.ItemDataRole.UserRole) + 1, record)
        item.setToolTip(record.display_name)
        item.setSizeHint(QSize(0, 40))
        self._file_list.insertItem(0, item)
        self._file_list.setCurrentItem(item)
        self._empty_label.setVisible(False)
        self._apply_filter()
        if self._search_open:
            self._search_input.setFocus()

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
            self._apply_filter()
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
        self._apply_filter()

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
        self._apply_filter()

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
