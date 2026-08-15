import os
import time
from collections.abc import Callable

import pytest

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskContext, TaskEvent, TaskQueue, TaskRequest, TaskState


def _echo_handler(request: TaskRequest, context: TaskContext) -> object:
    context.report_progress(0.5, "处理中")
    return request.payload["value"]


def _slow_echo_handler(request: TaskRequest, context: TaskContext) -> object:
    time.sleep(0.2)
    return request.payload["value"]


def _cooperative_handler(request: TaskRequest, context: TaskContext) -> object:
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        context.check_cancelled()
        time.sleep(0.01)
    return "finished"


def _uncooperative_handler(request: TaskRequest, context: TaskContext) -> object:
    time.sleep(1.0)
    return "finished"


def _crashing_handler(request: TaskRequest, context: TaskContext) -> object:
    os._exit(7)


def _critical_handler(request: TaskRequest, context: TaskContext) -> object:
    with context.critical_section("正在保存"):
        time.sleep(0.2)
    return "saved"


def _collect_until(
    task_queue: TaskQueue,
    complete: Callable[[list[TaskEvent]], bool],
    *,
    timeout: float = 5.0,
) -> list[TaskEvent]:
    events: list[TaskEvent] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events.extend(task_queue.poll_events())
        if complete(events):
            return events
        time.sleep(0.01)
    raise AssertionError(f"等待任务事件超时：{events!r}")


def test_tasks_run_fifo_in_one_persistent_process() -> None:
    task_queue = TaskQueue({"echo": _echo_handler})
    initial_worker_pid = task_queue.worker_pid
    try:
        for index, engine in enumerate(
            (EngineName.PYTHON, EngineName.COM, EngineName.PYTHON),
        ):
            task_queue.submit(
                TaskRequest(
                    task_id=f"task-{index}",
                    name=f"任务 {index}",
                    file_id="file-1",
                    engine=engine,
                    operation="echo",
                    payload={"value": index},
                )
            )

        events = _collect_until(
            task_queue,
            lambda current: sum(event.state is TaskState.SUCCEEDED for event in current) == 3,
        )

        assert initial_worker_pid is not None
        assert task_queue.worker_pid == initial_worker_pid
        assert [event.task_id for event in events if event.state is TaskState.SUCCEEDED] == [
            "task-0",
            "task-1",
            "task-2",
        ]
        assert [event.result for event in events if event.state is TaskState.SUCCEEDED] == [0, 1, 2]
        assert [event.progress for event in events if event.progress is not None] == [0.5, 0.5, 0.5]
        assert all(event.elapsed_seconds >= 0 for event in events)
    finally:
        assert task_queue.shutdown(timeout=1.0) is True


def test_queued_task_can_be_removed_before_it_starts() -> None:
    task_queue = TaskQueue({"slow-echo": _slow_echo_handler, "echo": _echo_handler})
    try:
        task_queue.submit(
            TaskRequest(
                task_id="active",
                name="当前任务",
                file_id="file-1",
                engine=EngineName.PYTHON,
                operation="slow-echo",
                payload={"value": "active"},
            )
        )
        task_queue.submit(
            TaskRequest(
                task_id="queued",
                name="排队任务",
                file_id="file-1",
                engine=EngineName.COM,
                operation="echo",
                payload={"value": "queued"},
            )
        )

        assert task_queue.remove_queued("queued") is True
        events = _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "active" and event.state is TaskState.SUCCEEDED
                for event in current
            ),
        )

        assert any(
            event.task_id == "queued" and event.state is TaskState.CANCELLED for event in events
        )
        assert not any(
            event.task_id == "queued" and event.state is TaskState.RUNNING for event in events
        )
    finally:
        time.sleep(0.25)
        task_queue.poll_events()
        assert task_queue.shutdown(timeout=1.0) is True


def test_running_task_can_be_cancelled_cooperatively() -> None:
    task_queue = TaskQueue({"cooperative": _cooperative_handler})
    try:
        task_queue.submit(
            TaskRequest(
                task_id="cancel-me",
                name="可取消任务",
                file_id="file-1",
                engine=EngineName.PYTHON,
                operation="cooperative",
            )
        )
        _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "cancel-me" and event.state is TaskState.RUNNING
                for event in current
            ),
        )

        assert task_queue.cancel("cancel-me") is True
        events = _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "cancel-me" and event.state is TaskState.CANCELLED
                for event in current
            ),
        )

        assert any(event.state is TaskState.CANCELLING for event in events)
        assert not any(event.state is TaskState.SUCCEEDED for event in events)
    finally:
        time.sleep(0.4)
        task_queue.poll_events()
        assert task_queue.shutdown(timeout=1.0) is True


def test_unresponsive_task_is_terminated_after_cancel_grace_period() -> None:
    task_queue = TaskQueue(
        {"uncooperative": _uncooperative_handler},
        cancel_grace_seconds=0.05,
    )
    try:
        task_queue.submit(
            TaskRequest(
                task_id="force-cancel-me",
                name="强制取消任务",
                file_id="file-1",
                engine=EngineName.COM,
                operation="uncooperative",
            )
        )
        _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "force-cancel-me" and event.state is TaskState.RUNNING
                for event in current
            ),
        )
        old_worker_pid = task_queue.worker_pid

        assert task_queue.cancel("force-cancel-me") is True
        events = _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "force-cancel-me" and event.state is TaskState.CANCELLED
                for event in current
            ),
        )

        assert old_worker_pid is not None
        assert task_queue.worker_pid is not None
        assert task_queue.worker_pid != old_worker_pid
        assert any(event.state is TaskState.CANCELLED for event in events)
    finally:
        assert task_queue.shutdown(timeout=1.0) is True


def test_worker_crash_fails_current_task_and_continues_queue() -> None:
    task_queue = TaskQueue({"crash": _crashing_handler, "echo": _echo_handler})
    try:
        task_queue.submit(
            TaskRequest(
                task_id="crash-me",
                name="崩溃任务",
                file_id="file-1",
                engine=EngineName.COM,
                operation="crash",
            )
        )
        task_queue.submit(
            TaskRequest(
                task_id="after-crash",
                name="崩溃后任务",
                file_id="file-1",
                engine=EngineName.PYTHON,
                operation="echo",
                payload={"value": "recovered"},
            )
        )

        events = _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "after-crash" and event.state is TaskState.SUCCEEDED
                for event in current
            ),
            timeout=1.0,
        )

        assert any(
            event.task_id == "crash-me"
            and event.state is TaskState.FAILED
            and event.error_code == "worker-exited"
            for event in events
        )
    finally:
        task_queue.shutdown(timeout=1.0)


def test_shutdown_cancels_active_task_before_closing_worker() -> None:
    task_queue = TaskQueue({"cooperative": _cooperative_handler})
    try:
        task_queue.submit(
            TaskRequest(
                task_id="shutdown-me",
                name="退出时取消",
                file_id="file-1",
                engine=EngineName.PYTHON,
                operation="cooperative",
            )
        )
        _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "shutdown-me" and event.state is TaskState.RUNNING
                for event in current
            ),
        )

        assert task_queue.shutdown(timeout=1.0) is True
        with pytest.raises(RuntimeError, match="已关闭"):
            task_queue.submit(
                TaskRequest(
                    task_id="after-shutdown",
                    name="关闭后任务",
                    file_id="file-1",
                    engine=EngineName.PYTHON,
                    operation="cooperative",
                )
            )
    finally:
        time.sleep(0.4)
        task_queue.poll_events()
        task_queue.shutdown(timeout=1.0)


def test_cancel_waits_for_critical_section_to_finish() -> None:
    task_queue = TaskQueue(
        {"critical": _critical_handler},
        cancel_grace_seconds=0.05,
    )
    try:
        task_queue.submit(
            TaskRequest(
                task_id="critical-save",
                name="安全保存",
                file_id="file-1",
                engine=EngineName.COM,
                operation="critical",
            )
        )
        _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "critical-save" and event.critical for event in current
            ),
        )
        old_worker_pid = task_queue.worker_pid

        assert task_queue.cancel("critical-save") is True
        time.sleep(0.1)
        task_queue.poll_events()
        assert task_queue.worker_pid == old_worker_pid

        events = _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "critical-save" and event.state is TaskState.CANCELLED
                for event in current
            ),
        )
        assert any(event.state is TaskState.CANCELLED for event in events)
    finally:
        assert task_queue.shutdown(timeout=1.0) is True


def test_shutdown_force_stops_noncritical_unresponsive_task() -> None:
    task_queue = TaskQueue({"uncooperative": _uncooperative_handler})
    try:
        task_queue.submit(
            TaskRequest(
                task_id="shutdown-force",
                name="退出强制收尾",
                file_id="file-1",
                engine=EngineName.PYTHON,
                operation="uncooperative",
            )
        )
        _collect_until(
            task_queue,
            lambda current: any(
                event.task_id == "shutdown-force" and event.state is TaskState.RUNNING
                for event in current
            ),
        )

        assert task_queue.shutdown(timeout=0.05) is True
        assert task_queue.worker_pid is None
    finally:
        time.sleep(1.1)
        task_queue.poll_events()
        task_queue.shutdown(timeout=1.0)
