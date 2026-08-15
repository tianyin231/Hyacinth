import json
import os
import shutil
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from openpyxl import load_workbook

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskContext, TaskHandler
from hyacinth.versioning import (
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    write_recovery_manifest,
)

APPLY_SORT_PREVIEW_OPERATION = "apply-sort-preview"
COPY_CHUNK_SIZE = 1024 * 1024


class ApplyVersionTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...

    def set_engine(self, engine: EngineName) -> None: ...

    def commit(self) -> None: ...

    def critical_section(self, message: str = "") -> AbstractContextManager[None]: ...


class ApplyMetadataStore(Protocol):
    def get_workbook(self, file_id: str) -> ImportedWorkbook: ...

    def record_child_version(
        self,
        version: VersionRecord,
        expected_parent_version_id: str,
    ) -> None: ...


MetadataStoreFactory = Callable[[Path], ApplyMetadataStore]


def run_apply_sort_preview_task(
    request: TaskRequest,
    context: ApplyVersionTaskContext,
    *,
    metadata_store_factory: MetadataStoreFactory = MetadataStore,
) -> ImportedWorkbook:
    library_root = _payload_path(request, "library_root")
    preview_path = _payload_path(request, "preview_path")
    preview_hash = _payload_string(request, "preview_hash")
    parent_version_id = _payload_string(request, "parent_version_id")
    version_id = _payload_string(request, "version_id")
    sheet_name = _payload_string(request, "sheet_name")
    sort_keys = request.payload.get("sort_keys")
    if not isinstance(sort_keys, list) or not sort_keys:
        raise ValueError("任务参数缺少排序键：sort_keys")

    context.set_engine(EngineName.PYTHON)
    context.check_cancelled()
    store = metadata_store_factory(library_root)
    workbook_record = store.get_workbook(request.file_id)
    parent = workbook_record.head_version
    if parent is None or parent.version_id != parent_version_id:
        raise ValueError("当前 HEAD 已变化，请重新生成预览")

    actual_hash = _file_hash(preview_path, context)
    if actual_hash != preview_hash:
        raise ValueError("临时预览已变化，请重新生成预览")
    if actual_hash == parent.content_hash:
        raise ValueError("排序结果没有变化，无需生成新版本")
    preview_workbook = load_workbook(preview_path, read_only=True)
    preview_workbook.close()

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
        name="多列排序",
        created_at=datetime.now(UTC),
        operation="sort",
        engine=EngineName.PYTHON,
        snapshot_path=final_snapshot,
        content_hash=actual_hash,
        parameters_json=json.dumps(
            {"sheet_name": sheet_name, "sort_keys": sort_keys},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    result = ImportedWorkbook(
        file_id=workbook_record.file_id,
        display_name=workbook_record.display_name,
        original_path=workbook_record.original_path,
        working_path=workbook_record.working_path,
        root_version=child,
    )

    try:
        context.report_progress(0.2, "正在准备子版本快照")
        staging_snapshot.parent.mkdir(parents=True, exist_ok=True)
        _copy_file(preview_path, staging_snapshot, context)
        if _file_hash(staging_snapshot, context) != actual_hash:
            raise RuntimeError("子版本快照校验失败")
        write_recovery_manifest(staging_directory / "manifest.json", library_root, result)
        _copy_file(preview_path, working_temporary, context)
        context.check_cancelled()
        with context.critical_section("正在安全提交子版本"):
            context.commit()
            os.replace(staging_directory, final_directory)
            store.record_child_version(child, parent_version_id)
            os.replace(working_temporary, workbook_record.working_path)
    finally:
        shutil.rmtree(staging_directory, ignore_errors=True)
        working_temporary.unlink(missing_ok=True)

    context.report_progress(1.0, "新版本已创建")
    return result


def apply_sort_preview_task(request: TaskRequest, context: TaskContext) -> object:
    return run_apply_sort_preview_task(request, context)


def apply_version_handlers() -> dict[str, TaskHandler]:
    return {APPLY_SORT_PREVIEW_OPERATION: apply_sort_preview_task}


def _copy_file(source: Path, destination: Path, context: ApplyVersionTaskContext) -> None:
    with source.open("rb") as source_file, destination.open("wb") as destination_file:
        while chunk := source_file.read(COPY_CHUNK_SIZE):
            context.check_cancelled()
            destination_file.write(chunk)
    context.check_cancelled()
    shutil.copystat(source, destination)


def _file_hash(path: Path, context: ApplyVersionTaskContext) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(COPY_CHUNK_SIZE):
            context.check_cancelled()
            digest.update(chunk)
    context.check_cancelled()
    return digest.hexdigest()


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
