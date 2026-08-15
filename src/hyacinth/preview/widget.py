from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QStackedWidget,
    QTabBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hyacinth.grid.model import WorkbookTableModel
from hyacinth.preview.data_source import SqliteGridDataSource
from hyacinth.preview.index_task import WorkbookPreview


class WorkbookPreviewWidget(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workbook-preview")
        self.setMinimumWidth(320)
        self._preview: WorkbookPreview | None = None
        self._source: SqliteGridDataSource | None = None

        self._state = QLabel("选择一个文件查看工作表", self)
        self._state.setObjectName("preview-state")
        self._state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state.setWordWrap(True)

        self._table = QTableView(self)
        self._table.setObjectName("preview-table")
        self._table.setAccessibleName("Excel 工作表预览")
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
        self._stack.addWidget(self._state)
        self._stack.addWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self.setStyleSheet(
            """
            QFrame#workbook-preview { background: #ffffff; }
            QLabel#preview-state {
                color: #5d6673;
                background: #ffffff;
                padding: 24px;
                font-size: 13px;
            }
            QTableView#preview-table {
                color: #20242b;
                background: #ffffff;
                alternate-background-color: #f8fafc;
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
            QTabBar#preview-sheet-tabs {
                background: #f4f6f8;
                border-top: 1px solid #dfe3e8;
            }
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
            """
        )

    def set_loading(self, display_name: str) -> None:
        self._close_source()
        self._preview = None
        self._state.setText(f"正在加载 {display_name}…")
        self._stack.setCurrentIndex(0)

    def set_error(self, message: str) -> None:
        self._close_source()
        self._preview = None
        self._state.setText(f"无法加载预览\n{message}")
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
        if previous_model is not None:
            previous_model.deleteLater()
        if self._source is not None:
            self._source.close()
            self._source = None

    def closeEvent(self, event: QCloseEvent) -> None:
        self._close_source()
        super().closeEvent(event)
