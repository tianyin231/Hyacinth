from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QWidget,
)

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks.contracts import TERMINAL_TASK_STATES, TaskEvent, TaskState

_STATE_LABELS = {
    TaskState.QUEUED: "等待中",
    TaskState.RUNNING: "处理中",
    TaskState.CANCELLING: "正在取消",
    TaskState.SUCCEEDED: "已完成",
    TaskState.FAILED: "失败",
    TaskState.CANCELLED: "已取消",
}

_STATE_COLORS = {
    TaskState.QUEUED: "#4B5563",
    TaskState.RUNNING: "#0F6CBD",
    TaskState.CANCELLING: "#9A6700",
    TaskState.SUCCEEDED: "#107C10",
    TaskState.FAILED: "#C42B1C",
    TaskState.CANCELLED: "#4B5563",
}

_ENGINE_LABELS = {
    EngineName.COM: "Excel 增强模式",
    EngineName.PYTHON: "Python 兼容模式",
}


class TaskStatusWidget(QWidget):
    cancel_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("task-status")
        self.setFixedHeight(34)
        self._active_task_id: str | None = None

        self._state = QLabel("就绪", self)
        self._state.setObjectName("task-status-state")
        self._state.setFixedWidth(72)

        self._name = QLabel("没有正在执行的任务", self)
        self._name.setObjectName("task-status-name")
        self._name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._progress = QProgressBar(self)
        self._progress.setObjectName("task-status-progress")
        self._progress.setFixedSize(160, 8)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)

        self._engine = QLabel("引擎待命", self)
        self._engine.setObjectName("task-status-engine")
        self._engine.setFixedWidth(112)

        self._elapsed = QLabel("0.0 秒", self)
        self._elapsed.setObjectName("task-status-elapsed")
        self._elapsed.setFixedWidth(56)

        self._cancel = QPushButton(self)
        self._cancel.setObjectName("task-status-cancel")
        self._cancel.setFixedSize(28, 28)
        self._cancel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self._cancel.setToolTip("取消当前任务")
        self._cancel.setAccessibleName("取消当前任务")
        self._cancel.setEnabled(False)
        self._cancel.clicked.connect(self._request_cancel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(self._state)
        layout.addWidget(self._name, 1)
        layout.addWidget(self._progress)
        layout.addWidget(self._engine)
        layout.addWidget(self._elapsed)
        layout.addWidget(self._cancel)

        self.setStyleSheet(
            """
            QWidget#task-status {
                background: #F8FAFC;
                border-top: 1px solid #D8DEE8;
                color: #242424;
            }
            QLabel#task-status-state { font-weight: 600; }
            QLabel#task-status-engine, QLabel#task-status-elapsed { color: #5C6370; }
            QProgressBar#task-status-progress {
                background: #E5EAF1;
                border: 0;
                border-radius: 4px;
            }
            QProgressBar#task-status-progress::chunk {
                background: #0F6CBD;
                border-radius: 4px;
            }
            QPushButton#task-status-cancel {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton#task-status-cancel:hover:enabled {
                background: #E8EDF4;
                border-color: #C7CFDB;
            }
            QPushButton#task-status-cancel:focus {
                border-color: #0F6CBD;
            }
            """
        )

    def apply_event(self, event: TaskEvent) -> None:
        self._active_task_id = event.task_id
        self._state.setText(_STATE_LABELS[event.state])
        self._set_state_color(_STATE_COLORS[event.state])
        self._name.setText(f"{event.name} · {event.file_id}")
        self._name.setToolTip(event.message)
        if event.engine is None:
            engine_label = "无需引擎" if event.state in TERMINAL_TASK_STATES else "准备中"
        else:
            engine_label = _ENGINE_LABELS[event.engine]
        self._engine.setText(engine_label)
        self._elapsed.setText(f"{event.elapsed_seconds:.1f} 秒")

        if event.progress is None:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 100)
            self._progress.setValue(round(event.progress * 100))
        if event.state is TaskState.SUCCEEDED:
            self._progress.setRange(0, 100)
            self._progress.setValue(100)

        self._cancel.setEnabled(
            event.state not in TERMINAL_TASK_STATES and event.state is not TaskState.CANCELLING
        )

    def _request_cancel(self) -> None:
        if self._active_task_id is not None:
            self.cancel_requested.emit(self._active_task_id)

    def _set_state_color(self, color: str) -> None:
        palette = self._state.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
        self._state.setPalette(palette)
