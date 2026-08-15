from pathlib import Path
from typing import Protocol
from uuid import uuid4

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QWidget

from hyacinth.excel.task_handler import CONVERT_XLS_OPERATION, conversion_task_handlers
from hyacinth.tasks import (
    TaskQueue,
    TaskQueueBridge,
    TaskRequest,
    TaskStatusWidget,
)
from hyacinth.tasks.qt_bridge import TaskQueuePort


class ApplicationTaskQueue(TaskQueuePort, Protocol):
    def submit(self, request: TaskRequest) -> None: ...


class HyacinthMainWindow(QMainWindow):
    def __init__(self, task_queue: ApplicationTaskQueue) -> None:
        super().__init__()
        self.setObjectName("main-window")
        self.setWindowTitle("风信子")
        self.resize(960, 640)

        workspace = QWidget(self)
        workspace.setObjectName("workspace")
        self.setCentralWidget(workspace)

        self._task_queue = task_queue
        self._task_bridge = TaskQueueBridge(task_queue, parent=self)
        self._task_status = TaskStatusWidget(self)
        self._task_bridge.event_received.connect(self._task_status.apply_event)
        self._task_status.cancel_requested.connect(self._task_bridge.cancel)

        status_bar = self.statusBar()
        status_bar.setObjectName("main-status-bar")
        status_bar.setSizeGripEnabled(False)
        status_bar.setContentsMargins(0, 0, 0, 0)
        status_bar.addWidget(self._task_status, 1)
        self._task_bridge.start()

    def submit_conversion(
        self,
        source: Path,
        destination: Path,
        *,
        file_id: str | None = None,
    ) -> str:
        task_id = uuid4().hex
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="转换旧版工作簿",
                file_id=file_id or source.name,
                engine=None,
                operation=CONVERT_XLS_OPERATION,
                payload={
                    "source_path": str(source),
                    "destination_path": str(destination),
                },
            )
        )
        return task_id

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._task_bridge.shutdown(timeout=1.0):
            event.accept()
        else:
            event.ignore()


def create_main_window(
    task_queue: ApplicationTaskQueue | None = None,
) -> HyacinthMainWindow:
    return HyacinthMainWindow(task_queue or TaskQueue(conversion_task_handlers()))
