from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hyacinth.ui.icons import fluent_icon
from hyacinth.versioning import VersionRecord

APP_STYLESHEET = """
QMainWindow#main-window, QWidget#workspace-root {
    background: #edf1f6;
    color: #20242b;
    font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
}
QFrame#application-header {
    background: #f5f8fb;
    border-bottom: 1px solid #d5dbe4;
}
QLabel#app-brand { color: #20242b; font-size: 14px; font-weight: 700; }
QLabel#document-title { color: #4f5967; font-size: 12px; }
QLabel#document-state { color: #5f6977; font-size: 12px; }
QFrame#top-toolbar {
    background: #f9fbfd;
    border-bottom: 1px solid #d5dbe4;
}
QPushButton[class="tool-button"] {
    min-height: 32px;
    padding: 0 11px;
    color: #343a45;
    background: #fbfcfe;
    border: 1px solid #c6ced9;
    border-radius: 6px;
}
QPushButton[class="tool-button"]:hover { background: #f5f8fb; border-color: #aeb7c4; }
QPushButton[class="tool-button"]:pressed { background: #e8edf3; }
QPushButton[class="tool-button"]:focus { border: 2px solid #0f6cbd; }
QPushButton[class="tool-button"]:disabled { color: #9aa2ad; background: #f5f6f8; }
QPushButton#toolbar-import-button {
    color: #ffffff;
    background: #0f6cbd;
    border-color: #0f6cbd;
    font-weight: 600;
}
QPushButton#toolbar-import-button:hover { background: #115ea3; }
QPushButton#toolbar-import-button:pressed { background: #0c3b5e; }
QFrame#toolbar-divider { background: #dfe3e8; }
QLabel#engine-mode-pill {
    color: #25695c;
    background: #eff9f6;
    border: 1px solid #bcd9d2;
    border-radius: 13px;
    padding: 5px 10px;
}
QSplitter#main-workspace-splitter, QSplitter#left-workspace-splitter {
    background: #eef1f5;
}
QSplitter::handle { background: #d8dde5; }
QSplitter::handle:hover { background: #0f6cbd; }
QSplitter#main-workspace-splitter::handle { width: 1px; }
QSplitter#left-workspace-splitter::handle { height: 1px; }
QFrame#function-panel, QFrame#file-library, QFrame#version-tree-panel {
    background: #f7f9fc;
}
QFrame#panel-header {
    background: #fbfcfe;
    border-bottom: 1px solid #d9dfe7;
}
QLabel[class="panel-title"] { color: #343a45; font-weight: 650; }
QLabel#development-badge {
    color: #68717e;
    background: #eef1f4;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
}
QLabel#sort-state { color: #566170; padding: 5px 0; }
QLabel#sort-state[error="true"] { color: #a4262c; }
QLabel[class="form-label"] { color: #5e6876; font-size: 12px; }
QComboBox[class="field-control"], QLineEdit[class="field-control"] {
    min-height: 31px;
    color: #343a45;
    background: #ffffff;
    border: 1px solid #bdc6d2;
    border-radius: 6px;
    padding: 0 8px;
}
QComboBox[class="field-control"]:disabled, QLineEdit[class="field-control"]:disabled {
    color: #9099a5;
    background: #f2f4f7;
    border-color: #d8dde5;
}
QComboBox[class="field-control"]:focus, QLineEdit[class="field-control"]:focus {
    border: 2px solid #0f6cbd;
}
QListWidget#deduplicate-key-columns, QListWidget#blank-rows-key-columns {
    color: #343a45;
    background: #ffffff;
    border: 1px solid #bdc6d2;
    border-radius: 6px;
    outline: none;
}
QListWidget#deduplicate-key-columns::item, QListWidget#blank-rows-key-columns::item {
    min-height: 25px;
    padding: 0 6px;
}
QListWidget#deduplicate-key-columns::item:selected,
QListWidget#blank-rows-key-columns::item:selected {
    color: #0b5a9d;
    background: #e5f2fb;
}
QCheckBox { color: #46515f; spacing: 7px; }
QCheckBox:disabled { color: #9099a5; }
QFrame#function-footer { background: #fafbfc; border-top: 1px solid #dfe3e8; }
QLabel#function-empty-title, QLabel#tree-empty-title {
    color: #303844;
    font-size: 14px;
    font-weight: 600;
}
QLabel#function-empty-detail, QLabel#tree-empty-detail {
    color: #647080;
    font-size: 12px;
}
QLabel#function-empty-icon, QLabel#tree-empty-icon { background: #eaf3fb; border-radius: 22px; }
QFrame#root-version-card {
    background: #ffffff;
    border: 1px solid #cfd5de;
    border-left: 3px solid #0f6cbd;
    border-radius: 7px;
}
QFrame#child-version-card {
    background: #ffffff;
    border: 1px solid #cfd5de;
    border-left: 3px solid #25695c;
    border-radius: 7px;
}
QLabel#root-version-name { color: #343a45; font-weight: 600; }
QLabel#root-version-file { color: #343a45; font-size: 11px; }
QLabel#root-version-meta { color: #68717e; font-size: 10px; }
QLabel#root-version-head {
    color: #0b5a9d;
    background: #e5f2fb;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
}
QLabel#temporary-result-banner {
    color: #7a4d00;
    background: #fff4ce;
    border-bottom: 1px solid #e5c365;
    padding: 5px 10px;
}
QPushButton#function-apply-button {
    color: #ffffff;
    background: #0f6cbd;
    border-color: #0f6cbd;
    font-weight: 600;
}
QPushButton#function-apply-button:disabled {
    color: #9aa2ad;
    background: #f5f6f8;
    border-color: #cfd5de;
}
QGraphicsView#version-tree-view { background: #fbfcfe; border: 0; }
QFrame#editor-frame { background: #ffffff; }
QFrame#formula-bar, QFrame#format-bar {
    background: #fafbfc;
    border-bottom: 1px solid #dfe3e8;
}
QLabel#formula-name, QLabel#formula-value, QLabel#font-family-control {
    color: #4d5663;
    background: #ffffff;
    border: 1px solid #cfd5de;
    border-radius: 4px;
    padding: 4px 8px;
}
QLabel#formula-fx { color: #0f6cbd; font-family: Georgia; font-style: italic; }
QLabel[class="format-control"] { color: #4d5663; padding: 4px 7px; }
QFrame#workbook-preview { background: #ffffff; }
QFrame#preview-empty-card {
    min-width: 330px;
    max-width: 430px;
    background: rgba(255, 255, 255, 238);
    border: 1px solid #cfd7e2;
    border-radius: 10px;
}
QLabel#preview-empty-icon { background: #e6f2fb; border-radius: 27px; }
QLabel#preview-state {
    color: #27313d;
    background: transparent;
    font-size: 18px;
    font-weight: 650;
}
QLabel#preview-state-detail { color: #5e6978; background: transparent; font-size: 12px; }
QPushButton#preview-import-button {
    min-height: 34px;
    padding: 0 16px;
    color: #ffffff;
    background: #0f6cbd;
    border: 1px solid #0f6cbd;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton#preview-import-button:hover { background: #115ea3; }
QPushButton#preview-import-button:pressed { background: #0c3b5e; }
QPushButton#preview-import-button:focus { border: 2px solid #ffffff; }
QTableView#preview-table {
    color: #20242b;
    background: #ffffff;
    gridline-color: #e3e7ec;
    border: 0;
    selection-background-color: #dceefb;
    selection-color: #20242b;
}
QTableView#preview-table:focus { border: 2px solid #0f6cbd; }
QHeaderView::section {
    color: #4d5663;
    background: #f4f6f8;
    border: 0;
    border-right: 1px solid #dfe3e8;
    border-bottom: 1px solid #dfe3e8;
    padding: 4px 6px;
}
QTabBar#preview-sheet-tabs { background: #f4f6f8; border-top: 1px solid #dfe3e8; }
QTabBar#preview-sheet-tabs::tab {
    color: #46505d;
    background: transparent;
    min-width: 76px;
    min-height: 30px;
    padding: 0 12px;
    border-right: 1px solid #dfe3e8;
}
QTabBar#preview-sheet-tabs::tab:selected {
    color: #0f548c;
    background: #ffffff;
    border-top: 2px solid #0f6cbd;
}
QTabBar#preview-sheet-tabs:focus { border: 2px solid #0f6cbd; }
QLabel#library-empty-state {
    color: #647080;
    background: #f7f9fc;
    padding: 24px 12px;
    line-height: 1.5;
}
QListWidget#library-file-list {
    color: #343a45;
    background: transparent;
    border: 0;
    padding: 5px 6px;
    outline: 0;
}
QListWidget#library-file-list::item { border-radius: 5px; padding: 0 9px; }
QListWidget#library-file-list::item:selected {
    color: #20242b;
    background: #e5f2fb;
    border-left: 2px solid #0f6cbd;
}
QListWidget#library-file-list:focus { border: 2px solid #0f6cbd; }
QStatusBar#main-status-bar { background: #f0f2f5; border-top: 1px solid #d8dde5; }
"""


def _panel_header(title: str, *, badge: str | None = None) -> QFrame:
    header = QFrame()
    header.setObjectName("panel-header")
    header.setFixedHeight(38)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(11, 0, 9, 0)
    title_label = QLabel(title, header)
    title_label.setProperty("class", "panel-title")
    layout.addWidget(title_label)
    layout.addStretch()
    if badge is not None:
        badge_label = QLabel(badge, header)
        badge_label.setObjectName("development-badge")
        layout.addWidget(badge_label)
    return header


def _tool_button(
    text: str,
    name: str,
    parent: QWidget,
    *,
    enabled: bool = True,
    icon: str | None = None,
) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName(name)
    button.setProperty("class", "tool-button")
    button.setMinimumHeight(32)
    if icon is not None:
        button.setIcon(
            fluent_icon(icon, color="#ffffff" if name == "toolbar-import-button" else "#4d5663")
        )
        button.setIconSize(QSize(17, 17))
    button.setEnabled(enabled)
    return button


class ApplicationHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("application-header")
        self.setFixedHeight(42)

        mark = QLabel(self)
        mark.setObjectName("brand-mark")
        mark.setPixmap(fluent_icon("brand", color="#0f6cbd", size=20).pixmap(20, 20))
        mark.setFixedSize(20, 20)
        brand = QLabel("风信子", self)
        brand.setObjectName("app-brand")
        self._document = QLabel("未选择文件", self)
        self._document.setObjectName("document-title")
        self._document.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._document.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        state = QLabel("本地工作台", self)
        state.setObjectName("document-state")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(7)
        layout.addWidget(mark)
        layout.addWidget(brand)
        layout.addWidget(self._document, 1)
        layout.addWidget(state)

    def set_document_name(self, display_name: str | None) -> None:
        self._document.setText(display_name or "未选择文件")


class CommandBar(QFrame):
    import_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("top-toolbar")
        self.setFixedHeight(44)

        import_button = _tool_button("导入文件", "toolbar-import-button", self, icon="plus")
        import_button.setAccessibleName("导入 Excel 文件")
        import_button.clicked.connect(self.import_requested)
        save_button = _tool_button(
            "保存为新版本", "toolbar-save-version-button", self, enabled=False, icon="save"
        )
        undo_button = _tool_button("撤销", "toolbar-undo-button", self, enabled=False, icon="undo")
        redo_button = _tool_button("重做", "toolbar-redo-button", self, enabled=False, icon="redo")
        compare_button = _tool_button(
            "对比版本", "toolbar-compare-button", self, enabled=False, icon="compare"
        )
        recycle_button = _tool_button(
            "回收站", "toolbar-recycle-button", self, enabled=False, icon="trash"
        )
        settings_button = _tool_button(
            "设置", "toolbar-settings-button", self, enabled=False, icon="settings"
        )

        divider = QFrame(self)
        divider.setObjectName("toolbar-divider")
        divider.setFixedSize(1, 20)
        mode = QLabel("●  引擎自动选择", self)
        mode.setObjectName("engine-mode-pill")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(7)
        layout.addWidget(import_button)
        layout.addWidget(save_button)
        layout.addWidget(divider)
        layout.addWidget(undo_button)
        layout.addWidget(redo_button)
        layout.addWidget(compare_button)
        layout.addWidget(recycle_button)
        layout.addStretch()
        layout.addWidget(mode)
        layout.addWidget(settings_button)


class FunctionPanel(QFrame):
    preview_requested = Signal(str, object)
    deduplicate_preview_requested = Signal(str, object)
    delete_blank_rows_preview_requested = Signal(str, object)
    cancel_requested = Signal()
    apply_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("function-panel")
        self.setMinimumSize(230, 240)

        empty_body = QWidget(self)
        empty_layout = QVBoxLayout(empty_body)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.setSpacing(8)
        empty_layout.addStretch()
        empty_icon = QLabel(empty_body)
        empty_icon.setObjectName("function-empty-icon")
        empty_icon.setPixmap(fluent_icon("sort", color="#0f6cbd", size=22).pixmap(22, 22))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setFixedSize(44, 44)
        empty_title = QLabel("先导入一个 Excel 文件", empty_body)
        empty_title.setObjectName("function-empty-title")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_detail = QLabel("导入后即可配置排序或去重\n并在应用前预览完整结果", empty_body)
        empty_detail.setObjectName("function-empty-detail")
        empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_detail.setWordWrap(True)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_detail)
        empty_layout.addStretch()

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(11, 10, 11, 10)
        body_layout.setSpacing(5)
        self._headers_by_sheet: dict[str, tuple[str, ...]] = {}
        self._operation = self._field(body_layout, "处理功能", "processing-operation")
        self._operation.addItem("多列排序", "sort")
        self._operation.addItem("删除重复行", "deduplicate")
        self._operation.addItem("删除空白行", "delete_blank_rows")
        self._operation.currentIndexChanged.connect(self._switch_operation)
        self._sheet = self._field(body_layout, "处理工作表", "sort-sheet")
        self._sheet.currentTextChanged.connect(self._refresh_columns)

        sort_page = QWidget(body)
        sort_layout = QVBoxLayout(sort_page)
        sort_layout.setContentsMargins(0, 0, 0, 0)
        sort_layout.setSpacing(5)
        self._primary = self._field(sort_layout, "第一优先级", "sort-primary-column")
        self._primary_direction = self._direction_field(
            sort_layout, "第一排序方向", "sort-primary-direction"
        )
        self._secondary = self._field(sort_layout, "第二优先级", "sort-secondary-column")
        self._secondary_direction = self._direction_field(
            sort_layout, "第二排序方向", "sort-secondary-direction"
        )
        self._range = QLabel("当前 used range · 首行作为表头", sort_page)
        self._range.setObjectName("sort-range-note")
        self._empty = QLabel("空值始终排在末尾", sort_page)
        self._empty.setObjectName("sort-empty-note")
        sort_layout.addWidget(self._range)
        sort_layout.addWidget(self._empty)
        sort_layout.addStretch()

        deduplicate_page = QWidget(body)
        deduplicate_layout = QVBoxLayout(deduplicate_page)
        deduplicate_layout.setContentsMargins(0, 0, 0, 0)
        deduplicate_layout.setSpacing(5)
        key_label = QLabel("判断重复的关键列", deduplicate_page)
        key_label.setProperty("class", "form-label")
        self._deduplicate_columns = QListWidget(deduplicate_page)
        self._deduplicate_columns.setObjectName("deduplicate-key-columns")
        self._deduplicate_columns.setAccessibleName("判断重复的关键列")
        self._deduplicate_columns.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._deduplicate_columns.setMaximumHeight(92)
        self._deduplicate_keep = self._field(
            deduplicate_layout,
            "重复时保留",
            "deduplicate-keep",
        )
        self._deduplicate_keep.addItem("第一次出现", "first")
        self._deduplicate_keep.addItem("最后一次出现", "last")
        self._deduplicate_ignore_case = QCheckBox("忽略英文字母大小写", deduplicate_page)
        self._deduplicate_ignore_case.setObjectName("deduplicate-ignore-case")
        self._deduplicate_trim = QCheckBox("忽略文本首尾空格", deduplicate_page)
        self._deduplicate_trim.setObjectName("deduplicate-trim-whitespace")
        deduplicate_note = QLabel("未选择关键列时按整行判断 · 空值参与比较", deduplicate_page)
        deduplicate_note.setObjectName("deduplicate-note")
        deduplicate_note.setWordWrap(True)
        self._deduplicate_details = QPushButton("查看保留 / 删除对应关系", deduplicate_page)
        self._deduplicate_details.setObjectName("deduplicate-details-button")
        self._deduplicate_details.setProperty("class", "tool-button")
        self._deduplicate_details.setEnabled(False)
        self._deduplicate_details.clicked.connect(self._show_duplicate_details)
        deduplicate_layout.insertWidget(0, key_label)
        deduplicate_layout.insertWidget(1, self._deduplicate_columns)
        deduplicate_layout.addWidget(self._deduplicate_ignore_case)
        deduplicate_layout.addWidget(self._deduplicate_trim)
        deduplicate_layout.addWidget(deduplicate_note)
        deduplicate_layout.addWidget(self._deduplicate_details)
        deduplicate_layout.addStretch()

        blank_rows_page = QWidget(body)
        blank_rows_layout = QVBoxLayout(blank_rows_page)
        blank_rows_layout.setContentsMargins(0, 0, 0, 0)
        blank_rows_layout.setSpacing(5)
        blank_rows_label = QLabel("判断空白的关键列", blank_rows_page)
        blank_rows_label.setProperty("class", "form-label")
        self._blank_rows_columns = QListWidget(blank_rows_page)
        self._blank_rows_columns.setObjectName("blank-rows-key-columns")
        self._blank_rows_columns.setAccessibleName("判断空白的关键列")
        self._blank_rows_columns.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._blank_rows_columns.setMaximumHeight(92)
        self._blank_rows_allow_unsafe = QCheckBox(
            "发现公式等结构时生成兼容预览",
            blank_rows_page,
        )
        self._blank_rows_allow_unsafe.setObjectName("blank-rows-allow-unsafe")
        blank_rows_note = QLabel(
            "未选择关键列时按整行判断 · 空白文本视为空 · 首行表头不会删除",
            blank_rows_page,
        )
        blank_rows_note.setObjectName("blank-rows-note")
        blank_rows_note.setWordWrap(True)
        self._blank_rows_details = QPushButton("查看将删除的原始行号", blank_rows_page)
        self._blank_rows_details.setObjectName("blank-rows-details-button")
        self._blank_rows_details.setProperty("class", "tool-button")
        self._blank_rows_details.setEnabled(False)
        self._blank_rows_details.clicked.connect(self._show_blank_rows_details)
        blank_rows_layout.addWidget(blank_rows_label)
        blank_rows_layout.addWidget(self._blank_rows_columns)
        blank_rows_layout.addWidget(self._blank_rows_allow_unsafe)
        blank_rows_layout.addWidget(blank_rows_note)
        blank_rows_layout.addWidget(self._blank_rows_details)
        blank_rows_layout.addStretch()

        self._parameter_stack = QStackedWidget(body)
        self._parameter_stack.setObjectName("processing-parameter-stack")
        self._parameter_stack.addWidget(sort_page)
        self._parameter_stack.addWidget(deduplicate_page)
        self._parameter_stack.addWidget(blank_rows_page)
        body_layout.addWidget(self._parameter_stack, 1)

        self._state = QLabel("选择文件后可配置处理功能", body)
        self._state.setObjectName("sort-state")
        self._state.setWordWrap(True)
        self._state.setAccessibleName("处理状态")
        body_layout.addWidget(self._state)
        self._duplicate_mapping: tuple[tuple[int, tuple[int, ...]], ...] = ()
        self._deleted_blank_row_numbers: tuple[int, ...] = ()

        self._footer = QFrame(self)
        self._footer.setObjectName("function-footer")
        self._footer.setFixedHeight(45)
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(10, 0, 10, 0)
        footer_layout.setSpacing(7)
        self._cancel = _tool_button("取消", "function-cancel-button", self._footer, enabled=False)
        self._cancel.setAccessibleName("取消临时预览")
        self._reset = _tool_button("重置", "function-reset-button", self._footer, enabled=False)
        self._cancel.clicked.connect(self.cancel_requested)
        self._reset.clicked.connect(self._reset_fields)
        footer_layout.addWidget(self._cancel)
        footer_layout.addWidget(self._reset)
        footer_layout.addStretch()
        self._preview = _tool_button("预览", "function-preview-button", self._footer, enabled=False)
        self._apply = _tool_button("应用", "function-apply-button", self._footer, enabled=False)
        self._preview.setAccessibleName("预览处理结果")
        self._apply.setAccessibleName("应用临时结果为新版本")
        self._preview.clicked.connect(self._emit_preview)
        self._apply.clicked.connect(self.apply_requested)
        footer_layout.addWidget(self._preview)
        footer_layout.addWidget(self._apply)

        self._body_stack = QStackedWidget(self)
        self._body_stack.setObjectName("function-body-stack")
        self._body_stack.addWidget(empty_body)
        self._body_stack.addWidget(body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_panel_header("数据处理", badge="Python 安全模式"))
        layout.addWidget(self._body_stack, 1)
        layout.addWidget(self._footer)

        self._controls = (
            self._operation,
            self._sheet,
            self._primary,
            self._primary_direction,
            self._secondary,
            self._secondary_direction,
            self._deduplicate_columns,
            self._deduplicate_keep,
            self._deduplicate_ignore_case,
            self._deduplicate_trim,
            self._blank_rows_columns,
            self._blank_rows_allow_unsafe,
        )
        self.clear_workbook()

    def set_workbook(self, headers_by_sheet: dict[str, tuple[str, ...]]) -> None:
        self._headers_by_sheet = headers_by_sheet
        self._sheet.blockSignals(True)
        self._sheet.clear()
        self._sheet.addItems(tuple(headers_by_sheet))
        self._sheet.blockSignals(False)
        self._refresh_columns(self._sheet.currentText())
        self._switch_operation()
        enabled = bool(headers_by_sheet)
        self._body_stack.setCurrentIndex(1 if enabled else 0)
        self._footer.setVisible(enabled)
        self._set_config_enabled(enabled)
        self._state.setText(self._ready_message())
        self._state.setProperty("error", False)
        self._state.style().unpolish(self._state)
        self._state.style().polish(self._state)

    def clear_workbook(self) -> None:
        self._headers_by_sheet.clear()
        self._sheet.clear()
        self._primary.clear()
        self._secondary.clear()
        self._deduplicate_columns.clear()
        self._blank_rows_columns.clear()
        self._duplicate_mapping = ()
        self._deleted_blank_row_numbers = ()
        self._deduplicate_details.setEnabled(False)
        self._blank_rows_details.setEnabled(False)
        self._set_config_enabled(False)
        self._body_stack.setCurrentIndex(0)
        self._footer.setVisible(False)
        self._state.setText("选择文件后可配置处理功能")

    def set_busy(self, message: str) -> None:
        self._set_config_enabled(False)
        self._preview.setEnabled(False)
        self._apply.setEnabled(False)
        self._cancel.setEnabled(True)
        self._state.setText(message)
        self._set_state_error(False)

    def set_preview_ready(self, message: str = "临时结果已就绪，尚未生成版本") -> None:
        self._set_config_enabled(False)
        self._preview.setEnabled(False)
        self._apply.setEnabled(True)
        self._cancel.setEnabled(True)
        self._state.setText(message)
        self._set_state_error(False)

    def set_deduplicate_preview_ready(
        self,
        duplicate_groups: int,
        deleted_rows: int,
        mapping: tuple[tuple[int, tuple[int, ...]], ...],
        message: str | None = None,
    ) -> None:
        self._duplicate_mapping = mapping
        summary = f"{duplicate_groups} 个重复组 · 将删除 {deleted_rows} 行"
        self.set_preview_ready(
            f"{message} · {summary}" if message else f"临时结果已就绪 · {summary}"
        )
        self._deduplicate_details.setEnabled(bool(mapping))

    def set_delete_blank_rows_preview_ready(
        self,
        deleted_row_numbers: tuple[int, ...],
        compatibility_warning: bool,
        message: str | None = None,
    ) -> None:
        self._deleted_blank_row_numbers = deleted_row_numbers
        summary = f"将删除 {len(deleted_row_numbers)} 行"
        if compatibility_warning:
            summary += " · 兼容预览可能影响公式等结构"
        self.set_preview_ready(
            f"{message} · {summary}" if message else f"临时结果已就绪 · {summary}"
        )
        self._blank_rows_details.setEnabled(bool(deleted_row_numbers))

    def set_error(self, message: str) -> None:
        self._set_config_enabled(bool(self._headers_by_sheet))
        self._cancel.setEnabled(False)
        self._apply.setEnabled(False)
        self._deduplicate_details.setEnabled(False)
        self._blank_rows_details.setEnabled(False)
        self._state.setText(message)
        self._set_state_error(True)

    def _set_state_error(self, error: bool) -> None:
        self._state.setProperty("error", error)
        self._state.style().unpolish(self._state)
        self._state.style().polish(self._state)

    def _field(self, layout: QVBoxLayout, label: str, name: str) -> QComboBox:
        label_widget = QLabel(label, self)
        label_widget.setProperty("class", "form-label")
        field = QComboBox(self)
        field.setObjectName(name)
        field.setProperty("class", "field-control")
        field.setAccessibleName(label)
        layout.addWidget(label_widget)
        layout.addWidget(field)
        return field

    def _direction_field(self, layout: QVBoxLayout, label: str, name: str) -> QComboBox:
        field = self._field(layout, label, name)
        field.addItem("升序", "asc")
        field.addItem("降序", "desc")
        return field

    def _refresh_columns(self, sheet_name: str) -> None:
        headers = self._headers_by_sheet.get(sheet_name, ())
        self._primary.clear()
        self._secondary.clear()
        self._secondary.addItem("不使用", None)
        self._deduplicate_columns.clear()
        self._blank_rows_columns.clear()
        for index, header in enumerate(headers):
            label = header or f"第 {index + 1} 列"
            self._primary.addItem(label, index)
            self._secondary.addItem(label, index)
            self._deduplicate_columns.addItem(label)
            self._deduplicate_columns.item(index).setData(Qt.ItemDataRole.UserRole, index)
            self._blank_rows_columns.addItem(label)
            self._blank_rows_columns.item(index).setData(Qt.ItemDataRole.UserRole, index)
        self._set_config_enabled(bool(self._headers_by_sheet))

    def _reset_fields(self) -> None:
        self._primary.setCurrentIndex(0)
        self._primary_direction.setCurrentIndex(0)
        self._secondary.setCurrentIndex(0)
        self._secondary_direction.setCurrentIndex(0)
        self._deduplicate_columns.clearSelection()
        self._deduplicate_keep.setCurrentIndex(0)
        self._deduplicate_ignore_case.setChecked(False)
        self._deduplicate_trim.setChecked(False)
        self._blank_rows_columns.clearSelection()
        self._blank_rows_allow_unsafe.setChecked(False)
        self._state.setText("已重置处理条件")

    def _set_config_enabled(self, enabled: bool) -> None:
        for control in getattr(self, "_controls", ()):
            control.setEnabled(enabled)
        self._reset.setEnabled(enabled)
        self._preview.setEnabled(enabled and self._primary.count() > 0)
        self._deduplicate_details.setEnabled(
            enabled and bool(self._duplicate_mapping) and self._apply.isEnabled()
        )
        self._blank_rows_details.setEnabled(
            enabled and bool(self._deleted_blank_row_numbers) and self._apply.isEnabled()
        )

    def _emit_preview(self) -> None:
        operation = self._operation.currentData()
        if operation == "deduplicate":
            self._emit_deduplicate_preview()
            return
        if operation == "delete_blank_rows":
            self._emit_delete_blank_rows_preview()
            return
        primary = self._primary.currentData()
        if not isinstance(primary, int):
            self.set_error("请选择第一排序列")
            return
        sort_keys: list[dict[str, object]] = [
            {"column_index": primary, "direction": self._primary_direction.currentData()}
        ]
        secondary = self._secondary.currentData()
        if isinstance(secondary, int):
            if secondary == primary:
                self.set_error("第二排序列不能与第一排序列相同")
                return
            sort_keys.append(
                {
                    "column_index": secondary,
                    "direction": self._secondary_direction.currentData(),
                }
            )
        self.preview_requested.emit(self._sheet.currentText(), sort_keys)

    def _emit_deduplicate_preview(self) -> None:
        key_columns = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._deduplicate_columns.selectedItems()
        ]
        self.deduplicate_preview_requested.emit(
            self._sheet.currentText(),
            {
                "key_columns": key_columns,
                "keep": self._deduplicate_keep.currentData(),
                "ignore_case": self._deduplicate_ignore_case.isChecked(),
                "trim_whitespace": self._deduplicate_trim.isChecked(),
            },
        )

    def _emit_delete_blank_rows_preview(self) -> None:
        key_columns = [
            item.data(Qt.ItemDataRole.UserRole) for item in self._blank_rows_columns.selectedItems()
        ]
        self.delete_blank_rows_preview_requested.emit(
            self._sheet.currentText(),
            {
                "key_columns": key_columns,
                "allow_unsafe": self._blank_rows_allow_unsafe.isChecked(),
            },
        )

    def _switch_operation(self, _index: int = -1) -> None:
        operation = self._operation.currentData()
        page_index = {"sort": 0, "deduplicate": 1, "delete_blank_rows": 2}.get(operation, 0)
        self._parameter_stack.setCurrentIndex(page_index)
        if self._headers_by_sheet:
            self._state.setText(self._ready_message())
        accessible_names = {
            "sort": "预览排序结果",
            "deduplicate": "预览删除重复行结果",
            "delete_blank_rows": "预览删除空白行结果",
        }
        self._preview.setAccessibleName(accessible_names.get(operation, "预览处理结果"))

    def _ready_message(self) -> str:
        if self._operation.currentData() == "deduplicate":
            return "选择关键列后预览；未选择时按整行判断"
        if self._operation.currentData() == "delete_blank_rows":
            return "选择关键列后预览；未选择时删除整行均为空的行"
        return "配置排序条件后预览完整数据行"

    def _show_duplicate_details(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("重复行对应关系")
        dialog.resize(560, 420)
        table = QTableView(dialog)
        table.setObjectName("deduplicate-mapping-table")
        table.setModel(DuplicateMappingModel(self._duplicate_mapping, table))
        table.horizontalHeader().setStretchLastSection(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout = QVBoxLayout(dialog)
        layout.addWidget(table)
        layout.addWidget(buttons)
        dialog.exec()

    def _show_blank_rows_details(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("将删除的空白行")
        dialog.resize(360, 420)
        table = QTableView(dialog)
        table.setObjectName("blank-rows-details-table")
        table.setModel(DeletedRowsModel(self._deleted_blank_row_numbers, table))
        table.horizontalHeader().setStretchLastSection(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout = QVBoxLayout(dialog)
        layout.addWidget(table)
        layout.addWidget(buttons)
        dialog.exec()


class DuplicateMappingModel(QAbstractTableModel):
    def __init__(
        self,
        mapping: tuple[tuple[int, tuple[int, ...]], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mapping = mapping

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else len(self._mapping)

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else 2

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        kept_row, deleted_rows = self._mapping[index.row()]
        if index.column() == 0:
            return f"第 {kept_row} 行"
        return "、".join(f"第 {row} 行" for row in deleted_rows)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return ("保留行", "删除行")[section]


class DeletedRowsModel(QAbstractTableModel):
    def __init__(self, row_numbers: tuple[int, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row_numbers = row_numbers

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else len(self._row_numbers)

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else 1

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return f"第 {self._row_numbers[index.row()]} 行"

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return "原始行号" if section == 0 else None


class VersionTreePanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("version-tree-panel")
        self.setMinimumWidth(280)

        search = QLineEdit(self)
        search.setObjectName("version-search")
        search.setProperty("class", "field-control")
        search.setPlaceholderText("搜索版本名称、功能或备注")
        search.setAccessibleName("搜索版本")
        search.setEnabled(False)

        search_row = QFrame(self)
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(9, 5, 9, 5)
        search_layout.addWidget(search)

        empty = QWidget(self)
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(22, 22, 22, 22)
        empty_layout.setSpacing(8)
        empty_layout.addStretch()
        empty_icon = QLabel(empty)
        empty_icon.setObjectName("tree-empty-icon")
        empty_icon.setPixmap(fluent_icon("tree", color="#0f6cbd", size=22).pixmap(22, 22))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setFixedSize(44, 44)
        self._empty_title = QLabel("选择文件查看版本演化树", empty)
        self._empty_title.setObjectName("tree-empty-title")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail = QLabel("导入后将从根版本开始记录每次处理", empty)
        self._empty_detail.setObjectName("tree-empty-detail")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail.setWordWrap(True)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_detail)
        empty_layout.addStretch()

        self._scene = QGraphicsScene(self)
        self._scene.setObjectName("version-tree-scene")
        self._scene.setSceneRect(0, 0, 320, 480)
        self._view = QGraphicsView(self._scene, self)
        self._view.setObjectName("version-tree-view")
        self._view.setAccessibleName("版本演化树")
        self._view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._content = QStackedWidget(self)
        self._content.addWidget(empty)
        self._content.addWidget(self._view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_panel_header("版本演化树"))
        layout.addWidget(search_row)
        layout.addWidget(self._content, 1)

    def set_workbook(
        self,
        display_name: str | None,
        versions: VersionRecord | tuple[VersionRecord, ...] | None = None,
        head_version_id: str | None = None,
    ) -> None:
        if display_name is None:
            self._empty_title.setText("选择文件查看版本演化树")
            self._empty_detail.setText("根版本会在文件导入完成后显示")
            self._content.setCurrentIndex(0)
            return
        if versions is None:
            self._empty_title.setText("旧记录尚未建立根版本")
            self._empty_detail.setText("文件仍可预览，后续可安全补建版本记录")
            self._content.setCurrentIndex(0)
            return

        records = (versions,) if isinstance(versions, VersionRecord) else versions
        head_id = head_version_id or records[-1].version_id
        self._render_versions(display_name, records, head_id)
        self._content.setCurrentIndex(1)

    def _render_versions(
        self,
        display_name: str,
        versions: tuple[VersionRecord, ...],
        head_version_id: str,
    ) -> None:
        previous_scene = self._scene
        scene = QGraphicsScene(self)
        scene.setObjectName("version-tree-scene")
        positions: dict[str, tuple[float, float]] = {}
        depths: dict[str, int] = {}
        proxies: dict[str, QGraphicsProxyWidget] = {}
        for index, version in enumerate(versions):
            depth = (
                0
                if version.parent_version_id is None
                else depths.get(version.parent_version_id, 0) + 1
            )
            depths[version.version_id] = depth
            position = (28.0 + depth * 260.0, 42.0 + index * 126.0)
            positions[version.version_id] = position
            card = self._version_card(
                display_name,
                version,
                is_head=version.version_id == head_version_id,
            )
            proxy = scene.addWidget(card)
            assert isinstance(proxy, QGraphicsProxyWidget)
            proxy.setPos(*position)
            proxies[version.version_id] = proxy
        pen = QPen(Qt.GlobalColor.gray, 1.5)
        for version in versions:
            parent_id = version.parent_version_id
            if parent_id is None or parent_id not in positions:
                continue
            parent_proxy = proxies[parent_id]
            child_proxy = proxies[version.version_id]
            parent_rect = parent_proxy.sceneBoundingRect()
            child_rect = child_proxy.sceneBoundingRect()
            line = scene.addLine(
                parent_rect.right(),
                parent_rect.center().y(),
                child_rect.left(),
                child_rect.center().y(),
                pen,
            )
            line.setZValue(-1)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-20, -20, 40, 40))
        self._view.setScene(scene)
        self._scene = scene
        if versions:
            self._view.centerOn(proxies[versions[0].version_id])
        previous_scene.deleteLater()

    def _version_card(
        self,
        display_name: str,
        version: VersionRecord,
        *,
        is_head: bool,
    ) -> QFrame:
        card = QFrame()
        is_root = version.parent_version_id is None
        card.setObjectName("root-version-card" if is_root else "child-version-card")
        card.setFixedSize(230, 108)
        card.setStyleSheet(
            """
            QFrame#root-version-card, QFrame#child-version-card {
                background: #ffffff;
                border: 1px solid #cfd5de;
                border-left: 3px solid #0f6cbd;
                border-radius: 7px;
            }
            QLabel { border: 0; background: transparent; }
            QLabel#root-version-name { color: #343a45; font-weight: 600; }
            QLabel#root-version-file { color: #343a45; font-size: 11px; }
            QLabel#root-version-meta { color: #68717e; font-size: 10px; }
            QLabel#root-version-head {
                color: #0b5a9d;
                background: #e5f2fb;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
            }
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        title = QLabel(version.name, card)
        title.setObjectName("root-version-name")
        file_name = QLabel(display_name, card)
        file_name.setObjectName("root-version-file")
        file_name.setToolTip(display_name)
        metadata = QLabel(
            f"{version.created_at.astimezone().strftime('%Y-%m-%d %H:%M')} · "
            f"{Path(display_name).suffix.removeprefix('.').upper()}",
            card,
        )
        metadata.setObjectName("root-version-meta")
        head = QLabel("HEAD · 根版本" if is_root else "HEAD", card)
        head.setObjectName("root-version-head")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setMaximumWidth(82)
        layout.addWidget(title)
        layout.addWidget(file_name)
        layout.addWidget(metadata)
        head.setVisible(is_head)
        layout.addWidget(head)
        return card


class WorkbookEditorFrame(QFrame):
    def __init__(self, preview: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-frame")
        self.setMinimumWidth(480)

        formula = QFrame(self)
        formula.setObjectName("formula-bar")
        formula.setFixedHeight(36)
        formula_layout = QHBoxLayout(formula)
        formula_layout.setContentsMargins(6, 4, 6, 4)
        formula_layout.setSpacing(6)
        name = QLabel("A1", formula)
        name.setObjectName("formula-name")
        name.setFixedWidth(70)
        fx = QLabel("fx", formula)
        fx.setObjectName("formula-fx")
        fx.setFixedWidth(24)
        fx.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value = QLabel("", formula)
        value.setObjectName("formula-value")
        value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        formula_layout.addWidget(name)
        formula_layout.addWidget(fx)
        formula_layout.addWidget(value, 1)

        format_bar = QFrame(self)
        format_bar.setObjectName("format-bar")
        format_bar.setFixedHeight(36)
        format_layout = QHBoxLayout(format_bar)
        format_layout.setContentsMargins(7, 4, 7, 4)
        format_layout.setSpacing(3)
        family = QLabel("Segoe UI", format_bar)
        family.setObjectName("font-family-control")
        family.setFixedWidth(82)
        format_layout.addWidget(family)
        for text in ("11", "B", "I", "≡", "$", "%", ".00"):
            control = QLabel(text, format_bar)
            control.setProperty("class", "format-control")
            control.setAlignment(Qt.AlignmentFlag.AlignCenter)
            format_layout.addWidget(control)
        format_layout.addStretch()

        self._temporary_banner = QLabel("临时结果 · 尚未生成版本", self)
        self._temporary_banner.setObjectName("temporary-result-banner")
        self._temporary_banner.setAccessibleName("临时结果状态")
        self._temporary_banner.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(formula)
        layout.addWidget(format_bar)
        layout.addWidget(self._temporary_banner)
        layout.addWidget(preview, 1)

    def set_temporary_result(self, visible: bool) -> None:
        self._temporary_banner.setVisible(visible)
