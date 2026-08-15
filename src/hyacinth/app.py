import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from openpyxl.utils import get_column_letter
from PySide6.QtCore import QPoint, QSize, QStandardPaths, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
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
    SqliteGridDataSource,
    WorkbookPreview,
    WorkbookPreviewWidget,
    preview_index_path,
    preview_task_handlers,
)
from hyacinth.processing import (
    APPLY_SORT_PREVIEW_OPERATION,
    SORT_PREVIEW_OPERATION,
    SortPreviewResult,
    apply_version_handlers,
    sort_preview_handlers,
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
from hyacinth.versioning import MetadataStore


class ApplicationTaskQueue(TaskQueuePort, Protocol):
    def submit(self, request: TaskRequest) -> None: ...


FilePicker = Callable[[QWidget], Path | None]
ErrorPresenter = Callable[[QWidget, str], None]

DEFAULT_WINDOW_SIZE = QSize(1440, 900)
MINIMUM_WINDOW_SIZE = QSize(1024, 640)
AVAILABLE_SCREEN_RATIO = 0.9


def initial_window_size(available_size: QSize) -> QSize:
    return QSize(
        min(
            DEFAULT_WINDOW_SIZE.width(),
            max(MINIMUM_WINDOW_SIZE.width(), int(available_size.width() * AVAILABLE_SCREEN_RATIO)),
        ),
        min(
            DEFAULT_WINDOW_SIZE.height(),
            max(
                MINIMUM_WINDOW_SIZE.height(),
                int(available_size.height() * AVAILABLE_SCREEN_RATIO),
            ),
        ),
    )


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
        self.setMinimumSize(MINIMUM_WINDOW_SIZE)
        self._apply_initial_window_geometry()
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
        self._preview_is_temporary = False
        self._current_workbook: ImportedWorkbook | None = None
        self._sort_task_id: str | None = None
        self._sort_result: SortPreviewResult | None = None
        self._temporary_preview: WorkbookPreview | None = None
        self._apply_task_id: str | None = None
        self._apply_version_id: str | None = None

        self._application_header = ApplicationHeader(workspace_root)
        self._command_bar = CommandBar(workspace_root)
        self._command_bar.import_requested.connect(self._choose_import_file)
        self._function_panel = FunctionPanel(workspace_root)
        self._function_panel.preview_requested.connect(self._submit_sort_preview)
        self._function_panel.cancel_requested.connect(self._cancel_sort_workflow)
        self._function_panel.apply_requested.connect(self._submit_apply_sort_preview)
        self._file_library = FileLibraryWidget(
            discover_imported_workbooks(library_root),
            workspace_root,
        )
        self._file_library.workbook_selected.connect(self._select_workbook)
        self._version_tree = VersionTreePanel(workspace_root)
        self._workbook_preview = WorkbookPreviewWidget(workspace_root)
        self._workbook_preview.import_requested.connect(self._choose_import_file)
        self._editor = WorkbookEditorFrame(self._workbook_preview, workspace_root)

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
        main_splitter.addWidget(self._editor)
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
        self._task_bridge.event_received.connect(self._apply_sort_event)
        self._task_bridge.event_received.connect(self._apply_apply_event)
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

    def _apply_initial_window_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(DEFAULT_WINDOW_SIZE)
            return
        available = screen.availableGeometry()
        target = initial_window_size(available.size())
        self.resize(target)
        top_left = available.center() - QPoint(target.width() // 2, target.height() // 2)
        self.move(max(available.left(), top_left.x()), max(available.top(), top_left.y()))

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
        if (
            self._current_workbook is not None
            and self._current_workbook.file_id != workbook.file_id
        ):
            self._cancel_sort_workflow(reload_base=False)
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
        self._current_workbook = workbook
        self.setWindowTitle(f"风信子 — {workbook.display_name}")
        self._application_header.set_document_name(workbook.display_name)
        self._show_versions(workbook)
        self._function_panel.clear_workbook()
        self._editor.set_temporary_result(False)
        self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _load_preview(self, source: Path, display_name: str, *, temporary: bool) -> None:
        task_id = uuid4().hex
        self._preview_task_id = task_id
        self._preview_is_temporary = temporary
        self._workbook_preview.set_loading(display_name)
        index_path = source.parent / "preview.sqlite" if temporary else preview_index_path(source)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=f"加载 {display_name}",
                file_id=self._current_workbook.file_id if self._current_workbook else source.name,
                engine=None,
                operation=BUILD_PREVIEW_INDEX_OPERATION,
                payload={
                    "working_path": str(source),
                    "index_path": str(index_path),
                },
            )
        )

    def _apply_preview_event(self, event: TaskEvent) -> None:
        if event.task_id != self._preview_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, WorkbookPreview):
            self._workbook_preview.show_preview(event.result)
            if self._preview_is_temporary:
                self._temporary_preview = event.result
                self._editor.set_temporary_result(True)
                self._function_panel.set_preview_ready()
                self._set_sort_navigation_enabled(True)
            else:
                self._editor.set_temporary_result(False)
                self._function_panel.set_workbook(self._headers_for_preview(event.result))
            self._preview_task_id = None
        elif event.state is TaskState.FAILED:
            self._workbook_preview.set_error(event.message or "工作簿无法打开")
            if self._preview_is_temporary:
                self._function_panel.set_error(event.message or "临时结果无法打开")
                self._set_sort_navigation_enabled(True)
            self._preview_task_id = None
        elif event.state is TaskState.CANCELLED:
            was_temporary = self._preview_is_temporary
            self._preview_task_id = None
            if was_temporary:
                self._set_sort_navigation_enabled(True)
                workbook = self._current_workbook
                self._discard_sort_result()
                if workbook is not None:
                    self._load_preview(
                        workbook.working_path,
                        workbook.display_name,
                        temporary=False,
                    )
            else:
                self._workbook_preview.set_error("加载已取消，可重新选择文件")

    def _submit_sort_preview(self, sheet_name: str, sort_keys: object) -> None:
        workbook = self._current_workbook
        parent = workbook.head_version if workbook is not None else None
        if workbook is None or parent is None or not isinstance(sort_keys, list):
            self._function_panel.set_error("当前文件尚未建立可处理的根版本")
            return
        self._discard_sort_result()
        task_id = uuid4().hex
        preview_id = uuid4().hex
        preview_path = (
            workbook.working_path.parent.parent / ".previews" / preview_id / "result.xlsx"
        )
        self._sort_task_id = task_id
        self._function_panel.set_busy("正在生成临时排序结果…")
        self._set_sort_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="生成排序预览",
                file_id=workbook.file_id,
                engine=None,
                operation=SORT_PREVIEW_OPERATION,
                payload={
                    "source_path": str(parent.snapshot_path),
                    "preview_path": str(preview_path),
                    "parent_version_id": parent.version_id,
                    "sheet_name": sheet_name,
                    "sort_keys": sort_keys,
                },
            )
        )

    def _apply_sort_event(self, event: TaskEvent) -> None:
        if event.task_id != self._sort_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, SortPreviewResult):
            self._sort_result = event.result
            self._sort_task_id = None
            display_name = (
                self._current_workbook.display_name if self._current_workbook else "临时结果"
            )
            self._load_preview(event.result.preview_path, display_name, temporary=True)
        elif event.state is TaskState.FAILED:
            self._sort_task_id = None
            self._set_sort_navigation_enabled(True)
            self._function_panel.set_error(event.message or "排序预览生成失败")
        elif event.state is TaskState.CANCELLED:
            self._sort_task_id = None
            self._set_sort_navigation_enabled(True)
            workbook = self._current_workbook
            self._discard_sort_result()
            if workbook is not None:
                self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _submit_apply_sort_preview(self) -> None:
        workbook = self._current_workbook
        result = self._sort_result
        if workbook is None or result is None:
            self._function_panel.set_error("没有可应用的临时结果")
            return
        task_id = uuid4().hex
        version_id = uuid4().hex
        self._apply_task_id = task_id
        self._apply_version_id = version_id
        self._workbook_preview.clear_preview("正在应用临时结果…")
        self._function_panel.set_busy("正在创建不可变子版本…")
        self._set_sort_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="应用排序结果",
                file_id=workbook.file_id,
                engine=None,
                operation=APPLY_SORT_PREVIEW_OPERATION,
                payload={
                    "library_root": str(self._library_root),
                    "preview_path": str(result.preview_path),
                    "preview_hash": result.content_hash,
                    "parent_version_id": result.parent_version_id,
                    "version_id": version_id,
                    "sheet_name": result.sheet_name,
                    "sort_keys": [
                        {"column_index": key.column_index, "direction": key.direction.value}
                        for key in result.sort_keys
                    ],
                },
            )
        )

    def _apply_apply_event(self, event: TaskEvent) -> None:
        if event.task_id != self._apply_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ImportedWorkbook):
            self._finish_applied_version(event.result)
        elif event.state is TaskState.FAILED:
            recovered = self._recover_applied_version()
            if not recovered:
                self._restore_temporary_preview(
                    f"应用失败：{event.message or '请重试或取消临时结果'}"
                )
        elif event.state is TaskState.CANCELLED:
            self._restore_temporary_preview("应用已取消，可重试或取消临时结果")

    def _finish_applied_version(self, workbook: ImportedWorkbook) -> None:
        self._discard_sort_result()
        self._apply_task_id = None
        self._apply_version_id = None
        self._set_sort_navigation_enabled(True)
        self._current_workbook = workbook
        self._file_library.replace_workbook(workbook)
        self._show_versions(workbook)
        self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _recover_applied_version(self) -> bool:
        workbook = self._current_workbook
        version_id = self._apply_version_id
        if workbook is None or version_id is None:
            return False
        store = MetadataStore(self._library_root)
        store.reconcile_manifests()
        try:
            recovered = store.get_workbook(workbook.file_id)
        except ValueError:
            return False
        head = recovered.head_version
        if head is None or head.version_id != version_id:
            return False
        self._finish_applied_version(recovered)
        return True

    def _restore_temporary_preview(self, message: str) -> None:
        self._apply_task_id = None
        self._apply_version_id = None
        self._set_sort_navigation_enabled(True)
        if self._temporary_preview is not None:
            self._workbook_preview.show_preview(self._temporary_preview)
            self._editor.set_temporary_result(True)
            self._function_panel.set_preview_ready(message)
        else:
            self._function_panel.set_error(message)

    def _cancel_sort_workflow(self, *, reload_base: bool = True) -> None:
        if self._apply_task_id is not None:
            self._task_queue.cancel(self._apply_task_id)
            self._function_panel.set_busy("正在请求取消应用…")
            return
        if self._sort_task_id is not None:
            self._task_queue.cancel(self._sort_task_id)
            self._function_panel.set_busy("正在请求取消排序预览…")
            return
        if self._preview_task_id is not None and self._preview_is_temporary:
            self._task_queue.cancel(self._preview_task_id)
            self._function_panel.set_busy("正在请求取消临时结果加载…")
            return
        workbook = self._current_workbook
        self._discard_sort_result()
        if reload_base and workbook is not None:
            self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _discard_sort_result(self) -> None:
        self._workbook_preview.clear_preview()
        self._editor.set_temporary_result(False)
        if self._sort_result is not None:
            shutil.rmtree(self._sort_result.preview_path.parent, ignore_errors=True)
        self._sort_result = None
        self._temporary_preview = None

    def _show_versions(self, workbook: ImportedWorkbook) -> None:
        head = workbook.head_version
        if head is None:
            self._version_tree.set_workbook(workbook.display_name, None)
            return
        versions = MetadataStore(self._library_root).list_versions(workbook.file_id)
        self._version_tree.set_workbook(workbook.display_name, versions, head.version_id)

    def _set_sort_navigation_enabled(self, enabled: bool) -> None:
        self._command_bar.setEnabled(enabled)
        self._file_library.setEnabled(enabled)

    def _headers_for_preview(self, preview: WorkbookPreview) -> dict[str, tuple[str, ...]]:
        headers: dict[str, tuple[str, ...]] = {}
        for sheet in preview.sheets:
            source = SqliteGridDataSource(preview.index_path, sheet)
            try:
                headers[sheet.title] = tuple(
                    f"{get_column_letter(column + 1)} · {source.value_at(0, column) or '未命名列'}"
                    for column in range(sheet.column_count)
                )
            finally:
                source.close()
        return headers

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
            self._discard_sort_result()
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
    handlers.update(sort_preview_handlers())
    handlers.update(apply_version_handlers())
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
