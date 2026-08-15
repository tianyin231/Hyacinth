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


@dataclass(frozen=True, slots=True)
class ImportedWorkbook:
    file_id: str
    display_name: str
    original_path: Path
    working_path: Path
    root_version: VersionRecord | None = None

    @property
    def head_version(self) -> VersionRecord | None:
        return self.root_version
