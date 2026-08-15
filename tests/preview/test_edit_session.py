from PySide6.QtTest import QSignalSpy
from pytestqt.qtbot import QtBot

from hyacinth.preview import EditSession


def test_edit_session_tracks_sparse_changes_and_undo_redo(qtbot: QtBot) -> None:
    session = EditSession()
    changed = QSignalSpy(session.cell_changed)

    session.set_value(
        "销售",
        1,
        0,
        base_value="apple",
        current_value="apple",
        new_value="pear",
    )

    assert session.is_dirty
    assert session.value_at("销售", 1, 0, "apple") == "pear"
    assert session.edits()[0].value == "pear"
    session.undo()
    assert not session.is_dirty
    assert session.value_at("销售", 1, 0, "apple") == "apple"
    session.redo()
    assert session.is_dirty
    assert session.value_at("销售", 1, 0, "apple") == "pear"
    assert changed.count() == 3
