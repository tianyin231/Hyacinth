from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from hyacinth.tasks.contracts import TaskEvent


class TaskQueuePort(Protocol):
    def poll_events(self) -> tuple[TaskEvent, ...]: ...

    def cancel(self, task_id: str) -> bool: ...

    def shutdown(self, timeout: float = 1.0) -> bool: ...


class TaskQueueBridge(QObject):
    event_received = Signal(object)

    def __init__(
        self,
        task_queue: TaskQueuePort,
        *,
        poll_interval_ms: int = 50,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._task_queue = task_queue
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self.poll_once)

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._timer.start()

    def poll_once(self) -> None:
        for event in self._task_queue.poll_events():
            self.event_received.emit(event)

    def cancel(self, task_id: str) -> bool:
        return self._task_queue.cancel(task_id)

    def shutdown(self, timeout: float = 1.0) -> bool:
        self._timer.stop()
        self.poll_once()
        return self._task_queue.shutdown(timeout)
