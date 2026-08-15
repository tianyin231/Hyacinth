import time
import tracemalloc

import pytest
from PySide6.QtWidgets import QApplication, QTableView
from pytestqt.qtbot import QtBot

from hyacinth.grid.data_source import SparseGridDataSource
from hyacinth.grid.model import WorkbookTableModel

ROWS = 1_048_576
COLUMNS = 256


@pytest.mark.performance
def test_extreme_grid_model_creation_is_constant_cost() -> None:
    base_reads = 0

    def base_value_at(row: int, column: int) -> str:
        nonlocal base_reads
        base_reads += 1
        return f"R{row + 1}C{column + 1}"

    tracemalloc.start()
    started = time.perf_counter()
    source = SparseGridDataSource(
        row_count=ROWS,
        column_count=COLUMNS,
        base_value_at=base_value_at,
    )
    model = WorkbookTableModel(source)
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"model_create_seconds={elapsed:.6f} python_peak_bytes={peak_bytes}")
    assert model.rowCount() == ROWS
    assert model.columnCount() == COLUMNS
    assert base_reads == 0
    assert elapsed < 0.1
    assert peak_bytes < 20 * 1024 * 1024


@pytest.mark.performance
def test_extreme_grid_view_requests_only_visible_cells(
    qtbot: QtBot,
    qapp: QApplication,
) -> None:
    base_reads = 0

    def base_value_at(row: int, column: int) -> str:
        nonlocal base_reads
        base_reads += 1
        return f"R{row + 1}C{column + 1}"

    source = SparseGridDataSource(
        row_count=ROWS,
        column_count=COLUMNS,
        base_value_at=base_value_at,
    )
    model = WorkbookTableModel(source)
    view = QTableView()
    view.resize(1920, 1080)
    qtbot.addWidget(view)

    started = time.perf_counter()
    view.setModel(model)
    view.show()
    qapp.processEvents()
    first_render_seconds = time.perf_counter() - started
    first_render_reads = base_reads

    base_reads = 0
    started = time.perf_counter()
    view.scrollTo(model.index(ROWS - 1, COLUMNS - 1))
    qapp.processEvents()
    jump_seconds = time.perf_counter() - started
    jump_reads = base_reads

    print(
        f"first_render_seconds={first_render_seconds:.6f} "
        f"first_render_reads={first_render_reads} "
        f"jump_seconds={jump_seconds:.6f} jump_reads={jump_reads}"
    )
    assert first_render_seconds < 1.0
    assert jump_seconds < 1.0
    assert first_render_reads < 10_000
    assert jump_reads < 10_000
