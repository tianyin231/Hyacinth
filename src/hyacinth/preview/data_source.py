import sqlite3
from collections import OrderedDict
from pathlib import Path

from hyacinth.preview.index_task import SheetPreview

LOGICAL_PREVIEW_ROWS = 1_048_576
LOGICAL_PREVIEW_COLUMNS = 256


class SqliteGridDataSource:
    def __init__(
        self,
        index_path: Path,
        sheet: SheetPreview,
        *,
        row_cache_size: int = 128,
    ) -> None:
        self.row_count = max(sheet.row_count, LOGICAL_PREVIEW_ROWS)
        self.column_count = max(sheet.column_count, LOGICAL_PREVIEW_COLUMNS)
        self._sheet_index = sheet.index
        self._visible_row_count = sheet.visible_row_count
        self._row_cache_size = row_cache_size
        self._rows: OrderedDict[int, dict[int, str]] = OrderedDict()
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
                cell_column: value
                for cell_column, value in self._connection.execute(
                    "SELECT column_index, display_value FROM cells "
                    "WHERE sheet_index = ? AND row_index = ?",
                    (self._sheet_index, source_row),
                )
            }
            self._rows[row] = values
            if len(self._rows) > self._row_cache_size:
                self._rows.popitem(last=False)
        else:
            self._rows.move_to_end(row)
        return values.get(column, "")

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

    def set_value(self, row: int, column: int, value: object) -> None:
        raise RuntimeError("工作簿预览为只读")

    def close(self) -> None:
        self._connection.close()
        self._rows.clear()
