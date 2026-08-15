from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsLineItem,
    QGraphicsProxyWidget,
    QGraphicsView,
    QLabel,
    QPushButton,
)
from pytestqt.qtbot import QtBot

from hyacinth.versioning import VersionRecord


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


def test_function_panel_emits_accessible_sort_parameters(qtbot: QtBot) -> None:
    from hyacinth.ui import FunctionPanel

    panel = FunctionPanel()
    qtbot.addWidget(panel)
    panel.set_workbook({"销售": ("A · 名称", "B · 数量")})
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
