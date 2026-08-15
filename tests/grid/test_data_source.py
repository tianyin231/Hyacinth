import pytest


def test_sparse_grid_source_stores_only_edited_cells() -> None:
    try:
        from hyacinth.grid.data_source import SparseGridDataSource
    except ImportError:
        pytest.fail("hyacinth.grid.data_source.SparseGridDataSource is not implemented")

    source = SparseGridDataSource(
        row_count=100_000,
        column_count=50,
        base_value_at=lambda row, column: f"R{row + 1}C{column + 1}",
    )

    assert source.value_at(9, 3) == "R10C4"
    assert source.edit_count == 0

    source.set_value(9, 3, "edited")

    assert source.value_at(9, 3) == "edited"
    assert source.value_at(9, 4) == "R10C5"
    assert source.edit_count == 1


def test_sparse_grid_source_does_not_read_base_for_edited_cell() -> None:
    from hyacinth.grid.data_source import SparseGridDataSource

    base_reads = 0

    def base_value_at(row: int, column: int) -> str:
        nonlocal base_reads
        base_reads += 1
        return f"R{row + 1}C{column + 1}"

    source = SparseGridDataSource(
        row_count=100_000,
        column_count=50,
        base_value_at=base_value_at,
    )
    source.set_value(9, 3, "edited")

    assert source.value_at(9, 3) == "edited"
    assert base_reads == 0
