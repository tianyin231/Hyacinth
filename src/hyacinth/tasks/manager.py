import multiprocessing
from collections import deque
from collections.abc import Callable, Mapping
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Protocol, cast

from hyacinth.tasks.contracts import (
    TERMINAL_TASK_STATES,
    TaskEvent,
    TaskRequest,
    TaskState,
)
from hyacinth.tasks.worker import CancelFlag, TaskHandler, run_task_worker


class ProcessContext(Protocol):
    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]: ...

    def Event(self) -> CancelFlag: ...

    def Process(
        self,
        *,
        target: Callable[..., object],
        args: tuple[object, ...],
        name: str,
    ) -> BaseProcess: ...


class TaskQueue:
    def __init__(
        self,
        handlers: Mapping[str, TaskHandler],
        *,
        process_context: ProcessContext | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._context = process_context or cast(
            ProcessContext,
            multiprocessing.get_context("spawn"),
        )
        self._pending: deque[TaskRequest] = deque()
        self._local_events: deque[TaskEvent] = deque()
        self._known_task_ids: set[str] = set()
        self._active: TaskRequest | None = None
        self._closed = False
        self._process: BaseProcess | None = None
        self._command_connection: Connection | None = None
        self._event_connection: Connection | None = None
        self._cancel_flag: CancelFlag | None = None
        self._start_worker()

    @property
    def worker_pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    def submit(self, request: TaskRequest) -> None:
        if self._closed:
            raise RuntimeError("任务队列已关闭")
        if request.task_id in self._known_task_ids:
            raise ValueError(f"任务 ID 已存在：{request.task_id}")
        self._known_task_ids.add(request.task_id)
        self._pending.append(request)
        self._local_events.append(_event_for(request, TaskState.QUEUED))
        self._dispatch_next()

    def poll_events(self) -> tuple[TaskEvent, ...]:
        events = list(self._local_events)
        self._local_events.clear()
        connection = self._event_connection
        while connection is not None and connection.poll():
            event = connection.recv()
            if not isinstance(event, TaskEvent):
                continue
            events.append(event)
            if event.state in TERMINAL_TASK_STATES:
                self._active = None
                self._dispatch_next()
        return tuple(events)

    def shutdown(self, timeout: float = 1.0) -> bool:
        if self._closed:
            return True
        self._closed = True
        if self._active is not None:
            return False
        connection = self._command_connection
        process = self._process
        if connection is not None and process is not None and process.is_alive():
            connection.send(None)
            process.join(timeout)
            if process.is_alive():
                process.terminate()
                process.join(timeout)
        self._close_connections()
        return True

    def _start_worker(self) -> None:
        command_receive, command_send = self._context.Pipe(duplex=False)
        event_receive, event_send = self._context.Pipe(duplex=False)
        cancel_flag = self._context.Event()
        process = self._context.Process(
            target=run_task_worker,
            args=(command_receive, event_send, cancel_flag, self._handlers),
            name="hyacinth-task-worker",
        )
        process.start()
        command_receive.close()
        event_send.close()
        self._process = process
        self._command_connection = command_send
        self._event_connection = event_receive
        self._cancel_flag = cancel_flag

    def _dispatch_next(self) -> None:
        if self._active is not None or not self._pending:
            return
        request = self._pending.popleft()
        self._active = request
        if self._cancel_flag is not None:
            self._cancel_flag.clear()
        assert self._command_connection is not None
        self._command_connection.send(request)

    def _close_connections(self) -> None:
        if self._command_connection is not None:
            self._command_connection.close()
        if self._event_connection is not None:
            self._event_connection.close()
        self._command_connection = None
        self._event_connection = None


def _event_for(request: TaskRequest, state: TaskState) -> TaskEvent:
    return TaskEvent(
        task_id=request.task_id,
        state=state,
        name=request.name,
        file_id=request.file_id,
        engine=request.engine,
        elapsed_seconds=0.0,
    )
