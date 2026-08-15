import os
from contextlib import AbstractContextManager
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler
from hyacinth.versioning.models import ImportedWorkbook, VersionRecord
from hyacinth.versioning.store import MetadataStore

DELETE_VERSION_OPERATION = "delete-version"
COPY_CHUNK_SIZE = 1024 * 1024


class DeleteVersionTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...

    def set_engine(self, engine: EngineName) -> None: ...

    def commit(self) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


def run_delete_version_task(
    request: TaskRequest,
    context: DeleteVersionTaskContext,
) -> ImportedWorkbook:
    library_root = _payload_path(request, "library_root")
    version_id = _payload_string(request, "version_id")
    expected_head_version_id = _payload_string(request, "expected_head_version_id")
    selected_replacement_id = _payload_optional_string(request, "replacement_version_id")
    store = MetadataStore(library_root)
    workbook = store.get_workbook(request.file_id)
    plan = store.plan_version_deletion(request.file_id, version_id)
    if plan.current_head_version_id != expected_head_version_id:
        raise ValueError("当前 HEAD 已变化，请刷新版本树")
    replacement = _select_replacement(plan.replacement_candidates, selected_replacement_id)

    context.set_engine(EngineName.PYTHON)
    context.check_cancelled()
    if not plan.requires_head_switch:
        with context.critical_section("正在删除版本节点"):
            context.commit()
            store.soft_delete_version(
                request.file_id,
                version_id,
                expected_head_version_id,
            )
        context.report_progress(1.0, "版本已移入回收状态")
        return store.get_workbook(request.file_id)

    assert replacement is not None
    temporary = workbook.working_path.with_name(
        f".{workbook.working_path.name}.{request.task_id}.tmp"
    )
    temporary.unlink(missing_ok=True)
    try:
        context.report_progress(0.1, "正在准备新的当前工作版本")
        actual_hash = _copy_and_hash(replacement.snapshot_path, temporary, context)
        if actual_hash != replacement.content_hash:
            raise ValueError("新 HEAD 版本快照哈希校验失败")
        context.check_cancelled()
        with context.critical_section("正在安全删除并切换当前工作版本"):
            context.commit()
            store.soft_delete_version(
                request.file_id,
                version_id,
                expected_head_version_id,
                replacement.version_id,
            )
            try:
                os.replace(temporary, workbook.working_path)
            except OSError:
                store.restore_version(request.file_id, version_id)
                store.switch_head(
                    request.file_id,
                    expected_head_version_id,
                    replacement.version_id,
                )
                raise
    finally:
        temporary.unlink(missing_ok=True)

    context.report_progress(1.0, "版本已删除，当前工作版本已安全切换")
    return store.get_workbook(request.file_id)


def delete_version_task(request: TaskRequest, context: TaskContext) -> object:
    return run_delete_version_task(request, context)


def delete_version_handlers() -> dict[str, TaskHandler]:
    return {DELETE_VERSION_OPERATION: delete_version_task}


def _select_replacement(
    candidates: tuple[VersionRecord, ...],
    selected_version_id: str | None,
) -> VersionRecord | None:
    if not candidates:
        return None
    if selected_version_id is None:
        if len(candidates) != 1:
            raise ValueError("删除当前 HEAD 前请选择新的工作版本")
        return candidates[0]
    for candidate in candidates:
        if candidate.version_id == selected_version_id:
            return candidate
    raise ValueError("所选的新 HEAD 不是可用的相邻版本")


def _copy_and_hash(
    source: Path,
    destination: Path,
    context: DeleteVersionTaskContext,
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


def _payload_optional_string(request: TaskRequest, key: str) -> str | None:
    value = request.payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"任务参数 {key} 必须是非空字符串或空值")
    return value


def _payload_path(request: TaskRequest, key: str) -> Path:
    return Path(_payload_string(request, key))
