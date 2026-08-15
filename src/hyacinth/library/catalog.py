from pathlib import Path

from hyacinth.library.import_task import ImportedWorkbook


def discover_imported_workbooks(library_root: Path) -> tuple[ImportedWorkbook, ...]:
    files_root = library_root / "files"
    if not files_root.is_dir():
        return ()

    records: list[ImportedWorkbook] = []
    directories = sorted(
        files_root.iterdir(),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for directory in directories:
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
    return tuple(records)
