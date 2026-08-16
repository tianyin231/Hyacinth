"""左上“功能选择”面板测试（需求第 16/27 节）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QListWidget
from pytestqt.qtbot import QtBot

from hyacinth.ui.function_panel import (
    FUNCTION_ENTRIES,
    FunctionSelectionPanel,
    highlight_match,
)


def _entry_labels(panel: FunctionSelectionPanel) -> list[tuple[str, QLabel]]:
    listing = panel.findChild(QListWidget, "function-list")
    assert listing is not None
    labels: list[tuple[str, QLabel]] = []
    for row in range(listing.count()):
        item = listing.item(row)
        widget = listing.itemWidget(item) if item is not None else None
        assert isinstance(widget, QLabel)
        labels.append((str(item.data(0) or ""), widget))
    return labels


def test_highlight_match_wraps_query_in_span() -> None:
    assert highlight_match("删除重复行", "") == "删除重复行"
    assert highlight_match("删除重复行", "排序") == "删除重复行"
    assert "background" in highlight_match("删除重复行", "重复")
    assert highlight_match("删除重复行", "重复").startswith("删除<span")


def test_function_panel_lists_all_functions_without_query(qtbot: QtBot) -> None:
    panel = FunctionSelectionPanel()
    qtbot.addWidget(panel)
    listing = panel.findChild(QListWidget, "function-list")
    assert listing is not None
    assert listing.count() == len(FUNCTION_ENTRIES)


def test_function_panel_filters_by_keyword_and_highlights(qtbot: QtBot) -> None:
    panel = FunctionSelectionPanel()
    qtbot.addWidget(panel)
    # “重复”是标签文本“删除重复行”的子串 → 命中并高亮该片段。
    panel._search_input.setText("重复")
    panel._apply_filter()

    listing = panel.findChild(QListWidget, "function-list")
    assert listing is not None
    assert listing.count() == 1
    _action, entry = _entry_labels(panel)[0]
    assert entry.textFormat() == Qt.TextFormat.RichText
    assert entry.text().startswith("删除<span")  # 匹配文字高亮（需求第 27 节）

    panel._search_input.setText("不存在的功能")
    panel._apply_filter()
    assert listing.count() == 0
    assert panel._empty_label.isVisibleTo(panel)


def test_function_panel_emits_trigger_when_enabled(qtbot: QtBot) -> None:
    panel = FunctionSelectionPanel()
    qtbot.addWidget(panel)
    spy = QSignalSpy(panel.function_triggered)
    panel.set_actions_enabled(False)
    panel._search_input.setText("筛选")
    panel._apply_filter()
    listing = panel.findChild(QListWidget, "function-list")
    assert listing is not None
    item = listing.item(0)
    assert item is not None
    listing.itemClicked.emit(item)
    assert spy.count() == 0

    panel.set_actions_enabled(True)
    listing.itemClicked.emit(listing.item(0))
    assert spy.count() == 1
    assert spy.at(0)[0] == "filter"
