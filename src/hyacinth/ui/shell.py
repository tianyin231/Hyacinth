from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl.utils import get_column_letter
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QContextMenuEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hyacinth.ui.icons import fluent_icon
from hyacinth.versioning import VersionLayout, VersionRecord

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
QFrame#temporary-result-banner {
    color: #7a4d00;
    background: #fff4ce;
    border-bottom: 1px solid #e5c365;
}
QFrame#temporary-result-banner QLabel { color: #7a4d00; }
QPushButton#banner-apply-button {
    color: #ffffff;
    background: #0f6cbd;
    border: 1px solid #0f6cbd;
    font-weight: 600;
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
QFrame#formula-bar, QFrame#format-bar, QFrame#editor-ribbon {
    background: #f6f8fb;
    border-bottom: 1px solid #dfe3e8;
}
QFrame#ribbon-group { background: transparent; }
QLabel#ribbon-group-label { color: #6b7482; font-size: 10px; }
QFrame#ribbon-separator { background: #e2e6ec; }
QPushButton[class="ribbon-button"] {
    min-height: 26px;
    padding: 0 10px;
    color: #343a45;
    background: #fbfcfe;
    border: 1px solid #c6ced9;
    border-radius: 4px;
}
QPushButton[class="ribbon-button"]:hover { background: #eef4fb; border-color: #9ec4ea; }
QPushButton[class="ribbon-button"]:pressed { background: #dcebfa; }
QPushButton[class="ribbon-button"]:disabled { color: #9aa2ad; background: #f5f6f8; }
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
QFrame#version-storage-status { background: transparent; }
QLabel#storage-format-pill {
    color: #0b5a9d;
    background: #e5f2fb;
    border: 1px solid #bcd9f2;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 650;
}
QLabel#storage-size-text { color: #5c6370; font-size: 12px; }
"""

VERSION_CANVAS_RECT = QRectF(-5000.0, -5000.0, 10000.0, 10000.0)
VERSION_NODE_WIDTH = 230.0
VERSION_NODE_HEIGHT = 108.0


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
    save_version_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    export_requested = Signal()
    recycle_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("top-toolbar")
        self.setFixedHeight(44)

        import_button = _tool_button("导入文件", "toolbar-import-button", self, icon="plus")
        import_button.setAccessibleName("导入 Excel 文件")
        import_button.clicked.connect(self.import_requested)
        self._save_button = _tool_button(
            "保存为新版本", "toolbar-save-version-button", self, enabled=False, icon="save"
        )
        self._save_button.setShortcut(QKeySequence.StandardKey.Save)
        self._save_button.setToolTip("将当前未保存修改创建为新的子版本 (Ctrl+S)")
        self._save_button.clicked.connect(self.save_version_requested)
        self._export_button = _tool_button(
            "导出版本", "toolbar-export-button", self, enabled=False, icon="download"
        )
        self._export_button.setToolTip("导出当前预览的不可变版本")
        self._export_button.clicked.connect(self.export_requested)
        self._undo_button = _tool_button(
            "撤销", "toolbar-undo-button", self, enabled=False, icon="undo"
        )
        self._undo_button.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_button.setToolTip("撤销当前编辑会话中的上一步修改 (Ctrl+Z)")
        self._undo_button.clicked.connect(self.undo_requested)
        self._redo_button = _tool_button(
            "重做", "toolbar-redo-button", self, enabled=False, icon="redo"
        )
        self._redo_button.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_button.setToolTip("重做当前编辑会话中的修改 (Ctrl+Y)")
        self._redo_button.clicked.connect(self.redo_requested)
        compare_button = _tool_button(
            "对比版本", "toolbar-compare-button", self, enabled=False, icon="compare"
        )
        self._recycle_button = _tool_button("回收站", "toolbar-recycle-button", self, icon="trash")
        settings_button = _tool_button(
            "设置", "toolbar-settings-button", self, enabled=False, icon="settings"
        )
        compare_button.setToolTip("版本对比将在后续节点开放")
        self._recycle_button.setToolTip("查看回收站中的文件，恢复或永久删除")
        self._recycle_button.setAccessibleName("打开文件回收站")
        self._recycle_button.clicked.connect(self.recycle_requested)
        settings_button.setToolTip("设置将在后续节点开放")

        divider = QFrame(self)
        divider.setObjectName("toolbar-divider")
        divider.setFixedSize(1, 20)
        mode = QLabel("●  引擎自动选择", self)
        mode.setObjectName("engine-mode-pill")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(7)
        layout.addWidget(import_button)
        layout.addWidget(self._save_button)
        layout.addWidget(self._export_button)
        layout.addWidget(divider)
        layout.addWidget(self._undo_button)
        layout.addWidget(self._redo_button)
        layout.addWidget(compare_button)
        layout.addWidget(self._recycle_button)
        layout.addStretch()
        layout.addWidget(mode)
        layout.addWidget(settings_button)

    def set_edit_state(self, dirty: bool, can_undo: bool, can_redo: bool) -> None:
        self._save_button.setEnabled(dirty)
        self._undo_button.setEnabled(can_undo)
        self._redo_button.setEnabled(can_redo)

    def set_version_available(self, available: bool) -> None:
        self._export_button.setEnabled(available)


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


LANE_HEADER_HEIGHT = 40.0
LANE_GAP = 56.0
NODE_DX = 260.0
NODE_DY = 126.0


@dataclass(frozen=True, slots=True)
class FileVersionTree:
    file_id: str
    display_name: str
    versions: tuple[VersionRecord, ...]
    head_version_id: str | None
    layouts: dict[str, VersionLayout]


class TrimDetailsModel(QAbstractTableModel):
    def __init__(
        self,
        cells: tuple[tuple[str, str, str, str], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cells = cells

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._cells)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else 3

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row_text, column_text, before, after = self._cells[index.row()]
        return (row_text, column_text, f"{before} → {after}")[index.column()]

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object | None:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return ("行", "列", "内容变化")[section]


class FindDetailsModel(QAbstractTableModel):
    def __init__(
        self,
        changes: tuple[tuple[str, int, int, str, str], ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._changes = changes

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._changes)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else 4

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        sheet, row, column, before, after = self._changes[index.row()]
        return (sheet, f"R{row}C{column}", before, after)[index.column()]

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object | None:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return ("工作表", "位置", "修改前", "修改后")[section]


class _VersionTreeView(QGraphicsView):
    node_selected = Signal(str, str)
    position_changing = Signal(str, str, float, float)
    position_committed = Signal(str, str, float, float)

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self._drag_proxy: QGraphicsProxyWidget | None = None
        self._drag_file_id: str | None = None
        self._drag_version_id: str | None = None
        self._drag_origin_view: QPoint | None = None
        self._drag_origin_scene: QPointF | None = None
        self._dragged = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._reset_node_drag()
        if event.button() is Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None and not isinstance(item, QGraphicsProxyWidget):
                item = item.parentItem()
            if isinstance(item, QGraphicsProxyWidget):
                card = item.widget()
                if card is not None:
                    version_id = str(card.property("version-id"))
                    file_id = str(card.property("file-id"))
                    self._drag_proxy = item
                    self._drag_file_id = file_id
                    self._drag_version_id = version_id
                    self._drag_origin_view = event.position().toPoint()
                    self._drag_origin_scene = item.pos()
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                    card.setFocus()
                    if not bool(card.property("deleted")):
                        self.node_selected.emit(file_id, version_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_proxy is not None
            and self._drag_file_id is not None
            and self._drag_version_id is not None
            and self._drag_origin_view is not None
            and self._drag_origin_scene is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            movement = event.position().toPoint() - self._drag_origin_view
            if movement.manhattanLength() >= QApplication.startDragDistance():
                self._dragged = True
                scene_delta = self.mapToScene(event.position().toPoint()) - self.mapToScene(
                    self._drag_origin_view
                )
                position = self._drag_origin_scene + scene_delta
                self.position_changing.emit(
                    self._drag_file_id,
                    self._drag_version_id,
                    position.x(),
                    position.y(),
                )
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() is Qt.MouseButton.LeftButton
            and self._dragged
            and self._drag_proxy is not None
            and self._drag_file_id is not None
            and self._drag_version_id is not None
        ):
            position = self._drag_proxy.pos()
            self.position_committed.emit(
                self._drag_file_id,
                self._drag_version_id,
                position.x(),
                position.y(),
            )
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._reset_node_drag()

    def wheelEvent(self, event: QWheelEvent) -> None:
        vertical_delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if vertical_delta != 0:
                factor = 1.15 if vertical_delta > 0 else 1 / 1.15
                target_scale = self.transform().m11() * factor
                if 0.4 <= target_scale <= 2.5:
                    self.scale(factor, factor)
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            horizontal_delta = vertical_delta or event.angleDelta().x()
            scrollbar = self.horizontalScrollBar()
            scrollbar.setValue(scrollbar.value() - horizontal_delta)
            event.accept()
            return
        super().wheelEvent(event)

    def _reset_node_drag(self) -> None:
        self._drag_proxy = None
        self._drag_file_id = None
        self._drag_version_id = None
        self._drag_origin_view = None
        self._drag_origin_scene = None
        self._dragged = False


class _VersionNodeCard(QFrame):
    selected = Signal(str)
    continue_requested = Signal(str)
    delete_requested = Signal(str)
    context_menu_requested = Signal(str, QPoint)

    def __init__(self, version_id: str, *, deleted: bool, file_id: str = "") -> None:
        super().__init__()
        self._version_id = version_id
        self._deleted = deleted
        self.setProperty("version-id", version_id)
        self.setProperty("file-id", file_id)
        self.setProperty("deleted", deleted)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.setFocus()
            if self._deleted:
                super().mousePressEvent(event)
                return
            self.selected.emit(self._version_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and not self._deleted:
            self.continue_requested.emit(self._version_id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.context_menu_requested.emit(self._version_id, event.globalPos())
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete and not self._deleted:
            self.delete_requested.emit(self._version_id)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self._deleted:
            self.continue_requested.emit(self._version_id)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space and not self._deleted:
            self.selected.emit(self._version_id)
            event.accept()
            return
        super().keyPressEvent(event)


class VersionTreePanel(QFrame):
    focus_mode_requested = Signal(bool)
    version_preview_requested = Signal(str, str)
    version_continue_requested = Signal(str, str)
    version_position_changed = Signal(str, str, float, float)
    version_delete_requested = Signal(str, str)
    version_restore_requested = Signal(str, str)
    version_export_requested = Signal(str, str, bool)
    version_purge_requested = Signal(str, str)
    layout_reset_requested = Signal()

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
        self._continue = QPushButton("从此继续", self)
        self._continue.setObjectName("version-continue-button")
        self._continue.setProperty("class", "tool-button")
        self._continue.setAccessibleName("从选中的历史版本继续")
        self._continue.setToolTip("设为当前工作版本；后续保存会从这里创建新分支")
        self._continue.setEnabled(False)
        self._continue.clicked.connect(self._continue_selected_version)
        self._undo_delete = QPushButton("撤销删除", self)
        self._undo_delete.setObjectName("version-undo-delete-button")
        self._undo_delete.setProperty("class", "tool-button")
        self._undo_delete.setAccessibleName("恢复刚刚删除的版本")
        self._undo_delete.setVisible(False)
        self._undo_delete.clicked.connect(self._restore_recently_deleted)

        search_row = QFrame(self)
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(9, 5, 9, 5)
        search_layout.addWidget(search)
        search_layout.addWidget(self._continue)
        search_layout.addWidget(self._undo_delete)

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
        self._empty_title = QLabel("导入文件查看版本演化树", empty)
        self._empty_title.setObjectName("tree-empty-title")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail = QLabel("每个文件的版本树都会显示在同一画布", empty)
        self._empty_detail.setObjectName("tree-empty-detail")
        self._empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_detail.setWordWrap(True)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_detail)
        empty_layout.addStretch()

        self._scene = QGraphicsScene(self)
        self._scene.setObjectName("version-tree-scene")
        self._scene.setSceneRect(VERSION_CANVAS_RECT)
        self._view = _VersionTreeView(self._scene, self)
        self._view.setObjectName("version-tree-view")
        self._view.setAccessibleName("版本演化树")
        self._view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.node_selected.connect(self._select_version)
        self._view.position_changing.connect(self._move_version)
        self._view.position_committed.connect(self._commit_version_position)

        self._content = QStackedWidget(self)
        self._content.addWidget(empty)
        self._content.addWidget(self._view)

        header = _panel_header("版本演化树")
        self._focus_button = QPushButton("专注", header)
        self._focus_button.setObjectName("version-focus-button")
        self._focus_button.setProperty("class", "tool-button")
        self._focus_button.setCheckable(True)
        self._focus_button.setAccessibleName("进入版本图谱专注模式")
        self._focus_button.setToolTip("隐藏其他区域，只查看全部文件的版本图谱")
        self._focus_button.clicked.connect(self._toggle_focus_mode)
        self._reset_layout_button = QPushButton("重整布局", header)
        self._reset_layout_button.setObjectName("version-reset-layout-button")
        self._reset_layout_button.setProperty("class", "tool-button")
        self._reset_layout_button.setAccessibleName("恢复全部节点的默认排布")
        self._reset_layout_button.setToolTip("清除所有文件的手动节点位置并恢复默认排布")
        self._reset_layout_button.clicked.connect(lambda: self.layout_reset_requested.emit())
        self._mode_button = QPushButton("仅看当前文件", header)
        self._mode_button.setObjectName("version-mode-toggle-button")
        self._mode_button.setProperty("class", "tool-button")
        self._mode_button.setAccessibleName("切换仅当前文件与全部文件的画布模式")
        self._mode_button.setToolTip("在只显示当前文件的版本树和全部文件画布之间切换")
        self._mode_button.clicked.connect(self._toggle_view_mode)
        header_layout = header.layout()
        assert header_layout is not None
        header_layout.addWidget(self._mode_button)
        header_layout.addWidget(self._reset_layout_button)
        header_layout.addWidget(self._focus_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(search_row)
        layout.addWidget(self._content, 1)
        self._cards: dict[tuple[str, str], _VersionNodeCard] = {}
        self._proxies: dict[tuple[str, str], QGraphicsProxyWidget] = {}
        self._edge_relations: list[tuple[str, str, str, QGraphicsLineItem]] = []
        # addRect/addSimpleText 返回的项必须保存 Python 引用，
        # 否则重建场景后未引用项会被 PySide6 垃圾回收连带销毁。
        self._lane_decorations: list[QGraphicsItem] = []
        # 固定节点保存泳道内相对坐标，泳道高度变化时节点随泳道移动。
        self._lane_content_tops: dict[str, float] = {}
        self._single_file_mode = False
        self._items_by_file: dict[str, list[QGraphicsItem]] = {}
        # 已渲染节点的泳道相对位置记忆：重建画布时已有节点保持原位，
        # 只有新节点按树形算法插入并避让；手动“重整布局”才整体重排。
        self._remembered_lane_positions: dict[tuple[str, str], tuple[float, float]] = {}
        self._last_trees: tuple[FileVersionTree, ...] = ()
        self._last_current_file_id: str | None = None
        self._records: dict[tuple[str, str], VersionRecord] = {}
        self._tree_heads: dict[str, str | None] = {}
        self._current_file_id: str | None = None
        self._file_ids_by_version: dict[str, str] = {}
        self._selected_key: tuple[str, str] | None = None
        self._recently_deleted_key: tuple[str, str] | None = None
        # QGraphicsProxyWidget 的延迟销毁在 Qt 6.11/Windows 下存在原生崩溃窗口。
        # 版本树只在文件或节点变化时重建，因此保留旧场景到面板销毁更安全且开销可控。
        self._retired_scenes: list[QGraphicsScene] = []

    def set_workbooks(
        self,
        trees: tuple[FileVersionTree, ...],
        *,
        current_file_id: str | None = None,
        focus_file_id: str | None = None,
        focus_version_id: str | None = None,
    ) -> None:
        self._current_file_id = current_file_id
        self._last_trees = trees
        self._last_current_file_id = current_file_id
        self._tree_heads = {tree.file_id: tree.head_version_id for tree in trees}
        self._records = {
            (tree.file_id, version.version_id): version
            for tree in trees
            for version in tree.versions
        }
        self._file_ids_by_version = {
            version.version_id: tree.file_id for tree in trees for version in tree.versions
        }
        if not trees:
            self._empty_title.setText("导入文件查看版本演化树")
            self._empty_detail.setText("每个文件的版本树都会显示在同一画布")
            self._content.setCurrentIndex(0)
            self._continue.setEnabled(False)
            self.clear_delete_undo()
            self._selected_key = None
            return

        focus_tree = next(
            (tree for tree in trees if tree.file_id == (focus_file_id or current_file_id)),
            trees[0],
        )
        if focus_tree.head_version_id is not None:
            self._selected_key = (focus_tree.file_id, focus_tree.head_version_id)
        self._render_workbooks(
            trees,
            current_file_id,
            focus_key=(
                (focus_file_id, focus_version_id)
                if focus_file_id is not None and focus_version_id is not None
                else None
            ),
        )
        self._content.setCurrentIndex(1)
        self._continue.setEnabled(False)
        self.clear_delete_undo()

    def show_delete_undo(self, file_id: str, version_id: str) -> None:
        self._recently_deleted_key = (file_id, version_id)
        self._undo_delete.setVisible(True)
        self._undo_delete.setEnabled(True)

    def clear_delete_undo(self) -> None:
        self._recently_deleted_key = None
        self._undo_delete.setVisible(False)

    def focus_anchor(self) -> QPointF:
        return self._view.mapToScene(self._view.viewport().rect().center())

    def restore_focus_anchor(self, anchor: QPointF) -> None:
        self._view.centerOn(anchor)

    def _render_workbooks(
        self,
        trees: tuple[FileVersionTree, ...],
        current_file_id: str | None,
        focus_key: tuple[str, str] | None,
    ) -> None:
        previous_scene = self._scene
        scene = QGraphicsScene(self)
        scene.setObjectName("version-tree-scene")
        scene.setSceneRect(VERSION_CANVAS_RECT)
        anchor = self._view.mapToScene(self._view.viewport().rect().center())
        self._cards = {}
        self._proxies = {}
        self._edge_relations = []
        self._lane_content_tops = {}
        self._items_by_file = {}
        # 全画布已占用区域：新节点对全部已定位节点避让，已定位节点永不移动。
        occupied: list[QRectF] = []
        render_trees: tuple[FileVersionTree, ...] = trees
        if (
            self._single_file_mode
            and current_file_id is not None
            and any(tree.file_id == current_file_id for tree in trees)
        ):
            render_trees = tuple(tree for tree in trees if tree.file_id == current_file_id)
        lane_top = 42.0
        focus_proxy: QGraphicsProxyWidget | None = None
        first_proxy: QGraphicsProxyWidget | None = None
        for tree in render_trees:
            lane_positions = self._lane_positions(tree, occupied)
            lane_rows = 1
            for _, y in lane_positions.values():
                lane_rows = max(lane_rows, int((y - lane_top - LANE_HEADER_HEIGHT) // NODE_DY) + 1)
            lane_height = LANE_HEADER_HEIGHT + (lane_rows + 1) * NODE_DY + 10.0
            is_current = tree.file_id == current_file_id
            self._items_by_file[tree.file_id] = []
            self._lane_content_tops[tree.file_id] = lane_top + LANE_HEADER_HEIGHT
            for version in tree.versions:
                position = lane_positions[version.version_id]
                bounded = self._bounded_position(*position)
                key = (tree.file_id, version.version_id)
                card = self._version_card(
                    tree.display_name,
                    version,
                    file_id=tree.file_id,
                    is_head=tree.head_version_id == version.version_id,
                    is_current_file=is_current,
                )
                card.selected.connect(lambda vid, fid=tree.file_id: self._select_version(fid, vid))
                card.continue_requested.connect(
                    lambda vid, fid=tree.file_id: self._request_continue(fid, vid)
                )
                card.delete_requested.connect(
                    lambda vid, fid=tree.file_id: self._request_delete(fid, vid)
                )
                card.context_menu_requested.connect(
                    lambda vid, pos, fid=tree.file_id: self._show_context_menu(fid, vid, pos)
                )
                proxy = scene.addWidget(card)
                assert isinstance(proxy, QGraphicsProxyWidget)
                proxy.setPos(*bounded)
                if not is_current:
                    proxy.setOpacity(0.78)
                self._proxies[key] = proxy
                self._cards[key] = card
                self._items_by_file[tree.file_id].append(proxy)
                if first_proxy is None:
                    first_proxy = proxy
                if key == focus_key:
                    focus_proxy = proxy
            for version in tree.versions:
                parent_id = version.parent_version_id
                if parent_id is None:
                    continue
                parent_proxy = self._proxies.get((tree.file_id, parent_id))
                child_proxy = self._proxies.get((tree.file_id, version.version_id))
                if parent_proxy is None or child_proxy is None:
                    continue
                parent_rect = parent_proxy.sceneBoundingRect()
                child_rect = child_proxy.sceneBoundingRect()
                line = scene.addLine(
                    parent_rect.right(),
                    parent_rect.center().y(),
                    child_rect.left(),
                    child_rect.center().y(),
                    QPen(Qt.GlobalColor.gray, 1.5),
                )
                line.setZValue(-1)
                self._edge_relations.append((tree.file_id, parent_id, version.version_id, line))
                self._items_by_file[tree.file_id].append(line)
            lane_top += lane_height + LANE_GAP
        self._view.setScene(scene)
        self._scene = scene
        if focus_proxy is not None:
            self._view.centerOn(focus_proxy)
        elif previous_scene.items() or first_proxy is None:
            self._view.centerOn(anchor)
        elif first_proxy is not None:
            self._view.centerOn(first_proxy)
        self._apply_view_mode_visibility()
        self._retired_scenes.append(previous_scene)
        # 只保留少量退役场景防止长会话累积拖垮内存；隔多轮再销毁
        # 可避开 QGraphicsProxyWidget 延迟销毁的原生竞态窗口。
        del self._retired_scenes[:-3]

    def _lane_positions(
        self,
        tree: FileVersionTree,
        occupied: list[QRectF],
    ) -> dict[str, tuple[float, float]]:
        """解析每个版本的画布绝对坐标。

        固定布局与位置记忆优先且永不移动；新节点按树形算法在泳道基线
        定位，并对全画布已占用区域避让。记忆保存绝对坐标。
        """
        tree_positions, _ = self._layout_lane(tree)
        lane_base = self._lane_content_tops.get(tree.file_id, 82.0)
        lane_positions: dict[str, tuple[float, float]] = {}
        for version in tree.versions:
            key = (tree.file_id, version.version_id)
            layout = tree.layouts.get(version.version_id)
            if layout is not None and layout.fixed:
                position = (layout.x, layout.y)
            elif key in self._remembered_lane_positions:
                position = self._remembered_lane_positions[key]
            else:
                tree_x, tree_y = tree_positions[version.version_id]
                position = (28.0 + tree_x, lane_base + tree_y)
                candidate = QRectF(
                    position[0], position[1], VERSION_NODE_WIDTH, VERSION_NODE_HEIGHT
                )
                while any(candidate.adjusted(-8, -8, 8, 8).intersects(rect) for rect in occupied):
                    position = (position[0], position[1] + NODE_DY)
                    candidate.moveTop(position[1])
            occupied.append(
                QRectF(position[0], position[1], VERSION_NODE_WIDTH, VERSION_NODE_HEIGHT)
            )
            lane_positions[version.version_id] = position
            self._remembered_lane_positions[key] = position
        return lane_positions

    def clear_remembered_layouts(self) -> None:
        self._remembered_lane_positions.clear()

    def _layout_lane(self, tree: FileVersionTree) -> tuple[dict[str, tuple[float, float]], int]:
        """树形排布：叶子按序占行，父节点纵向居中于其子树区间。

        固定节点不参与自动排布；以“最近的固定祖先”为边界，
        每棵自动子树独立分配行，保证所有非固定节点（含固定节点的后代）都被排布。
        """
        children: dict[str | None, list[VersionRecord]] = {}
        for version in tree.versions:
            children.setdefault(version.parent_version_id, []).append(version)
        fixed_ids = {version_id for version_id, layout in tree.layouts.items() if layout.fixed}
        depth_of: dict[str, int] = {}
        for version in tree.versions:
            depth_of[version.version_id] = (
                0
                if version.parent_version_id is None
                else depth_of.get(version.parent_version_id, 0) + 1
            )
        positions: dict[str, tuple[float, float]] = {}
        next_row = 0

        def assign(version: VersionRecord, depth: int) -> tuple[int, int]:
            nonlocal next_row
            auto_kids = [
                child
                for child in children.get(version.version_id, [])
                if child.version_id not in fixed_ids
            ]
            if not auto_kids:
                row = next_row
                next_row += 1
                span = (row, row)
            else:
                spans = [assign(child, depth + 1) for child in auto_kids]
                span = (spans[0][0], spans[-1][1])
            center_y = (span[0] + span[1]) / 2 * NODE_DY
            positions[version.version_id] = (depth * NODE_DX, center_y)
            return span

        for version in tree.versions:
            is_auto_root = version.version_id not in fixed_ids and (
                version.parent_version_id is None or version.parent_version_id in fixed_ids
            )
            if is_auto_root:
                assign(version, depth_of[version.version_id])
        max_depth = max(depth_of.values(), default=0)
        return positions, max_depth

    def _version_card(
        self,
        display_name: str,
        version: VersionRecord,
        *,
        file_id: str,
        is_head: bool,
        is_current_file: bool,
    ) -> _VersionNodeCard:
        is_deleted = version.deleted_at is not None
        card = _VersionNodeCard(version.version_id, deleted=is_deleted, file_id=file_id)
        is_root = version.parent_version_id is None
        card.setObjectName("root-version-card" if is_root else "child-version-card")
        card.setAccessibleName(
            f"已删除版本 {version.name}" if is_deleted else f"版本 {version.name}"
        )
        card.setFixedSize(230, 108)
        selected = self._selected_key is not None and self._selected_key == (
            file_id,
            version.version_id,
        )
        card.setProperty("selected", selected)
        emphasis = "#0f6cbd" if is_current_file else "#8a94a3"
        card.setStyleSheet(
            f"""
            QFrame#root-version-card, QFrame#child-version-card {{
                background: #ffffff;
                border: 1px solid #cfd5de;
                border-left: 3px solid {emphasis};
                border-radius: 7px;
            }}
            QFrame#root-version-card[selected="true"],
            QFrame#child-version-card[selected="true"],
            QFrame#root-version-card:focus,
            QFrame#child-version-card:focus {{
                border: 2px solid #0f6cbd;
                border-left: 4px solid #0f6cbd;
            }}
            QFrame#root-version-card[deleted="true"],
            QFrame#child-version-card[deleted="true"] {{
                background: #eef1f4;
                border: 1px dashed #9aa2ad;
                border-left: 3px solid #9aa2ad;
            }}
            QFrame#root-version-card[deleted="true"] QLabel,
            QFrame#child-version-card[deleted="true"] QLabel {{ color: #7b8491; }}
            QLabel {{ border: 0; background: transparent; }}
            QLabel#root-version-name {{ color: #343a45; font-weight: 600; }}
            QLabel#root-version-file {{ color: #343a45; font-size: 11px; }}
            QLabel#root-version-meta {{ color: #68717e; font-size: 10px; }}
            QLabel#root-version-head {{
                color: #0b5a9d;
                background: #e5f2fb;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        title = QLabel(f"已删除 · {version.name}" if is_deleted else version.name, card)
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
        # 根版本标记独立于 HEAD：多根画布中非 HEAD 的根节点也要一眼可辨（需求第 47 节）。
        if is_head and is_root:
            badge_text = "HEAD · 根版本"
        elif is_head:
            badge_text = "HEAD"
        else:
            badge_text = "根版本"
        head = QLabel(badge_text, card)
        head.setObjectName("root-version-head")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setMaximumWidth(82)
        layout.addWidget(title)
        layout.addWidget(file_name)
        layout.addWidget(metadata)
        head.setVisible(is_head or is_root)
        layout.addWidget(head)
        if is_deleted and version.deleted_at is not None:
            card.setToolTip(
                f"已于 {version.deleted_at.astimezone().strftime('%Y-%m-%d %H:%M')} 删除；"
                "右键可恢复"
            )
        return card

    def _select_version(self, file_id: str, version_id: str) -> None:
        key = (file_id, version_id)
        record = self._records.get(key)
        if record is None or record.deleted_at is not None:
            return
        selection_changed = key != self._selected_key
        self._selected_key = key
        for card_key, card in self._cards.items():
            card.setProperty("selected", card_key == key)
            card.style().unpolish(card)
            card.style().polish(card)
        self._continue.setEnabled(version_id != self._tree_heads.get(file_id))
        if selection_changed:
            self.version_preview_requested.emit(file_id, version_id)

    def _continue_selected_version(self) -> None:
        if self._selected_key is not None:
            self._request_continue(*self._selected_key)

    def _request_continue(self, file_id: str, version_id: str) -> None:
        record = self._records.get((file_id, version_id))
        head_id = self._tree_heads.get(file_id)
        if record is not None and record.deleted_at is None and version_id != head_id:
            self.version_continue_requested.emit(file_id, version_id)

    def _request_delete(self, file_id: str, version_id: str) -> None:
        record = self._records.get((file_id, version_id))
        if record is not None and record.deleted_at is None:
            self.version_delete_requested.emit(file_id, version_id)

    def _request_restore(self, file_id: str, version_id: str) -> None:
        record = self._records.get((file_id, version_id))
        if record is not None and record.deleted_at is not None:
            self.version_restore_requested.emit(file_id, version_id)

    def _request_export(self, file_id: str, version_id: str, save_as: bool) -> None:
        record = self._records.get((file_id, version_id))
        if record is not None and record.deleted_at is not None:
            return
        self.version_export_requested.emit(file_id, version_id, save_as)

    def _restore_recently_deleted(self) -> None:
        if self._recently_deleted_key is not None:
            self.version_restore_requested.emit(*self._recently_deleted_key)

    def _show_context_menu(self, file_id: str, version_id: str, global_position: QPoint) -> None:
        record = self._records.get((file_id, version_id))
        if record is None:
            return
        menu = QMenu(self)
        if record.deleted_at is not None:
            restore = menu.addAction("恢复版本")
            restore.triggered.connect(lambda: self._request_restore(file_id, version_id))
            menu.addSeparator()
            purge_action = menu.addAction("永久删除该版本")
            purge_action.triggered.connect(
                lambda: self.version_purge_requested.emit(file_id, version_id)
            )
        else:
            preview = menu.addAction("预览版本")
            preview.triggered.connect(lambda: self._select_version(file_id, version_id))
            download = menu.addAction("下载该节点")
            download.triggered.connect(lambda: self._request_export(file_id, version_id, False))
            save_as = menu.addAction("另存为…")
            save_as.triggered.connect(lambda: self._request_export(file_id, version_id, True))
            if version_id != self._tree_heads.get(file_id):
                continue_action = menu.addAction("从此继续")
                continue_action.triggered.connect(
                    lambda: self._request_continue(file_id, version_id)
                )
            menu.addSeparator()
            delete_action = menu.addAction("删除版本")
            delete_action.triggered.connect(lambda: self._request_delete(file_id, version_id))
        menu.exec(global_position)

    def _move_version(self, file_id: str, version_id: str, x: float, y: float) -> None:
        proxy = self._proxies.get((file_id, version_id))
        if proxy is None:
            return
        bounded_x, bounded_y = self._bounded_position(x, y)
        proxy.setPos(bounded_x, bounded_y)
        for lane_file_id, parent_id, child_id, line in self._edge_relations:
            if version_id not in {parent_id, child_id} or lane_file_id != file_id:
                continue
            parent_rect = self._proxies[(file_id, parent_id)].sceneBoundingRect()
            child_rect = self._proxies[(file_id, child_id)].sceneBoundingRect()
            line.setLine(
                parent_rect.right(),
                parent_rect.center().y(),
                child_rect.left(),
                child_rect.center().y(),
            )

    def _commit_version_position(
        self,
        file_id: str,
        version_id: str,
        x: float,
        y: float,
    ) -> None:
        self.version_position_changed.emit(file_id, version_id, x, y)

    def _toggle_view_mode(self) -> None:
        self._single_file_mode = not self._single_file_mode
        if self._single_file_mode:
            self._mode_button.setText("查看全部文件")
        else:
            self._mode_button.setText("仅看当前文件")
        # 只切换泳道显隐，不重建场景：节点、连线与视口位置原样保持。
        self._apply_view_mode_visibility()

    def _apply_view_mode_visibility(self) -> None:
        single = self._single_file_mode and self._current_file_id is not None
        for file_id, items in self._items_by_file.items():
            visible = (not single) or file_id == self._current_file_id
            for item in items:
                item.setVisible(visible)

    def _toggle_focus_mode(self, enabled: bool) -> None:
        if enabled:
            self._focus_button.setText("退出专注")
            self._focus_button.setAccessibleName("退出版本图谱专注模式")
            self._focus_button.setToolTip("恢复完整工作台布局")
        else:
            self._focus_button.setText("专注")
            self._focus_button.setAccessibleName("进入版本图谱专注模式")
            self._focus_button.setToolTip("隐藏其他区域，只查看全部文件的版本图谱")
        self.focus_mode_requested.emit(enabled)

    @staticmethod
    def _bounded_position(x: float, y: float) -> tuple[float, float]:
        return (
            min(
                max(x, VERSION_CANVAS_RECT.left()),
                VERSION_CANVAS_RECT.right() - VERSION_NODE_WIDTH,
            ),
            min(
                max(y, VERSION_CANVAS_RECT.top()),
                VERSION_CANVAS_RECT.bottom() - VERSION_NODE_HEIGHT,
            ),
        )


class _RibbonGroup(QFrame):
    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon-group")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 1)
        layout.setSpacing(1)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(3)
        layout.addLayout(self.buttons)
        label = QLabel(title, self)
        label.setObjectName("ribbon-group-label")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def add_button(self, text: str, name: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setProperty("class", "ribbon-button")
        button.setMinimumHeight(28)
        self.buttons.addWidget(button)
        return button


class TemporaryResultBanner(QFrame):
    apply_requested = Signal()
    cancel_requested = Signal()
    details_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("temporary-result-banner")
        message = QLabel("临时结果 · 尚未生成版本", self)
        message.setObjectName("banner-message")
        self._message = message
        self._details = QPushButton("查看明细", self)
        self._details.setObjectName("banner-details-button")
        self._details.setProperty("class", "ribbon-button")
        self._apply = QPushButton("应用生成版本", self)
        self._apply.setObjectName("banner-apply-button")
        self._apply.setProperty("class", "ribbon-button")
        self._cancel = QPushButton("取消", self)
        self._cancel.setObjectName("banner-cancel-button")
        self._cancel.setProperty("class", "ribbon-button")
        self._details.clicked.connect(self.details_requested)
        self._apply.clicked.connect(self.apply_requested)
        self._cancel.clicked.connect(self.cancel_requested)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(6)
        message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(message, 1)
        layout.addWidget(self._details)
        layout.addWidget(self._apply)
        layout.addWidget(self._cancel)
        self.setVisible(False)

    def show_message(
        self, text: str, *, can_apply: bool = False, can_details: bool = False
    ) -> None:
        self._message.setText(text)
        self._apply.setEnabled(can_apply)
        self._details.setEnabled(can_details)
        self._details.setVisible(can_details)
        self.setVisible(True)

    def hide_banner(self) -> None:
        self.setVisible(False)


class ProcessingParamsBar(QFrame):
    """功能区条下方的原位参数确认行（需求第 16 节：不用遮挡数据的弹窗）。

    为“删除重复行”“清除首尾空格”等选项被入口写死的功能提供确认界面；
    关键列跟随表格当前选中列预填，改列通过重新选中表格区域完成。
    """

    deduplicate_confirmed = Signal(dict)
    trim_confirmed = Signal(dict)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("processing-params-bar")
        self._columns: list[int] = []

        self._title = QLabel("", self)
        self._title.setProperty("class", "panel-title")
        self._columns_label = QLabel("", self)
        self._columns_label.setObjectName("params-columns-label")
        self._columns_label.setProperty("class", "form-label")

        self._keep = QComboBox(self)
        self._keep.setObjectName("params-keep-combo")
        self._keep.setProperty("class", "field-control")
        self._keep.addItem("保留第一条", "first")
        self._keep.addItem("保留最后一条", "last")
        self._keep.setMinimumHeight(28)
        keep_label = QLabel("重复时", self)
        keep_label.setProperty("class", "form-label")
        self._ignore_case = QCheckBox("忽略大小写", self)
        self._ignore_case.setObjectName("params-ignore-case")
        self._ignore_trim = QCheckBox("比较时忽略首尾空格", self)
        self._ignore_trim.setObjectName("params-ignore-trim")
        self._collapse = QCheckBox("压缩中间连续空格", self)
        self._collapse.setObjectName("params-collapse-spaces")

        confirm = QPushButton("生成预览", self)
        confirm.setObjectName("params-confirm-button")
        confirm.setProperty("class", "ribbon-button")
        confirm.clicked.connect(self._emit_confirm)
        collapse_button = QPushButton("收起", self)
        collapse_button.setObjectName("params-collapse-button")
        collapse_button.setProperty("class", "ribbon-button")
        collapse_button.clicked.connect(self.dismissed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        layout.addWidget(self._title)
        layout.addWidget(self._columns_label)
        layout.addStretch(1)
        self._deduplicate_controls = (keep_label, self._keep, self._ignore_case, self._ignore_trim)
        for widget in self._deduplicate_controls:
            layout.addWidget(widget)
        layout.addWidget(self._collapse)
        layout.addWidget(confirm)
        self.setVisible(False)

    def show_deduplicate(self, columns: list[int]) -> None:
        self._columns = list(columns)
        self._title.setText("删除重复行")
        self._columns_label.setText(self._columns_text("未选列时按整行判断"))
        for widget in self._deduplicate_controls:
            widget.setVisible(True)
        self._collapse.setVisible(True)
        self.setVisible(True)

    def show_trim(self, columns: list[int]) -> None:
        self._columns = list(columns)
        self._title.setText("清除首尾空格")
        self._columns_label.setText(self._columns_text("未选列时处理全部文本列"))
        for widget in self._deduplicate_controls:
            widget.setVisible(False)
        self._collapse.setVisible(True)
        self.setVisible(True)

    def hide_bar(self) -> None:
        self.setVisible(False)

    def _columns_text(self, empty_hint: str) -> str:
        if not self._columns:
            return empty_hint
        letters = "、".join(get_column_letter(column + 1) for column in self._columns)
        return f"关键列 {letters}"

    def _emit_confirm(self) -> None:
        title = self._title.text()
        if title == "删除重复行":
            self.deduplicate_confirmed.emit(
                {
                    "key_columns": list(self._columns),
                    "keep": self._keep.currentData(),
                    "ignore_case": self._ignore_case.isChecked(),
                    "trim_whitespace": self._ignore_trim.isChecked(),
                }
            )
        elif title == "清除首尾空格":
            self.trim_confirmed.emit(
                {
                    "key_columns": list(self._columns),
                    "collapse_spaces": self._collapse.isChecked(),
                }
            )


class ProcessingDetailsDialog(QDialog):
    """两阶段预览的明细查看窗口，按处理结果类型接收对应表格模型。"""

    def __init__(
        self,
        title: str,
        model: QAbstractTableModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("processing-details-dialog")
        self.setWindowTitle(title)
        self.resize(520, 360)
        self.setModal(False)

        table = QTableView(self)
        table.setObjectName("processing-details-table")
        table.setModel(model)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setDefaultSectionSize(26)
        table.horizontalHeader().setStretchLastSection(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.addWidget(table, 1)
        layout.addWidget(buttons)


class FilterDialog(QDialog):
    params_submitted = Signal(object)

    def __init__(
        self,
        sheet_name: str,
        column_labels: tuple[str, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-dialog")
        self.setWindowTitle(f"筛选 · {sheet_name}")
        self.setModal(False)
        self.resize(480, 280)
        self._sheet_name = sheet_name
        self._column_labels = column_labels
        self._condition_rows: list[dict[str, object]] = []

        form = QVBoxLayout(self)
        form.setContentsMargins(14, 14, 14, 12)
        form.setSpacing(8)
        form.addLayout(self._build_condition_row())

        self._second = QCheckBox("添加第二条件", self)
        self._second.setToolTip("最多配置两个条件（DEC-021）")
        connector_label = QLabel("条件组合", self)
        connector_label.setProperty("class", "form-label")
        self._connector = QComboBox(self)
        self._connector.setProperty("class", "field-control")
        self._connector.addItem("并且", "and")
        self._connector.addItem("或者", "or")
        self._connector.setToolTip("跨列条件仅支持“并且”；同一列的两个条件可用“或者”")
        connector_row = QHBoxLayout()
        connector_row.addWidget(self._second)
        connector_row.addWidget(connector_label)
        connector_row.addWidget(self._connector)
        connector_row.addStretch()
        form.addLayout(connector_row)

        second_row = self._build_condition_row()
        assert isinstance(second_row, QHBoxLayout)
        self._second_frame = QFrame(self)
        self._second_frame.setObjectName("filter-second-condition")
        second_layout = QHBoxLayout(self._second_frame)
        second_layout.setContentsMargins(0, 0, 0, 0)
        second_layout.addLayout(second_row)
        self._second_frame.setVisible(False)
        self._second.toggled.connect(self._second_frame.setVisible)
        form.addWidget(self._second_frame)

        note = QLabel("跨列条件仅支持“并且”；同一列的两个条件可用“或者”", self)
        note.setProperty("class", "form-label")
        self._refresh_operators(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        apply_button = QPushButton("预览筛选", self)
        apply_button.setObjectName("filter-apply-button")
        apply_button.setProperty("class", "ribbon-button")
        apply_button.clicked.connect(self._submit)

        form.addWidget(note)
        form.addStretch()
        button_row = QHBoxLayout()
        button_row.addWidget(apply_button)
        button_row.addStretch()
        button_row.addWidget(buttons)
        form.addLayout(button_row)

    def _build_condition_row(self) -> QHBoxLayout:
        column = QComboBox(self)
        column.setProperty("class", "field-control")
        column.addItems(self._column_labels)
        value_type = QComboBox(self)
        value_type.setProperty("class", "field-control")
        value_type.addItem("文本", "text")
        value_type.addItem("数字", "number")
        value_type.addItem("日期", "date")
        operator = QComboBox(self)
        operator.setProperty("class", "field-control")
        value = QLineEdit(self)
        value.setPlaceholderText("比较值")
        index = len(self._condition_rows)
        for widget in (column, value_type, operator, value):
            widget.setMinimumHeight(30)
        value_type.currentIndexChanged.connect(lambda _i, i=index: self._refresh_operators(i))
        self._condition_rows.append(
            {"column": column, "value_type": value_type, "operator": operator, "value": value}
        )
        row = QHBoxLayout()
        row.addWidget(column, 2)
        row.addWidget(value_type, 2)
        row.addWidget(operator, 2)
        row.addWidget(value, 3)
        return row

    def _refresh_operators(self, index: int) -> None:
        row = self._condition_rows[index]
        operator = row["operator"]
        value_type = row["value_type"]
        assert isinstance(operator, QComboBox) and isinstance(value_type, QComboBox)
        operator.blockSignals(True)
        operator.clear()
        current_type = value_type.currentData()
        items = [("等于", "equal"), ("不等于", "not_equal")]
        if current_type == "text":
            items += [("包含", "contains"), ("不包含", "not_contains")]
        else:
            items += [("大于", "greater_than"), ("小于", "less_than"), ("介于", "between")]
        items += [("为空", "blank"), ("不为空", "not_blank")]
        for label, data in items:
            operator.addItem(label, data)
        operator.blockSignals(False)
        value = row["value"]
        assert isinstance(value, QLineEdit)
        value.setVisible(operator.currentData() not in {"blank", "not_blank"})

    def _submit(self) -> None:
        conditions = [self._condition_payload(0)]
        if self._second.isChecked():
            conditions.append(self._condition_payload(1))
        connector = self._connector.currentData()
        if (
            len(conditions) == 2
            and connector == "or"
            and conditions[0]["column_index"] != conditions[1]["column_index"]
        ):
            connector = "and"
        self.params_submitted.emit(
            {
                "sheet_name": self._sheet_name,
                "conditions": conditions,
                "connector": connector,
            }
        )

    def _condition_payload(self, index: int) -> dict[str, object]:
        row = self._condition_rows[index]
        column = row["column"]
        operator = row["operator"]
        value_type = row["value_type"]
        value = row["value"]
        assert (
            isinstance(column, QComboBox)
            and isinstance(operator, QComboBox)
            and isinstance(value_type, QComboBox)
            and isinstance(value, QLineEdit)
        )
        return {
            "column_index": column.currentIndex(),
            "operator": operator.currentData(),
            "value_type": value_type.currentData(),
            "value": value.text() or None,
            "second_value": None,
        }


class _FindMatchModel(QAbstractTableModel):
    """查找替换对话框内嵌匹配列表：位置、修改前后与逐项替换状态。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._matches: tuple[tuple[str, int, int, str, str], ...] = ()
        self._replaced: set[int] = set()

    def set_matches(self, changes: tuple[tuple[str, int, int, str, str], ...]) -> None:
        self.beginResetModel()
        self._matches = changes
        self._replaced.clear()
        self.endResetModel()

    def match_at(self, row: int) -> tuple[str, int, int, str, str] | None:
        if 0 <= row < len(self._matches):
            return self._matches[row]
        return None

    def mark_replaced(self, row: int) -> None:
        if 0 <= row < len(self._matches) and row not in self._replaced:
            self._replaced.add(row)
            top_left = self.index(row, 3)
            self.dataChanged.emit(top_left, top_left, [Qt.ItemDataRole.DisplayRole])

    def next_unreplaced(self, after: int) -> int:
        total = len(self._matches)
        for offset in range(1, total + 1):
            candidate = (after + offset) % total
            if candidate not in self._replaced:
                return candidate
        return -1

    @property
    def replaced_count(self) -> int:
        return len(self._replaced)

    @property
    def total(self) -> int:
        return len(self._matches)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._matches)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else 4

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        sheet, row, column, before, after = self._matches[index.row()]
        if index.column() == 0:
            return f"{sheet}!R{row}C{column}"
        if index.column() == 1:
            return before
        if index.column() == 2:
            return after
        return "已替换" if index.row() in self._replaced else "待替换"

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object | None:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return ("位置", "当前内容", "替换为", "状态")[section]


class SortDialog(QDialog):
    """多列排序参数对话框（需求第 19.1 节：最多两个排序键，各自升序/降序）。"""

    params_submitted = Signal(dict)

    def __init__(self, sheet_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sort-dialog")
        self.setWindowTitle("多列排序")
        self.setModal(False)
        self.setMinimumWidth(380)
        self._sheet_name = sheet_name
        self._columns: tuple[str, ...] = ()

        form = QGridLayout(self)
        form.setContentsMargins(16, 16, 16, 12)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)

        key_label = QLabel("主要关键字", self)
        key_label.setProperty("class", "form-label")
        self._key1_column = QComboBox(self)
        self._key1_column.setProperty("class", "field-control")
        self._key1_direction = QComboBox(self)
        self._key1_direction.setProperty("class", "field-control")
        self._key1_direction.addItem("升序", "asc")
        self._key1_direction.addItem("降序", "desc")
        form.addWidget(key_label, 0, 0)
        form.addWidget(self._key1_column, 0, 1)
        form.addWidget(self._key1_direction, 0, 2)

        self._second = QCheckBox("使用次要关键字", self)
        secondary_label = QLabel("次要关键字", self)
        secondary_label.setProperty("class", "form-label")
        self._key2_column = QComboBox(self)
        self._key2_column.setProperty("class", "field-control")
        self._key2_direction = QComboBox(self)
        self._key2_direction.setProperty("class", "field-control")
        self._key2_direction.addItem("升序", "asc")
        self._key2_direction.addItem("降序", "desc")
        self._key2_column.setEnabled(False)
        self._key2_direction.setEnabled(False)
        self._second.toggled.connect(self._update_secondary_state)
        form.addWidget(self._second, 1, 0)
        form.addWidget(secondary_label, 2, 0)
        form.addWidget(self._key2_column, 2, 1)
        form.addWidget(self._key2_direction, 2, 2)

        hint = QLabel("排序始终移动完整数据行，表头不参与排序", self)
        hint.setProperty("class", "hint-label")
        form.addWidget(hint, 3, 0, 1, 3)

        self._status = QLabel("", self)
        self._status.setObjectName("sort-dialog-status")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        submit_button = QPushButton("生成排序预览", self)
        submit_button.setObjectName("sort-submit-button")
        submit_button.setProperty("class", "ribbon-button")
        submit_button.clicked.connect(self._submit)
        row = QHBoxLayout()
        row.addWidget(submit_button)
        row.addStretch()
        row.addWidget(buttons)
        form.addWidget(self._status, 4, 0, 1, 3)
        form.addLayout(row, 5, 0, 1, 3)

    def set_sheet(self, sheet_name: str) -> None:
        """每次打开时对齐用户当前正在查看的工作表。"""
        self._sheet_name = sheet_name

    def set_columns(self, columns: tuple[str, ...], initial_column: int = 0) -> None:
        """每次打开时刷新可选列并保持与当前选中列一致。"""
        self._columns = columns
        for combo in (self._key1_column, self._key2_column):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(list(columns))
            combo.blockSignals(False)
        if columns:
            clamped = max(0, min(initial_column, len(columns) - 1))
            self._key1_column.setCurrentIndex(clamped)
            if clamped + 1 < len(columns):
                self._key2_column.setCurrentIndex(clamped + 1)

    def _update_secondary_state(self, checked: bool) -> None:
        self._key2_column.setEnabled(checked)
        self._key2_direction.setEnabled(checked)

    def _submit(self) -> None:
        if not self._columns:
            self._status.setText("当前工作表没有可排序的列")
            return
        keys: list[dict[str, object]] = [
            {
                "column_index": self._key1_column.currentIndex(),
                "direction": self._key1_direction.currentData(),
            }
        ]
        if self._second.isChecked():
            if self._key2_column.currentIndex() == self._key1_column.currentIndex():
                self._status.setText("次要关键字不能与主要关键字相同")
                return
            keys.append(
                {
                    "column_index": self._key2_column.currentIndex(),
                    "direction": self._key2_direction.currentData(),
                }
            )
        self._status.setText("")
        self.params_submitted.emit(
            {"sheet_name": self._sheet_name, "sort_keys": keys, "multi_column": len(keys) > 1}
        )


class FindReplaceDialog(QDialog):
    params_submitted = Signal(str, object)
    replace_selected_requested = Signal(int)

    def __init__(self, sheet_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("find-replace-dialog")
        self.setWindowTitle("查找和替换")
        self.setModal(False)
        self.resize(480, 460)
        self._sheet_name = sheet_name

        form = QGridLayout(self)
        form.setContentsMargins(16, 16, 16, 12)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        find_label = QLabel("查找内容", self)
        find_label.setProperty("class", "form-label")
        self._find_text = QLineEdit(self)
        replace_label = QLabel("替换为", self)
        replace_label.setProperty("class", "form-label")
        self._replace_text = QLineEdit(self)
        scope_label = QLabel("范围", self)
        scope_label.setProperty("class", "form-label")
        self._scope = QComboBox(self)
        self._scope.setProperty("class", "field-control")
        self._scope.addItem("当前工作表", "sheet")
        self._scope.addItem("全部工作表", "all")
        mode_label = QLabel("查找范围", self)
        mode_label.setProperty("class", "form-label")
        self._mode = QComboBox(self)
        self._mode.setProperty("class", "field-control")
        self._mode.addItem("值", "values")
        self._mode.addItem("公式", "formulas")
        self._match_case = QCheckBox("区分大小写", self)
        self._whole_cell = QCheckBox("单元格匹配", self)
        self._ignore_trim = QCheckBox("忽略首尾空格", self)
        self._ignore_trim.setToolTip("比较时先清除查找内容和单元格文本的首尾空格")
        options = QHBoxLayout()
        options.addWidget(self._match_case)
        options.addWidget(self._whole_cell)
        options.addWidget(self._ignore_trim)
        form.addWidget(find_label, 0, 0)
        form.addWidget(self._find_text, 0, 1)
        form.addWidget(replace_label, 1, 0)
        form.addWidget(self._replace_text, 1, 1)
        form.addWidget(scope_label, 2, 0)
        form.addWidget(self._scope, 2, 1)
        form.addWidget(mode_label, 3, 0)
        form.addWidget(self._mode, 3, 1)
        form.addLayout(options, 4, 0, 1, 2)

        self._status = QLabel("", self)
        self._status.setObjectName("find-dialog-status")
        self._match_model = _FindMatchModel(self)
        self._matches_table = QTableView(self)
        self._matches_table.setObjectName("find-matches-table")
        self._matches_table.setAccessibleName("查找匹配列表")
        self._matches_table.setModel(self._match_model)
        self._matches_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._matches_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._matches_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._matches_table.horizontalHeader().setStretchLastSection(True)
        self._matches_table.verticalHeader().setVisible(False)
        self._matches_table.setMinimumHeight(120)
        selection_model = self._matches_table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(
                lambda _current, _previous: self._update_replace_state()
            )
        self._mode.currentIndexChanged.connect(lambda _index: self._update_replace_state())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        find_button = QPushButton("查找全部", self)
        find_button.setProperty("class", "ribbon-button")
        find_button.clicked.connect(lambda: self._submit(replace_all=False))
        self._replace_one = QPushButton("替换选中项", self)
        self._replace_one.setObjectName("find-replace-one-button")
        self._replace_one.setProperty("class", "ribbon-button")
        self._replace_one.setEnabled(False)
        self._replace_one.setToolTip("把选中匹配写入当前编辑会话，逐项决定是否替换")
        self._replace_one.clicked.connect(self._emit_replace_selected)
        replace_button = QPushButton("全部替换", self)
        replace_button.setObjectName("find-replace-all-button")
        replace_button.setProperty("class", "ribbon-button")
        replace_button.clicked.connect(lambda: self._submit(replace_all=True))
        row = QHBoxLayout()
        row.addWidget(find_button)
        row.addWidget(self._replace_one)
        row.addWidget(replace_button)
        row.addStretch()
        row.addWidget(buttons)
        form.addWidget(self._status, 5, 0, 1, 2)
        form.addWidget(self._matches_table, 6, 0, 1, 2)
        form.addLayout(row, 7, 0, 1, 2)

    def set_sheet(self, sheet_name: str) -> None:
        """每次打开时对齐用户当前正在查看的工作表。"""
        self._sheet_name = sheet_name

    def set_status(self, message: str, has_details: bool) -> None:
        self._status.setText(message)
        if not has_details:
            self._match_model.set_matches(())
        self._update_replace_state()

    def set_matches(self, changes: tuple[tuple[str, int, int, str, str], ...]) -> None:
        """需求第 19.4 节：只查找后列出匹配，供逐项替换选择。"""
        self._match_model.set_matches(changes)
        if changes:
            self._matches_table.resizeColumnsToContents()
            self._matches_table.selectRow(0)
            self._status.setText(f"找到 {len(changes)} 处匹配，可选中后逐项替换")
        self._update_replace_state()

    def mark_replaced(self, row: int) -> None:
        self._match_model.mark_replaced(row)
        replaced = self._match_model.replaced_count
        total = self._match_model.total
        self._status.setText(f"已替换 {replaced}/{total} 处，继续选择下一处或直接保存为新版本")
        following = self._match_model.next_unreplaced(row)
        if following >= 0:
            self._matches_table.selectRow(following)
        self._update_replace_state()

    def match_at(self, row: int) -> tuple[str, int, int, str, str] | None:
        return self._match_model.match_at(row)

    def _emit_replace_selected(self) -> None:
        selection_model = self._matches_table.selectionModel()
        row = selection_model.currentIndex().row() if selection_model is not None else -1
        if row >= 0:
            self.replace_selected_requested.emit(row)

    def _update_replace_state(self) -> None:
        selection_model = self._matches_table.selectionModel()
        selected = selection_model is not None and selection_model.currentIndex().row() >= 0
        values_mode = self._mode.currentData() == "values"
        has_row = (
            self._match_model.match_at(
                selection_model.currentIndex().row() if selection_model is not None else -1
            )
            is not None
        )
        self._replace_one.setEnabled(selected and has_row and values_mode)

    def _submit(self, *, replace_all: bool) -> None:
        if not self._find_text.text():
            self._status.setText("请输入查找内容")
            return
        self.params_submitted.emit(
            self._sheet_name,
            {
                "all_sheets": self._scope.currentData() == "all",
                "mode": self._mode.currentData(),
                "find_text": self._find_text.text(),
                "replace_text": self._replace_text.text(),
                "match_case": self._match_case.isChecked(),
                "whole_cell": self._whole_cell.isChecked(),
                "trim_whitespace": self._ignore_trim.isChecked(),
                "replace_all": replace_all,
            },
        )


class WorkbookEditorFrame(QFrame):
    sort_requested = Signal(int, str)
    multi_sort_requested = Signal()
    one_step_requested = Signal(str, list)
    filter_requested = Signal()
    find_replace_requested = Signal()
    apply_requested = Signal()
    preview_cancel_requested = Signal()
    details_requested = Signal()
    deduplicate_params_confirmed = Signal(dict)
    trim_params_confirmed = Signal(dict)
    params_dismissed = Signal()

    def __init__(self, preview: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("editor-frame")
        self.setMinimumWidth(480)
        self._preview = preview

        ribbon = QFrame(self)
        ribbon.setObjectName("editor-ribbon")
        ribbon.setFixedHeight(64)
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(8, 4, 8, 2)
        ribbon_layout.setSpacing(0)

        sort_group = _RibbonGroup("排序和筛选", ribbon)
        self._sort_asc = sort_group.add_button("升序 A→Z", "bar-sort-asc-button")
        self._sort_desc = sort_group.add_button("降序 Z→A", "bar-sort-desc-button")
        self._multi_sort = sort_group.add_button("多列排序…", "bar-sort-multi-button")
        self._filter = sort_group.add_button("筛选", "bar-filter-button")
        self._sort_asc.clicked.connect(lambda: self._emit_sort("asc"))
        self._sort_desc.clicked.connect(lambda: self._emit_sort("desc"))
        self._multi_sort.clicked.connect(self.multi_sort_requested)
        self._filter.clicked.connect(self.filter_requested)

        data_group = _RibbonGroup("数据工具", ribbon)
        self._deduplicate = data_group.add_button("删除重复行", "bar-deduplicate-button")
        self._blank_rows = data_group.add_button("删除空白行", "bar-blank-rows-button")
        self._trim = data_group.add_button("清除空格", "bar-trim-button")
        self._deduplicate.clicked.connect(
            lambda: self.one_step_requested.emit("deduplicate", self._selected_columns())
        )
        self._blank_rows.clicked.connect(
            lambda: self.one_step_requested.emit("delete_blank_rows", self._selected_columns())
        )
        self._trim.clicked.connect(
            lambda: self.one_step_requested.emit("trim", self._selected_columns())
        )

        find_group = _RibbonGroup("查找", ribbon)
        self._find = find_group.add_button("查找替换", "bar-find-replace-button")
        self._find.clicked.connect(self.find_replace_requested)

        for group in (sort_group, data_group, find_group):
            ribbon_layout.addWidget(group)
            separator = QFrame(ribbon)
            separator.setObjectName("ribbon-separator")
            separator.setFixedSize(1, 48)
            ribbon_layout.addWidget(separator)
        ribbon_layout.addStretch()

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

        self._banner = TemporaryResultBanner(self)
        self._params_bar = ProcessingParamsBar(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(ribbon)
        layout.addWidget(self._params_bar)
        layout.addWidget(formula)
        layout.addWidget(format_bar)
        layout.addWidget(self._banner)
        layout.addWidget(preview, 1)
        self._banner.apply_requested.connect(self.apply_requested)
        self._banner.cancel_requested.connect(self.preview_cancel_requested)
        self._banner.details_requested.connect(self.details_requested)
        self._params_bar.deduplicate_confirmed.connect(self.deduplicate_params_confirmed)
        self._params_bar.trim_confirmed.connect(self.trim_params_confirmed)
        self._params_bar.dismissed.connect(self.params_dismissed)

    def show_deduplicate_params(self, columns: list[int]) -> None:
        self._params_bar.show_deduplicate(columns)

    def show_trim_params(self, columns: list[int]) -> None:
        self._params_bar.show_trim(columns)

    def hide_params_bar(self) -> None:
        self._params_bar.hide_bar()

    def _emit_sort(self, direction: str) -> None:
        columns = self._selected_columns()
        self.sort_requested.emit(columns[0] if columns else 0, direction)

    def _selected_columns(self) -> list[int]:
        getter = getattr(self._preview, "selected_columns", None)
        return getter() if getter is not None else []

    def set_actions_enabled(self, enabled: bool) -> None:
        # 处理预览期间当前预览会被清空，功能区条必须随之禁用，
        # 避免入口在无当前工作表状态下误弹错误提示。
        for button in (
            self._sort_asc,
            self._sort_desc,
            self._multi_sort,
            self._filter,
            self._deduplicate,
            self._blank_rows,
            self._trim,
            self._find,
        ):
            button.setEnabled(enabled)

    def set_busy(self, message: str) -> None:
        self._banner.show_message(message, can_apply=False, can_details=False)

    def set_preview_ready(self, message: str, *, can_details: bool) -> None:
        self._banner.show_message(message, can_apply=True, can_details=can_details)

    def set_error(self, message: str) -> None:
        self._banner.show_message(message, can_apply=False, can_details=False)

    def clear_banner(self) -> None:
        self._banner.hide_banner()


def format_byte_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


class VersionStorageStatus(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("version-storage-status")
        self._format = QLabel("未选择文件", self)
        self._format.setObjectName("storage-format-pill")
        self._sizes = QLabel("", self)
        self._sizes.setObjectName("storage-size-text")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 10, 0)
        layout.setSpacing(8)
        layout.addWidget(self._format)
        layout.addWidget(self._sizes)

    def set_empty(self) -> None:
        self._format.setText("未选择文件")
        self._sizes.setText("")

    def set_stats(self, file_format: str, total_bytes: int, preview_bytes: int) -> None:
        self._format.setText(file_format)
        self._sizes.setText(
            f"版本总占用 {format_byte_size(total_bytes)}"
            f" · 当前预览 {format_byte_size(preview_bytes)}"
        )


@dataclass(frozen=True, slots=True)
class RecycleEntry:
    kind: str
    file_id: str
    file_display_name: str
    version_id: str | None = None
    version_name: str | None = None
    version_count: int = 0
    deleted_at: datetime | None = None

    @property
    def deleted_at_text(self) -> str:
        return (
            self.deleted_at.astimezone().strftime("%Y-%m-%d %H:%M")
            if self.deleted_at is not None
            else ""
        )

    @property
    def display_text(self) -> str:
        if self.kind == "file":
            return (
                f"文件 · {self.file_display_name} · {self.version_count} 个版本"
                f" · 删除于 {self.deleted_at_text}"
            )
        return (
            f"版本 · {self.file_display_name} / {self.version_name} · 删除于 {self.deleted_at_text}"
        )


class RecycleBinDialog(QDialog):
    restore_file_requested = Signal(str)
    restore_version_requested = Signal(str, str)
    purge_file_requested = Signal(str)

    def __init__(
        self,
        entries: tuple[RecycleEntry, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recycle-bin-dialog")
        self.setWindowTitle("回收站")
        self.resize(560, 400)
        self.setModal(False)

        self._entry_list = QListWidget(self)
        self._entry_list.setObjectName("recycle-file-list")
        self._entry_list.setAccessibleName("回收站条目列表")
        self._entry_list.currentItemChanged.connect(self._update_actions)

        self._restore = _tool_button("恢复选中项", "recycle-restore-button", self)
        self._restore.setAccessibleName("恢复选中的已删除文件或版本")
        self._restore.clicked.connect(self._emit_restore)
        self._purge = _tool_button("永久删除", "recycle-purge-button", self)
        self._purge.setAccessibleName("永久删除选中的文件")
        self._purge.clicked.connect(self._emit_purge)
        self._hint = QLabel(
            "文件恢复后回到删除前的位置；版本恢复后回到原版本树；永久删除无法撤销", self
        )
        self._hint.setProperty("class", "form-label")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(9)
        layout.addWidget(self._entry_list, 1)
        layout.addWidget(self._hint)
        actions_row = QHBoxLayout()
        actions_row.addWidget(self._restore)
        actions_row.addWidget(self._purge)
        actions_row.addStretch()
        actions_row.addWidget(buttons)
        layout.addLayout(actions_row)
        self.refresh(entries)

    def refresh(self, entries: tuple[RecycleEntry, ...]) -> None:
        self._entry_list.clear()
        for entry in entries:
            item = QListWidgetItem(entry.display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setSizeHint(QSize(0, 34))
            self._entry_list.addItem(item)
        self._update_actions()

    def selected_entry(self) -> RecycleEntry | None:
        item = self._entry_list.currentItem()
        data = None if item is None else item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, RecycleEntry) else None

    def mark_busy(self, busy: bool) -> None:
        self._restore.setEnabled(not busy)
        self._purge.setEnabled(not busy)
        self._entry_list.setEnabled(not busy)

    def _emit_restore(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            return
        if entry.kind == "file":
            self.restore_file_requested.emit(entry.file_id)
        elif entry.version_id is not None:
            self.restore_version_requested.emit(entry.file_id, entry.version_id)

    def _emit_purge(self) -> None:
        entry = self.selected_entry()
        if entry is not None and entry.kind == "file":
            self.purge_file_requested.emit(entry.file_id)

    def _update_actions(
        self,
        _current: QListWidgetItem | None = None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        entry = self.selected_entry()
        self._restore.setEnabled(entry is not None)
        self._purge.setEnabled(entry is not None and entry.kind == "file")
