from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)

from hyacinth.grid.data_source import GridDataSource


def excel_column_name(column: int) -> str:
    name = ""
    value = column + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


class WorkbookTableModel(QAbstractTableModel):
    def __init__(
        self,
        source: GridDataSource,
        parent: QObject | None = None,
        *,
        editable: bool = True,
        edit_value_at: Callable[[int, int], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._editable = editable
        self._edit_value_at = edit_value_at
        self.data_row_count = getattr(source, "data_row_count", source.row_count)
        self.data_column_count = getattr(source, "data_column_count", source.column_count)

    def extend_grid(self, extra_rows: int, extra_columns: int) -> None:
        extend = getattr(self._source, "extend", None)
        if extend is not None:
            extend(extra_rows, extra_columns)
        self.data_row_count = getattr(self._source, "data_row_count", self._source.row_count)
        self.data_column_count = getattr(
            self._source, "data_column_count", self._source.column_count
        )
        self.layoutChanged.emit()

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return self._source.row_count

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0
        return self._source.column_count

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.EditRole and self._edit_value_at is not None:
            return self._edit_value_at(index.row(), index.column())
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._source.value_at(index.row(), index.column())
        return None

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not self._editable or not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        self._source.set_value(index.row(), index.column(), value)
        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )
        return True

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self._editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is Qt.Orientation.Horizontal:
            return excel_column_name(section)
        return str(section + 1)
