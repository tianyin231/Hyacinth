import sqlite3
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QTableView
from pytestqt.qtbot import QtBot

from hyacinth.grid.model import WorkbookTableModel
from hyacinth.preview import SheetPreview, SqliteGridDataSource


@pytest.mark.performance
def test_sparse_preview_jumps_to_extreme_grid_end(
    qtbot: QtBot,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "preview.sqlite"
    connection = sqlite3.connect(index_path)
    connection.executescript(
        """
        CREATE TABLE cells (
            sheet_index INTEGER NOT NULL,
            row_index INTEGER NOT NULL,
            column_index INTEGER NOT NULL,
            display_value TEXT NOT NULL,
            formula TEXT,
            PRIMARY KEY (sheet_index, row_index, column_index)
        );
        INSERT INTO cells VALUES (0, 1048575, 255, '末端', NULL);
        """
    )
    connection.close()
    sheet = SheetPreview(0, "数据", 1_048_576, 256)
    source = SqliteGridDataSource(index_path, sheet)
    model = WorkbookTableModel(source, editable=False)
    view = QTableView()
    view.resize(1920, 1080)
    qtbot.addWidget(view)
    view.setModel(model)
    view.show()
    qapp.processEvents()

    started = time.perf_counter()
    view.scrollTo(model.index(1_048_575, 255))
    qapp.processEvents()
    elapsed = time.perf_counter() - started

    assert model.data(model.index(1_048_575, 255)) == "末端"
    assert elapsed < 1.0
    source.close()
