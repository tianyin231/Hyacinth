from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from hyacinth.excel.contracts import (
    ConversionProgress,
    ConversionResult,
    EngineName,
)
from hyacinth.excel.python_engine import PythonExcelEngine
from hyacinth.excel.task_handler import run_conversion_task
from hyacinth.tasks import TaskRequest

FIXTURES = Path(__file__).parents[1] / "fixtures"


class RecordingContext:
    def __init__(self) -> None:
        self.engine: EngineName | None = None
        self.progress: list[tuple[float | None, str]] = []
        self.critical_messages: list[str] = []

    def set_engine(self, engine: EngineName) -> None:
        self.engine = engine

    def report_progress(self, progress: float | None, message: str = "") -> None:
        self.progress.append((progress, message))

    def check_cancelled(self) -> None:
        pass

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        self.critical_messages.append(message)
        yield


class RecordingEngine:
    def __init__(self, name: EngineName, *, fail: bool = False) -> None:
        self.name = name
        self._fail = fail

    def convert_xls_to_xlsx(
        self,
        source: Path,
        destination: Path,
        progress: ConversionProgress | None = None,
    ) -> ConversionResult:
        destination.write_bytes(b"temporary output")
        if self._fail:
            raise RuntimeError("conversion failed")
        return ConversionResult(engine=self.name, output_path=destination)


def test_conversion_task_selects_python_and_commits_output(tmp_path: Path) -> None:
    destination = tmp_path / "working-copy.xlsx"
    context = RecordingContext()
    request = TaskRequest(
        task_id="convert-1",
        name="转换旧版工作簿",
        file_id="file-1",
        engine=None,
        operation="convert-xls",
        payload={
            "source_path": str(FIXTURES / "legacy-fidelity.xls"),
            "destination_path": str(destination),
        },
    )

    result = run_conversion_task(
        request,
        context,
        select_engine=lambda: PythonExcelEngine(),
    )

    assert result.engine is EngineName.PYTHON
    assert result.output_path == destination
    assert destination.exists()
    assert context.engine is EngineName.PYTHON
    assert context.progress[0] == (None, "正在检测 Excel 引擎")
    assert context.progress[-1][0] == 1.0


def test_com_conversion_runs_inside_critical_section(tmp_path: Path) -> None:
    destination = tmp_path / "working-copy.xlsx"
    context = RecordingContext()
    request = TaskRequest(
        task_id="convert-com",
        name="COM 转换",
        file_id="file-1",
        engine=None,
        operation="convert-xls",
        payload={"source_path": "source.xls", "destination_path": str(destination)},
    )

    result = run_conversion_task(
        request,
        context,
        select_engine=lambda: RecordingEngine(EngineName.COM),
    )

    assert result.engine is EngineName.COM
    assert context.critical_messages == ["Excel 正在转换并安全保存"]


def test_failed_conversion_does_not_publish_partial_output(tmp_path: Path) -> None:
    destination = tmp_path / "working-copy.xlsx"
    context = RecordingContext()
    request = TaskRequest(
        task_id="convert-fail",
        name="失败转换",
        file_id="file-1",
        engine=None,
        operation="convert-xls",
        payload={"source_path": "source.xls", "destination_path": str(destination)},
    )

    with pytest.raises(RuntimeError, match="conversion failed"):
        run_conversion_task(
            request,
            context,
            select_engine=lambda: RecordingEngine(EngineName.PYTHON, fail=True),
        )

    assert not destination.exists()
    assert list(tmp_path.glob("hyacinth-convert-*")) == []
