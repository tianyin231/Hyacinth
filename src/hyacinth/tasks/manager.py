import multiprocessing
import time
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
        cancel_grace_seconds: float = 5.0,
    ) -> None:
        if cancel_grace_seconds <= 0:
            raise ValueError("取消宽限时间必须大于 0")
        self._handlers = dict(handlers)
        self._context = process_context or cast(
            ProcessContext,
            multiprocessing.get_context("spawn"),
        )
        self._pending: deque[TaskRequest] = deque()
        self._local_events: deque[TaskEvent] = deque()
        self._known_task_ids: set[str] = set()
        self._active: TaskRequest | None = None
        self._cancelling = False
        self._cancel_started_at: float | None = None
        self._active_critical = False
        self._cancel_grace_seconds = cancel_grace_seconds
        self._closed = False
        self._accepting = True
        self._shutting_down = False
        self._process: BaseProcess | None = None
        self._command_connection: Connection | None = None
        self._event_connection: Connection | None = None
        self._cancel_flag: CancelFlag | None = None
        self._start_worker()

    @property
    def worker_pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    def submit(self, request: TaskRequest) -> None:
        if not self._accepting:
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
        while connection is not None:
            try:
                has_event = connection.poll()
            except (EOFError, OSError):
                break
            if not has_event:
                break
            try:
                event = connection.recv()
            except (EOFError, OSError):
                break
            if not isinstance(event, TaskEvent):
                continue
            events.append(event)
            self._active_critical = event.critical
            if event.state in TERMINAL_TASK_STATES:
                self._known_task_ids.discard(event.task_id)
                self._active = None
                self._active_critical = False
                self._dispatch_next()
        self._recover_from_worker_exit()
        self._terminate_unresponsive_active_task_if_needed()
        return tuple(events)

    def cancel(self, task_id: str) -> bool:
        if self._closed:
            return False
        if self._active is not None and self._active.task_id == task_id:
            if self._cancelling:
                return True
            self._cancelling = True
            self._cancel_started_at = time.monotonic()
            if self._cancel_flag is not None:
                self._cancel_flag.set()
            self._local_events.append(
                _event_for(self._active, TaskState.CANCELLING, message="正在请求取消")
            )
            return True
        return self.remove_queued(task_id)

    def remove_queued(self, task_id: str) -> bool:
        for request in tuple(self._pending):
            if request.task_id != task_id:
                continue
            self._pending.remove(request)
            self._known_task_ids.discard(task_id)
            self._local_events.append(
                _event_for(request, TaskState.CANCELLED, message="已从队列移除")
            )
            return True
        return False

    def shutdown(self, timeout: float = 1.0) -> bool:
        if self._closed:
            return True
        self._accepting = False
        self._shutting_down = True
        for request in tuple(self._pending):
            self.remove_queued(request.task_id)
        if self._active is not None:
            self.cancel(self._active.task_id)
            deadline = time.monotonic() + timeout
            while self._active is not None and time.monotonic() < deadline:
                self.poll_events()
                time.sleep(0.01)
            if self._active is not None:
                if self._active_critical:
                    return False
                self._force_cancel_active_task("退出超时，已终止后台 Worker")
        self._closed = True
        connection = self._command_connection
        process = self._process
        if connection is not None and process is not None and process.is_alive():
            try:
                connection.send(None)
            except (EOFError, OSError):
                pass
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

    def _terminate_unresponsive_active_task_if_needed(self) -> None:
        if (
            self._active is None
            or not self._cancelling
            or self._active_critical
            or self._cancel_started_at is None
            or time.monotonic() - self._cancel_started_at < self._cancel_grace_seconds
        ):
            return
        self._force_cancel_active_task("取消超时，已重建后台 Worker")
        if self._closed or self._shutting_down:
            return
        self._start_worker()
        self._dispatch_next()

    def _force_cancel_active_task(self, message: str) -> None:
        assert self._active is not None
        request = self._active
        process = self._process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(self._cancel_grace_seconds)
        self._close_connections()
        self._process = None
        self._known_task_ids.discard(request.task_id)
        self._active = None
        self._cancelling = False
        self._cancel_started_at = None
        self._active_critical = False
        self._local_events.append(_event_for(request, TaskState.CANCELLED, message=message))

    def _recover_from_worker_exit(self) -> None:
        process = self._process
        if process is None or process.is_alive():
            return
        request = self._active
        self._close_connections()
        self._process = None
        if request is not None:
            self._known_task_ids.discard(request.task_id)
        self._active = None
        self._cancelling = False
        self._cancel_started_at = None
        self._active_critical = False
        if request is not None:
            self._local_events.append(
                _event_for(
                    request,
                    TaskState.FAILED,
                    message="后台 Worker 异常退出",
                    error_code="worker-exited",
                )
            )
        if not self._closed and not self._shutting_down:
            self._start_worker()
            self._dispatch_next()

    def _dispatch_next(self) -> None:
        if self._active is not None or not self._pending or self._shutting_down:
            return
        request = self._pending.popleft()
        self._active = request
        self._cancelling = False
        self._cancel_started_at = None
        self._active_critical = False
        if self._cancel_flag is not None:
            self._cancel_flag.clear()
        assert self._command_connection is not None
        try:
            self._command_connection.send(request)
        except (EOFError, OSError):
            self._known_task_ids.discard(request.task_id)
            self._active = None
            self._close_connections()
            self._process = None
            self._cancelling = False
            self._cancel_started_at = None
            self._active_critical = False
            self._local_events.append(
                _event_for(
                    request,
                    TaskState.FAILED,
                    message="后台 Worker 在派发任务时退出",
                    error_code="worker-exited",
                )
            )
            if not self._closed and not self._shutting_down:
                self._start_worker()
                self._dispatch_next()

    def _close_connections(self) -> None:
        if self._command_connection is not None:
            self._command_connection.close()
        if self._event_connection is not None:
            self._event_connection.close()
        self._command_connection = None
        self._event_connection = None


def _event_for(
    request: TaskRequest,
    state: TaskState,
    *,
    message: str = "",
    error_code: str | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=request.task_id,
        state=state,
        name=request.name,
        file_id=request.file_id,
        engine=request.engine,
        elapsed_seconds=0.0,
        message=message,
        error_code=error_code,
    )
