from pathlib import Path

from hyacinth.library.catalog import discover_imported_workbooks


def test_discovery_returns_only_complete_published_workbooks(tmp_path: Path) -> None:
    library_root = tmp_path / "library"
    complete = library_root / "files" / "file-complete"
    original = complete / "original" / "销售报表.xlsx"
    working = complete / "working" / "current.xlsx"
    original.parent.mkdir(parents=True)
    working.parent.mkdir(parents=True)
    original.write_bytes(b"original")
    working.write_bytes(b"working")
    incomplete = library_root / "files" / "file-incomplete" / "original"
    incomplete.mkdir(parents=True)
    (incomplete / "未完成.xlsx").write_bytes(b"partial")

    records = discover_imported_workbooks(library_root)

    assert len(records) == 1
    assert records[0].file_id == "file-complete"
    assert records[0].display_name == "销售报表.xlsx"
    assert records[0].original_path == original
    assert records[0].working_path == working
