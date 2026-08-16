"""左上“功能选择”面板：功能搜索 + 点击直达（需求第 16/27 节）。"""

from __future__ import annotations

import html

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 功能索引：action_id 与功能区条按钮一一对应，关键词用于搜索匹配。
FUNCTION_ENTRIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("sort-asc", "升序 A→Z", ("升序", "排序", "正序", "字母", "sort")),
    ("sort-desc", "降序 Z→A", ("降序", "排序", "倒序", "倒排", "sort")),
    ("multi-sort", "多列排序…", ("多列", "排序", "关键字", "优先级", "两列")),
    ("filter", "筛选", ("筛选", "过滤", "条件", "filter")),
    ("deduplicate", "删除重复行", ("去重", "重复", "去重复", "清理", "dedup")),
    ("blank-rows", "删除空白行", ("空白行", "空行", "清理", "删除行")),
    ("trim", "清除空格", ("空格", "首尾", "清除", "trim")),
    ("find-replace", "查找替换", ("查找", "替换", "搜索", "find", "replace")),
)


def highlight_match(text: str, query: str) -> str:
    """把 text 中首个 query 命中片段包上高亮 span，返回 HTML。"""
    if not query:
        return html.escape(text)
    index = text.lower().find(query.lower())
    if index < 0:
        return html.escape(text)
    end = index + len(query)
    return (
        f"{html.escape(text[:index])}"
        f'<span style="background:#fde68a;">{html.escape(text[index:end])}</span>'
        f"{html.escape(text[end:])}"
    )


class FunctionSelectionPanel(QFrame):
    """“功能选择”面板：搜索过滤功能区条全部功能，点击触发对应功能。"""

    function_triggered = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("function-selection")
        self.setMinimumSize(230, 150)
        # 与功能区条一致：常态可点（无预览时走“请先选择文件”提示），
        # 处理任务进行期间统一禁用。
        self._enabled = True
        self._query = ""

        header = QFrame(self)
        header.setObjectName("panel-header")
        header.setFixedHeight(38)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(11, 0, 9, 0)
        title = QLabel("功能选择", self)
        title.setProperty("class", "panel-title")
        header_layout.addWidget(title)

        self._search_input = QLineEdit(self)
        self._search_input.setObjectName("function-search-input")
        self._search_input.setPlaceholderText("搜索功能，如：去重 / 排序")
        self._search_input.setClearButtonEnabled(True)

        self._function_list = QListWidget(self)
        self._function_list.setObjectName("function-list")
        self._function_list.setAccessibleName("功能列表")
        self._function_list.itemClicked.connect(self._handle_clicked)

        self._empty_label = QLabel("没有匹配的功能", self)
        self._empty_label.setObjectName("function-empty-state")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)

        # 约 150ms 延迟实时过滤（需求第 27 节）。
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._apply_filter)
        self._search_input.textChanged.connect(lambda _text: self._debounce.start())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._search_input)
        layout.addWidget(self._function_list, 1)
        layout.addWidget(self._empty_label)
        self._apply_filter()

    def set_actions_enabled(self, enabled: bool) -> None:
        """无可用预览时禁用条目点击（与功能区条同步）。"""
        self._enabled = enabled
        self._apply_filter()

    def focus_search(self) -> None:
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _apply_filter(self) -> None:
        self._query = self._search_input.text().strip()
        self._function_list.clear()
        visible = 0
        for action_id, label, keywords in FUNCTION_ENTRIES:
            if self._query and not self._matches(label, keywords):
                continue
            visible += 1
            item = QListWidgetItem(self._function_list)
            item.setData(Qt.ItemDataRole.UserRole, action_id)
            item.setSizeHint(QSize(0, 30))
            entry = QLabel(self._function_list)
            entry.setProperty("class", "function-entry")
            # 显式富文本：高亮匹配文字（需求第 27 节）。
            entry.setTextFormat(Qt.TextFormat.RichText)
            entry.setText(highlight_match(label, self._query))
            entry.setToolTip(f"执行：{label}" if self._enabled else "先选择文件加载预览后再使用")
            if not self._enabled:
                entry.setProperty("class", "function-entry disabled")
            self._function_list.addItem(item)
            self._function_list.setItemWidget(item, entry)
        self._empty_label.setVisible(visible == 0)

    def _matches(self, label: str, keywords: tuple[str, ...]) -> bool:
        query = self._query.lower()
        return query in label.lower() or any(query in word.lower() for word in keywords)

    def _handle_clicked(self, item: QListWidgetItem) -> None:
        if not self._enabled:
            return
        action_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(action_id, str):
            self.function_triggered.emit(action_id)
