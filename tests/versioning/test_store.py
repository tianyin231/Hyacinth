import json
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from hyacinth.excel.contracts import EngineName
from hyacinth.versioning import (
    ImportedWorkbook,
    MetadataStore,
    VersionLayout,
    VersionRecord,
    write_recovery_manifest,
)


def _record(root: Path) -> ImportedWorkbook:
    original = root / "files" / "file-1" / "original" / "销售.xls"
    working = root / "files" / "file-1" / "working" / "current.xlsx"
    snapshot = root / "files" / "file-1" / "versions" / "version-1" / "snapshot.xlsx"
    version = VersionRecord(
        version_id="version-1",
        file_id="file-1",
        parent_version_id=None,
        name="导入原始文件",
        created_at=datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        operation="import",
        engine=EngineName.COM,
        snapshot_path=snapshot,
        content_hash=sha256(b"snapshot").hexdigest(),
    )
    return ImportedWorkbook("file-1", "销售.xls", original, working, version, version.created_at)


def test_metadata_store_persists_root_version_and_head_with_relative_paths(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)

    store.record_import(record)

    assert store.list_workbooks() == (record,)
    with sqlite3.connect(tmp_path / "library.sqlite3") as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        stored_path = connection.execute(
            "SELECT snapshot_path FROM versions WHERE version_id = ?",
            ("version-1",),
        ).fetchone()[0]
        head = connection.execute(
            "SELECT head_version_id FROM files WHERE file_id = ?",
            ("file-1",),
        ).fetchone()[0]

    assert stored_path == "files/file-1/versions/version-1/snapshot.xlsx"
    assert head == "version-1"


def test_recovery_manifest_can_rebuild_missing_database_record(tmp_path: Path) -> None:
    record = _record(tmp_path)
    version = record.root_version
    assert version is not None
    manifest = version.snapshot_path.parent / "manifest.json"
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    manifest.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"working")
    version.snapshot_path.write_bytes(b"snapshot")
    write_recovery_manifest(manifest, tmp_path, record)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    store = MetadataStore(tmp_path)
    assert store.list_workbooks() == ()

    assert store.reconcile_manifests() == 1
    assert store.list_workbooks() == (record,)
    assert payload["schema_version"] == 1
    assert payload["file"]["head_version_id"] == "version-1"
    assert payload["version"]["parent_version_id"] is None


def test_reconcile_skips_unreadable_or_corrupt_manifests(tmp_path: Path) -> None:
    record = _record(tmp_path)
    version = record.root_version
    assert version is not None
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"working")
    version.snapshot_path.parent.mkdir(parents=True)
    version.snapshot_path.write_bytes(b"corrupt snapshot")
    write_recovery_manifest(version.snapshot_path.parent / "manifest.json", tmp_path, record)

    unreadable_manifest = (
        tmp_path / "files" / "unreadable" / "versions" / "version-2" / "manifest.json"
    )
    unreadable_manifest.mkdir(parents=True)

    store = MetadataStore(tmp_path)
    assert store.reconcile_manifests() == 0
    assert store.list_workbooks() == ()


def test_child_version_moves_head_and_persists_parameters(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child = VersionRecord(
        version_id="version-2",
        file_id=record.file_id,
        parent_version_id="version-1",
        name="多列排序",
        created_at=datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        operation="sort",
        engine=EngineName.PYTHON,
        snapshot_path=tmp_path / "files/file-1/versions/version-2/snapshot.xlsx",
        content_hash=sha256(b"sorted").hexdigest(),
        parameters_json='{"sheet_name":"销售"}',
    )

    store.record_child_version(child, "version-1")

    assert store.get_workbook("file-1").head_version == child
    assert store.list_versions("file-1") == (record.root_version, child)


def test_child_version_rejects_stale_head_without_partial_insert(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child = VersionRecord(
        "version-2",
        record.file_id,
        "version-1",
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        tmp_path / "files/file-1/versions/version-2/snapshot.xlsx",
        sha256(b"sorted").hexdigest(),
    )

    with pytest.raises(ValueError, match="HEAD"):
        store.record_child_version(child, "version-stale")

    assert store.list_versions("file-1") == (record.root_version,)


def test_switch_head_selects_existing_version_without_changing_history(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child = VersionRecord(
        "version-2",
        record.file_id,
        "version-1",
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        tmp_path / "files/file-1/versions/version-2/snapshot.xlsx",
        sha256(b"sorted").hexdigest(),
    )
    store.record_child_version(child, "version-1")

    selected = store.switch_head("file-1", "version-1", "version-2")

    assert selected == record.root_version
    assert store.get_workbook("file-1").head_version == record.root_version
    assert store.list_versions("file-1") == (record.root_version, child)


def test_switch_head_rejects_stale_current_head(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    with pytest.raises(ValueError, match="HEAD"):
        store.switch_head("file-1", "version-1", "version-stale")

    assert store.get_workbook("file-1").head_version == record.root_version


def test_soft_delete_historical_version_preserves_head_and_restore_does_not_move_it(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    root = record.root_version
    assert root is not None
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child = VersionRecord(
        "version-2",
        record.file_id,
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        tmp_path / "files/file-1/versions/version-2/snapshot.xlsx",
        sha256(b"sorted").hexdigest(),
    )
    store.record_child_version(child, root.version_id)

    deleted, replacement = store.soft_delete_version(
        record.file_id,
        root.version_id,
        child.version_id,
        deleted_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
    )

    assert deleted.deleted_at == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    assert replacement is None
    assert store.get_workbook(record.file_id).head_version == child
    restored = store.restore_version(record.file_id, root.version_id)
    assert restored == root
    assert store.get_workbook(record.file_id).head_version == child


def test_soft_delete_head_uses_nearest_undeleted_parent(tmp_path: Path) -> None:
    record = _record(tmp_path)
    root = record.root_version
    assert root is not None
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child = VersionRecord(
        "version-2",
        record.file_id,
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        tmp_path / "files/file-1/versions/version-2/snapshot.xlsx",
        sha256(b"sorted").hexdigest(),
    )
    store.record_child_version(child, root.version_id)

    plan = store.plan_version_deletion(record.file_id, child.version_id)
    deleted, replacement = store.soft_delete_version(
        record.file_id,
        child.version_id,
        child.version_id,
        deleted_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
    )

    assert plan.replacement_candidates == (root,)
    assert deleted.deleted_at is not None
    assert replacement == root
    assert store.get_workbook(record.file_id).head_version == root


def test_soft_delete_root_head_requires_child_choice_when_branches_exist(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    root = record.root_version
    assert root is not None
    store = MetadataStore(tmp_path)
    store.record_import(record)
    children = tuple(
        VersionRecord(
            f"version-{index}",
            record.file_id,
            root.version_id,
            f"分支 {index}",
            datetime(2026, 8, 15, 8 + index, 0, tzinfo=UTC),
            "sort",
            EngineName.PYTHON,
            tmp_path / f"files/file-1/versions/version-{index}/snapshot.xlsx",
            str(index) * 64,
        )
        for index in (2, 3)
    )
    store.record_child_version(children[0], root.version_id)
    store.switch_head(record.file_id, root.version_id, children[0].version_id)
    store.record_child_version(children[1], root.version_id)
    store.switch_head(record.file_id, root.version_id, children[1].version_id)

    plan = store.plan_version_deletion(record.file_id, root.version_id)
    assert plan.replacement_candidates == children
    with pytest.raises(ValueError, match="请选择"):
        store.soft_delete_version(record.file_id, root.version_id, root.version_id)

    _deleted, replacement = store.soft_delete_version(
        record.file_id,
        root.version_id,
        root.version_id,
        children[1].version_id,
    )
    assert replacement == children[1]
    assert store.get_workbook(record.file_id).head_version == children[1]


def test_only_remaining_version_cannot_be_deleted_or_selected_after_deletion(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    with pytest.raises(ValueError, match="只剩一个"):
        store.plan_version_deletion(record.file_id, "version-1")


def test_version_layout_is_persisted_without_changing_version_metadata(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    store.save_version_layout(record.file_id, "version-1", 96.5, 72.0, fixed=True)

    assert MetadataStore(tmp_path).list_version_layouts(record.file_id) == {
        "version-1": VersionLayout(96.5, 72.0, True),
    }
    assert store.get_workbook(record.file_id).head_version == record.root_version


def test_version_layout_rejects_version_from_another_file(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    with pytest.raises(ValueError, match="版本"):
        store.save_version_layout("other-file", "version-1", 10.0, 20.0, fixed=True)


def test_reconcile_known_file_child_version_and_working_copy(tmp_path: Path) -> None:
    record = _record(tmp_path)
    version = record.root_version
    assert version is not None
    record.original_path.parent.mkdir(parents=True)
    record.working_path.parent.mkdir(parents=True)
    version.snapshot_path.parent.mkdir(parents=True)
    record.original_path.write_bytes(b"original")
    record.working_path.write_bytes(b"snapshot")
    version.snapshot_path.write_bytes(b"snapshot")
    store = MetadataStore(tmp_path)
    store.record_import(record)
    child_snapshot = tmp_path / "files/file-1/versions/version-2/snapshot.xlsx"
    child_snapshot.parent.mkdir(parents=True)
    child_snapshot.write_bytes(b"sorted")
    child = VersionRecord(
        "version-2",
        record.file_id,
        version.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        child_snapshot,
        sha256(b"sorted").hexdigest(),
    )
    write_recovery_manifest(
        child_snapshot.parent / "manifest.json",
        tmp_path,
        ImportedWorkbook(
            record.file_id,
            record.display_name,
            record.original_path,
            record.working_path,
            child,
        ),
    )

    assert store.reconcile_manifests() == 1
    assert record.working_path.read_bytes() == b"sorted"
    assert store.get_workbook(record.file_id).head_version == child


def test_reconcile_does_not_reactivate_soft_deleted_manifest_version(tmp_path: Path) -> None:
    record = _record(tmp_path)
    root = record.root_version
    assert root is not None
    for path, content in (
        (record.original_path, b"original"),
        (record.working_path, b"root"),
        (root.snapshot_path, b"snapshot"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    child_snapshot = tmp_path / "files/file-1/versions/version-2/snapshot.xlsx"
    child_snapshot.parent.mkdir(parents=True)
    child_snapshot.write_bytes(b"child")
    child = VersionRecord(
        "version-2",
        record.file_id,
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        EngineName.PYTHON,
        child_snapshot,
        sha256(b"child").hexdigest(),
    )
    write_recovery_manifest(
        child_snapshot.parent / "manifest.json",
        tmp_path,
        ImportedWorkbook(
            record.file_id,
            record.display_name,
            record.original_path,
            record.working_path,
            child,
        ),
    )
    store = MetadataStore(tmp_path)
    store.record_import(record)
    store.record_child_version(child, root.version_id)
    store.soft_delete_version(record.file_id, child.version_id, child.version_id)

    assert store.reconcile_manifests() == 0
    assert store.get_workbook(record.file_id).head_version == root
    assert store.get_version(record.file_id, child.version_id).deleted_at is not None


def test_update_version_meta_edits_name_note_and_milestone(tmp_path: Path) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    store.update_version_meta(
        record.file_id,
        "version-1",
        name="  发货基线  ",
        note="周五发布前确认",
        milestone=True,
    )

    version = store.get_version(record.file_id, "version-1")
    assert version.name == "发货基线"
    assert version.note == "周五发布前确认"
    assert version.milestone is True
    # 内容与父子关系不受元数据编辑影响
    assert version.content_hash == record.head_version.content_hash
    assert version.snapshot_path == record.head_version.snapshot_path
    assert version.parent_version_id is None
    assert store.get_workbook(record.file_id).head_version.version_id == "version-1"


def test_update_version_meta_rejects_blank_name_and_unknown_version(
    tmp_path: Path,
) -> None:
    record = _record(tmp_path)
    store = MetadataStore(tmp_path)
    store.record_import(record)

    with pytest.raises(ValueError, match="名称不能为空"):
        store.update_version_meta(record.file_id, "version-1", name="   ", note="", milestone=False)
    with pytest.raises(ValueError, match="找不到版本记录"):
        store.update_version_meta(record.file_id, "missing", name="x", note="", milestone=False)
    # 失败的更新不落库
    assert store.get_version(record.file_id, "version-1").name == "导入原始文件"


def test_app_settings_roundtrip_and_upsert(tmp_path: Path) -> None:
    store = MetadataStore(tmp_path)

    assert store.get_setting("workspace.current_sheet") is None
    store.set_setting("workspace.current_sheet", "二月")
    assert store.get_setting("workspace.current_sheet") == "二月"
    store.set_setting("workspace.current_sheet", "三月")
    assert store.get_setting("workspace.current_sheet") == "三月"
    store.set_setting("workspace.window_maximized", "1")
    assert store.get_setting("workspace.window_maximized") == "1"
