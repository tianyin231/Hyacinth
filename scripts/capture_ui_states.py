import argparse
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QComboBox

from hyacinth.app import ApplicationTaskQueue, create_main_window
from hyacinth.excel.contracts import EngineName
from hyacinth.preview import run_preview_index_task
from hyacinth.tasks import TaskEvent, TaskRequest, TaskState
from hyacinth.versioning import ImportedWorkbook, MetadataStore, VersionRecord


class CaptureTaskQueue(ApplicationTaskQueue):
    def __init__(self) -> None:
        self.events: list[TaskEvent] = []
        self.submitted: list[TaskRequest] = []

    def submit(self, request: TaskRequest) -> None:
        self.submitted.append(request)

    def poll_events(self) -> tuple[TaskEvent, ...]:
        events = tuple(self.events)
        self.events.clear()
        return events

    def cancel(self, task_id: str) -> bool:
        return True

    def shutdown(self, timeout: float = 1.0) -> bool:
        return True


class CaptureTaskContext:
    def report_progress(self, progress: float | None, message: str = "") -> None:
        return

    def check_cancelled(self) -> None:
        return

    def set_engine(self, engine: EngineName) -> None:
        return

    def commit(self) -> None:
        return

    @contextmanager
    def critical_section(self, message: str = "") -> Iterator[None]:
        yield


def _seed_workbook(library_root: Path) -> None:
    directory = library_root / "files" / "visual-file"
    original = directory / "original" / "销售报表.xlsx"
    working = directory / "working" / "current.xlsx"
    snapshot = directory / "versions" / "root-version" / "snapshot.xlsx"
    for path in (original, working, snapshot):
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "销售明细"
        sheet.append(["日期", "商品", "数量", "销售额"])
        sheet.append(["2026/08/12", "苹果", 12, 360])
        sheet.append(["2026/08/12", "蓝莓", 5, 240])
        sheet.append(["2026/08/13", "西瓜", 18, 482.4])
        workbook.save(path)
        workbook.close()
    version = VersionRecord(
        "root-version",
        "visual-file",
        None,
        "导入原始文件",
        datetime.now(UTC),
        "import",
        None,
        snapshot,
        sha256(snapshot.read_bytes()).hexdigest(),
    )
    MetadataStore(library_root).record_import(
        ImportedWorkbook(
            "visual-file",
            "销售报表.xlsx",
            original,
            working,
            version,
        )
    )


def _wait(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def capture_ui_states(output_directory: Path) -> tuple[Path, Path, Path]:
    app = QApplication.instance() or QApplication([])
    output_directory.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix="hyacinth-empty-") as empty_directory,
        tempfile.TemporaryDirectory(prefix="hyacinth-populated-") as populated_directory,
    ):
        empty_window = create_main_window(
            task_queue=CaptureTaskQueue(),
            library_root=Path(empty_directory),
        )
        empty_window.show()
        app.processEvents()
        empty_path = output_directory / "default-empty-state.png"
        if not empty_window.grab().save(str(empty_path)):
            raise RuntimeError("无法保存默认空状态截图")
        empty_window.close()

        populated_root = Path(populated_directory)
        _seed_workbook(populated_root)
        task_queue = CaptureTaskQueue()
        populated_window = create_main_window(
            task_queue=task_queue,
            library_root=populated_root,
        )
        populated_window.show()
        app.processEvents()
        request = task_queue.submitted[0]
        preview = run_preview_index_task(request, CaptureTaskContext())
        task_queue.events.append(
            TaskEvent(
                request.task_id,
                TaskState.SUCCEEDED,
                request.name,
                request.file_id,
                EngineName.PYTHON,
                result=preview,
            )
        )
        _wait(150)
        app.processEvents()
        populated_path = output_directory / "fluent-shell-populated.png"
        if not populated_window.grab().save(str(populated_path)):
            raise RuntimeError("无法保存有数据状态截图")
        operation = populated_window.findChild(QComboBox, "processing-operation")
        if operation is None:
            raise RuntimeError("找不到处理功能选择器")
        operation.setCurrentIndex(operation.findData("deduplicate"))
        app.processEvents()
        deduplicate_path = output_directory / "deduplicate-configured.png"
        if not populated_window.grab().save(str(deduplicate_path)):
            raise RuntimeError("无法保存删除重复行配置截图")
        populated_window.close()
    return empty_path, populated_path, deduplicate_path


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取风信子默认、有数据与去重配置界面状态")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/playwright"),
        help="截图输出目录",
    )
    arguments = parser.parse_args()
    for path in capture_ui_states(arguments.output):
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
