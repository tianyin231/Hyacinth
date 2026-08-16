"""恢复到此版本：复制目标历史节点内容，在当前 HEAD 之后生成恢复子节点。

需求第 12/31 节：不移动版本指针、不覆盖后续历史；恢复结果是一个新的
"恢复版本"子节点并成为新的 HEAD，原节点全部保持不变。
"""

import json
import os
import shutil
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler
from hyacinth.versioning.models import ImportedWorkbook, VersionRecord
from hyacinth.versioning.store import MetadataStore, write_recovery_manifest

RESTORE_VERSION_OPERATION = "restore-version"
COPY_CHUNK_SIZE = 1024 * 1024


class RestoreVersionTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...

    def set_engine(self, engine: EngineName) -> None: ...

    def commit(self) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


def run_restore_version_task(
    request: TaskRequest,
    context: RestoreVersionTaskContext,
    *,
    metadata_store_factory: type[MetadataStore] = MetadataStore,
) -> ImportedWorkbook:
    library_root = Path(str(request.payload["library_root"]))
    source_version_id = str(request.payload["source_version_id"])
    parent_version_id = str(request.payload["parent_version_id"])
    version_id = str(request.payload["version_id"])

    context.set_engine(EngineName.PYTHON)
    context.check_cancelled()
    store = metadata_store_factory(library_root)
    workbook_record = store.get_workbook(request.file_id)
    head = workbook_record.head_version
    if head is None or head.version_id != parent_version_id:
        raise ValueError("当前工作版本已变化，请重试恢复")
    source = store.get_version(request.file_id, source_version_id)
    if source.deleted_at is not None:
        raise ValueError("已删除的版本不能恢复，请先在回收站恢复该版本")
    if source.content_hash == head.content_hash:
        raise ValueError("目标版本内容与当前工作版本相同，无需恢复")

    context.report_progress(0.2, "正在校验目标版本快照")
    if _hash(source.snapshot_path) != source.content_hash:
        raise ValueError("目标版本快照与记录不一致，请刷新版本树")

    staging_directory = library_root / ".staging" / f"{request.file_id}-{request.task_id}"
    final_directory = library_root / "files" / request.file_id / "versions" / version_id
    if final_directory.exists():
        raise ValueError("目标版本已存在，请刷新版本记录")
    staging_snapshot = staging_directory / "snapshot.xlsx"
    final_snapshot = final_directory / "snapshot.xlsx"
    working_temporary = workbook_record.working_path.with_name(
        f".{workbook_record.working_path.name}.{request.task_id}.tmp"
    )
    child = VersionRecord(
        version_id=version_id,
        file_id=request.file_id,
        parent_version_id=parent_version_id,
        name=f"恢复自“{source.name}”",
        created_at=datetime.now(UTC),
        operation="restore",
        engine=EngineName.PYTHON,
        snapshot_path=final_snapshot,
        content_hash=source.content_hash,
        parameters_json=json.dumps(
            {"source_version_id": source.version_id, "source_name": source.name},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        note=source.note,
        milestone=False,
    )
    result = ImportedWorkbook(
        file_id=workbook_record.file_id,
        display_name=workbook_record.display_name,
        original_path=workbook_record.original_path,
        working_path=workbook_record.working_path,
        root_version=child,
        imported_at=workbook_record.imported_at,
    )

    try:
        context.report_progress(0.4, "正在准备恢复版本快照")
        staging_snapshot.parent.mkdir(parents=True, exist_ok=True)
        _copy(source.snapshot_path, staging_snapshot)
        if _hash(staging_snapshot) != source.content_hash:
            raise RuntimeError("恢复版本快照校验失败")
        write_recovery_manifest(staging_directory / "manifest.json", library_root, result)
        _copy(staging_snapshot, working_temporary)
        context.check_cancelled()
        with context.critical_section("正在安全提交恢复版本"):
            context.commit()
            os.replace(staging_directory, final_directory)
            store.record_child_version(child, parent_version_id)
            os.replace(working_temporary, workbook_record.working_path)
    finally:
        shutil.rmtree(staging_directory, ignore_errors=True)
        working_temporary.unlink(missing_ok=True)

    context.report_progress(1.0, "恢复版本已创建")
    return store.get_workbook(request.file_id)


def restore_version_task(request: TaskRequest, context: TaskContext) -> object:
    return run_restore_version_task(request, context)


def restore_version_handlers() -> dict[str, TaskHandler]:
    return {RESTORE_VERSION_OPERATION: restore_version_task}


def _hash(path: Path) -> str:
    from hashlib import sha256

    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("wb") as dst:
        while chunk := src.read(COPY_CHUNK_SIZE):
            dst.write(chunk)
    shutil.copystat(source, destination)
