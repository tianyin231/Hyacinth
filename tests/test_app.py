import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from openpyxl import Workbook
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsProxyWidget,
    QGraphicsView,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabBar,
    QTableView,
)
from pytestqt.qtbot import QtBot

from hyacinth.excel.contracts import EngineName
from hyacinth.library import IMPORT_WORKBOOK_OPERATION, ImportedWorkbook
from hyacinth.preview import BUILD_PREVIEW_INDEX_OPERATION, run_preview_index_task
from hyacinth.processing import (
    APPLY_SORT_PREVIEW_OPERATION,
    SORT_PREVIEW_OPERATION,
    run_apply_sort_preview_task,
    run_sort_preview_task,
)
from hyacinth.tasks import TaskEvent, TaskRequest, TaskState, TaskStatusWidget
from hyacinth.versioning import MetadataStore, VersionRecord


def _child[WidgetT: QObject](parent: QObject, child_type: type[WidgetT], name: str) -> WidgetT:
    child = parent.findChild(child_type, name)
    assert child is not None
    return child


class FakeApplicationTaskQueue:
    def __init__(self, events: list[TaskEvent]) -> None:
        self._events = events
        self.cancelled: list[str] = []
        self.submitted: list[TaskRequest] = []
        self.shutdown_called = False

    def submit(self, request: TaskRequest) -> None:
        self.submitted.append(request)

    def push_event(self, event: TaskEvent) -> None:
        self._events.append(event)

    def poll_events(self) -> tuple[TaskEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def cancel(self, task_id: str) -> bool:
        self.cancelled.append(task_id)
        return True

    def shutdown(self, timeout: float = 1.0) -> bool:
        self.shutdown_called = True
        return True


class PreviewTaskContext:
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


def _seed_versioned_workbook(library_root: Path) -> ImportedWorkbook:
    directory = library_root / "files/file-1"
    original = directory / "original/销售.xlsx"
    working = directory / "working/current.xlsx"
    snapshot = directory / "versions/version-1/snapshot.xlsx"
    for path in (original, working, snapshot):
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "销售"
        sheet.append(["名称", "数量"])
        sheet.append(["apple", 2])
        sheet.append(["banana", 1])
        workbook.save(path)
        workbook.close()
    version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "import",
        None,
        snapshot,
        sha256(snapshot.read_bytes()).hexdigest(),
    )
    record = ImportedWorkbook("file-1", "销售.xlsx", original, working, version)
    MetadataStore(library_root).record_import(record)
    return record


def test_create_main_window_uses_product_identity(qtbot: QtBot) -> None:
    try:
        from hyacinth.app import create_main_window
    except ModuleNotFoundError:
        pytest.fail("hyacinth.app.create_main_window is not implemented")

    window = create_main_window()
    qtbot.addWidget(window)

    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "风信子"
    assert window.objectName() == "main-window"


def test_main_window_matches_approved_workspace_shell(qtbot: QtBot) -> None:
    from hyacinth.app import create_main_window

    window = create_main_window()
    qtbot.addWidget(window)

    main_splitter = _child(window, QSplitter, "main-workspace-splitter")
    left_splitter = _child(window, QSplitter, "left-workspace-splitter")
    import_button = _child(window, QPushButton, "toolbar-import-button")
    import_button_parent = import_button.parent()

    assert _child(window, QLabel, "app-brand").text() == "风信子"
    assert _child(window, QLabel, "document-title").text() == "未选择文件"
    assert _child(window, QFrame, "function-panel").isEnabled()
    assert _child(window, QFrame, "file-library").isEnabled()
    assert _child(window, QFrame, "version-tree-panel").isEnabled()
    assert _child(window, QFrame, "formula-bar").isEnabled()
    assert _child(window, QFrame, "format-bar").isEnabled()
    assert main_splitter.count() == 3
    assert left_splitter.count() == 2
    assert import_button_parent is not None
    assert import_button_parent.objectName() == "top-toolbar"
    assert import_button.minimumHeight() >= 30
    assert not _child(window, QPushButton, "toolbar-save-version-button").isEnabled()


def test_main_runs_qt_event_loop() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from PySide6.QtCore import QTimer; "
                "from PySide6.QtWidgets import QApplication; "
                "from hyacinth.__main__ import main; "
                "app = QApplication.instance() or QApplication([]); "
                "QTimer.singleShot(0, app.quit); "
                "raise SystemExit(main([]))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr


def test_main_window_connects_task_queue_to_status_bar(qtbot: QtBot) -> None:
    event = TaskEvent(
        task_id="convert-1",
        state=TaskState.RUNNING,
        name="转换旧版工作簿",
        file_id="销售报表.xls",
        engine=EngineName.COM,
        progress=None,
        elapsed_seconds=1.2,
    )
    task_queue = FakeApplicationTaskQueue([event])

    from hyacinth.app import create_main_window

    window = create_main_window(task_queue=task_queue)
    qtbot.addWidget(window)
    window.show()
    status = _child(window, TaskStatusWidget, "task-status")

    qtbot.waitUntil(
        lambda: _child(status, QLabel, "task-status-state").text() == "处理中",
        timeout=500,
    )
    qtbot.mouseClick(  # type: ignore[no-untyped-call]
        _child(status, QPushButton, "task-status-cancel"),
        Qt.MouseButton.LeftButton,
    )
    window.close()

    assert task_queue.cancelled == ["convert-1"]
    assert task_queue.shutdown_called is True


def test_import_button_submits_task_and_lists_successful_result(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    source = tmp_path / "销售报表.xlsx"
    source.write_bytes(b"source")
    library_root = tmp_path / "library"
    task_queue = FakeApplicationTaskQueue([])

    from hyacinth.app import create_main_window

    window = create_main_window(
        task_queue=task_queue,
        library_root=library_root,
        file_picker=lambda _parent: source,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(  # type: ignore[no-untyped-call]
        _child(window, QPushButton, "toolbar-import-button"),
        Qt.MouseButton.LeftButton,
    )

    assert len(task_queue.submitted) == 1
    request = task_queue.submitted[0]
    assert request.operation == IMPORT_WORKBOOK_OPERATION
    assert request.payload == {
        "source_path": str(source),
        "library_root": str(library_root),
    }

    directory = library_root / "files" / request.file_id
    result = ImportedWorkbook(
        file_id=request.file_id,
        display_name=source.name,
        original_path=directory / "original" / source.name,
        working_path=directory / "working" / "current.xlsx",
    )
    task_queue.push_event(
        TaskEvent(
            task_id=request.task_id,
            state=TaskState.SUCCEEDED,
            name=request.name,
            file_id=request.file_id,
            engine=None,
            result=result,
        )
    )
    file_list = _child(window, QListWidget, "library-file-list")
    qtbot.waitUntil(lambda: file_list.count() == 1, timeout=500)

    assert file_list.item(0).text() == source.name
    assert file_list.currentRow() == 0


def test_failed_import_shows_reason_and_keeps_import_available(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    source = tmp_path / "损坏.xlsx"
    source.write_bytes(b"invalid")
    task_queue = FakeApplicationTaskQueue([])
    errors: list[str] = []

    from hyacinth.app import create_main_window

    window = create_main_window(
        task_queue=task_queue,
        library_root=tmp_path / "library",
        file_picker=lambda _parent: source,
        error_presenter=lambda _parent, message: errors.append(message),
    )
    qtbot.addWidget(window)
    window.show()
    button = _child(window, QPushButton, "toolbar-import-button")
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    request = task_queue.submitted[0]
    task_queue.push_event(
        TaskEvent(
            task_id=request.task_id,
            state=TaskState.FAILED,
            name=request.name,
            file_id=request.file_id,
            engine=None,
            message="工作簿无法打开",
        )
    )

    qtbot.waitUntil(lambda: errors == ["工作簿无法打开"], timeout=500)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert len(task_queue.submitted) == 2


def test_existing_file_loads_working_copy_and_renders_selected_sheet(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    library_root = tmp_path / "library"
    directory = library_root / "files" / "file-1"
    original = directory / "original" / "销售.xlsx"
    working = directory / "working" / "current.xlsx"
    original.parent.mkdir(parents=True)
    working.parent.mkdir(parents=True)
    original.write_bytes(b"original")
    workbook = Workbook()
    sales = workbook.active
    assert sales is not None
    sales.title = "销售"
    sales["A1"] = "一月"
    workbook.create_sheet("库存")["B2"] = 42
    workbook.save(working)
    workbook.close()
    task_queue = FakeApplicationTaskQueue([])

    from hyacinth.app import create_main_window

    window = create_main_window(task_queue=task_queue, library_root=library_root)
    qtbot.addWidget(window)
    window.show()

    assert len(task_queue.submitted) == 1
    request = task_queue.submitted[0]
    assert request.operation == BUILD_PREVIEW_INDEX_OPERATION
    assert request.payload["working_path"] == str(working)
    assert _child(window, QLabel, "document-title").text() == "销售.xlsx"
    assert window.windowTitle() == "风信子 — 销售.xlsx"
    preview = run_preview_index_task(request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            task_id=request.task_id,
            state=TaskState.SUCCEEDED,
            name=request.name,
            file_id=request.file_id,
            engine=None,
            result=preview,
        )
    )
    table = _child(window, QTableView, "preview-table")
    tabs = _child(window, QTabBar, "preview-sheet-tabs")
    qtbot.waitUntil(lambda: table.model() is not None, timeout=500)

    assert [tabs.tabText(index) for index in range(tabs.count())] == ["销售", "库存"]
    assert table.model().data(table.model().index(0, 0)) == "一月"
    window.close()
    preview.index_path.unlink()

    assert not preview.index_path.exists()


def test_switching_files_cancels_old_preview_and_ignores_its_result(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    library_root = tmp_path / "library"
    records: list[ImportedWorkbook] = []
    for file_id, name in (("file-1", "一.xlsx"), ("file-2", "二.xlsx")):
        directory = library_root / "files" / file_id
        original = directory / "original" / name
        working = directory / "working" / "current.xlsx"
        original.parent.mkdir(parents=True)
        working.parent.mkdir(parents=True)
        original.write_bytes(b"original")
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet["A1"] = name
        workbook.save(working)
        workbook.close()
        records.append(ImportedWorkbook(file_id, name, original, working))
    task_queue = FakeApplicationTaskQueue([])

    from hyacinth.app import create_main_window

    window = create_main_window(task_queue=task_queue, library_root=library_root)
    qtbot.addWidget(window)
    window.show()
    first_request = task_queue.submitted[0]
    stale_preview = run_preview_index_task(first_request, PreviewTaskContext())
    file_list = _child(window, QListWidget, "library-file-list")
    file_list.setCurrentRow(1)

    assert len(task_queue.submitted) == 2
    assert task_queue.cancelled == [first_request.task_id]
    task_queue.push_event(
        TaskEvent(
            task_id=first_request.task_id,
            state=TaskState.SUCCEEDED,
            name=first_request.name,
            file_id=first_request.file_id,
            engine=None,
            result=stale_preview,
        )
    )
    state = _child(window, QLabel, "preview-state")
    qtbot.wait(100)

    assert "正在加载" in state.text()


def test_sort_preview_apply_creates_child_and_refreshes_tree(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    library_root = tmp_path / "library"
    record = _seed_versioned_workbook(library_root)
    task_queue = FakeApplicationTaskQueue([])
    from hyacinth.app import create_main_window

    window = create_main_window(task_queue=task_queue, library_root=library_root)
    qtbot.addWidget(window)
    window.show()
    initial_request = task_queue.submitted[0]
    base_preview = run_preview_index_task(initial_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            initial_request.task_id,
            TaskState.SUCCEEDED,
            initial_request.name,
            initial_request.file_id,
            None,
            result=base_preview,
        )
    )
    preview_button = _child(window, QPushButton, "function-preview-button")
    qtbot.waitUntil(preview_button.isEnabled, timeout=500)
    primary = _child(window, QComboBox, "sort-primary-column")
    primary.setCurrentIndex(1)
    qtbot.mouseClick(preview_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    sort_request = task_queue.submitted[-1]
    assert sort_request.operation == SORT_PREVIEW_OPERATION
    assert not _child(window, QFrame, "top-toolbar").isEnabled()
    assert not _child(window, QListWidget, "library-file-list").isEnabled()
    parent = record.head_version
    assert parent is not None
    assert sort_request.payload["source_path"] == str(parent.snapshot_path)
    sort_result = run_sort_preview_task(sort_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            sort_request.task_id,
            TaskState.SUCCEEDED,
            sort_request.name,
            sort_request.file_id,
            EngineName.PYTHON,
            result=sort_result,
        )
    )
    qtbot.waitUntil(lambda: len(task_queue.submitted) == 3, timeout=500)
    temporary_index_request = task_queue.submitted[-1]
    temporary_preview = run_preview_index_task(temporary_index_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            temporary_index_request.task_id,
            TaskState.SUCCEEDED,
            temporary_index_request.name,
            temporary_index_request.file_id,
            None,
            result=temporary_preview,
        )
    )
    apply_button = _child(window, QPushButton, "function-apply-button")
    banner = _child(window, QLabel, "temporary-result-banner")
    qtbot.waitUntil(apply_button.isEnabled, timeout=500)
    assert banner.isVisible()
    assert _child(window, QFrame, "top-toolbar").isEnabled()
    assert _child(window, QListWidget, "library-file-list").isEnabled()
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    apply_request = task_queue.submitted[-1]
    assert apply_request.operation == APPLY_SORT_PREVIEW_OPERATION
    assert not _child(window, QFrame, "top-toolbar").isEnabled()
    assert not _child(window, QListWidget, "library-file-list").isEnabled()
    assert apply_request.payload["preview_path"] == str(sort_result.preview_path)
    assert apply_request.payload["preview_hash"] == sort_result.content_hash
    applied = run_apply_sort_preview_task(apply_request, PreviewTaskContext())
    task_queue.push_event(
        TaskEvent(
            apply_request.task_id,
            TaskState.SUCCEEDED,
            apply_request.name,
            apply_request.file_id,
            EngineName.PYTHON,
            result=applied,
        )
    )
    qtbot.waitUntil(lambda: len(task_queue.submitted) == 5, timeout=500)
    tree = _child(window, QGraphicsView, "version-tree-view")
    proxies = [item for item in tree.scene().items() if isinstance(item, QGraphicsProxyWidget)]
    head = MetadataStore(library_root).get_workbook("file-1").head_version

    assert len(proxies) == 2
    assert head is not None and head.parent_version_id == "version-1"
    assert not sort_result.preview_path.parent.exists()
    assert _child(window, QFrame, "top-toolbar").isEnabled()
    assert _child(window, QListWidget, "library-file-list").isEnabled()
