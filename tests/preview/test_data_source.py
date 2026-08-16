import sqlite3
from pathlib import Path


def test_sqlite_grid_source_random_access_uses_sparse_rows(tmp_path: Path) -> None:
    from hyacinth.preview import SheetPreview, SqliteGridDataSource

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
        INSERT INTO cells VALUES (0, 0, 0, '首行', NULL);
        INSERT INTO cells VALUES (0, 1048575, 255, '末端', NULL);
        """
    )
    connection.close()
    sheet = SheetPreview(index=0, title="数据", row_count=1_048_576, column_count=256)
    source = SqliteGridDataSource(index_path, sheet)

    try:
        assert source.data_row_count == 1_048_576
        assert source.row_count == 1_048_576 + 32
        assert source.column_count == 256 + 4
        assert source.value_at(0, 0) == "首行"
        assert source.value_at(500_000, 20) == ""
        assert source.value_at(1_048_575, 255) == "末端"
    finally:
        source.close()


def test_small_sheet_shows_data_area_plus_edit_margin(
    tmp_path: Path,
) -> None:
    from hyacinth.preview import SheetPreview, SqliteGridDataSource

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
        INSERT INTO cells VALUES (0, 0, 0, '表头', NULL);
        """
    )
    connection.close()
    source = SqliteGridDataSource(index_path, SheetPreview(0, "小表", 2, 3))

    try:
        assert source.data_row_count == 2
        assert source.data_column_count == 3
        assert source.row_count == 2 + 32
        assert source.column_count == 3 + 4
        assert source.value_at(0, 0) == "表头"
        assert source.value_at(100, 20) == ""
    finally:
        source.close()


def test_editable_filtered_source_saves_visible_cell_to_physical_source_row(
    tmp_path: Path,
) -> None:
    from hyacinth.preview import (
        EditableGridDataSource,
        EditSession,
        SheetPreview,
        SqliteGridDataSource,
    )

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
        CREATE TABLE visible_rows (
            sheet_index INTEGER NOT NULL,
            visible_row_index INTEGER NOT NULL,
            source_row_index INTEGER NOT NULL,
            PRIMARY KEY (sheet_index, visible_row_index)
        );
        INSERT INTO cells VALUES (0, 0, 0, '表头', NULL);
        INSERT INTO cells VALUES (0, 2, 0, '实际第三行', NULL);
        INSERT INTO visible_rows VALUES (0, 0, 0);
        INSERT INTO visible_rows VALUES (0, 1, 2);
        """
    )
    connection.close()
    source = SqliteGridDataSource(
        index_path,
        SheetPreview(0, "筛选结果", 3, 1, visible_row_count=2),
    )
    session = EditSession()
    editable = EditableGridDataSource(source, session, "筛选结果")

    try:
        assert editable.value_at(1, 0) == "实际第三行"
        editable.set_value(1, 0, "已修改")
        assert session.edits()[0].row == 2
        assert source.visible_row_index(2) == 1
    finally:
        source.close()
