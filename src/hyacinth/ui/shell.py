from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen
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
QLabel#sort-state { color: #5d6673; padding: 4px 0; }
QLabel#sort-state[error="true"] { color: #a4262c; }
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
    preview_requested = Signal(str, object)
    cancel_requested = Signal()
    apply_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("function-panel")
        self.setMinimumSize(230, 240)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(11, 10, 11, 10)
        body_layout.setSpacing(5)
        self._headers_by_sheet: dict[str, tuple[str, ...]] = {}
        self._sheet = self._field(body_layout, "处理工作表", "sort-sheet")
        self._sheet.currentTextChanged.connect(self._refresh_columns)
        self._primary = self._field(body_layout, "第一优先级", "sort-primary-column")
        self._primary_direction = self._direction_field(
            body_layout, "第一排序方向", "sort-primary-direction"
        )
        self._secondary = self._field(body_layout, "第二优先级", "sort-secondary-column")
        self._secondary_direction = self._direction_field(
            body_layout, "第二排序方向", "sort-secondary-direction"
        )
        self._range = QLabel("当前 used range · 首行作为表头", body)
        self._range.setObjectName("sort-range-note")
        self._empty = QLabel("空值始终排在末尾", body)
        self._empty.setObjectName("sort-empty-note")
        self._state = QLabel("选择文件后可配置排序", body)
        self._state.setObjectName("sort-state")
        self._state.setWordWrap(True)
        self._state.setAccessibleName("排序状态")
        body_layout.addWidget(self._range)
        body_layout.addWidget(self._empty)
        body_layout.addWidget(self._state)
        body_layout.addStretch()

        footer = QFrame(self)
        footer.setObjectName("function-footer")
        footer.setFixedHeight(43)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 0, 10, 0)
        footer_layout.setSpacing(7)
        self._cancel = _tool_button("取消", "function-cancel-button", footer, enabled=False)
        self._cancel.setAccessibleName("取消临时预览")
        self._reset = _tool_button("重置", "function-reset-button", footer, enabled=False)
        self._cancel.clicked.connect(self.cancel_requested)
        self._reset.clicked.connect(self._reset_fields)
        footer_layout.addWidget(self._cancel)
        footer_layout.addWidget(self._reset)
        footer_layout.addStretch()
        self._preview = _tool_button("预览", "function-preview-button", footer, enabled=False)
        self._apply = _tool_button("应用", "function-apply-button", footer, enabled=False)
        self._preview.setAccessibleName("预览排序结果")
        self._apply.setAccessibleName("应用临时结果为新版本")
        self._preview.clicked.connect(self._emit_preview)
        self._apply.clicked.connect(self.apply_requested)
        footer_layout.addWidget(self._preview)
        footer_layout.addWidget(self._apply)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_panel_header("多列排序", badge="Python 安全模式"))
        layout.addWidget(body, 1)
        layout.addWidget(footer)

        self._controls = (
            self._sheet,
            self._primary,
            self._primary_direction,
            self._secondary,
            self._secondary_direction,
        )
        self._set_config_enabled(False)

    def set_workbook(self, headers_by_sheet: dict[str, tuple[str, ...]]) -> None:
        self._headers_by_sheet = headers_by_sheet
        self._sheet.blockSignals(True)
        self._sheet.clear()
        self._sheet.addItems(tuple(headers_by_sheet))
        self._sheet.blockSignals(False)
        self._refresh_columns(self._sheet.currentText())
        enabled = bool(headers_by_sheet)
        self._set_config_enabled(enabled)
        self._state.setText("配置排序条件后预览完整数据行")
        self._state.setProperty("error", False)
        self._state.style().unpolish(self._state)
        self._state.style().polish(self._state)

    def clear_workbook(self) -> None:
        self._headers_by_sheet.clear()
        self._sheet.clear()
        self._primary.clear()
        self._secondary.clear()
        self._set_config_enabled(False)
        self._state.setText("选择文件后可配置排序")

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

    def set_error(self, message: str) -> None:
        self._set_config_enabled(bool(self._headers_by_sheet))
        self._cancel.setEnabled(False)
        self._apply.setEnabled(False)
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
        for index, header in enumerate(headers):
            label = header or f"第 {index + 1} 列"
            self._primary.addItem(label, index)
            self._secondary.addItem(label, index)

    def _reset_fields(self) -> None:
        self._primary.setCurrentIndex(0)
        self._primary_direction.setCurrentIndex(0)
        self._secondary.setCurrentIndex(0)
        self._secondary_direction.setCurrentIndex(0)
        self._state.setText("已重置排序条件")

    def _set_config_enabled(self, enabled: bool) -> None:
        for control in getattr(self, "_controls", ()):
            control.setEnabled(enabled)
        self._reset.setEnabled(enabled)
        self._preview.setEnabled(enabled and self._primary.count() > 0)

    def _emit_preview(self) -> None:
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
