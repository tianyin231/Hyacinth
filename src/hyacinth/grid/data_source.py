from collections.abc import Callable
from typing import Protocol


class GridDataSource(Protocol):
    row_count: int
    column_count: int

    def value_at(self, row: int, column: int) -> object: ...

    def set_value(self, row: int, column: int, value: object) -> None: ...


class SparseGridDataSource:
    def __init__(
        self,
        *,
        row_count: int,
        column_count: int,
        base_value_at: Callable[[int, int], object],
    ) -> None:
        self.row_count = row_count
        self.column_count = column_count
        self._base_value_at = base_value_at
        self._edits: dict[tuple[int, int], object] = {}

    @property
    def edit_count(self) -> int:
        return len(self._edits)

    def value_at(self, row: int, column: int) -> object:
        key = (row, column)
        if key in self._edits:
            return self._edits[key]
        return self._base_value_at(row, column)

    def set_value(self, row: int, column: int, value: object) -> None:
        self._edits[(row, column)] = value
