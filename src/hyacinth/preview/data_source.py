import sqlite3
from collections import OrderedDict
from pathlib import Path

from hyacinth.preview.edit_session import EditSession
from hyacinth.preview.index_task import SheetPreview

# 网格只显示数据区域加少量编辑余量；需要更多行列时用户可通过
# 右键菜单自主扩展，避免百万行逻辑网格在全选等操作中卡死界面。
EDIT_MARGIN_ROWS = 32
EDIT_MARGIN_COLUMNS = 4


class SqliteGridDataSource:
    def __init__(
        self,
        index_path: Path,
        sheet: SheetPreview,
        *,
        row_cache_size: int = 128,
    ) -> None:
        self.data_row_count = sheet.row_count
        self.data_column_count = sheet.column_count
        self.row_count = sheet.row_count + EDIT_MARGIN_ROWS
        self.column_count = sheet.column_count + EDIT_MARGIN_COLUMNS
        self._sheet_index = sheet.index
        self._physical_row_count = sheet.row_count
        self._visible_row_count = sheet.visible_row_count
        self._row_cache_size = row_cache_size
        self._rows: OrderedDict[int, dict[int, tuple[str, str | None]]] = OrderedDict()
        self._connection = sqlite3.connect(
            f"{index_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )

    def value_at(self, row: int, column: int) -> object:
        values = self._rows.get(row)
        if values is None:
            source_row = self._source_row(row)
            if source_row is None:
                return ""
            values = {
                cell_column: (display_value, formula)
                for cell_column, display_value, formula in self._connection.execute(
                    "SELECT column_index, display_value, formula FROM cells "
                    "WHERE sheet_index = ? AND row_index = ?",
                    (self._sheet_index, source_row),
                )
            }
            self._rows[row] = values
            if len(self._rows) > self._row_cache_size:
                self._rows.popitem(last=False)
        else:
            self._rows.move_to_end(row)
        cell = values.get(column)
        return cell[0] if cell is not None else ""

    def edit_value_at(self, row: int, column: int) -> object:
        self.value_at(row, column)
        cell = self._rows.get(row, {}).get(column)
        if cell is None:
            return ""
        display_value, formula = cell
        return formula or display_value

    def _source_row(self, visible_row: int) -> int | None:
        if self._visible_row_count is None:
            return visible_row
        if visible_row >= self._visible_row_count:
            return None
        row = self._connection.execute(
            "SELECT source_row_index FROM visible_rows "
            "WHERE sheet_index = ? AND visible_row_index = ?",
            (self._sheet_index, visible_row),
        ).fetchone()
        return int(row[0]) if row is not None else None

    def source_row_index(self, visible_row: int) -> int:
        source_row = self._source_row(visible_row)
        if source_row is not None:
            return source_row
        if self._visible_row_count is None:
            return visible_row
        return self._physical_row_count + max(0, visible_row - self._visible_row_count)

    def visible_row_index(self, source_row: int) -> int | None:
        if self._visible_row_count is None:
            return source_row
        row = self._connection.execute(
            "SELECT visible_row_index FROM visible_rows "
            "WHERE sheet_index = ? AND source_row_index = ?",
            (self._sheet_index, source_row),
        ).fetchone()
        if row is not None:
            return int(row[0])
        if source_row >= self._physical_row_count:
            return self._visible_row_count + source_row - self._physical_row_count
        return None

    def set_value(self, row: int, column: int, value: object) -> None:
        raise RuntimeError("工作簿预览为只读")

    def extend(self, extra_rows: int, extra_columns: int) -> None:
        self.row_count += max(0, extra_rows)
        self.column_count += max(0, extra_columns)

    def close(self) -> None:
        self._connection.close()
        self._rows.clear()


class EditableGridDataSource:
    def __init__(
        self,
        source: SqliteGridDataSource,
        session: EditSession,
        sheet_name: str,
    ) -> None:
        self.row_count = source.row_count
        self.column_count = source.column_count
        self.data_row_count = source.data_row_count
        self.data_column_count = source.data_column_count
        self._source = source
        self._session = session
        self._sheet_name = sheet_name

    def value_at(self, row: int, column: int) -> object:
        source_row = self._source.source_row_index(row)
        return self._session.value_at(
            self._sheet_name,
            source_row,
            column,
            self._source.value_at(row, column),
        )

    def edit_value_at(self, row: int, column: int) -> object:
        source_row = self._source.source_row_index(row)
        return self._session.value_at(
            self._sheet_name,
            source_row,
            column,
            self._source.edit_value_at(row, column),
        )

    def extend(self, extra_rows: int, extra_columns: int) -> None:
        self._source.extend(extra_rows, extra_columns)
        self.row_count = self._source.row_count
        self.column_count = self._source.column_count

    def set_value(self, row: int, column: int, value: object) -> None:
        source_row = self._source.source_row_index(row)
        self._session.set_value(
            self._sheet_name,
            source_row,
            column,
            base_value=self._source.edit_value_at(row, column),
            current_value=self.edit_value_at(row, column),
            new_value=value,
        )
