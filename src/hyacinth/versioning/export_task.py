import os
import re
import shutil
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler
from hyacinth.versioning.store import MetadataStore

EXPORT_VERSION_OPERATION = "export-version"
COPY_CHUNK_SIZE = 1024 * 1024
MAX_FILENAME_LENGTH = 180
_INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class ExportedVersion:
    version_id: str
    path: Path


class ExportTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...

    def commit(self) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


def suggested_export_filename(
    display_name: str,
    version_name: str,
    created_at_text: str,
    extension: str,
) -> str:
    base = _clean_filename_part(Path(display_name).stem) or "工作簿"
    version = _clean_filename_part(version_name) or "版本"
    suffix = extension if extension.startswith(".") else f".{extension}"
    ending = f"_{version}_{created_at_text}{suffix.lower()}"
    available = max(1, MAX_FILENAME_LENGTH - len(ending))
    return f"{base[:available]}{ending}"


def run_export_version_task(
    request: TaskRequest,
    context: ExportTaskContext,
) -> ExportedVersion:
    library_root = _payload_path(request, "library_root")
    version_id = _payload_string(request, "version_id")
    destination_directory_value = request.payload.get("destination_directory")
    destination_path_value = request.payload.get("destination_path")
    if (destination_directory_value is None) == (destination_path_value is None):
        raise ValueError("导出任务必须且只能指定目标目录或目标文件")

    store = MetadataStore(library_root)
    workbook = store.get_workbook(request.file_id)
    version = store.get_version(request.file_id, version_id)
    if version.deleted_at is not None:
        raise ValueError("已删除版本不能导出，请先恢复")
    source = workbook.original_path if version.parent_version_id is None else version.snapshot_path
    extension = source.suffix.lower()
    if extension not in {".xls", ".xlsx"}:
        raise ValueError("版本导出源文件格式无效")
    timestamp = version.created_at.astimezone().strftime("%Y%m%d-%H%M%S")
    suggested_name = suggested_export_filename(
        workbook.display_name,
        version.name,
        timestamp,
        extension,
    )
    if destination_directory_value is not None:
        if not isinstance(destination_directory_value, str) or not destination_directory_value:
            raise ValueError("导出目标目录无效")
        destination_directory = Path(destination_directory_value)
        requested_destination = destination_directory / suggested_name
    else:
        if not isinstance(destination_path_value, str) or not destination_path_value:
            raise ValueError("导出目标文件无效")
        selected = Path(destination_path_value)
        requested_destination = selected.with_suffix(extension)
        destination_directory = requested_destination.parent

    destination_directory.mkdir(parents=True, exist_ok=True)
    temporary = destination_directory / f".{suggested_name}.{request.task_id}.tmp"
    temporary.unlink(missing_ok=True)
    claimed: Path | None = None
    try:
        context.report_progress(0.05, "正在准备导出")
        source_size = max(source.stat().st_size, 1)
        copied = 0
        with source.open("rb") as source_file, temporary.open("wb") as destination_file:
            while chunk := source_file.read(COPY_CHUNK_SIZE):
                context.check_cancelled()
                destination_file.write(chunk)
                copied += len(chunk)
                context.report_progress(min(copied / source_size * 0.9, 0.9), "正在导出版本")
        shutil.copystat(source, temporary)
        context.check_cancelled()
        with context.critical_section("正在完成导出"):
            claimed = _claim_unique_destination(requested_destination)
            context.commit()
            os.replace(temporary, claimed)
        context.report_progress(1.0, "版本已导出")
        return ExportedVersion(version_id, claimed)
    except BaseException:
        if claimed is not None and claimed.exists() and claimed.stat().st_size == 0:
            claimed.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def export_version_task(request: TaskRequest, context: TaskContext) -> object:
    return run_export_version_task(request, context)


def export_version_handlers() -> dict[str, TaskHandler]:
    return {EXPORT_VERSION_OPERATION: export_version_task}


def _claim_unique_destination(path: Path) -> Path:
    candidate = path
    counter = 0
    while True:
        try:
            candidate.touch(exist_ok=False)
            return candidate
        except FileExistsError:
            counter += 1
            candidate = path.with_name(f"{path.stem}({counter}){path.suffix}")


def _clean_filename_part(value: str) -> str:
    return _INVALID_FILENAME_CHARACTERS.sub("_", value).strip(" .")


def _payload_path(request: TaskRequest, key: str) -> Path:
    value = request.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数缺少路径：{key}")
    return Path(value)


def _payload_string(request: TaskRequest, key: str) -> str:
    value = request.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数缺少：{key}")
    return value
