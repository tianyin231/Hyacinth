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
        assert source.row_count == 1_048_576
        assert source.column_count == 256
        assert source.value_at(0, 0) == "首行"
        assert source.value_at(500_000, 20) == ""
        assert source.value_at(1_048_575, 255) == "末端"
    finally:
        source.close()


def test_small_sheet_keeps_excel_like_blank_grid_without_materializing_cells(
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
        assert source.row_count == 1_048_576
        assert source.column_count == 256
        assert source.value_at(0, 0) == "表头"
        assert source.value_at(100, 20) == ""
    finally:
        source.close()
