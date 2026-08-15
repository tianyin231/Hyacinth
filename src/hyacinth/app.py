import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from openpyxl.utils import get_column_letter
from PySide6.QtCore import QPoint, QSize, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
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
    APPLY_DEDUPLICATE_PREVIEW_OPERATION,
    APPLY_DELETE_BLANK_ROWS_PREVIEW_OPERATION,
    APPLY_FILTER_PREVIEW_OPERATION,
    APPLY_SORT_PREVIEW_OPERATION,
    DEDUPLICATE_PREVIEW_OPERATION,
    DELETE_BLANK_ROWS_PREVIEW_OPERATION,
    FILTER_PREVIEW_OPERATION,
    SAVE_MANUAL_EDITS_OPERATION,
    SORT_PREVIEW_OPERATION,
    DeduplicatePreviewResult,
    DeleteBlankRowsPreviewResult,
    FilterPreviewResult,
    SortPreviewResult,
    apply_version_handlers,
    deduplicate_preview_handlers,
    delete_blank_rows_preview_handlers,
    filter_preview_handlers,
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
from hyacinth.versioning import (
    CHECKOUT_VERSION_OPERATION,
    DELETE_VERSION_OPERATION,
    EXPORT_VERSION_OPERATION,
    ExportedVersion,
    MetadataStore,
    VersionRecord,
    checkout_version_handlers,
    delete_version_handlers,
    export_version_handlers,
    suggested_export_filename,
)


class ApplicationTaskQueue(TaskQueuePort, Protocol):
    def submit(self, request: TaskRequest) -> None: ...


FilePicker = Callable[[QWidget], Path | None]
ErrorPresenter = Callable[[QWidget, str], None]
ConfirmationPresenter = Callable[[QWidget, str, str], bool]
VersionChoicePresenter = Callable[[QWidget, tuple[VersionRecord, ...]], str | None]
UnsavedChangesPresenter = Callable[[QWidget, str], str]
SaveAsPicker = Callable[[QWidget, str], Path | None]
ExportPresenter = Callable[[QWidget, Path], None]

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
        confirmation_presenter: ConfirmationPresenter,
        version_choice_presenter: VersionChoicePresenter,
        unsaved_changes_presenter: UnsavedChangesPresenter,
        save_as_picker: SaveAsPicker,
        export_presenter: ExportPresenter,
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
        self._confirmation_presenter = confirmation_presenter
        self._version_choice_presenter = version_choice_presenter
        self._unsaved_changes_presenter = unsaved_changes_presenter
        self._save_as_picker = save_as_picker
        self._export_presenter = export_presenter
        self._task_queue = task_queue
        self._import_task_ids: set[str] = set()
        self._preview_task_id: str | None = None
        self._preview_is_temporary = False
        self._current_workbook: ImportedWorkbook | None = None
        self._processing_task_id: str | None = None
        self._processing_result: (
            SortPreviewResult
            | DeduplicatePreviewResult
            | DeleteBlankRowsPreviewResult
            | FilterPreviewResult
            | None
        ) = None
        self._temporary_preview: WorkbookPreview | None = None
        self._apply_task_id: str | None = None
        self._apply_version_id: str | None = None
        self._manual_save_task_id: str | None = None
        self._manual_save_version_id: str | None = None
        self._checkout_task_id: str | None = None
        self._delete_task_id: str | None = None
        self._delete_version_id: str | None = None
        self._previewed_version_id: str | None = None
        self._close_after_manual_save = False
        self._export_task_id: str | None = None

        self._application_header = ApplicationHeader(workspace_root)
        self._command_bar = CommandBar(workspace_root)
        self._command_bar.import_requested.connect(self._choose_import_file)
        self._command_bar.save_version_requested.connect(self._submit_manual_save)
        self._command_bar.undo_requested.connect(self._workbook_preview_undo)
        self._command_bar.redo_requested.connect(self._workbook_preview_redo)
        self._command_bar.export_requested.connect(self._export_current_version)
        self._function_panel = FunctionPanel(workspace_root)
        self._function_panel.preview_requested.connect(self._submit_sort_preview)
        self._function_panel.deduplicate_preview_requested.connect(self._submit_deduplicate_preview)
        self._function_panel.delete_blank_rows_preview_requested.connect(
            self._submit_delete_blank_rows_preview
        )
        self._function_panel.filter_preview_requested.connect(self._submit_filter_preview)
        self._function_panel.cancel_requested.connect(self._cancel_processing_workflow)
        self._function_panel.apply_requested.connect(self._submit_apply_processing_preview)
        self._file_library = FileLibraryWidget(
            discover_imported_workbooks(library_root),
            workspace_root,
        )
        self._file_library.workbook_selected.connect(self._select_workbook)
        self._version_tree = VersionTreePanel(workspace_root)
        self._version_tree.version_preview_requested.connect(self._preview_version)
        self._version_tree.version_continue_requested.connect(self._continue_from_version)
        self._version_tree.version_position_changed.connect(self._save_version_position)
        self._version_tree.version_delete_requested.connect(self._request_delete_version)
        self._version_tree.version_restore_requested.connect(self._restore_deleted_version)
        self._version_tree.version_export_requested.connect(self._request_export_version)
        self._workbook_preview = WorkbookPreviewWidget(workspace_root)
        self._workbook_preview.import_requested.connect(self._choose_import_file)
        self._workbook_preview.edit_state_changed.connect(self._apply_edit_state)
        self._editor = WorkbookEditorFrame(self._workbook_preview, workspace_root)

        left_splitter = QSplitter(Qt.Orientation.Vertical, workspace_root)
        left_splitter.setObjectName("left-workspace-splitter")
        left_splitter.addWidget(self._function_panel)
        left_splitter.addWidget(self._file_library)
        left_splitter.setStretchFactor(0, 4)
        left_splitter.setStretchFactor(1, 2)
        left_splitter.setSizes([420, 180])

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
        self._task_bridge.event_received.connect(self._apply_processing_event)
        self._task_bridge.event_received.connect(self._apply_apply_event)
        self._task_bridge.event_received.connect(self._apply_manual_save_event)
        self._task_bridge.event_received.connect(self._apply_checkout_event)
        self._task_bridge.event_received.connect(self._apply_delete_event)
        self._task_bridge.event_received.connect(self._apply_export_event)
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
            and not self._resolve_unsaved_changes("切换文件")
        ):
            self._file_library.select_workbook(self._current_workbook.file_id)
            return
        if (
            self._current_workbook is not None
            and self._current_workbook.file_id != workbook.file_id
        ):
            self._cancel_processing_workflow(reload_base=False)
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
        self._current_workbook = workbook
        self._previewed_version_id = (
            workbook.head_version.version_id if workbook.head_version is not None else None
        )
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
            head = self._current_workbook.head_version if self._current_workbook else None
            editable = (
                not self._preview_is_temporary
                and head is not None
                and self._previewed_version_id == head.version_id
            )
            self._workbook_preview.show_preview(event.result, editable=editable)
            if self._preview_is_temporary:
                self._temporary_preview = event.result
                self._editor.set_temporary_result(True)
                self._show_processing_preview_ready()
                self._set_processing_navigation_enabled(True)
            else:
                self._editor.set_temporary_result(False)
                self._function_panel.set_workbook(self._headers_for_preview(event.result))
                self._function_panel.setEnabled(
                    head is not None and self._previewed_version_id == head.version_id
                )
            self._preview_task_id = None
        elif event.state is TaskState.FAILED:
            self._workbook_preview.set_error(event.message or "工作簿无法打开")
            if self._preview_is_temporary:
                self._function_panel.set_error(event.message or "临时结果无法打开")
                self._set_processing_navigation_enabled(True)
            self._preview_task_id = None
        elif event.state is TaskState.CANCELLED:
            was_temporary = self._preview_is_temporary
            self._preview_task_id = None
            if was_temporary:
                self._set_processing_navigation_enabled(True)
                workbook = self._current_workbook
                self._discard_processing_result()
                if workbook is not None:
                    self._load_preview(
                        workbook.working_path,
                        workbook.display_name,
                        temporary=False,
                    )
            else:
                self._workbook_preview.set_error("加载已取消，可重新选择文件")

    def _submit_sort_preview(self, sheet_name: str, sort_keys: object) -> None:
        if not isinstance(sort_keys, list):
            self._function_panel.set_error("排序参数无效，请重新选择")
            return
        self._submit_processing_preview(
            operation=SORT_PREVIEW_OPERATION,
            task_name="生成排序预览",
            busy_message="正在生成临时排序结果…",
            sheet_name=sheet_name,
            parameters={"sort_keys": sort_keys},
        )

    def _submit_deduplicate_preview(self, sheet_name: str, parameters: object) -> None:
        if not isinstance(parameters, dict):
            self._function_panel.set_error("去重参数无效，请重新选择")
            return
        self._submit_processing_preview(
            operation=DEDUPLICATE_PREVIEW_OPERATION,
            task_name="生成删除重复行预览",
            busy_message="正在检查并删除临时结果中的重复行…",
            sheet_name=sheet_name,
            parameters=parameters,
        )

    def _submit_delete_blank_rows_preview(
        self,
        sheet_name: str,
        parameters: object,
    ) -> None:
        if not isinstance(parameters, dict):
            self._function_panel.set_error("删除空白行参数无效，请重新选择")
            return
        self._submit_processing_preview(
            operation=DELETE_BLANK_ROWS_PREVIEW_OPERATION,
            task_name="生成删除空白行预览",
            busy_message="正在检查并删除临时结果中的空白行…",
            sheet_name=sheet_name,
            parameters=parameters,
        )

    def _submit_filter_preview(self, sheet_name: str, parameters: object) -> None:
        if not isinstance(parameters, dict):
            self._function_panel.set_error("条件筛选参数无效，请重新配置")
            return
        self._submit_processing_preview(
            operation=FILTER_PREVIEW_OPERATION,
            task_name="生成条件筛选预览",
            busy_message="正在计算匹配行并生成筛选预览…",
            sheet_name=sheet_name,
            parameters=parameters,
        )

    def _submit_processing_preview(
        self,
        *,
        operation: str,
        task_name: str,
        busy_message: str,
        sheet_name: str,
        parameters: dict[str, object],
    ) -> None:
        workbook = self._current_workbook
        parent = workbook.head_version if workbook is not None else None
        if workbook is None or parent is None:
            self._function_panel.set_error("当前文件尚未建立可处理的根版本")
            return
        self._discard_processing_result()
        task_id = uuid4().hex
        preview_id = uuid4().hex
        preview_path = (
            workbook.working_path.parent.parent / ".previews" / preview_id / "result.xlsx"
        )
        self._processing_task_id = task_id
        self._function_panel.set_busy(busy_message)
        self._set_processing_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=task_name,
                file_id=workbook.file_id,
                engine=None,
                operation=operation,
                payload={
                    "source_path": str(parent.snapshot_path),
                    "preview_path": str(preview_path),
                    "parent_version_id": parent.version_id,
                    "sheet_name": sheet_name,
                    **parameters,
                },
            )
        )

    def _apply_processing_event(self, event: TaskEvent) -> None:
        if event.task_id != self._processing_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(
            event.result,
            (
                SortPreviewResult,
                DeduplicatePreviewResult,
                DeleteBlankRowsPreviewResult,
                FilterPreviewResult,
            ),
        ):
            self._processing_result = event.result
            self._processing_task_id = None
            display_name = (
                self._current_workbook.display_name if self._current_workbook else "临时结果"
            )
            self._load_preview(event.result.preview_path, display_name, temporary=True)
        elif event.state is TaskState.FAILED:
            self._processing_task_id = None
            self._set_processing_navigation_enabled(True)
            self._function_panel.set_error(event.message or "处理预览生成失败")
        elif event.state is TaskState.CANCELLED:
            self._processing_task_id = None
            self._set_processing_navigation_enabled(True)
            workbook = self._current_workbook
            self._discard_processing_result()
            if workbook is not None:
                self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _submit_apply_processing_preview(self) -> None:
        workbook = self._current_workbook
        result = self._processing_result
        if workbook is None or result is None:
            self._function_panel.set_error("没有可应用的临时结果")
            return
        task_id = uuid4().hex
        version_id = uuid4().hex
        self._apply_task_id = task_id
        self._apply_version_id = version_id
        self._workbook_preview.clear_preview("正在应用临时结果…")
        self._function_panel.set_busy("正在创建不可变子版本…")
        self._set_processing_navigation_enabled(False)
        if isinstance(result, SortPreviewResult):
            operation = APPLY_SORT_PREVIEW_OPERATION
            task_name = "应用排序结果"
            parameters: dict[str, object] = {
                "sort_keys": [
                    {"column_index": key.column_index, "direction": key.direction.value}
                    for key in result.sort_keys
                ]
            }
        elif isinstance(result, DeduplicatePreviewResult):
            operation = APPLY_DEDUPLICATE_PREVIEW_OPERATION
            task_name = "应用删除重复行结果"
            parameters = {
                "key_columns": list(result.key_columns),
                "keep": result.keep.value,
                "ignore_case": result.ignore_case,
                "trim_whitespace": result.trim_whitespace,
                "duplicate_groups": len(result.duplicate_groups),
                "deleted_rows": result.deleted_rows,
            }
        elif isinstance(result, DeleteBlankRowsPreviewResult):
            operation = APPLY_DELETE_BLANK_ROWS_PREVIEW_OPERATION
            task_name = "应用删除空白行结果"
            parameters = {
                "key_columns": list(result.key_columns),
                "allow_unsafe": result.allow_unsafe,
                "compatibility_warning": result.compatibility_warning,
                "deleted_row_numbers": list(result.deleted_row_numbers),
            }
        else:
            operation = APPLY_FILTER_PREVIEW_OPERATION
            task_name = "应用条件筛选结果"
            parameters = {
                "conditions": [
                    {
                        "column_index": condition.column_index,
                        "operator": condition.operator.value,
                        "value_type": condition.value_type.value,
                        "value": condition.value,
                        "second_value": condition.second_value,
                    }
                    for condition in result.conditions
                ],
                "connector": result.connector.value,
                "matched_rows": result.matched_rows,
                "total_rows": result.total_rows,
            }
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=task_name,
                file_id=workbook.file_id,
                engine=None,
                operation=operation,
                payload={
                    "library_root": str(self._library_root),
                    "preview_path": str(result.preview_path),
                    "preview_hash": result.content_hash,
                    "parent_version_id": result.parent_version_id,
                    "version_id": version_id,
                    "sheet_name": result.sheet_name,
                    **parameters,
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
        self._discard_processing_result()
        self._apply_task_id = None
        self._apply_version_id = None
        self._set_processing_navigation_enabled(True)
        self._current_workbook = workbook
        self._previewed_version_id = (
            workbook.head_version.version_id if workbook.head_version is not None else None
        )
        self._file_library.replace_workbook(workbook)
        self._show_versions(workbook)
        self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _workbook_preview_undo(self) -> None:
        self._workbook_preview.undo()

    def _workbook_preview_redo(self) -> None:
        self._workbook_preview.redo()

    def _apply_edit_state(self, dirty: bool, can_undo: bool, can_redo: bool) -> None:
        self._command_bar.set_edit_state(dirty, can_undo, can_redo)
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        self._function_panel.setEnabled(
            not dirty
            and head is not None
            and self._previewed_version_id == head.version_id
            and self._manual_save_task_id is None
        )

    def _submit_manual_save(self) -> None:
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        edits = self._workbook_preview.pending_edits()
        if (
            workbook is None
            or head is None
            or not edits
            or self._manual_save_task_id is not None
            or self._previewed_version_id != head.version_id
        ):
            return
        task_id = uuid4().hex
        version_id = uuid4().hex
        self._manual_save_task_id = task_id
        self._manual_save_version_id = version_id
        self._set_processing_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="保存手动编辑",
                file_id=workbook.file_id,
                engine=None,
                operation=SAVE_MANUAL_EDITS_OPERATION,
                payload={
                    "library_root": str(self._library_root),
                    "parent_version_id": head.version_id,
                    "version_id": version_id,
                    "edits": [
                        {
                            "sheet_name": edit.sheet_name,
                            "row": edit.row,
                            "column": edit.column,
                            "value": edit.value,
                        }
                        for edit in edits
                    ],
                },
            )
        )

    def _apply_manual_save_event(self, event: TaskEvent) -> None:
        if event.task_id != self._manual_save_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ImportedWorkbook):
            self._manual_save_task_id = None
            self._manual_save_version_id = None
            self._workbook_preview.clear_edits()
            self._set_processing_navigation_enabled(True)
            self._current_workbook = event.result
            head = event.result.head_version
            self._previewed_version_id = head.version_id if head is not None else None
            self._file_library.replace_workbook(event.result)
            self._show_versions(event.result)
            self._load_preview(
                event.result.working_path,
                event.result.display_name,
                temporary=False,
            )
            if self._close_after_manual_save:
                self._close_after_manual_save = False
                self.close()
        elif event.state in {TaskState.FAILED, TaskState.CANCELLED}:
            self._manual_save_task_id = None
            self._manual_save_version_id = None
            self._close_after_manual_save = False
            self._set_processing_navigation_enabled(True)
            self._error_presenter(
                self,
                event.message
                or ("保存已取消" if event.state is TaskState.CANCELLED else "保存失败"),
            )

    def _preview_version(self, version_id: str) -> None:
        workbook = self._current_workbook
        if workbook is None or self._checkout_task_id is not None:
            return
        if version_id != self._previewed_version_id and not self._resolve_unsaved_changes(
            "切换版本"
        ):
            return
        try:
            version = MetadataStore(self._library_root).get_version(workbook.file_id, version_id)
        except ValueError as error:
            self._error_presenter(self, str(error))
            return
        if version.deleted_at is not None:
            self._error_presenter(self, "已删除版本只能恢复，不能预览")
            return
        if self._processing_result is not None:
            self._cancel_processing_workflow(reload_base=False)
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
        self._previewed_version_id = version_id
        self._function_panel.setEnabled(
            workbook.head_version is not None and version_id == workbook.head_version.version_id
        )
        self._load_preview(version.snapshot_path, workbook.display_name, temporary=False)

    def _continue_from_version(self, version_id: str) -> None:
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        if workbook is None or head is None or version_id == head.version_id:
            return
        if not self._resolve_unsaved_changes("切换当前工作版本"):
            return
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
            self._preview_task_id = None
        task_id = uuid4().hex
        self._checkout_task_id = task_id
        self._set_processing_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name="从历史版本继续",
                file_id=workbook.file_id,
                engine=None,
                operation=CHECKOUT_VERSION_OPERATION,
                payload={
                    "library_root": str(self._library_root),
                    "version_id": version_id,
                    "expected_head_version_id": head.version_id,
                },
            )
        )

    def _apply_checkout_event(self, event: TaskEvent) -> None:
        if event.task_id != self._checkout_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ImportedWorkbook):
            self._checkout_task_id = None
            self._current_workbook = event.result
            head = event.result.head_version
            self._previewed_version_id = head.version_id if head is not None else None
            self._file_library.replace_workbook(event.result)
            self._show_versions(event.result)
            self._function_panel.setEnabled(True)
            self._set_processing_navigation_enabled(True)
            self._load_preview(
                event.result.working_path,
                event.result.display_name,
                temporary=False,
            )
        elif event.state is TaskState.FAILED:
            self._checkout_task_id = None
            self._set_processing_navigation_enabled(True)
            self._error_presenter(self, event.message or "当前工作版本切换失败")
            self._restore_current_head_preview()
        elif event.state is TaskState.CANCELLED:
            self._checkout_task_id = None
            self._set_processing_navigation_enabled(True)
            self._restore_current_head_preview()

    def _request_delete_version(self, version_id: str) -> None:
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        if workbook is None or head is None or self._delete_task_id is not None:
            return
        if (
            self._processing_result is not None
            or self._processing_task_id is not None
            or self._apply_task_id is not None
        ):
            self._error_presenter(self, "请先取消或应用当前临时预览，再删除版本")
            return
        store = MetadataStore(self._library_root)
        try:
            plan = store.plan_version_deletion(workbook.file_id, version_id)
        except ValueError as error:
            self._error_presenter(self, str(error))
            return
        replacement: VersionRecord | None = None
        if plan.requires_head_switch:
            if len(plan.replacement_candidates) == 1:
                replacement = plan.replacement_candidates[0]
            else:
                selected_id = self._version_choice_presenter(
                    self,
                    plan.replacement_candidates,
                )
                if selected_id is None:
                    return
                replacement = next(
                    (
                        candidate
                        for candidate in plan.replacement_candidates
                        if candidate.version_id == selected_id
                    ),
                    None,
                )
                if replacement is None:
                    self._error_presenter(self, "选择的新 HEAD 已不可用，请刷新版本树")
                    return
        if replacement is None:
            detail = "当前工作版本 HEAD 保持不变。"
        else:
            detail = f"删除后 HEAD 将切换到“{replacement.name}”。"
        if not self._confirmation_presenter(
            self,
            "删除版本",
            f"确定将“{plan.target.name}”移入回收状态吗？\n{detail}\n可立即撤销或稍后恢复。",
        ):
            return
        if self._preview_task_id is not None:
            self._task_queue.cancel(self._preview_task_id)
            self._preview_task_id = None
        task_id = uuid4().hex
        self._delete_task_id = task_id
        self._delete_version_id = version_id
        self._set_processing_navigation_enabled(False)
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=f"删除版本 {plan.target.name}",
                file_id=workbook.file_id,
                engine=None,
                operation=DELETE_VERSION_OPERATION,
                payload={
                    "library_root": str(self._library_root),
                    "version_id": version_id,
                    "expected_head_version_id": head.version_id,
                    "replacement_version_id": (
                        replacement.version_id if replacement is not None else None
                    ),
                },
            )
        )

    def _apply_delete_event(self, event: TaskEvent) -> None:
        if event.task_id != self._delete_task_id:
            return
        deleted_version_id = self._delete_version_id
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ImportedWorkbook):
            self._delete_task_id = None
            self._delete_version_id = None
            self._current_workbook = event.result
            head = event.result.head_version
            self._previewed_version_id = head.version_id if head is not None else None
            self._file_library.replace_workbook(event.result)
            self._show_versions(event.result)
            if deleted_version_id is not None:
                self._version_tree.show_delete_undo(deleted_version_id)
            self._set_processing_navigation_enabled(True)
            self._load_preview(
                event.result.working_path,
                event.result.display_name,
                temporary=False,
            )
        elif event.state is TaskState.FAILED:
            self._delete_task_id = None
            self._delete_version_id = None
            self._set_processing_navigation_enabled(True)
            self._error_presenter(self, event.message or "版本删除失败")
            self._restore_current_head_preview()
        elif event.state is TaskState.CANCELLED:
            self._delete_task_id = None
            self._delete_version_id = None
            self._set_processing_navigation_enabled(True)
            self._restore_current_head_preview()

    def _restore_deleted_version(self, version_id: str) -> None:
        workbook = self._current_workbook
        if workbook is None or self._delete_task_id is not None:
            return
        try:
            MetadataStore(self._library_root).restore_version(workbook.file_id, version_id)
            refreshed = MetadataStore(self._library_root).get_workbook(workbook.file_id)
        except ValueError as error:
            self._error_presenter(self, str(error))
            return
        self._current_workbook = refreshed
        self._file_library.replace_workbook(refreshed)
        self._show_versions(refreshed)
        self._version_tree.clear_delete_undo()

    def _restore_current_head_preview(self) -> None:
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        if workbook is None or head is None:
            return
        self._previewed_version_id = head.version_id
        self._show_versions(workbook)
        self._function_panel.setEnabled(True)
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
        self._set_processing_navigation_enabled(True)
        if self._temporary_preview is not None:
            self._workbook_preview.show_preview(self._temporary_preview)
            self._editor.set_temporary_result(True)
            self._show_processing_preview_ready(message)
        else:
            self._function_panel.set_error(message)

    def _show_processing_preview_ready(self, message: str | None = None) -> None:
        result = self._processing_result
        if isinstance(result, DeduplicatePreviewResult):
            mapping = tuple(
                (group.kept_row, group.deleted_rows) for group in result.duplicate_groups
            )
            self._function_panel.set_deduplicate_preview_ready(
                len(result.duplicate_groups),
                result.deleted_rows,
                mapping,
                message,
            )
            return
        if isinstance(result, DeleteBlankRowsPreviewResult):
            self._function_panel.set_delete_blank_rows_preview_ready(
                result.deleted_row_numbers,
                result.compatibility_warning,
                message,
            )
            return
        if isinstance(result, FilterPreviewResult):
            self._function_panel.set_filter_preview_ready(
                result.matched_rows,
                result.total_rows,
                message,
            )
            return
        self._function_panel.set_preview_ready(message or "临时结果已就绪，尚未生成版本")

    def _cancel_processing_workflow(self, *, reload_base: bool = True) -> None:
        if self._apply_task_id is not None:
            self._task_queue.cancel(self._apply_task_id)
            self._function_panel.set_busy("正在请求取消应用…")
            return
        if self._processing_task_id is not None:
            self._task_queue.cancel(self._processing_task_id)
            self._function_panel.set_busy("正在请求取消处理预览…")
            return
        if self._preview_task_id is not None and self._preview_is_temporary:
            self._task_queue.cancel(self._preview_task_id)
            self._function_panel.set_busy("正在请求取消临时结果加载…")
            return
        workbook = self._current_workbook
        self._discard_processing_result()
        if reload_base and workbook is not None:
            self._load_preview(workbook.working_path, workbook.display_name, temporary=False)

    def _discard_processing_result(self) -> None:
        self._workbook_preview.clear_preview()
        self._editor.set_temporary_result(False)
        if self._processing_result is not None:
            shutil.rmtree(self._processing_result.preview_path.parent, ignore_errors=True)
        self._processing_result = None
        self._temporary_preview = None

    def _show_versions(self, workbook: ImportedWorkbook) -> None:
        head = workbook.head_version
        if head is None:
            self._command_bar.set_version_available(False)
            self._version_tree.set_workbook(workbook.display_name, None)
            return
        self._command_bar.set_version_available(True)
        store = MetadataStore(self._library_root)
        versions = store.list_versions(workbook.file_id)
        layouts = store.list_version_layouts(workbook.file_id)
        self._version_tree.set_workbook(
            workbook.display_name,
            versions,
            head.version_id,
            layouts,
        )

    def _export_current_version(self) -> None:
        workbook = self._current_workbook
        head = workbook.head_version if workbook is not None else None
        version_id = self._previewed_version_id or (head.version_id if head is not None else None)
        if version_id is not None:
            self._request_export_version(version_id, False)

    def _request_export_version(self, version_id: str, save_as: bool) -> None:
        workbook = self._current_workbook
        if workbook is None or self._export_task_id is not None:
            return
        try:
            version = MetadataStore(self._library_root).get_version(workbook.file_id, version_id)
        except ValueError as error:
            self._error_presenter(self, str(error))
            return
        if version.deleted_at is not None:
            self._error_presenter(self, "已删除版本不能导出，请先恢复")
            return
        extension = (
            workbook.original_path.suffix
            if version.parent_version_id is None
            else version.snapshot_path.suffix
        )
        filename = suggested_export_filename(
            workbook.display_name,
            version.name,
            version.created_at.astimezone().strftime("%Y%m%d-%H%M%S"),
            extension,
        )
        payload: dict[str, object] = {
            "library_root": str(self._library_root),
            "version_id": version_id,
        }
        if save_as:
            destination = self._save_as_picker(self, filename)
            if destination is None:
                return
            payload["destination_path"] = str(destination)
        else:
            payload["destination_directory"] = str(default_export_directory())
        task_id = uuid4().hex
        self._export_task_id = task_id
        self._task_queue.submit(
            TaskRequest(
                task_id=task_id,
                name=f"导出 {version.name}",
                file_id=workbook.file_id,
                engine=None,
                operation=EXPORT_VERSION_OPERATION,
                payload=payload,
            )
        )

    def _apply_export_event(self, event: TaskEvent) -> None:
        if event.task_id != self._export_task_id:
            return
        if event.state is TaskState.SUCCEEDED and isinstance(event.result, ExportedVersion):
            self._export_task_id = None
            self._export_presenter(self, event.result.path)
        elif event.state in {TaskState.FAILED, TaskState.CANCELLED}:
            self._export_task_id = None
            self._error_presenter(
                self,
                event.message
                or ("导出已取消" if event.state is TaskState.CANCELLED else "导出失败"),
            )

    def _save_version_position(self, version_id: str, x: float, y: float) -> None:
        workbook = self._current_workbook
        if workbook is None:
            return
        try:
            MetadataStore(self._library_root).save_version_layout(
                workbook.file_id,
                version_id,
                x,
                y,
                fixed=True,
            )
        except ValueError as error:
            self._error_presenter(self, str(error))

    def _set_processing_navigation_enabled(self, enabled: bool) -> None:
        self._command_bar.setEnabled(enabled)
        self._file_library.setEnabled(enabled)
        self._version_tree.setEnabled(enabled)

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
        if self._workbook_preview.pending_edits():
            choice = self._unsaved_changes_presenter(self, "退出软件")
            if choice == "cancel":
                event.ignore()
                return
            if choice == "save":
                self._close_after_manual_save = True
                self._submit_manual_save()
                event.ignore()
                return
            self._workbook_preview.clear_edits()
        if self._task_bridge.shutdown(timeout=1.0):
            self._discard_processing_result()
            self._workbook_preview.close()
            event.accept()
        else:
            event.ignore()

    def _resolve_unsaved_changes(self, action: str) -> bool:
        if not self._workbook_preview.pending_edits():
            return True
        choice = self._unsaved_changes_presenter(self, action)
        if choice == "discard":
            self._workbook_preview.clear_edits()
            return True
        if choice == "save":
            self._submit_manual_save()
        return False


def create_main_window(
    task_queue: ApplicationTaskQueue | None = None,
    *,
    library_root: Path | None = None,
    file_picker: FilePicker | None = None,
    error_presenter: ErrorPresenter | None = None,
    confirmation_presenter: ConfirmationPresenter | None = None,
    version_choice_presenter: VersionChoicePresenter | None = None,
    unsaved_changes_presenter: UnsavedChangesPresenter | None = None,
    save_as_picker: SaveAsPicker | None = None,
    export_presenter: ExportPresenter | None = None,
) -> HyacinthMainWindow:
    handlers = conversion_task_handlers()
    handlers.update(import_task_handlers())
    handlers.update(preview_task_handlers())
    handlers.update(sort_preview_handlers())
    handlers.update(deduplicate_preview_handlers())
    handlers.update(delete_blank_rows_preview_handlers())
    handlers.update(filter_preview_handlers())
    handlers.update(apply_version_handlers())
    handlers.update(checkout_version_handlers())
    handlers.update(delete_version_handlers())
    handlers.update(export_version_handlers())
    return HyacinthMainWindow(
        task_queue or TaskQueue(handlers),
        library_root or default_library_root(),
        file_picker or select_workbook_file,
        error_presenter or show_import_error,
        confirmation_presenter or confirm_action,
        version_choice_presenter or choose_replacement_version,
        unsaved_changes_presenter or ask_unsaved_changes,
        save_as_picker or select_export_path,
        export_presenter or show_export_success,
    )


def default_library_root() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(documents) / "Hyacinth"


def default_export_directory() -> Path:
    downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return Path(downloads) if downloads else Path.home() / "Downloads"


def select_workbook_file(parent: QWidget) -> Path | None:
    file_name, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        "导入 Excel 文件",
        "",
        "Excel 工作簿 (*.xlsx *.xls)",
    )
    return Path(file_name) if file_name else None


def select_export_path(parent: QWidget, filename: str) -> Path | None:
    initial = default_export_directory() / filename
    file_name, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        "另存版本为",
        str(initial),
        "Excel 工作簿 (*.xlsx *.xls)",
    )
    return Path(file_name) if file_name else None


def show_import_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "导入失败", message)


def show_export_success(parent: QWidget, path: Path) -> None:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("导出完成")
    dialog.setText(f"版本已导出为 {path.name}")
    dialog.setInformativeText(str(path))
    dialog.setIcon(QMessageBox.Icon.Information)
    open_file = dialog.addButton("打开文件", QMessageBox.ButtonRole.AcceptRole)
    open_folder = dialog.addButton("打开所在位置", QMessageBox.ButtonRole.ActionRole)
    dialog.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
    dialog.exec()
    if dialog.clickedButton() is open_file:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    elif dialog.clickedButton() is open_folder:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def confirm_action(parent: QWidget, title: str, message: str) -> bool:
    return (
        QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        == QMessageBox.StandardButton.Yes
    )


def choose_replacement_version(
    parent: QWidget,
    candidates: tuple[VersionRecord, ...],
) -> str | None:
    labels = [
        f"{candidate.name} · {candidate.created_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
        f" · {candidate.version_id[:8]}"
        for candidate in candidates
    ]
    selected, accepted = QInputDialog.getItem(
        parent,
        "选择新的当前工作版本",
        "删除当前 HEAD 后切换到：",
        labels,
        0,
        False,
    )
    if not accepted:
        return None
    return candidates[labels.index(selected)].version_id


def ask_unsaved_changes(parent: QWidget, action: str) -> str:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("有未保存的修改")
    dialog.setText(f"{action}前，是否将当前单元格修改保存为新版本？")
    dialog.setInformativeText("选择“放弃”会丢弃本次尚未保存的编辑。")
    dialog.setIcon(QMessageBox.Icon.Warning)
    save_button = dialog.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
    discard_button = dialog.addButton("放弃", QMessageBox.ButtonRole.DestructiveRole)
    dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(save_button)
    dialog.exec()
    clicked = dialog.clickedButton()
    if clicked is save_button:
        return "save"
    if clicked is discard_button:
        return "discard"
    return "cancel"
