import os
from contextlib import AbstractContextManager
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler
from hyacinth.versioning.models import ImportedWorkbook
from hyacinth.versioning.store import MetadataStore

CHECKOUT_VERSION_OPERATION = "checkout-version"
COPY_CHUNK_SIZE = 1024 * 1024


class CheckoutTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...

    def set_engine(self, engine: EngineName) -> None: ...

    def commit(self) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


def run_checkout_version_task(
    request: TaskRequest,
    context: CheckoutTaskContext,
) -> ImportedWorkbook:
    library_root = _payload_path(request, "library_root")
    version_id = _payload_string(request, "version_id")
    expected_head_version_id = _payload_string(request, "expected_head_version_id")
    store = MetadataStore(library_root)
    workbook = store.get_workbook(request.file_id)
    target = store.get_version(request.file_id, version_id)
    if target.version_id == expected_head_version_id:
        return workbook

    context.set_engine(EngineName.PYTHON)
    context.check_cancelled()
    temporary = workbook.working_path.with_name(
        f".{workbook.working_path.name}.{request.task_id}.tmp"
    )
    temporary.unlink(missing_ok=True)
    try:
        context.report_progress(0.1, "正在读取目标版本")
        actual_hash = _copy_and_hash(target.snapshot_path, temporary, context)
        if actual_hash != target.content_hash:
            raise ValueError("目标版本快照哈希校验失败")
        context.check_cancelled()
        with context.critical_section("正在安全切换当前工作版本"):
            context.commit()
            store.switch_head(request.file_id, version_id, expected_head_version_id)
            try:
                os.replace(temporary, workbook.working_path)
            except OSError:
                store.switch_head(request.file_id, expected_head_version_id, version_id)
                raise
    finally:
        temporary.unlink(missing_ok=True)

    context.report_progress(1.0, "当前工作版本已切换")
    return store.get_workbook(request.file_id)


def checkout_version_task(request: TaskRequest, context: TaskContext) -> object:
    return run_checkout_version_task(request, context)


def checkout_version_handlers() -> dict[str, TaskHandler]:
    return {CHECKOUT_VERSION_OPERATION: checkout_version_task}


def _copy_and_hash(
    source: Path,
    destination: Path,
    context: CheckoutTaskContext,
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    with source.open("rb") as source_file, destination.open("wb") as destination_file:
        while chunk := source_file.read(COPY_CHUNK_SIZE):
            context.check_cancelled()
            digest.update(chunk)
            destination_file.write(chunk)
        destination_file.flush()
        os.fsync(destination_file.fileno())
    return digest.hexdigest()


def _payload_string(request: TaskRequest, key: str) -> str:
    value = request.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数 {key} 必须是非空字符串")
    return value


def _payload_path(request: TaskRequest, key: str) -> Path:
    return Path(_payload_string(request, key))
