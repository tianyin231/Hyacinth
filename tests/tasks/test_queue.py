import time
from collections.abc import Callable

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks import TaskContext, TaskEvent, TaskQueue, TaskRequest, TaskState


def _echo_handler(request: TaskRequest, context: TaskContext) -> object:
    context.report_progress(0.5, "处理中")
    return request.payload["value"]


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
        assert [
            event.task_id for event in events if event.state is TaskState.SUCCEEDED
        ] == ["task-0", "task-1", "task-2"]
        assert [
            event.result for event in events if event.state is TaskState.SUCCEEDED
        ] == [0, 1, 2]
        assert [
            event.progress for event in events if event.progress is not None
        ] == [0.5, 0.5, 0.5]
        assert all(event.elapsed_seconds >= 0 for event in events)
    finally:
        assert task_queue.shutdown(timeout=1.0) is True
