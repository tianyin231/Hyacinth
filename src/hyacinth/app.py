from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hyacinth.excel.task_handler import CONVERT_XLS_OPERATION, conversion_task_handlers
from hyacinth.library import (
    IMPORT_WORKBOOK_OPERATION,
    FileLibraryWidget,
    ImportedWorkbook,
    discover_imported_workbooks,
    import_task_handlers,
)
from hyacinth.preview import (
    BUILD_PREVIEW_INDEX_OPERATION,
    WorkbookPreview,
    WorkbookPreviewWidget,
    preview_index_path,
    preview_task_handlers,
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
from hyacinth.ui import (
    APP_STYLESHEET,
    ApplicationHeader,
    CommandBar,
    FunctionPanel,
    VersionTreePanel,
    WorkbookEditorFrame,
)


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
        self.resize(1280, 760)
        self.setMinimumSize(1024, 640)
        self.setStyleSheet(APP_STYLESHEET)

        workspace_root = QWidget(self)
        workspace_root.setObjectName("workspace-root")
        self.setCentralWidget(workspace_root)

        self._library_root = library_root
        self._file_picker = file_picker
        self._error_presenter = error_presenter
        self._task_queue = task_queue
        self._import_task_ids: set[str] = set()
        self._preview_task_id: str | None = None

        self._application_header = ApplicationHeader(workspace_root)
        self._command_bar = CommandBar(workspace_root)
        self._command_bar.import_requested.connect(self._choose_import_file)
        self._function_panel = FunctionPanel(workspace_root)
        self._file_library = FileLibraryWidget(
            discover_imported_workbooks(library_root),
            workspace_root,
        )
        self._file_library.workbook_selected.connect(self._select_workbook)
        self._version_tree = VersionTreePanel(workspace_root)
        self._workbook_preview = WorkbookPreviewWidget(workspace_root)
        editor = WorkbookEditorFrame(self._workbook_preview, workspace_root)

        left_splitter = QSplitter(Qt.Orientation.Vertical, workspace_root)
        left_splitter.setObjectName("left-workspace-splitter")
        left_splitter.addWidget(self._function_panel)
        left_splitter.addWidget(self._file_library)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 2)
        left_splitter.setSizes([330, 210])

        main_splitter = QSplitter(Qt.Orientation.Horizontal, workspace_root)
        main_splitter.setObjectName("main-workspace-splitter")
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self._version_tree)
        main_splitter.addWidget(editor)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 0)
        main_splitter.setStretchFactor(2, 1)
        main_splitter.setSizes([260, 340, 680])

        workspace_layout = QVBoxLayout(workspace_root)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._application_header)
        workspace_layout.addWidget(self._command_bar)
        workspace_layout.addWidget(main_splitter, 1)

        self._task_bridge = TaskQueueBridge(task_queue, parent=self)
        self._task_status = TaskStatusWidget(self)
        self._task_bridge.event_received.connect(self._task_status.apply_event)
        self._task_bridge.event_received.connect(self._apply_import_event)
        self._task_bridge.event_received.connect(self._apply_preview_event)
        self._task_status.cancel_requested.connect(self._task_bridge.cancel)

        status_bar = self.statusBar()
        status_bar.setObjectName("main-status-bar")
        status_bar.setSizeGripEnabled(False)
        status_bar.setContentsMargins(0, 0, 0, 0)
        status_bar.addWidget(self._task_status, 1)
        self._task_bridge.start()
        current_workbook = self._file_library.current_workbook()
        if current_workbook is not None:
            self._select_workbook(current_workbook)

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

    def _select_workbook(self, workbook: ImportedWorkbook) -> None:
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
        self.setWindowTitle(f"风信子 — {workbook.display_name}")
        self._application_header.set_document_name(workbook.display_name)
        self._version_tree.set_workbook(workbook.display_name, workbook.root_version)
        task_id = uuid4().hex
        self._preview_task_id = task_id
        self._workbook_preview.set_loading(workbook.display_name)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=f"加载 {workbook.display_name}",
                file_id=workbook.file_id,
                engine=None,
                operation=BUILD_PREVIEW_INDEX_OPERATION,
                payload={
                    "working_path": str(workbook.working_path),
                    "index_path": str(preview_index_path(workbook.working_path)),
                },
            )
        )

    def _apply_preview_event(self, event: TaskEvent) -> None:
        if event.task_id != self._preview_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, WorkbookPreview):
            self._workbook_preview.show_preview(event.result)
            self._preview_task_id = None
        elif event.state is TaskState.FAILED:
            self._workbook_preview.set_error(event.message or "工作簿无法打开")
            self._preview_task_id = None
        elif event.state is TaskState.CANCELLED:
            self._workbook_preview.set_error("加载已取消，可重新选择文件")
            self._preview_task_id = None

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
            self._workbook_preview.close()
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
    handlers.update(preview_task_handlers())
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
