from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack


@dataclass(frozen=True, slots=True)
class CellEdit:
    sheet_name: str
    row: int
    column: int
    value: object


class _CellEditCommand(QUndoCommand):
    def __init__(
        self,
        session: "EditSession",
        key: tuple[str, int, int],
        before: object,
        after: object,
    ) -> None:
        super().__init__(f"编辑 {key[0]}!{key[1] + 1}")
        self._session = session
        self._key = key
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._session._apply_value(self._key, self._after)

    def undo(self) -> None:
        self._session._apply_value(self._key, self._before)


class EditSession(QObject):
    cell_changed = Signal(str, int, int)
    state_changed = Signal(bool, bool, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._base_values: dict[tuple[str, int, int], object] = {}
        self._edits: dict[tuple[str, int, int], object] = {}
        self._undo_stack = QUndoStack(self)
        self._undo_stack.canUndoChanged.connect(self._emit_state)
        self._undo_stack.canRedoChanged.connect(self._emit_state)

    @property
    def is_dirty(self) -> bool:
        return bool(self._edits)

    def value_at(self, sheet_name: str, row: int, column: int, fallback: object) -> object:
        return self._edits.get((sheet_name, row, column), fallback)

    def set_value(
        self,
        sheet_name: str,
        row: int,
        column: int,
        *,
        base_value: object,
        current_value: object,
        new_value: object,
    ) -> None:
        if new_value == current_value:
            return
        key = (sheet_name, row, column)
        self._base_values.setdefault(key, base_value)
        self._undo_stack.push(_CellEditCommand(self, key, current_value, new_value))

    def edits(self) -> tuple[CellEdit, ...]:
        return tuple(
            CellEdit(sheet_name, row, column, value)
            for (sheet_name, row, column), value in sorted(self._edits.items())
        )

    def undo(self) -> None:
        self._undo_stack.undo()

    def redo(self) -> None:
        self._undo_stack.redo()

    def clear(self) -> None:
        changed_cells = tuple(self._edits)
        self._edits.clear()
        self._base_values.clear()
        self._undo_stack.clear()
        for sheet_name, row, column in changed_cells:
            self.cell_changed.emit(sheet_name, row, column)
        self._emit_state()

    def _apply_value(self, key: tuple[str, int, int], value: object) -> None:
        if value == self._base_values[key]:
            self._edits.pop(key, None)
        else:
            self._edits[key] = value
        self.cell_changed.emit(*key)
        self._emit_state()

    def _emit_state(self, _value: bool | None = None) -> None:
        self.state_changed.emit(
            self.is_dirty,
            self._undo_stack.canUndo(),
            self._undo_stack.canRedo(),
        )
