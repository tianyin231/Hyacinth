from dataclasses import dataclass, field
from enum import StrEnum

from hyacinth.excel.contracts import EngineName


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_TASK_STATES = frozenset(
    {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED}
)


@dataclass(frozen=True, slots=True)
class TaskRequest:
    task_id: str
    name: str
    file_id: str
    engine: EngineName
    operation: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: str
    state: TaskState
    name: str
    file_id: str
    engine: EngineName
    progress: float | None = None
    elapsed_seconds: float = 0.0
    message: str = ""
    result: object | None = None
    error_code: str | None = None
    critical: bool = False
