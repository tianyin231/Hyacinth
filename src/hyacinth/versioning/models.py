from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hyacinth.excel.contracts import EngineName


@dataclass(frozen=True, slots=True)
class VersionRecord:
    version_id: str
    file_id: str
    parent_version_id: str | None
    name: str
    created_at: datetime
    operation: str
    engine: EngineName | None
    snapshot_path: Path
    content_hash: str
    parameters_json: str = "{}"
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VersionDeletionPlan:
    target: VersionRecord
    current_head_version_id: str
    replacement_candidates: tuple[VersionRecord, ...]

    @property
    def requires_head_switch(self) -> bool:
        return self.target.version_id == self.current_head_version_id


@dataclass(frozen=True, slots=True)
class VersionLayout:
    x: float
    y: float
    fixed: bool


@dataclass(frozen=True, slots=True)
class ImportedWorkbook:
    file_id: str
    display_name: str
    original_path: Path
    working_path: Path
    root_version: VersionRecord | None = None
    imported_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def head_version(self) -> VersionRecord | None:
        return self.root_version
