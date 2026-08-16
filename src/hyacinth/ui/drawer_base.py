"""右侧覆盖式抽屉公共基类（需求第 25 节弹层形态，版本对比复用）。

提供统一的覆盖式抽屉行为：从右往左滑入、向左滑出、点击外部区域关闭、
Esc 关闭、遵守系统“减少动画”设置、父窗口尺寸变化时贴住右边缘。
Header 与内容由子类自行构建，样式选择器由子类自定。
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QWidget

ANIMATION_MS = 220


def animations_enabled() -> bool:
    """遵守系统“减少动画”设置：关闭客户端区域动画时直接瞬移。"""
    if sys.platform != "win32":
        return True
    try:
        value = ctypes.c_uint(0)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0):
            return bool(value.value)
    except OSError:
        return True
    return True


class SlideDrawer(QFrame):
    """覆盖在主窗口右侧的滑入抽屉，不挤压四个主面板。"""

    closed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        width: int,
        object_name: str,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(width)
        self.hide()
        self._animation: QPropertyAnimation | None = None

        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(self.close_drawer)

        if parent is not None:
            parent.installEventFilter(self)

    def open_drawer(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            self.show()
            return
        self.setGeometry(self._target_geometry())
        self.show()
        self.raise_()
        if animations_enabled():
            start = QRect(parent.width(), 0, self.width(), parent.height())
            self.setGeometry(start)
            animation = QPropertyAnimation(self, b"geometry", self)
            animation.setDuration(ANIMATION_MS)
            animation.setStartValue(start)
            animation.setEndValue(self._target_geometry())
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._animation = animation
            animation.start()

    def close_now(self) -> None:
        """无动画即时关闭（用于抽屉互斥强制切换，避免动画期间两个抽屉共存）。"""
        if self.isVisible():
            self.hide()
            self.closed.emit()

    def close_drawer(self) -> None:
        if not self.isVisible():
            return
        if not animations_enabled():
            self.hide()
            self.closed.emit()
            return
        parent = self.parentWidget()
        end = QRect(
            parent.width() if parent is not None else self.x(),
            0,
            self.width(),
            self.height(),
        )
        animation = QPropertyAnimation(self, b"geometry", self)
        animation.setDuration(ANIMATION_MS)
        animation.setStartValue(self.geometry())
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(self._finish_close)
        self._animation = animation
        animation.start()

    def hit_test(self, global_position: QPoint) -> bool:
        """全局坐标是否落在抽屉内（主窗口点击外部关闭用）。"""
        return self.isVisible() and self.rect().contains(self.mapFromGlobal(global_position))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        # 父窗口尺寸变化时抽屉贴住右边缘。
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self.setGeometry(self._target_geometry())
        return super().eventFilter(obj, event)

    def _target_geometry(self) -> QRect:
        parent = self.parentWidget()
        if parent is None:
            return QRect(0, 0, self.width(), max(self.height(), 400))
        width = min(self.width(), parent.width())
        self.setFixedWidth(width)
        return QRect(parent.width() - width, 0, width, parent.height())

    def _finish_close(self) -> None:
        self.hide()
        self.closed.emit()
