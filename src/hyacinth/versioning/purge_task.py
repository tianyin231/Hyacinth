import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskHandler
from hyacinth.versioning.store import MetadataStore

PURGE_FILE_OPERATION = "purge-file"


@dataclass(frozen=True, slots=True)
class PurgedFile:
    file_id: str
    display_name: str


class PurgeFileTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...


def run_purge_file_task(request: TaskRequest, context: PurgeFileTaskContext) -> PurgedFile:
    library_root_value = request.payload.get("library_root")
    if not isinstance(library_root_value, str) or not library_root_value:
        raise ValueError("任务参数缺少：library_root")

    library_root = Path(library_root_value)
    store = MetadataStore(library_root)
    record = store.get_deleted_file(request.file_id)

    context.report_progress(0.1, "正在移出文件目录")
    directory = library_root / "files" / request.file_id
    pending = library_root / "files" / f".purge-{request.file_id}-{request.task_id}"
    moved = False
    try:
        if directory.is_dir():
            os.replace(directory, pending)
            moved = True
        context.report_progress(0.5, "正在清除文件记录")
        store.purge_file_records(request.file_id)
    except BaseException:
        if moved:
            os.replace(pending, directory)
        raise
    context.report_progress(0.9, "正在清理磁盘文件")
    if moved:
        shutil.rmtree(pending, ignore_errors=True)
    context.report_progress(1.0, "文件已永久删除")
    return PurgedFile(file_id=request.file_id, display_name=record.display_name)


def purge_file_task(request: TaskRequest, context: PurgeFileTaskContext) -> object:
    return run_purge_file_task(request, context)


def purge_file_handlers() -> dict[str, TaskHandler]:
    return {PURGE_FILE_OPERATION: purge_file_task}
