from hyacinth.tasks import TaskEvent, TaskRequest, TaskState
from hyacinth.tasks.worker import TaskContext, _execute


class RecordingConnection:
    def __init__(self) -> None:
        self.events: list[TaskEvent] = []

    def send(self, value: object) -> None:
        assert isinstance(value, TaskEvent)
        self.events.append(value)


class MutableCancelFlag:
    def __init__(self) -> None:
        self.value = False

    def is_set(self) -> bool:
        return self.value

    def clear(self) -> None:
        self.value = False

    def set(self) -> None:
        self.value = True


def test_worker_reports_success_when_cancel_arrives_after_commit() -> None:
    request = TaskRequest(
        task_id="commit-1",
        name="提交任务",
        file_id="file-1",
        engine=None,
        operation="commit",
    )
    connection = RecordingConnection()
    cancel_flag = MutableCancelFlag()

    def commit_then_cancel(_request: TaskRequest, context: TaskContext) -> object:
        context.commit()
        cancel_flag.set()
        return "published"

    _execute(request, connection, cancel_flag, {"commit": commit_then_cancel})

    assert connection.events[-1].state is TaskState.SUCCEEDED
    assert connection.events[-1].result == "published"
