import sqlite3
from collections import OrderedDict
from pathlib import Path

from hyacinth.preview.index_task import SheetPreview


class SqliteGridDataSource:
    def __init__(
        self,
        index_path: Path,
        sheet: SheetPreview,
        *,
        row_cache_size: int = 128,
    ) -> None:
        self.row_count = sheet.row_count
        self.column_count = sheet.column_count
        self._sheet_index = sheet.index
        self._row_cache_size = row_cache_size
        self._rows: OrderedDict[int, dict[int, str]] = OrderedDict()
        self._connection = sqlite3.connect(
            f"{index_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )

    def value_at(self, row: int, column: int) -> object:
        values = self._rows.get(row)
        if values is None:
            values = {
                cell_column: value
                for cell_column, value in self._connection.execute(
                    "SELECT column_index, display_value FROM cells "
                    "WHERE sheet_index = ? AND row_index = ?",
                    (self._sheet_index, row),
                )
            }
            self._rows[row] = values
            if len(self._rows) > self._row_cache_size:
                self._rows.popitem(last=False)
        else:
            self._rows.move_to_end(row)
        return values.get(column, "")

    def set_value(self, row: int, column: int, value: object) -> None:
        raise RuntimeError("工作簿预览为只读")

    def close(self) -> None:
        self._connection.close()
        self._rows.clear()
