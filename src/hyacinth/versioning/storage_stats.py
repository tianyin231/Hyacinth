from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hyacinth.tasks import TaskRequest
from hyacinth.tasks.worker import TaskHandler
from hyacinth.versioning.store import MetadataStore

VERSION_STORAGE_STATS_OPERATION = "version-storage-stats"


@dataclass(frozen=True, slots=True)
class VersionStorageStats:
    total_bytes: int
    preview_bytes: int


class StorageStatsTaskContext(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...


def run_version_storage_stats_task(
    request: TaskRequest,
    context: StorageStatsTaskContext,
) -> VersionStorageStats:
    library_root_value = request.payload.get("library_root")
    if not isinstance(library_root_value, str) or not library_root_value:
        raise ValueError("任务参数缺少：library_root")
    preview_version_id_value = request.payload.get("preview_version_id")
    if preview_version_id_value is not None and not isinstance(preview_version_id_value, str):
        raise ValueError("任务参数无效：preview_version_id")

    store = MetadataStore(Path(library_root_value))
    versions = store.list_versions(request.file_id)
    unique_snapshots = {version.snapshot_path for version in versions}
    total_bytes = sum(_file_size(path) for path in unique_snapshots)
    preview_version_id = (
        preview_version_id_value if isinstance(preview_version_id_value, str) else None
    )
    preview_bytes = 0
    if preview_version_id is not None:
        preview_snapshot = next(
            (
                version.snapshot_path
                for version in versions
                if version.version_id == preview_version_id
            ),
            None,
        )
        if preview_snapshot is not None:
            preview_bytes = _file_size(preview_snapshot)
    return VersionStorageStats(total_bytes=total_bytes, preview_bytes=preview_bytes)


def version_storage_stats_handlers() -> dict[str, TaskHandler]:
    return {VERSION_STORAGE_STATS_OPERATION: version_storage_stats_task}


def version_storage_stats_task(request: TaskRequest, context: StorageStatsTaskContext) -> object:
    return run_version_storage_stats_task(request, context)


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
