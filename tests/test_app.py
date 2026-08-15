import os
import subprocess
import sys

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton
from pytestqt.qtbot import QtBot

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskEvent, TaskRequest, TaskState, TaskStatusWidget


def _child[WidgetT: QObject](parent: QObject, child_type: type[WidgetT], name: str) -> WidgetT:
    child = parent.findChild(child_type, name)
    assert child is not None
    return child


class FakeApplicationTaskQueue:
    def __init__(self, events: list[TaskEvent]) -> None:
        self._events = events
        self.cancelled: list[str] = []
        self.submitted: list[TaskRequest] = []
        self.shutdown_called = False

    def submit(self, request: TaskRequest) -> None:
        self.submitted.append(request)

    def poll_events(self) -> tuple[TaskEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def cancel(self, task_id: str) -> bool:
        self.cancelled.append(task_id)
        return True

    def shutdown(self, timeout: float = 1.0) -> bool:
        self.shutdown_called = True
        return True


def test_create_main_window_uses_product_identity(qtbot: QtBot) -> None:
    try:
        from hyacinth.app import create_main_window
    except ModuleNotFoundError:
        pytest.fail("hyacinth.app.create_main_window is not implemented")

    window = create_main_window()
    qtbot.addWidget(window)

    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "风信子"
    assert window.objectName() == "main-window"


def test_main_runs_qt_event_loop() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from PySide6.QtCore import QTimer; "
                "from PySide6.QtWidgets import QApplication; "
                "from hyacinth.__main__ import main; "
                "app = QApplication.instance() or QApplication([]); "
                "QTimer.singleShot(0, app.quit); "
                "raise SystemExit(main([]))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_main_window_connects_task_queue_to_status_bar(qtbot: QtBot) -> None:
    event = TaskEvent(
        task_id="convert-1",
        state=TaskState.RUNNING,
        name="转换旧版工作簿",
        file_id="销售报表.xls",
        engine=EngineName.COM,
        progress=None,
        elapsed_seconds=1.2,
    )
    task_queue = FakeApplicationTaskQueue([event])

    from hyacinth.app import create_main_window

    window = create_main_window(task_queue=task_queue)
    qtbot.addWidget(window)
    window.show()
    status = _child(window, TaskStatusWidget, "task-status")

    qtbot.waitUntil(
        lambda: _child(status, QLabel, "task-status-state").text() == "处理中",
        timeout=500,
    )
    qtbot.mouseClick(  # type: ignore[no-untyped-call]
        _child(status, QPushButton, "task-status-cancel"),
        Qt.MouseButton.LeftButton,
    )
    window.close()

    assert task_queue.cancelled == ["convert-1"]
    assert task_queue.shutdown_called is True
