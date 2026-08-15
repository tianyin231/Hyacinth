import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from multiprocessing.connection import Connection
from typing import Protocol

from hyacinth.excel.contracts import EngineName
from hyacinth.tasks.contracts import TaskEvent, TaskRequest, TaskState


class CancelFlag(Protocol):
    def is_set(self) -> bool: ...

    def clear(self) -> None: ...

    def set(self) -> None: ...


class EventSender(Protocol):
    def send(self, value: object) -> None: ...


class TaskCancelled(Exception):
    pass


class TaskContext:
    def __init__(
        self,
        request: TaskRequest,
        send_event: Callable[[TaskEvent], None],
        cancel_flag: CancelFlag,
        started_at: float,
    ) -> None:
        self._request = request
        self._engine = request.engine
        self._send_event = send_event
        self._cancel_flag = cancel_flag
        self._started_at = started_at
        self._committed = False

    def report_progress(self, progress: float | None, message: str = "") -> None:
        self._send_event(self._event(TaskState.RUNNING, progress=progress, message=message))

    def set_engine(self, engine: EngineName) -> None:
        self._engine = engine

    def cancel_requested(self) -> bool:
        return self._cancel_flag.is_set()

    def check_cancelled(self) -> None:
        if not self._committed and self.cancel_requested():
            raise TaskCancelled

    def commit(self) -> None:
        self.check_cancelled()
        self._committed = True

    @contextmanager
    def critical_section(self, message: str = "正在安全收尾") -> Iterator[None]:
        self._send_event(self._event(TaskState.RUNNING, message=message, critical=True))
        try:
            yield
        finally:
            self._send_event(self._event(TaskState.RUNNING, critical=False))
        self.check_cancelled()

    def _event(
        self,
        state: TaskState,
        *,
        progress: float | None = None,
        message: str = "",
        result: object | None = None,
        error_code: str | None = None,
        critical: bool = False,
    ) -> TaskEvent:
        return TaskEvent(
            task_id=self._request.task_id,
            state=state,
            name=self._request.name,
            file_id=self._request.file_id,
            engine=self._engine,
            progress=progress,
            elapsed_seconds=time.monotonic() - self._started_at,
            message=message,
            result=result,
            error_code=error_code,
            critical=critical,
        )


TaskHandler = Callable[[TaskRequest, TaskContext], object]


def run_task_worker(
    command_connection: Connection,
    event_connection: Connection,
    cancel_flag: CancelFlag,
    handlers: Mapping[str, TaskHandler],
) -> None:
    while True:
        request = command_connection.recv()
        if request is None:
            return
        if not isinstance(request, TaskRequest):
            continue
        _execute(request, event_connection, cancel_flag, handlers)


def _execute(
    request: TaskRequest,
    event_connection: EventSender,
    cancel_flag: CancelFlag,
    handlers: Mapping[str, TaskHandler],
) -> None:
    started_at = time.monotonic()
    context = TaskContext(request, event_connection.send, cancel_flag, started_at)
    event_connection.send(context._event(TaskState.RUNNING))
    try:
        handler = handlers[request.operation]
    except KeyError:
        event_connection.send(
            context._event(
                TaskState.FAILED,
                message=f"未知任务操作：{request.operation}",
                error_code="unknown-operation",
            )
        )
        return
    try:
        result = handler(request, context)
        context.check_cancelled()
    except TaskCancelled:
        event_connection.send(context._event(TaskState.CANCELLED))
    except Exception as error:
        event_connection.send(
            context._event(
                TaskState.FAILED,
                message=str(error),
                error_code="task-error",
            )
        )
    else:
        event_connection.send(context._event(TaskState.SUCCEEDED, result=result))
