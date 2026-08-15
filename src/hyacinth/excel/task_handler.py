import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from hyacinth.excel.contracts import (
    ConversionProgress,
    ConversionResult,
    EngineName,
)
from hyacinth.excel.selection import create_default_engine
from hyacinth.tasks.contracts import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler

CONVERT_XLS_OPERATION = "convert-xls"


class ConversionEngine(Protocol):
    name: EngineName

    def convert_xls_to_xlsx(
        self,
        source: Path,
        destination: Path,
        progress: ConversionProgress | None = None,
    ) -> ConversionResult: ...


class ConversionTaskContext(ConversionProgress, Protocol):
    def set_engine(self, engine: EngineName) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


EngineSelector = Callable[[], ConversionEngine]


def run_conversion_task(
    request: TaskRequest,
    context: ConversionTaskContext,
    *,
    select_engine: EngineSelector = create_default_engine,
) -> ConversionResult:
    source = _payload_path(request, "source_path")
    destination = _payload_path(request, "destination_path")
    destination.parent.mkdir(parents=True, exist_ok=True)

    context.report_progress(None, "正在检测 Excel 引擎")
    engine = select_engine()
    context.set_engine(engine.name)
    context.check_cancelled()
    context.report_progress(None, "正在转换工作簿")

    with TemporaryDirectory(prefix="hyacinth-convert-", dir=destination.parent) as directory:
        temporary_destination = Path(directory) / destination.name
        if engine.name is EngineName.COM:
            with context.critical_section("Excel 正在转换并安全保存"):
                result = engine.convert_xls_to_xlsx(source, temporary_destination)
        else:
            result = engine.convert_xls_to_xlsx(
                source,
                temporary_destination,
                progress=context,
            )
        context.check_cancelled()
        os.replace(temporary_destination, destination)

    context.report_progress(1.0, "转换完成")
    return replace(result, output_path=destination)


def convert_xls_task(request: TaskRequest, context: TaskContext) -> object:
    return run_conversion_task(request, context)


def conversion_task_handlers() -> dict[str, TaskHandler]:
    return {CONVERT_XLS_OPERATION: convert_xls_task}


def _payload_path(request: TaskRequest, key: str) -> Path:
    value = request.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数缺少路径：{key}")
    return Path(value)
