import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from openpyxl import load_workbook

from hyacinth.excel.selection import create_default_engine
from hyacinth.excel.task_handler import (
    ConversionTaskContext,
    EngineSelector,
    run_conversion_task,
)
from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler

IMPORT_WORKBOOK_OPERATION = "import-workbook"


@dataclass(frozen=True, slots=True)
class ImportedWorkbook:
    file_id: str
    display_name: str
    original_path: Path
    working_path: Path


class ImportTaskContext(ConversionTaskContext, Protocol):
    def commit(self) -> None: ...


def run_import_task(
    request: TaskRequest,
    context: ImportTaskContext,
    *,
    select_engine: EngineSelector = create_default_engine,
) -> ImportedWorkbook:
    source = _payload_path(request, "source_path")
    library_root = _payload_path(request, "library_root")
    if source.suffix.lower() not in {".xls", ".xlsx"}:
        raise ValueError("第一版只支持 .xls 和 .xlsx 文件")

    staging_root = library_root / ".staging"
    files_root = library_root / "files"
    staging_directory = staging_root / f"{request.file_id}-{request.task_id}"
    final_directory = files_root / request.file_id

    original = staging_directory / "original" / source.name
    working = staging_directory / "working" / "current.xlsx"
    final_original = final_directory / "original" / source.name
    final_working = final_directory / "working" / "current.xlsx"
    staging_root.mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)

    try:
        original.parent.mkdir(parents=True)
        working.parent.mkdir(parents=True)
        context.report_progress(None, "正在复制原始文件")
        shutil.copy2(source, original)
        context.check_cancelled()
        if source.suffix.lower() == ".xls":
            run_conversion_task(
                replace(
                    request,
                    payload={
                        "source_path": str(original),
                        "destination_path": str(working),
                    },
                ),
                context,
                select_engine=select_engine,
            )
        else:
            shutil.copy2(original, working)
        context.check_cancelled()
        context.report_progress(None, "正在校验工作副本")
        workbook = load_workbook(working, read_only=True)
        workbook.close()
        context.check_cancelled()
        with context.critical_section("正在安全完成导入"):
            context.commit()
            os.replace(staging_directory, final_directory)
    finally:
        shutil.rmtree(staging_directory, ignore_errors=True)

    context.report_progress(1.0, "导入完成")
    return ImportedWorkbook(
        file_id=request.file_id,
        display_name=source.name,
        original_path=final_original,
        working_path=final_working,
    )


def import_workbook_task(request: TaskRequest, context: TaskContext) -> object:
    return run_import_task(request, context)


def import_task_handlers() -> dict[str, TaskHandler]:
    return {IMPORT_WORKBOOK_OPERATION: import_workbook_task}


def _payload_path(request: TaskRequest, key: str) -> Path:
    value = request.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数缺少路径：{key}")
    return Path(value)
