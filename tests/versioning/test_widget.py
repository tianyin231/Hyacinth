from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsLineItem,
    QGraphicsProxyWidget,
    QGraphicsView,
    QLabel,
    QPushButton,
)
from pytestqt.qtbot import QtBot
from shiboken6 import isValid

from hyacinth.versioning import VersionLayout, VersionRecord


def _send_wheel(
    view: QGraphicsView,
    *,
    delta: int,
    modifiers: Qt.KeyboardModifier,
) -> None:
    position = QPointF(view.viewport().rect().center())
    event = QWheelEvent(
        position,
        QPointF(view.viewport().mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view.viewport(), event)


def _set_tree(
    panel: object,
    display_name: str,
    versions: tuple[VersionRecord, ...],
    head_version_id: str | None = None,
    layouts: dict[str, VersionLayout] | None = None,
) -> None:
    from hyacinth.ui import FileVersionTree

    head = head_version_id or (versions[-1].version_id if versions else None)
    panel.set_workbooks(  # type: ignore[attr-defined]
        (FileVersionTree("file-1", display_name, versions, head, layouts or {}),),
        current_file_id="file-1",
    )


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

    _set_tree(panel, "销售报表.xlsx", (version,))

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

    _set_tree(panel, "销售报表.xlsx", (root, child), child.version_id)
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
    # 非 HEAD 的根节点也要有独立的“根版本”标记（需求第 47 节）
    assert root_head is not None and root_head.text() == "根版本" and not root_head.isHidden()
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
    _set_tree(panel, "销售报表.xlsx", (version,), version.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    replaced_scene = view.scene()

    for _ in range(10):
        _set_tree(panel, "销售报表.xlsx", (version,), version.version_id)
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
    _set_tree(panel, "销售报表.xlsx", (root, child), child.version_id)
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

    assert preview_signal.args == ["file-1", "version-1"]
    assert cards["version-1"].property("selected") is True
    assert cards["version-2"].property("selected") is False
    assert continue_button.isEnabled()
    with qtbot.waitSignal(panel.version_continue_requested) as continue_signal:
        qtbot.mouseClick(continue_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert continue_signal.args == ["file-1", "version-1"]

    with qtbot.waitSignal(panel.version_continue_requested) as double_click_signal:
        qtbot.mouseDClick(cards["version-1"], Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert double_click_signal.args == ["file-1", "version-1"]


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
    _set_tree(
        panel,
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
    # 固定布局保存画布绝对坐标，渲染原样使用
    assert proxies[root.version_id].pos().y() == 60.0
    assert len(edges) == 1
    old_line = edges[0].line()
    root_card = proxies[root.version_id].widget()
    assert root_card is not None
    center = view.mapFromScene(proxies[root.version_id].sceneBoundingRect().center())

    with qtbot.waitSignal(panel.version_position_changed) as moved_signal:
        qtbot.mousePress(  # type: ignore[no-untyped-call]
            view.viewport(), Qt.MouseButton.LeftButton, pos=center
        )
        qtbot.mouseMove(view.viewport(), pos=center + QPoint(50, 35))  # type: ignore[no-untyped-call]
        qtbot.mouseRelease(
            view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=center + QPoint(50, 35),
        )  # type: ignore[no-untyped-call]

    assert moved_signal.args[0] == "file-1"
    assert moved_signal.args[1] == root.version_id
    assert moved_signal.args[2] > 80.0
    assert moved_signal.args[3] > 60.0
    assert edges[0].line() != old_line


def test_version_tree_wheel_gestures_follow_original_document(
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
    panel.resize(320, 420)
    panel.show()
    _set_tree(panel, "销售报表.xlsx", (root, child), child.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    qtbot.waitUntil(lambda: view.horizontalScrollBar().maximum() > 0)
    assert view.verticalScrollBar().maximum() > 0
    assert view.sceneRect().width() == 10000.0
    assert view.sceneRect().height() == 10000.0

    horizontal = view.horizontalScrollBar()
    vertical = view.verticalScrollBar()
    initial_horizontal = horizontal.value()
    initial_vertical = vertical.value()
    initial_scale = view.transform().m11()
    _send_wheel(view, delta=-120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert vertical.value() > initial_vertical

    _send_wheel(view, delta=-120, modifiers=Qt.KeyboardModifier.ShiftModifier)
    assert horizontal.value() > initial_horizontal
    assert view.transform().m11() == initial_scale

    _send_wheel(view, delta=120, modifiers=Qt.KeyboardModifier.ControlModifier)
    assert view.transform().m11() > initial_scale


def test_version_nodes_are_clamped_inside_large_canvas(qtbot: QtBot, tmp_path: Path) -> None:
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
    _set_tree(panel, "销售报表.xlsx", (root,), root.version_id)
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxy = next(item for item in view.scene().items() if isinstance(item, QGraphicsProxyWidget))

    panel._move_version("file-1", root.version_id, -100000.0, 100000.0)

    assert proxy.pos().x() == view.sceneRect().left()
    assert proxy.pos().y() == view.sceneRect().bottom() - proxy.size().height()


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
    _set_tree(panel, "销售报表.xlsx", (root, child), child.version_id)
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

    panel.show_delete_undo("file-1", root.version_id)
    undo = panel.findChild(QPushButton, "version-undo-delete-button")
    assert undo is not None and undo.isVisibleTo(panel)
    with qtbot.waitSignal(panel.version_restore_requested) as restore_signal:
        qtbot.mouseClick(undo, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]
    assert restore_signal.args == ["file-1", root.version_id]


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
    _set_tree(panel, "销售报表.xlsx", (root,), root.version_id)
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
    assert delete_signal.args == ["file-1", root.version_id]


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
    _set_tree(panel, "销售报表.xlsx", (root,), root.version_id)

    with qtbot.waitSignal(panel.version_export_requested) as download:
        panel._request_export("file-1", root.version_id, False)
    with qtbot.waitSignal(panel.version_export_requested) as save_as:
        panel._request_export("file-1", root.version_id, True)

    assert download.args == ["file-1", root.version_id, False]
    assert save_as.args == ["file-1", root.version_id, True]


def _record(
    version_id: str,
    parent_id: str | None,
    name: str,
    created_hour: int,
    snapshot: Path,
    *,
    deleted: bool = False,
) -> VersionRecord:
    return VersionRecord(
        version_id,
        "file-1",
        parent_id,
        name,
        datetime(2026, 8, 16, created_hour, 0, tzinfo=UTC),
        "import" if parent_id is None else "sort",
        None,
        snapshot,
        "a" * 64,
        deleted_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC) if deleted else None,
    )


def test_tree_layout_places_parent_centered_between_branches(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import VersionTreePanel

    root = _record("root", None, "导入原始文件", 8, tmp_path / "r.xlsx")
    branch_a = _record("branch-a", "root", "分支A", 9, tmp_path / "a.xlsx")
    branch_b = _record("branch-b", "root", "分支B", 10, tmp_path / "b.xlsx")
    leaf = _record("leaf", "branch-a", "叶子", 11, tmp_path / "l.xlsx")
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    _set_tree(panel, "销售.xlsx", (root, branch_a, branch_b, leaf), "leaf")

    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxies = {
        str(proxy.widget().property("version-id")): proxy
        for proxy in view.scene().items()
        if isinstance(proxy, QGraphicsProxyWidget) and proxy.widget() is not None
    }
    root_y = proxies["root"].pos().y()
    assert proxies["branch-a"].pos().y() != proxies["branch-b"].pos().y()
    assert root_y == (proxies["branch-a"].pos().y() + proxies["branch-b"].pos().y()) / 2
    assert proxies["leaf"].pos().y() == proxies["branch-a"].pos().y()
    assert proxies["branch-a"].pos().x() > proxies["root"].pos().x()


def test_deleted_version_node_can_be_dragged(qtbot: QtBot, tmp_path: Path) -> None:
    from hyacinth.ui import VersionTreePanel

    root = _record("root", None, "导入原始文件", 8, tmp_path / "r.xlsx")
    deleted = _record("deleted-child", "root", "已删除分支", 9, tmp_path / "d.xlsx", deleted=True)
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(700, 500)
    panel.show()
    _set_tree(panel, "销售.xlsx", (root, deleted), "root")
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    proxy = next(
        item
        for item in view.scene().items()
        if isinstance(item, QGraphicsProxyWidget)
        and item.widget() is not None
        and str(item.widget().property("version-id")) == "deleted-child"
    )
    center = view.mapFromScene(proxy.sceneBoundingRect().center())

    with qtbot.waitSignal(panel.version_position_changed) as moved:
        qtbot.mousePress(  # type: ignore[no-untyped-call]
            view.viewport(), Qt.MouseButton.LeftButton, pos=center
        )
        qtbot.mouseMove(view.viewport(), pos=center + QPoint(60, 40))  # type: ignore[no-untyped-call]
        qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=center + QPoint(60, 40))  # type: ignore[no-untyped-call]

    assert moved.args[0] == "file-1"
    assert moved.args[1] == "deleted-child"


def test_reset_layout_button_emits_signal(qtbot: QtBot) -> None:
    from hyacinth.ui import VersionTreePanel

    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    reset_button = panel.findChild(QPushButton, "version-reset-layout-button")
    assert reset_button is not None

    with qtbot.waitSignal(panel.layout_reset_requested):
        qtbot.mouseClick(reset_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]


def test_lane_positions_stay_stable_when_current_file_changes(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import FileVersionTree, VersionTreePanel

    root_a = _record("root-a", None, "导入A", 8, tmp_path / "a.xlsx")
    root_b = _record("root-b", None, "导入B", 9, tmp_path / "b.xlsx")
    tree_a = FileVersionTree("file-a", "A.xlsx", (root_a,), "root-a", {})
    tree_b = FileVersionTree("file-b", "B.xlsx", (root_b,), "root-b", {})
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.set_workbooks((tree_a, tree_b), current_file_id="file-a")
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None

    def position_of(version_id: str) -> tuple[float, float]:
        proxy = next(
            item
            for item in view.scene().items()
            if isinstance(item, QGraphicsProxyWidget)
            and item.widget() is not None
            and str(item.widget().property("version-id")) == version_id
        )
        return (proxy.pos().x(), proxy.pos().y())

    before_b = position_of("root-b")
    panel.set_workbooks((tree_a, tree_b), current_file_id="file-b")

    assert position_of("root-b") == before_b
    assert position_of("root-a")[1] < before_b[1]


def test_canvas_has_no_lane_decorations_and_nodes_survive_gc(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    import gc

    from hyacinth.ui import FileVersionTree, VersionTreePanel

    root = _record("root", None, "导入原始文件", 8, tmp_path / "r.xlsx")
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    trees = (
        FileVersionTree("file-1", "A.xlsx", (root,), "root", {}),
        FileVersionTree("file-2", "B.xlsx", (), None, {}),
    )
    panel.set_workbooks(trees, current_file_id="file-1")

    def node_count() -> int:
        view = panel.findChild(QGraphicsView, "version-tree-view")
        assert view is not None
        return sum(
            1
            for item in view.scene().items()
            if isinstance(item, QGraphicsProxyWidget) and item.widget() is not None
        )

    assert node_count() == 1
    gc.collect()
    assert node_count() == 1
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None
    assert not [item for item in view.scene().items() if isinstance(item, QGraphicsSimpleTextItem)]


def test_view_mode_toggle_filters_current_file_and_keeps_position(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import FileVersionTree, VersionTreePanel

    root_a = _record("root-a", None, "导入A", 8, tmp_path / "a.xlsx")
    root_b = _record("root-b", None, "导入B", 9, tmp_path / "b.xlsx")
    tree_a = FileVersionTree("file-a", "A.xlsx", (root_a,), "root-a", {})
    tree_b = FileVersionTree("file-b", "B.xlsx", (root_b,), "root-b", {})
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.resize(700, 500)
    panel.show()
    panel.set_workbooks((tree_a, tree_b), current_file_id="file-a")
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None

    def visible_file_ids() -> set[str]:
        return {
            str(proxy.widget().property("file-id"))
            for proxy in view.scene().items()
            if isinstance(proxy, QGraphicsProxyWidget)
            and proxy.widget() is not None
            and proxy.isVisible()
        }

    proxy_a = next(
        proxy
        for proxy in view.scene().items()
        if isinstance(proxy, QGraphicsProxyWidget)
        and proxy.widget() is not None
        and str(proxy.widget().property("version-id")) == "root-a"
    )
    view.centerOn(proxy_a)
    center_before = view.mapToScene(view.viewport().rect().center())
    retired_before = len(panel._retired_scenes)

    mode_button = panel.findChild(QPushButton, "version-mode-toggle-button")
    assert mode_button is not None
    qtbot.mouseClick(mode_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert visible_file_ids() == {"file-a"}
    assert mode_button.text() == "查看全部文件"
    proxy_a_after = next(
        proxy
        for proxy in view.scene().items()
        if isinstance(proxy, QGraphicsProxyWidget)
        and proxy.widget() is not None
        and str(proxy.widget().property("version-id")) == "root-a"
    )
    center_after = view.mapToScene(view.viewport().rect().center())
    # 模式切换只显隐泳道：场景未重建、视口零位移。
    assert proxy_a_after is proxy_a
    assert abs(center_after.y() - center_before.y()) < 0.1
    assert abs(center_after.x() - center_before.x()) < 0.1
    assert len(panel._retired_scenes) == retired_before

    for _ in range(7):
        qtbot.mouseClick(mode_button, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]

    assert len(panel._retired_scenes) == retired_before
    assert visible_file_ids() == {"file-a", "file-b"}
    assert mode_button.text() == "仅看当前文件"


def test_canvas_refresh_keeps_existing_nodes_until_manual_reset(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    from hyacinth.ui import FileVersionTree, VersionTreePanel

    root = _record("root", None, "导入原始文件", 8, tmp_path / "r.xlsx")
    branch_a = _record("branch-a", "root", "分支A", 9, tmp_path / "a.xlsx")
    branch_b = _record("branch-b", "root", "分支B", 10, tmp_path / "b.xlsx")
    branch_c = _record("branch-c", "root", "分支C", 11, tmp_path / "c.xlsx")
    panel = VersionTreePanel()
    qtbot.addWidget(panel)
    panel.show()
    view = panel.findChild(QGraphicsView, "version-tree-view")
    assert view is not None

    def positions(trees: tuple[FileVersionTree, ...]) -> dict[str, tuple[float, float]]:
        panel.set_workbooks(trees, current_file_id="file-1")
        return {
            str(proxy.widget().property("version-id")): (proxy.pos().x(), proxy.pos().y())
            for proxy in view.scene().items()
            if isinstance(proxy, QGraphicsProxyWidget) and proxy.widget() is not None
        }

    before = positions(
        (FileVersionTree("file-1", "销售.xlsx", (root, branch_a, branch_b), "branch-b", {}),)
    )

    # 模拟“从此继续”等触发的新版本节点加入后的画布刷新
    after = positions(
        (
            FileVersionTree(
                "file-1", "销售.xlsx", (root, branch_a, branch_b, branch_c), "branch-c", {}
            ),
        )
    )

    for version_id in ("root", "branch-a", "branch-b"):
        assert after[version_id] == before[version_id]

    def overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
        return abs(a[0] - b[0]) < 230.0 and abs(a[1] - b[1]) < 108.0

    assert not any(
        overlaps(after["branch-c"], after[vid]) for vid in ("root", "branch-a", "branch-b")
    )

    # 手动重整布局后全部节点回到树形默认排布
    panel.clear_remembered_layouts()
    reset = positions(
        (
            FileVersionTree(
                "file-1", "销售.xlsx", (root, branch_a, branch_b, branch_c), "branch-c", {}
            ),
        )
    )
    assert reset["branch-a"] == (28.0 + 260.0, 42.0 + 40.0)
    assert reset["branch-c"][1] == before["branch-b"][1] + 126.0
    assert reset["root"][1] == (reset["branch-a"][1] + reset["branch-c"][1]) / 2
