from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QGraphicsProxyWidget, QGraphicsView, QLabel
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
