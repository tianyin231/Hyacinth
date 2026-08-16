from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from openpyxl import Workbook

from hyacinth.excel.contracts import EngineName
from hyacinth.processing import (
    TRIM_PREVIEW_OPERATION,
    TrimPreviewResult,
    run_trim_preview_task,
    trim_preview_handlers,
)
from hyacinth.tasks import TaskRequest


class TrimContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def set_engine(self, engine: EngineName) -> None:
        return

    def commit(self) -> None:
        return

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


def _seed(path: Path, rows: list[list[object]], *, formulas: bool = False) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "数据"
    for row in rows:
        sheet.append(row)
    if formulas:
        sheet["C2"] = '=A2&"  x  "'
    workbook.save(path)
    workbook.close()


def _request(source: Path, preview: Path, **overrides: object) -> TaskRequest:
    payload: dict[str, object] = {
        "source_path": str(source),
        "preview_path": str(preview),
        "parent_version_id": "parent-1",
        "sheet_name": "数据",
        "key_columns": [],
        "collapse_spaces": False,
    }
    payload.update(overrides)
    return TaskRequest(
        task_id="task-1",
        name="清除首尾空格",
        file_id="file-1",
        engine=None,
        operation=TRIM_PREVIEW_OPERATION,
        payload=payload,
    )


def test_trim_strips_text_edges_and_keeps_middle(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    preview = tmp_path / "preview.xlsx"
    _seed(
        source,
        [
            ["名称", "数量"],
            ["  苹果  ", 3],
            ["\u3000西瓜\u00a0\t", " 5 "],
            ["已 干净", 1],
        ],
    )

    result = run_trim_preview_task(_request(source, preview), TrimContext())

    assert isinstance(result, TrimPreviewResult)
    assert [cell.after for cell in result.trimmed_cells] == ["苹果", "西瓜", "5"]
    assert any(cell.before == "  苹果  " for cell in result.trimmed_cells)
    changed = {(cell.row, cell.column) for cell in result.trimmed_cells}
    assert (2, 2) not in changed and (3, 2) in changed
    assert preview.is_file()


def test_trim_collapse_spaces_option(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    preview = tmp_path / "preview.xlsx"
    _seed(source, [["名称"], ["  a   b   c "]])
    request = _request(source, preview, collapse_spaces=True)

    result = run_trim_preview_task(request, TrimContext())

    assert result.trimmed_cells[0].after == "a b c"


def test_trim_key_columns_limit_scope(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    preview = tmp_path / "preview.xlsx"
    _seed(source, [["名称", "数量"], [" a ", " 9 "]])
    request = _request(source, preview, key_columns=[0])

    result = run_trim_preview_task(request, TrimContext())

    assert {(cell.row, cell.column) for cell in result.trimmed_cells} == {(2, 1)}


def test_trim_skips_formulas_and_reports_empty_result(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    preview = tmp_path / "preview.xlsx"
    _seed(source, [["名称", "数量"], ["=A1  ", 3], [" 干净 ", 4]])

    result = run_trim_preview_task(_request(source, preview), TrimContext())

    assert [cell.after for cell in result.trimmed_cells] == ["干净"]

    clean = tmp_path / "clean.xlsx"
    _seed(clean, [["名称"], ["干净"]])
    with pytest.raises(ValueError, match="没有需要清理"):
        run_trim_preview_task(_request(clean, tmp_path / "p2.xlsx"), TrimContext())


def test_trim_handlers_register_operation() -> None:
    assert set(trim_preview_handlers()) == {TRIM_PREVIEW_OPERATION}
