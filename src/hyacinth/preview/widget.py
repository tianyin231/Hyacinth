from PySide6.QtCore import (
    QAbstractItemModel,
    QItemSelection,
    QItemSelectionModel,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QCursor,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hyacinth.grid.model import WorkbookTableModel
from hyacinth.preview.data_source import EditableGridDataSource, SqliteGridDataSource
from hyacinth.preview.edit_session import CellEdit, EditSession
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
    """只读预览表格，不执行 Qt 默认的百万行键盘搜索，全选只选数据区域。"""

    def keyboardSearch(self, search: str) -> None:
        return

    def selectAll(self) -> None:
        model = self.model()
        data_rows = getattr(model, "data_row_count", None)
        data_columns = getattr(model, "data_column_count", None)
        if model is None or data_rows is None or data_columns is None:
            super().selectAll()
            return
        selection_model = self.selectionModel()
        if selection_model is None:
            return
        selection_model.clear()
        top_left = model.index(0, 0)
        bottom_right = model.index(
            min(int(data_rows), model.rowCount()) - 1,
            min(int(data_columns), model.columnCount()) - 1,
        )
        selection = QItemSelection(top_left, bottom_right)
        selection_model.select(
            selection,
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Current,
        )


class WorkbookPreviewWidget(QFrame):
    import_requested = Signal()
    edit_state_changed = Signal(bool, bool, bool)
    header_sort_requested = Signal(int, str)
    header_multi_sort_requested = Signal(int)
    header_filter_requested = Signal(int)
    processing_menu_requested = Signal(str, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workbook-preview")
        self.setMinimumWidth(320)
        self._preview: WorkbookPreview | None = None
        self._source: SqliteGridDataSource | None = None
        self._editable = False
        self._edit_session = EditSession(self)
        self._edit_session.state_changed.connect(self.edit_state_changed)
        self._edit_session.cell_changed.connect(self._refresh_edited_cell)
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
        header = self._table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._show_header_menu)
        header.setDefaultSectionSize(96)
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

    def _show_header_menu(self, column: int) -> None:
        menu = QMenu(self._table)
        sort_asc = menu.addAction("升序")
        sort_desc = menu.addAction("降序")
        multi_sort = menu.addAction("多列排序…")
        menu.addSeparator()
        filter_action = menu.addAction("按此列筛选…")
        chosen = menu.exec(QCursor.pos())
        if chosen is sort_asc:
            self.header_sort_requested.emit(column, "asc")
        elif chosen is sort_desc:
            self.header_sort_requested.emit(column, "desc")
        elif chosen is multi_sort:
            self.header_multi_sort_requested.emit(column)
        elif chosen is filter_action:
            self.header_filter_requested.emit(column)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if self._table.model() is None or self._table.model().rowCount() == 0:
            super().contextMenuEvent(event)
            return
        columns = sorted(
            {
                index.column()
                for index in self._table.selectionModel().selectedIndexes()
                if index.isValid()
            }
        )
        menu = QMenu(self)
        deduplicate = menu.addAction("删除重复行…")
        blank_rows = menu.addAction("删除空白行…")
        trim = menu.addAction("清除首尾空格…")
        find_replace = menu.addAction("查找替换…")
        menu.addSeparator()
        add_rows = menu.addAction("向下添加 20 行")
        add_columns = menu.addAction("向右添加 4 列")
        chosen = menu.exec(event.globalPos())
        actions = {
            deduplicate: "deduplicate",
            blank_rows: "delete_blank_rows",
            trim: "trim",
            find_replace: "find_replace",
        }
        if chosen in actions:
            self.processing_menu_requested.emit(actions[chosen], columns)
        elif chosen is add_rows or chosen is add_columns:
            model = self._table.model()
            if model is not None and hasattr(model, "extend_grid"):
                model.extend_grid(
                    20 if chosen is add_rows else 0, 4 if chosen is add_columns else 0
                )

    def selected_columns(self) -> list[int]:
        if self._table.model() is None:
            return []
        return sorted(
            {
                index.column()
                for index in self._table.selectionModel().selectedIndexes()
                if index.isValid()
            }
        )

    def current_preview(self) -> WorkbookPreview | None:
        return self._preview

    @property
    def current_sheet_name(self) -> str | None:
        """当前显示的工作表名；查找、筛选、排序等入口必须以此为准。"""
        preview = self._preview
        if preview is None or not preview.sheets:
            return None
        index = self._tabs.currentIndex()
        if 0 <= index < len(preview.sheets):
            return preview.sheets[index].title
        return preview.sheets[0].title

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

    def show_preview(self, preview: WorkbookPreview, *, editable: bool = False) -> None:
        # 重建标签前记住用户正在查看的工作表，重载后保持在同一张表。
        # 注意：加载中 _preview 已被清空，必须从标签栏自身取名字，不能依赖 current_sheet_name。
        previous_sheet = (
            self._tabs.tabText(self._tabs.currentIndex()) if self._tabs.count() else None
        )
        self._close_source()
        self._preview = preview
        self._set_editable(editable)
        self._tabs.blockSignals(True)
        while self._tabs.count():
            self._tabs.removeTab(0)
        for sheet in preview.sheets:
            self._tabs.addTab(sheet.title)
        restore_index = 0
        if previous_sheet is not None:
            for index, sheet in enumerate(preview.sheets):
                if sheet.title == previous_sheet:
                    restore_index = index
                    break
        self._tabs.blockSignals(False)
        self._stack.setCurrentIndex(1)
        self._tabs.setCurrentIndex(restore_index)
        self._show_sheet(restore_index)

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
        sheet = preview.sheets[index]
        self._source = SqliteGridDataSource(preview.index_path, sheet)
        if self._editable:
            source = EditableGridDataSource(self._source, self._edit_session, sheet.title)
            model = WorkbookTableModel(
                source,
                self._table,
                editable=True,
                edit_value_at=source.edit_value_at,
            )
        else:
            model = WorkbookTableModel(self._source, self._table, editable=False)
        self._table.setModel(model)

    def pending_edits(self) -> tuple[CellEdit, ...]:
        return self._edit_session.edits()

    @property
    def is_editable(self) -> bool:
        return self._editable

    def apply_cell_edit(
        self,
        sheet_name: str,
        row: int,
        column: int,
        *,
        base_value: object,
        new_value: object,
    ) -> None:
        """以源行坐标写入一次程序化单元格编辑（查找替换逐项替换）。

        坐标为 0 起始的物理行/列，与编辑会话键一致；跨工作表也无需
        切换当前显示页，cell_changed 会按需刷新可见单元格。
        """
        current = self._edit_session.value_at(sheet_name, row, column, base_value)
        self._edit_session.set_value(
            sheet_name,
            row,
            column,
            base_value=base_value,
            current_value=current,
            new_value=new_value,
        )

    def undo(self) -> None:
        self._edit_session.undo()

    def redo(self) -> None:
        self._edit_session.redo()

    def clear_edits(self) -> None:
        self._edit_session.clear()

    def _set_editable(self, editable: bool) -> None:
        self._editable = editable
        triggers = (
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
            if editable
            else QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setEditTriggers(triggers)
        description = (
            "双击或按 F2 编辑单元格，修改需保存为新版本" if editable else "当前版本为只读预览"
        )
        self._table.setAccessibleDescription(description)
        self._table.setToolTip(description)

    def _refresh_edited_cell(self, sheet_name: str, row: int, column: int) -> None:
        if self._tabs.tabText(self._tabs.currentIndex()) != sheet_name:
            return
        source = self._source
        if source is None:
            return
        visible_row = source.visible_row_index(row)
        if visible_row is None:
            return
        model = self._table.model()
        if isinstance(model, WorkbookTableModel):
            index = model.index(visible_row, column)
            model.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )

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
