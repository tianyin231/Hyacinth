from PySide6.QtTest import QSignalSpy
from pytestqt.qtbot import QtBot

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskEvent, TaskState
from hyacinth.tasks.qt_bridge import TaskQueueBridge


class FakeTaskQueue:
    def __init__(self, events: list[TaskEvent]) -> None:
        self._events = events
        self.cancelled: list[str] = []
        self.shutdown_timeout: float | None = None

    def poll_events(self) -> tuple[TaskEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def cancel(self, task_id: str) -> bool:
        self.cancelled.append(task_id)
        return True

    def shutdown(self, timeout: float = 1.0) -> bool:
        self.shutdown_timeout = timeout
        return True


def test_qt_bridge_polls_and_emits_task_events(qtbot: QtBot) -> None:
    event = TaskEvent(
        task_id="convert-1",
        state=TaskState.RUNNING,
        name="转换工作簿",
        file_id="file-1",
        engine=EngineName.PYTHON,
        progress=0.5,
    )
    task_queue = FakeTaskQueue([event])
    bridge = TaskQueueBridge(task_queue, poll_interval_ms=10)
    spy = QSignalSpy(bridge.event_received)

    bridge.start()
    qtbot.waitUntil(lambda: spy.count() == 1, timeout=500)

    assert spy.at(0)[0] == event
    assert bridge.cancel("convert-1") is True
    assert task_queue.cancelled == ["convert-1"]
    assert bridge.shutdown(timeout=0.25) is True
    assert task_queue.shutdown_timeout == 0.25
    assert bridge.is_running is False
