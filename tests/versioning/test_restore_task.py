"""恢复到此版本：复制目标内容在 HEAD 后生成恢复子节点（需求第 12/31 节）。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskRequest
from hyacinth.versioning import (
    RESTORE_VERSION_OPERATION,
    ImportedWorkbook,
    MetadataStore,
    VersionRecord,
    restore_version_handlers,
    restore_version_task,
    run_restore_version_task,
)


class RecordingContext:
    def __init__(self) -> None:
        self.committed = False
        self.critical_messages: list[str] = []

    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def set_engine(self, engine: EngineName) -> None:
        assert engine is EngineName.PYTHON

    def commit(self) -> None:
        self.committed = True

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        self.critical_messages.append(message)
        yield


def _seed_branch(root: Path) -> tuple[ImportedWorkbook, VersionRecord, VersionRecord]:
    directory = root / "files/file-1"
    original = directory / "original/销售.xlsx"
    working = directory / "working/current.xlsx"
    root_snapshot = directory / "versions/version-1/snapshot.xlsx"
    child_snapshot = directory / "versions/version-2/snapshot.xlsx"
    for path, content in (
        (original, b"original"),
        (working, b"child"),
        (root_snapshot, b"root"),
        (child_snapshot, b"child"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    root_version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "import",
        None,
        root_snapshot,
        sha256(b"root").hexdigest(),
        note="初始导入",
        milestone=True,
    )
    child_version = VersionRecord(
        "version-2",
        "file-1",
        "version-1",
        "多列排序",
        datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        child_snapshot,
        sha256(b"child").hexdigest(),
    )
    record = ImportedWorkbook("file-1", "销售.xlsx", original, working, root_version)
    store = MetadataStore(root)
    store.record_import(record)
    store.record_child_version(child_version, root_version.version_id)
    return record, root_version, child_version


def _request(root: Path, source_version_id: str = "version-1") -> TaskRequest:
    return TaskRequest(
        "restore-1",
        "恢复到此版本",
        "file-1",
        None,
        RESTORE_VERSION_OPERATION,
        {
            "library_root": str(root),
            "source_version_id": source_version_id,
            "parent_version_id": "version-2",
            "version_id": "version-restored",
        },
    )


def test_restore_handler_is_registered() -> None:
    assert restore_version_handlers() == {
        RESTORE_VERSION_OPERATION: restore_version_task,
    }


def test_restore_creates_recovery_child_and_switches_head(tmp_path: Path) -> None:
    import json

    record, root_version, child_version = _seed_branch(tmp_path)

    result = run_restore_version_task(_request(tmp_path), RecordingContext())

    head = result.head_version
    assert head is not None
    assert head.version_id == "version-restored"
    assert head.parent_version_id == "version-2"
    assert head.operation == "restore"
    assert "导入原始文件" in head.name
    # 恢复节点内容与目标版本一致，父链原节点全部保持不变
    assert head.content_hash == root_version.content_hash
    assert head.snapshot_path.read_bytes() == b"root"
    assert record.working_path.read_bytes() == b"root"
    versions = {v.version_id: v for v in MetadataStore(tmp_path).list_versions("file-1")}
    assert set(versions) == {"version-1", "version-2", "version-restored"}
    assert versions["version-2"].parent_version_id == "version-1"
    assert versions["version-1"].milestone is True
    assert json.loads(head.parameters_json)["source_version_id"] == "version-1"
    # 恢复节点沿用目标版本备注但不继承里程碑
    assert head.note == "初始导入"
    assert head.milestone is False


def test_restore_rejects_stale_head(tmp_path: Path) -> None:
    record, _root_version, _child_version = _seed_branch(tmp_path)
    request = TaskRequest(
        "restore-2",
        "恢复到此版本",
        "file-1",
        None,
        RESTORE_VERSION_OPERATION,
        {
            "library_root": str(tmp_path),
            "source_version_id": "version-1",
            "parent_version_id": "version-1",
            "version_id": "version-restored",
        },
    )
    with pytest.raises(ValueError, match="当前工作版本已变化"):
        run_restore_version_task(request, RecordingContext())
    head = MetadataStore(tmp_path).get_workbook("file-1").head_version
    assert head is not None and head.version_id == "version-2"
    assert record.working_path.read_bytes() == b"child"


def test_restore_rejects_corrupt_source_snapshot(tmp_path: Path) -> None:
    _record, root_version, _child_version = _seed_branch(tmp_path)
    root_version.snapshot_path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="快照与记录不一致"):
        run_restore_version_task(_request(tmp_path), RecordingContext())
    head = MetadataStore(tmp_path).get_workbook("file-1").head_version
    assert head is not None and head.version_id == "version-2"


def test_restore_rejects_identical_content(tmp_path: Path) -> None:
    _record, _root_version, _child_version = _seed_branch(tmp_path)
    request = TaskRequest(
        "restore-3",
        "恢复到此版本",
        "file-1",
        None,
        RESTORE_VERSION_OPERATION,
        {
            "library_root": str(tmp_path),
            "source_version_id": "version-2",
            "parent_version_id": "version-2",
            "version_id": "version-restored",
        },
    )
    with pytest.raises(ValueError, match="相同"):
        run_restore_version_task(request, RecordingContext())
