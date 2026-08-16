from pathlib import Path

from hyacinth.versioning import ImportedWorkbook, MetadataStore


def discover_imported_workbooks(library_root: Path) -> tuple[ImportedWorkbook, ...]:
    store = MetadataStore(library_root)
    store.reconcile_manifests()
    stored_records = [
        record
        for record in store.list_workbooks()
        if record.original_path.is_file()
        and record.working_path.is_file()
        and record.root_version is not None
        and record.root_version.snapshot_path.is_file()
    ]
    known_ids = {record.file_id for record in stored_records}
    # 已软删除的文件目录仍由数据库管理，不能再被只读发现当作旧记录恢复显示。
    known_ids.update(record.file_id for record in store.list_deleted_files())
    files_root = library_root / "files"
    if not files_root.is_dir():
        return tuple(stored_records)

    records: list[ImportedWorkbook] = []
    directories = sorted(
        files_root.iterdir(),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for directory in directories:
        if directory.name in known_ids or directory.name.startswith("."):
            continue
        original_directory = directory / "original"
        working = directory / "working" / "current.xlsx"
        if not directory.is_dir() or not original_directory.is_dir() or not working.is_file():
            continue
        originals = [path for path in original_directory.iterdir() if path.is_file()]
        if len(originals) != 1:
            continue
        original = originals[0]
        records.append(
            ImportedWorkbook(
                file_id=directory.name,
                display_name=original.name,
                original_path=original,
                working_path=working,
            )
        )
    return tuple((*stored_records, *records))
