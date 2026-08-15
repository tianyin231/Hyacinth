import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy


class FakeGridSource:
    row_count = 100_000
    column_count = 50

    def __init__(self) -> None:
        self.edits: dict[tuple[int, int], object] = {}

    def value_at(self, row: int, column: int) -> object:
        return self.edits.get((row, column), f"R{row + 1}C{column + 1}")

    def set_value(self, row: int, column: int, value: object) -> None:
        self.edits[(row, column)] = value


@pytest.mark.parametrize(
    ("column", "expected"),
    [(0, "A"), (25, "Z"), (26, "AA"), (255, "IV"), (16_383, "XFD")],
)
def test_excel_column_name(column: int, expected: str) -> None:
    try:
        from hyacinth.grid.model import excel_column_name
    except ModuleNotFoundError:
        pytest.fail("hyacinth.grid.model.excel_column_name is not implemented")

    assert excel_column_name(column) == expected


def test_model_exposes_shape_headers_and_values() -> None:
    try:
        from hyacinth.grid.model import WorkbookTableModel
    except ImportError:
        pytest.fail("hyacinth.grid.model.WorkbookTableModel is not implemented")

    model = WorkbookTableModel(FakeGridSource())
    index = model.index(4, 2)

    assert model.rowCount() == 100_000
    assert model.columnCount() == 50
    assert model.headerData(0, Qt.Orientation.Horizontal) == "A"
    assert model.headerData(49, Qt.Orientation.Horizontal) == "AX"
    assert model.headerData(4, Qt.Orientation.Vertical) == "5"
    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "R5C3"
    assert model.data(index, Qt.ItemDataRole.EditRole) == "R5C3"


def test_model_edits_source_and_emits_change() -> None:
    try:
        from hyacinth.grid.model import WorkbookTableModel
    except ImportError:
        pytest.fail("hyacinth.grid.model.WorkbookTableModel is not implemented")

    source = FakeGridSource()
    model = WorkbookTableModel(source)
    index = model.index(9, 3)
    changed = QSignalSpy(model.dataChanged)

    assert model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(index, "edited", Qt.ItemDataRole.EditRole) is True
    assert source.edits == {(9, 3): "edited"}
    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "edited"
    assert changed.count() == 1


def test_model_can_be_read_only() -> None:
    from hyacinth.grid.model import WorkbookTableModel

    source = FakeGridSource()
    model = WorkbookTableModel(source, editable=False)
    index = model.index(0, 0)

    assert not model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(index, "blocked", Qt.ItemDataRole.EditRole) is False
    assert source.edits == {}
