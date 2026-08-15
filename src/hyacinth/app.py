from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QWidget

from hyacinth.excel.task_handler import CONVERT_XLS_OPERATION, conversion_task_handlers
from hyacinth.library import (
    IMPORT_WORKBOOK_OPERATION,
    FileLibraryWidget,
    ImportedWorkbook,
    discover_imported_workbooks,
    import_task_handlers,
)
from hyacinth.tasks import (
    TaskEvent,
    TaskQueue,
    TaskQueueBridge,
    TaskRequest,
    TaskState,
    TaskStatusWidget,
)
from hyacinth.tasks.qt_bridge import TaskQueuePort


class ApplicationTaskQueue(TaskQueuePort, Protocol):
    def submit(self, request: TaskRequest) -> None: ...


FilePicker = Callable[[QWidget], Path | None]
ErrorPresenter = Callable[[QWidget, str], None]


class HyacinthMainWindow(QMainWindow):
    def __init__(
        self,
        task_queue: ApplicationTaskQueue,
        library_root: Path,
        file_picker: FilePicker,
        error_presenter: ErrorPresenter,
    ) -> None:
        super().__init__()
        self.setObjectName("main-window")
        self.setWindowTitle("风信子")
        self.resize(960, 640)

        workspace = QWidget(self)
        workspace.setObjectName("workspace")
        self.setCentralWidget(workspace)

        self._library_root = library_root
        self._file_picker = file_picker
        self._error_presenter = error_presenter
        self._import_task_ids: set[str] = set()
        self._file_library = FileLibraryWidget(
            discover_imported_workbooks(library_root),
            workspace,
        )
        self._file_library.import_requested.connect(self._choose_import_file)
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._file_library)
        workspace_layout.addStretch(1)

        self._task_queue = task_queue
        self._task_bridge = TaskQueueBridge(task_queue, parent=self)
        self._task_status = TaskStatusWidget(self)
        self._task_bridge.event_received.connect(self._task_status.apply_event)
        self._task_bridge.event_received.connect(self._apply_import_event)
        self._task_status.cancel_requested.connect(self._task_bridge.cancel)

        status_bar = self.statusBar()
        status_bar.setObjectName("main-status-bar")
        status_bar.setSizeGripEnabled(False)
        status_bar.setContentsMargins(0, 0, 0, 0)
        status_bar.addWidget(self._task_status, 1)
        self._task_bridge.start()

    def _choose_import_file(self) -> None:
        source = self._file_picker(self)
        if source is not None:
            self.submit_import(source)

    def submit_import(self, source: Path) -> str:
        task_id = uuid4().hex
        file_id = uuid4().hex
        self._import_task_ids.add(task_id)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=f"导入 {source.name}",
                file_id=file_id,
                engine=None,
                operation=IMPORT_WORKBOOK_OPERATION,
                payload={
                    "source_path": str(source),
                    "library_root": str(self._library_root),
                },
            )
        )
        return task_id

    def _apply_import_event(self, event: TaskEvent) -> None:
        if event.task_id not in self._import_task_ids:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ImportedWorkbook):
            self._file_library.add_workbook(event.result)
            self._import_task_ids.discard(event.task_id)
        elif event.state is TaskState.FAILED:
            self._error_presenter(self, event.message or "导入失败，请重试")
            self._import_task_ids.discard(event.task_id)
        elif event.state is TaskState.CANCELLED:
            self._import_task_ids.discard(event.task_id)

    def submit_conversion(
        self,
        source: Path,
        destination: Path,
        *,
        file_id: str | None = None,
    ) -> str:
        task_id = uuid4().hex
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="转换旧版工作簿",
                file_id=file_id or source.name,
                engine=None,
                operation=CONVERT_XLS_OPERATION,
                payload={
                    "source_path": str(source),
                    "destination_path": str(destination),
                },
            )
        )
        return task_id

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._task_bridge.shutdown(timeout=1.0):
            event.accept()
        else:
            event.ignore()


def create_main_window(
    task_queue: ApplicationTaskQueue | None = None,
    *,
    library_root: Path | None = None,
    file_picker: FilePicker | None = None,
    error_presenter: ErrorPresenter | None = None,
) -> HyacinthMainWindow:
    handlers = conversion_task_handlers()
    handlers.update(import_task_handlers())
    return HyacinthMainWindow(
        task_queue or TaskQueue(handlers),
        library_root or default_library_root(),
        file_picker or select_workbook_file,
        error_presenter or show_import_error,
    )


def default_library_root() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(documents) / "Hyacinth"


def select_workbook_file(parent: QWidget) -> Path | None:
    file_name, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        "导入 Excel 文件",
        "",
        "Excel 工作簿 (*.xlsx *.xls)",
    )
    return Path(file_name) if file_name else None


def show_import_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "导入失败", message)
