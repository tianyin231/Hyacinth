from PySide6.QtCore import QAbstractItemModel, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hyacinth.grid.model import WorkbookTableModel
from hyacinth.preview.data_source import SqliteGridDataSource
from hyacinth.preview.index_task import WorkbookPreview
from hyacinth.ui.icons import fluent_icon


class EmptyWorkbookCanvas(QFrame):
    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#fbfcfe"))
        painter.setPen(QPen(QColor("#edf0f4"), 1))
        for x in range(0, self.width(), 72):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 28):
            painter.drawLine(0, y, self.width(), y)
        painter.fillRect(0, 0, self.width(), 28, QColor("#f3f6f9"))
        painter.end()


class ReadOnlyWorkbookTableView(QTableView):
    """只读预览表格，不执行 Qt 默认的百万行键盘搜索。"""

    def keyboardSearch(self, search: str) -> None:
        return


class WorkbookPreviewWidget(QFrame):
    import_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workbook-preview")
        self.setMinimumWidth(320)
        self._preview: WorkbookPreview | None = None
        self._source: SqliteGridDataSource | None = None
        self._retired_sources: dict[
            int,
            tuple[QAbstractItemModel, SqliteGridDataSource],
        ] = {}

        empty_canvas = EmptyWorkbookCanvas(self)
        empty_canvas.setObjectName("preview-empty-canvas")
        state_card = QFrame(empty_canvas)
        state_card.setObjectName("preview-empty-card")
        state_layout = QVBoxLayout(state_card)
        state_layout.setContentsMargins(30, 26, 30, 26)
        state_layout.setSpacing(8)
        state_icon = QLabel(state_card)
        state_icon.setObjectName("preview-empty-icon")
        state_icon.setPixmap(fluent_icon("sheet", color="#0f6cbd", size=28).pixmap(28, 28))
        state_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_icon.setFixedSize(54, 54)
        self._state = QLabel("从 Excel 文件开始", state_card)
        self._state.setObjectName("preview-state")
        self._state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state.setWordWrap(True)
        self._state_detail = QLabel(
            "导入 XLSX 或 XLS，预览工作表并建立可追溯的根版本",
            state_card,
        )
        self._state_detail.setObjectName("preview-state-detail")
        self._state_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_detail.setWordWrap(True)
        self._import_button = QPushButton("导入 Excel 文件", state_card)
        self._import_button.setObjectName("preview-import-button")
        self._import_button.setAccessibleName("从空状态导入 Excel 文件")
        self._import_button.setIcon(fluent_icon("plus", color="#ffffff"))
        self._import_button.clicked.connect(self.import_requested)
        state_layout.addWidget(state_icon, 0, Qt.AlignmentFlag.AlignCenter)
        state_layout.addWidget(self._state)
        state_layout.addWidget(self._state_detail)
        state_layout.addSpacing(4)
        state_layout.addWidget(self._import_button, 0, Qt.AlignmentFlag.AlignCenter)

        empty_layout = QVBoxLayout(empty_canvas)
        empty_layout.setContentsMargins(32, 32, 32, 32)
        empty_layout.addStretch()
        empty_layout.addWidget(state_card, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()

        self._table = ReadOnlyWorkbookTableView(self)
        self._table.setObjectName("preview-table")
        self._table.setAccessibleName("Excel 工作表预览")
        self._table.setAccessibleDescription("当前为只读预览，单元格编辑功能尚未开放")
        self._table.setToolTip("当前为只读预览，单元格编辑功能尚未开放")
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table.horizontalHeader().setDefaultSectionSize(96)
        self._table.horizontalHeader().setMinimumSectionSize(48)
        self._table.verticalHeader().setDefaultSectionSize(24)

        self._tabs = QTabBar(self)
        self._tabs.setObjectName("preview-sheet-tabs")
        self._tabs.setAccessibleName("工作表标签")
        self._tabs.setDocumentMode(True)
        self._tabs.setExpanding(False)
        self._tabs.setUsesScrollButtons(True)
        self._tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._tabs.setMinimumHeight(34)
        self._tabs.currentChanged.connect(self._show_sheet)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._table, 1)
        content_layout.addWidget(self._tabs)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(empty_canvas)
        self._stack.addWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def set_loading(self, display_name: str) -> None:
        self._close_source()
        self._preview = None
        self._state.setText(f"正在加载 {display_name}…")
        self._state_detail.setText("正在建立高效预览索引，请稍候")
        self._import_button.setVisible(False)
        self._stack.setCurrentIndex(0)

    def set_error(self, message: str) -> None:
        self._close_source()
        self._preview = None
        self._state.setText(f"无法加载预览\n{message}")
        self._state_detail.setText("可以重新选择文件，原文件不会被修改")
        self._import_button.setText("选择其他文件")
        self._import_button.setVisible(True)
        self._stack.setCurrentIndex(0)

    def show_preview(self, preview: WorkbookPreview) -> None:
        self._close_source()
        self._preview = preview
        self._tabs.blockSignals(True)
        while self._tabs.count():
            self._tabs.removeTab(0)
        for sheet in preview.sheets:
            self._tabs.addTab(sheet.title)
        self._tabs.blockSignals(False)
        self._stack.setCurrentIndex(1)
        self._tabs.setCurrentIndex(0)
        self._show_sheet(0)

    def clear_preview(self, message: str = "选择一个文件查看工作表") -> None:
        self._close_source()
        self._preview = None
        if message == "选择一个文件查看工作表":
            self._state.setText("从 Excel 文件开始")
            self._state_detail.setText("导入 XLSX 或 XLS，预览工作表并建立可追溯的根版本")
            self._import_button.setText("导入 Excel 文件")
            self._import_button.setVisible(True)
        else:
            self._state.setText(message)
            self._state_detail.setText("请稍候")
            self._import_button.setVisible(False)
        self._stack.setCurrentIndex(0)

    def _show_sheet(self, index: int) -> None:
        preview = self._preview
        if preview is None or index < 0 or index >= len(preview.sheets):
            return
        self._close_source()
        self._source = SqliteGridDataSource(preview.index_path, preview.sheets[index])
        model = WorkbookTableModel(self._source, self._table, editable=False)
        self._table.setModel(model)

    def _close_source(self) -> None:
        previous_model = self._table.model()
        self._table.setModel(None)
        previous_source = self._source
        self._source = None
        if previous_model is None or previous_source is None:
            if previous_source is not None:
                previous_source.close()
            return
        key = id(previous_model)
        self._retired_sources[key] = (previous_model, previous_source)
        previous_model.destroyed.connect(
            lambda _object=None, source_key=key: self._dispose_retired_source(source_key)
        )
        previous_model.deleteLater()

    def _dispose_retired_source(self, key: int) -> None:
        retired = self._retired_sources.pop(key, None)
        if retired is not None:
            _model, source = retired
            source.close()

    def _dispose_all_retired_sources(self) -> None:
        for _model, source in self._retired_sources.values():
            source.close()
        self._retired_sources.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._close_source()
        self._dispose_all_retired_sources()
        super().closeEvent(event)
