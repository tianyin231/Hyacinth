from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hyacinth.versioning import VersionRecord

APP_STYLESHEET = """
QMainWindow#main-window, QWidget#workspace-root {
    background: #eef1f5;
    color: #20242b;
    font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
}
QFrame#application-header {
    background: #f7f8fa;
    border-bottom: 1px solid #d8dde5;
}
QLabel#brand-mark { color: #0f6cbd; font-size: 17px; }
QLabel#app-brand { color: #20242b; font-size: 13px; font-weight: 700; }
QLabel#document-title { color: #596270; font-size: 12px; }
QLabel#document-state { color: #68717e; font-size: 11px; }
QFrame#top-toolbar {
    background: #fbfcfd;
    border-bottom: 1px solid #d8dde5;
}
QPushButton[class="tool-button"] {
    min-height: 30px;
    padding: 0 10px;
    color: #343a45;
    background: #ffffff;
    border: 1px solid #cfd5de;
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
    background: #f7f8fa;
}
QFrame#panel-header {
    background: #fafbfc;
    border-bottom: 1px solid #dfe3e8;
}
QLabel[class="panel-title"] { color: #343a45; font-weight: 650; }
QLabel#development-badge {
    color: #68717e;
    background: #eef1f4;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
}
QLabel[class="form-label"] { color: #68717e; font-size: 11px; }
QComboBox[class="field-control"], QLineEdit[class="field-control"] {
    min-height: 29px;
    color: #343a45;
    background: #ffffff;
    border: 1px solid #cfd5de;
    border-radius: 5px;
    padding: 0 8px;
}
QComboBox[class="field-control"]:focus, QLineEdit[class="field-control"]:focus {
    border: 2px solid #0f6cbd;
}
QFrame#function-footer { background: #fafbfc; border-top: 1px solid #dfe3e8; }
QLabel#tree-empty-title { color: #343a45; font-size: 13px; font-weight: 600; }
QLabel#tree-empty-detail { color: #68717e; font-size: 11px; }
QFrame#root-version-card {
    background: #ffffff;
    border: 1px solid #cfd5de;
    border-left: 3px solid #0f6cbd;
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
QGraphicsView#version-tree-view { background: #fbfcfd; border: 0; }
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
QLabel#preview-state { color: #5d6673; background: #ffffff; padding: 24px; }
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
QLabel#library-empty-state { color: #68717e; padding: 24px 12px; }
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


def _tool_button(text: str, name: str, parent: QWidget, *, enabled: bool = True) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName(name)
    button.setProperty("class", "tool-button")
    button.setMinimumHeight(30)
    button.setEnabled(enabled)
    return button


class ApplicationHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("application-header")
        self.setFixedHeight(42)

        mark = QLabel("◆", self)
        mark.setObjectName("brand-mark")
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

        import_button = _tool_button("＋  导入文件", "toolbar-import-button", self)
        import_button.setAccessibleName("导入 Excel 文件")
        import_button.clicked.connect(self.import_requested)
        save_button = _tool_button(
            "保存为新版本", "toolbar-save-version-button", self, enabled=False
        )
        undo_button = _tool_button("撤销", "toolbar-undo-button", self, enabled=False)
        redo_button = _tool_button("重做", "toolbar-redo-button", self, enabled=False)
        compare_button = _tool_button("对比版本", "toolbar-compare-button", self, enabled=False)
        recycle_button = _tool_button("回收站", "toolbar-recycle-button", self, enabled=False)
        settings_button = _tool_button("设置", "toolbar-settings-button", self, enabled=False)

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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("function-panel")
        self.setMinimumSize(230, 240)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(11, 10, 11, 10)
        body_layout.setSpacing(5)
        self._add_field(body_layout, "处理工作表", "选择文件后可用")
        self._add_field(body_layout, "处理范围", "当前数据区域")
        self._add_field(body_layout, "排序优先级", "销售额 · 降序")
        self._add_field(body_layout, "第二优先级", "日期 · 升序")
        self._add_field(body_layout, "空值位置", "始终排在末尾")
        body_layout.addStretch()

        footer = QFrame(self)
        footer.setObjectName("function-footer")
        footer.setFixedHeight(43)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 0, 10, 0)
        footer_layout.setSpacing(7)
        for text in ("返回", "重置"):
            footer_layout.addWidget(
                _tool_button(text, f"function-{text}-button", footer, enabled=False)
            )
        footer_layout.addStretch()
        footer_layout.addWidget(
            _tool_button("预览结果", "function-preview-button", footer, enabled=False)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_panel_header("多列排序", badge="功能开发中"))
        layout.addWidget(body, 1)
        layout.addWidget(footer)

    def _add_field(self, layout: QVBoxLayout, label: str, value: str) -> None:
        label_widget = QLabel(label, self)
        label_widget.setProperty("class", "form-label")
        field = QComboBox(self)
        field.setProperty("class", "field-control")
        field.addItem(value)
        field.setEnabled(False)
        layout.addWidget(label_widget)
        layout.addWidget(field)


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
        empty_layout.addStretch()
        self._empty_title = QLabel("选择文件查看版本演化树", empty)
        self._empty_title.setObjectName("tree-empty-title")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail = QLabel("根版本会在文件导入完成后显示", empty)
        self._empty_detail.setObjectName("tree-empty-detail")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        root_version: VersionRecord | None = None,
    ) -> None:
        if display_name is None:
            self._empty_title.setText("选择文件查看版本演化树")
            self._empty_detail.setText("根版本会在文件导入完成后显示")
            self._content.setCurrentIndex(0)
            return
        if root_version is None:
            self._empty_title.setText("旧记录尚未建立根版本")
            self._empty_detail.setText("文件仍可预览，后续可安全补建版本记录")
            self._content.setCurrentIndex(0)
            return

        self._scene.clear()
        card = self._root_version_card(display_name, root_version)
        proxy = self._scene.addWidget(card)
        assert isinstance(proxy, QGraphicsProxyWidget)
        proxy.setPos(28, 42)
        self._content.setCurrentIndex(1)

    def _root_version_card(self, display_name: str, version: VersionRecord) -> QFrame:
        card = QFrame()
        card.setObjectName("root-version-card")
        card.setFixedSize(230, 108)
        card.setStyleSheet(
            """
            QFrame#root-version-card {
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
        head = QLabel("HEAD · 根版本", card)
        head.setObjectName("root-version-head")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setMaximumWidth(82)
        layout.addWidget(title)
        layout.addWidget(file_name)
        layout.addWidget(metadata)
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(formula)
        layout.addWidget(format_bar)
        layout.addWidget(preview, 1)
