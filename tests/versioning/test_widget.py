from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsLineItem,
    QGraphicsProxyWidget,
    QGraphicsView,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
)
from pytestqt.qtbot import QtBot
from shiboken6 import isValid

from hyacinth.versioning import VersionLayout, VersionRecord


def test_version_tree_renders_real_root_node_and_head(qtbot: QtBot, tmp_path: Path) -> None:
    from hyacinth.ui import VersionTreePanel

    version = VersionRecord(
        version_id="version-1",
        file_id="file-1",
        parent_version_id=None,
        name="导入原始文件",
        created_at=datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        operation="import",
        engine=None,
        snapshot_path=tmp_path / "snapshot.xlsx",
        content_hash="a" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(340, 500)
    panel.show()

    panel.set_workbook("销售报表.xlsx", version)

    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxies = [item for item in view.scene().items() if isinstance(item, QGraphicsProxyWidget)]
    assert len(proxies) == 1
    node_center = view.mapFromScene(proxies[0].sceneBoundingRect().center())
    assert view.viewport().rect().contains(node_center)
    card = proxies[0].widget()
    assert card is not None
    title = card.findChild(QLabel, "root-version-name")
    metadata = card.findChild(QLabel, "root-version-meta")
    head = card.findChild(QLabel, "root-version-head")
    assert title is not None and title.text() == "导入原始文件"
    assert metadata is not None and "2026-08-15" in metadata.text()
    assert "XLSX" in metadata.text()
    assert head is not None and head.text() == "HEAD · 根版本"


def test_version_tree_renders_child_to_right_with_edge_and_head(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    child = VersionRecord(
        "version-2",
        "file-1",
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        None,
        tmp_path / "child.xlsx",
        "b" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(340, 500)
    panel.show()

    panel.set_workbook("销售报表.xlsx", (root, child), child.version_id)
    qtbot.wait(20)

    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxies = [item for item in view.scene().items() if isinstance(item, QGraphicsProxyWidget)]
    edges = [item for item in view.scene().items() if isinstance(item, QGraphicsLineItem)]
    cards: dict[str, QGraphicsProxyWidget] = {}
    for proxy in proxies:
        widget = proxy.widget()
        assert widget is not None
        title = widget.findChild(QLabel, "root-version-name")
        assert title is not None
        cards[title.text()] = proxy
    assert len(proxies) == 2
    assert len(edges) == 1
    assert cards["多列排序"].x() > cards["导入原始文件"].x()
    root_rect = cards["导入原始文件"].sceneBoundingRect()
    assert view.viewport().rect().contains(view.mapFromScene(root_rect.topLeft()))
    assert view.viewport().rect().contains(view.mapFromScene(root_rect.bottomRight()))
    root_head = cards["导入原始文件"].widget().findChild(QLabel, "root-version-head")
    child_head = cards["多列排序"].widget().findChild(QLabel, "root-version-head")
    assert root_head is not None and root_head.isHidden()
    assert child_head is not None and child_head.text() == "HEAD" and not child_head.isHidden()


def test_version_tree_keeps_replaced_scene_alive_until_panel_closes(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    version = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.set_workbook("销售报表.xlsx", version, version.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    replaced_scene = view.scene()

    for _ in range(10):
        panel.set_workbook("销售报表.xlsx", version, version.version_id)
    qtbot.wait(20)

    assert isValid(replaced_scene)


def test_version_tree_selects_history_and_requests_continue(qtbot: QtBot, tmp_path: Path) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    child = VersionRecord(
        "version-2",
        "file-1",
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        None,
        tmp_path / "child.xlsx",
        "b" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(340, 500)
    panel.show()
    panel.set_workbook("销售报表.xlsx", (root, child), child.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    cards = {
        str(proxy.widget().property("version-id")): proxy.widget()
        for proxy in view.scene().items()
        if isinstance(proxy, QGraphicsProxyWidget) and proxy.widget() is not None
    }
    continue_button = panel.findChild(QPushButton, "version-continue-button")
    assert set(cards) == {"version-1", "version-2"}
    assert continue_button is not None and not continue_button.isEnabled()

    with qtbot.waitSignal(panel.version_preview_requested) as preview_signal:
        qtbot.mouseClick(cards["version-1"], Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert preview_signal.args == ["version-1"]
    assert cards["version-1"].property("selected") is True
    assert cards["version-2"].property("selected") is False
    assert continue_button.isEnabled()
    with qtbot.waitSignal(panel.version_continue_requested) as continue_signal:
        qtbot.mouseClick(continue_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert continue_signal.args == ["version-1"]

    with qtbot.waitSignal(panel.version_continue_requested) as double_click_signal:
        qtbot.mouseDClick(cards["version-1"], Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert double_click_signal.args == ["version-1"]


def test_version_tree_drag_moves_connected_edge_and_emits_persisted_position(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    child = VersionRecord(
        "version-2",
        "file-1",
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        None,
        tmp_path / "child.xlsx",
        "b" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(700, 500)
    panel.show()
    panel.set_workbook(
        "销售报表.xlsx",
        (root, child),
        child.version_id,
        {root.version_id: VersionLayout(80.0, 60.0, True)},
    )
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxies = {
        str(item.widget().property("version-id")): item
        for item in view.scene().items()
        if isinstance(item, QGraphicsProxyWidget) and item.widget() is not None
    }
    edges = [item for item in view.scene().items() if isinstance(item, QGraphicsLineItem)]
    assert proxies[root.version_id].pos().x() == 80.0
    assert proxies[root.version_id].pos().y() == 60.0
    assert len(edges) == 1
    old_line = edges[0].line()
    root_card = proxies[root.version_id].widget()
    assert root_card is not None
    center = root_card.rect().center()

    with qtbot.waitSignal(panel.version_position_changed) as moved_signal:
        qtbot.mousePress(root_card, Qt.MouseButton.LeftButton, pos=center)  # type: ignore[no-untyped-call]
        qtbot.mouseMove(root_card, pos=center + QPoint(50, 35))  # type: ignore[no-untyped-call]
        qtbot.mouseRelease(
            root_card,
            Qt.MouseButton.LeftButton,
            pos=center + QPoint(50, 35),
        )  # type: ignore[no-untyped-call]

    assert moved_signal.args[0] == root.version_id
    assert moved_signal.args[1] > 80.0
    assert moved_signal.args[2] > 60.0
    assert edges[0].line() != old_line


def test_deleted_version_is_placeholder_and_can_be_restored_but_not_previewed(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
        deleted_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
    )
    child = VersionRecord(
        "version-2",
        "file-1",
        root.version_id,
        "多列排序",
        datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "sort",
        None,
        tmp_path / "child.xlsx",
        "b" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.set_workbook("销售报表.xlsx", (root, child), child.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    cards = {
        str(item.widget().property("version-id")): item.widget()
        for item in view.scene().items()
        if isinstance(item, QGraphicsProxyWidget) and item.widget() is not None
    }
    deleted_card = cards[root.version_id]
    assert deleted_card.property("deleted") is True
    assert deleted_card.accessibleName() == "已删除版本 导入原始文件"

    with qtbot.assertNotEmitted(panel.version_preview_requested):
        qtbot.mouseClick(deleted_card, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    panel.show_delete_undo(root.version_id)
    undo = panel.findChild(QPushButton, "version-undo-delete-button")
    assert undo is not None and undo.isVisibleTo(panel)
    with qtbot.waitSignal(panel.version_restore_requested) as restore_signal:
        qtbot.mouseClick(undo, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert restore_signal.args == [root.version_id]


def test_version_card_delete_key_requests_soft_delete(qtbot: QtBot, tmp_path: Path) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.set_workbook("销售报表.xlsx", root, root.version_id)
    panel.show()
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    card = next(
        item.widget()
        for item in view.scene().items()
        if isinstance(item, QGraphicsProxyWidget) and item.widget() is not None
    )
    card.setFocus()
    with qtbot.waitSignal(panel.version_delete_requested) as delete_signal:
        QApplication.sendEvent(
            card,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier),
        )
    assert delete_signal.args == [root.version_id]


def test_version_tree_requests_download_and_save_as_for_active_node(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    root = VersionRecord(
        "version-1",
        "file-1",
        None,
        "导入原始文件",
        datetime(2026, 8, 15, 7, 30, tzinfo=UTC),
        "import",
        None,
        tmp_path / "root.xlsx",
        "a" * 64,
    )
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.set_workbook("销售报表.xlsx", root, root.version_id)

    with qtbot.waitSignal(panel.version_export_requested) as download:
        panel._request_export(root.version_id, False)
    with qtbot.waitSignal(panel.version_export_requested) as save_as:
        panel._request_export(root.version_id, True)

    assert download.args == [root.version_id, False]
    assert save_as.args == [root.version_id, True]


def test_function_panel_emits_accessible_sort_parameters(qtbot: QtBot) -> None:
    from hyacinth.ui import FunctionPanel

    panel = FunctionPanel()
    qtbot.addWidget(panel)
    stack = panel.findChild(QStackedWidget, "function-body-stack")
    footer = panel.findChild(QFrame, "function-footer")
    assert stack is not None and stack.currentIndex() == 0
    assert footer is not None and footer.isHidden()
    panel.set_workbook({"销售": ("A · 名称", "B · 数量")})
    assert stack.currentIndex() == 1
    primary = panel.findChild(QComboBox, "sort-primary-column")
    secondary = panel.findChild(QComboBox, "sort-secondary-column")
    preview = panel.findChild(QPushButton, "function-preview-button")
    apply = panel.findChild(QPushButton, "function-apply-button")
    cancel = panel.findChild(QPushButton, "function-cancel-button")
    assert primary is not None and secondary is not None
    assert preview is not None and apply is not None and cancel is not None
    primary.setCurrentIndex(1)

    with qtbot.waitSignal(panel.preview_requested) as signal:
        qtbot.mouseClick(preview, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert signal.args == [
        "销售",
        [{"column_index": 1, "direction": "asc"}],
    ]
    assert preview.accessibleName() == "预览排序结果"
    panel.set_preview_ready()
    assert apply.isEnabled()
    assert cancel.isEnabled()


def test_function_panel_emits_deduplicate_parameters_and_shows_mapping(
    qtbot: QtBot,
) -> None:
    from hyacinth.ui import FunctionPanel
    from hyacinth.ui.shell import DuplicateMappingModel

    panel = FunctionPanel()
    qtbot.addWidget(panel)
    panel.set_workbook({"销售": ("A · 名称", "B · 数量")})
    operation = panel.findChild(QComboBox, "processing-operation")
    parameter_stack = panel.findChild(QStackedWidget, "processing-parameter-stack")
    columns = panel.findChild(QListWidget, "deduplicate-key-columns")
    keep = panel.findChild(QComboBox, "deduplicate-keep")
    ignore_case = panel.findChild(QCheckBox, "deduplicate-ignore-case")
    trim = panel.findChild(QCheckBox, "deduplicate-trim-whitespace")
    preview = panel.findChild(QPushButton, "function-preview-button")
    details = panel.findChild(QPushButton, "deduplicate-details-button")
    state = panel.findChild(QLabel, "sort-state")
    assert operation is not None
    assert parameter_stack is not None
    assert columns is not None
    assert keep is not None
    assert ignore_case is not None
    assert trim is not None
    assert preview is not None
    assert details is not None
    assert state is not None
    operation.setCurrentIndex(operation.findData("deduplicate"))
    assert parameter_stack.currentIndex() == 1
    columns.item(0).setSelected(True)
    keep.setCurrentIndex(keep.findData("last"))
    ignore_case.setChecked(True)
    trim.setChecked(True)

    with qtbot.waitSignal(panel.deduplicate_preview_requested) as signal:
        qtbot.mouseClick(preview, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert signal.args == [
        "销售",
        {
            "key_columns": [0],
            "keep": "last",
            "ignore_case": True,
            "trim_whitespace": True,
        },
    ]
    panel.set_deduplicate_preview_ready(1, 2, ((4, (2, 3)),))
    assert "1 个重复组" in state.text()
    assert "删除 2 行" in state.text()
    assert details.isEnabled()

    model = DuplicateMappingModel(((4, (2, 3)),))
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "第 4 行"
    assert model.data(model.index(0, 1)) == "第 2 行、第 3 行"


def test_function_panel_emits_delete_blank_rows_parameters_and_shows_rows(
    qtbot: QtBot,
) -> None:
    from hyacinth.ui import FunctionPanel
    from hyacinth.ui.shell import DeletedRowsModel

    panel = FunctionPanel()
    qtbot.addWidget(panel)
    panel.set_workbook({"销售": ("A · 名称", "B · 数量")})
    operation = panel.findChild(QComboBox, "processing-operation")
    parameter_stack = panel.findChild(QStackedWidget, "processing-parameter-stack")
    columns = panel.findChild(QListWidget, "blank-rows-key-columns")
    allow_unsafe = panel.findChild(QCheckBox, "blank-rows-allow-unsafe")
    preview = panel.findChild(QPushButton, "function-preview-button")
    details = panel.findChild(QPushButton, "blank-rows-details-button")
    state = panel.findChild(QLabel, "sort-state")
    assert operation is not None
    assert parameter_stack is not None
    assert columns is not None
    assert allow_unsafe is not None
    assert preview is not None
    assert details is not None
    assert state is not None
    operation.setCurrentIndex(operation.findData("delete_blank_rows"))
    assert parameter_stack.currentIndex() == 2
    assert preview.accessibleName() == "预览删除空白行结果"
    columns.item(0).setSelected(True)
    allow_unsafe.setChecked(True)

    with qtbot.waitSignal(panel.delete_blank_rows_preview_requested) as signal:
        qtbot.mouseClick(preview, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert signal.args == [
        "销售",
        {"key_columns": [0], "allow_unsafe": True},
    ]
    panel.set_delete_blank_rows_preview_ready((3, 7), True)
    assert "删除 2 行" in state.text()
    assert "兼容预览" in state.text()
    assert details.isEnabled()

    model = DeletedRowsModel((3, 7))
    assert model.rowCount() == 2
    assert model.data(model.index(0, 0)) == "第 3 行"
    assert model.data(model.index(1, 0)) == "第 7 行"


def test_function_panel_emits_typed_filter_conditions_and_shows_statistics(
    qtbot: QtBot,
) -> None:
    from PySide6.QtWidgets import QLineEdit

    from hyacinth.ui import FunctionPanel

    panel = FunctionPanel()
    qtbot.addWidget(panel)
    panel.set_workbook({"销售": ("A · 名称", "B · 数量")})
    operation = panel.findChild(QComboBox, "processing-operation")
    parameter_stack = panel.findChild(QStackedWidget, "processing-parameter-stack")
    first_column = panel.findChild(QComboBox, "filter-first-column")
    first_operator = panel.findChild(QComboBox, "filter-first-operator")
    first_value = panel.findChild(QLineEdit, "filter-first-value")
    enable_second = panel.findChild(QCheckBox, "filter-enable-second")
    connector = panel.findChild(QComboBox, "filter-connector")
    second_column = panel.findChild(QComboBox, "filter-second-column")
    second_type = panel.findChild(QComboBox, "filter-second-type")
    second_operator = panel.findChild(QComboBox, "filter-second-operator")
    second_value = panel.findChild(QLineEdit, "filter-second-value")
    preview = panel.findChild(QPushButton, "function-preview-button")
    state = panel.findChild(QLabel, "sort-state")
    assert operation is not None and parameter_stack is not None
    assert first_column is not None and first_operator is not None and first_value is not None
    assert enable_second is not None and connector is not None
    assert second_column is not None and second_type is not None
    assert second_operator is not None and second_value is not None
    assert preview is not None and state is not None
    operation.setCurrentIndex(operation.findData("filter"))
    assert parameter_stack.currentIndex() == 3
    assert preview.accessibleName() == "预览条件筛选结果"
    first_operator.setCurrentIndex(first_operator.findData("contains"))
    first_value.setText("apple")
    enable_second.setChecked(True)
    second_column.setCurrentIndex(1)
    second_type.setCurrentIndex(second_type.findData("number"))
    second_operator.setCurrentIndex(second_operator.findData("greater_than"))
    second_value.setText("3")

    with qtbot.waitSignal(panel.filter_preview_requested) as signal:
        qtbot.mouseClick(preview, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert signal.args == [
        "销售",
        {
            "conditions": [
                {
                    "column_index": 0,
                    "operator": "contains",
                    "value_type": "text",
                    "value": "apple",
                    "second_value": None,
                },
                {
                    "column_index": 1,
                    "operator": "greater_than",
                    "value_type": "number",
                    "value": "3",
                    "second_value": None,
                },
            ],
            "connector": "and",
        },
    ]
    panel.set_filter_preview_ready(2, 5)
    assert "匹配 2 / 5 行" in state.text()
    assert "40.0%" in state.text()
