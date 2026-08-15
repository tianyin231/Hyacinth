from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton
from pytestqt.qtbot import QtBot

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskEvent, TaskState
from hyacinth.tasks.status_widget import TaskStatusWidget


def _child[WidgetT: QObject](parent: QObject, child_type: type[WidgetT], name: str) -> WidgetT:
    child = parent.findChild(child_type, name)
    assert child is not None
    return child


def test_status_widget_displays_running_task_and_requests_cancel(qtbot: QtBot) -> None:
    widget = TaskStatusWidget()
    qtbot.addWidget(widget)
    spy = QSignalSpy(widget.cancel_requested)
    event = TaskEvent(
        task_id="convert-1",
        state=TaskState.RUNNING,
        name="转换旧版工作簿",
        file_id="销售报表.xls",
        engine=EngineName.PYTHON,
        progress=0.4,
        elapsed_seconds=2.4,
        message="正在转换工作表 数据",
    )

    widget.apply_event(event)

    assert _child(widget, QLabel, "task-status-state").text() == "处理中"
    assert _child(widget, QLabel, "task-status-name").text() == "转换旧版工作簿 · 销售报表.xls"
    assert _child(widget, QLabel, "task-status-engine").text() == "Python 兼容模式"
    assert _child(widget, QLabel, "task-status-elapsed").text() == "2.4 秒"
    progress = _child(widget, QProgressBar, "task-status-progress")
    assert progress.value() == 40
    cancel_button = _child(widget, QPushButton, "task-status-cancel")
    assert cancel_button.isEnabled() is True

    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert spy.at(0)[0] == "convert-1"


def test_status_widget_disables_cancel_after_success(qtbot: QtBot) -> None:
    widget = TaskStatusWidget()
    qtbot.addWidget(widget)

    widget.apply_event(
        TaskEvent(
            task_id="convert-1",
            state=TaskState.SUCCEEDED,
            name="转换旧版工作簿",
            file_id="销售报表.xls",
            engine=EngineName.COM,
            progress=1.0,
            elapsed_seconds=3.0,
        )
    )

    assert _child(widget, QLabel, "task-status-state").text() == "已完成"
    assert _child(widget, QLabel, "task-status-engine").text() == "Excel 增强模式"
    assert _child(widget, QProgressBar, "task-status-progress").value() == 100
    assert _child(widget, QPushButton, "task-status-cancel").isEnabled() is False


def test_status_widget_does_not_claim_engine_detection_for_engine_free_task(
    qtbot: QtBot,
) -> None:
    widget = TaskStatusWidget()
    qtbot.addWidget(widget)

    widget.apply_event(
        TaskEvent(
            task_id="preview-1",
            state=TaskState.SUCCEEDED,
            name="加载预览",
            file_id="file-1",
            engine=None,
            progress=1.0,
            elapsed_seconds=0.3,
        )
    )

    assert _child(widget, QLabel, "task-status-engine").text() == "无需引擎"
