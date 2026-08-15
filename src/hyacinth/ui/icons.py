from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def fluent_icon(name: str, *, color: str = "#4d5663", size: int = 18) -> QIcon:
    pixmap = QPixmap(QSize(size * 2, size * 2))
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.45, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    drawings: dict[str, Callable[[QPainter, float], None]] = {
        "plus": _draw_plus,
        "save": _draw_save,
        "download": _draw_download,
        "undo": _draw_undo,
        "redo": _draw_redo,
        "compare": _draw_compare,
        "trash": _draw_trash,
        "settings": _draw_settings,
        "sheet": _draw_sheet,
        "tree": _draw_tree,
        "sort": _draw_sort,
        "brand": _draw_brand,
    }
    try:
        drawings[name](painter, float(size))
    except KeyError as error:
        raise ValueError(f"未知图标：{name}") from error
    finally:
        painter.end()
    return QIcon(pixmap)


def _draw_plus(painter: QPainter, size: float) -> None:
    center = size / 2
    painter.drawLine(QPointF(center, size * 0.24), QPointF(center, size * 0.76))
    painter.drawLine(QPointF(size * 0.24, center), QPointF(size * 0.76, center))


def _draw_save(painter: QPainter, size: float) -> None:
    painter.drawRoundedRect(QRectF(size * 0.2, size * 0.16, size * 0.6, size * 0.68), 1.8, 1.8)
    painter.drawRect(QRectF(size * 0.31, size * 0.16, size * 0.34, size * 0.22))
    painter.drawRoundedRect(QRectF(size * 0.31, size * 0.55, size * 0.38, size * 0.2), 1.5, 1.5)


def _draw_download(painter: QPainter, size: float) -> None:
    painter.drawLine(QPointF(size * 0.5, size * 0.18), QPointF(size * 0.5, size * 0.62))
    painter.drawLine(QPointF(size * 0.34, size * 0.48), QPointF(size * 0.5, size * 0.64))
    painter.drawLine(QPointF(size * 0.66, size * 0.48), QPointF(size * 0.5, size * 0.64))
    painter.drawLine(QPointF(size * 0.24, size * 0.78), QPointF(size * 0.76, size * 0.78))


def _draw_undo(painter: QPainter, size: float) -> None:
    path = QPainterPath(QPointF(size * 0.25, size * 0.5))
    path.cubicTo(
        QPointF(size * 0.42, size * 0.25),
        QPointF(size * 0.75, size * 0.32),
        QPointF(size * 0.78, size * 0.62),
    )
    painter.drawPath(path)
    painter.drawLine(QPointF(size * 0.25, size * 0.5), QPointF(size * 0.42, size * 0.5))
    painter.drawLine(QPointF(size * 0.25, size * 0.5), QPointF(size * 0.31, size * 0.34))


def _draw_redo(painter: QPainter, size: float) -> None:
    painter.save()
    painter.translate(size, 0)
    painter.scale(-1, 1)
    _draw_undo(painter, size)
    painter.restore()


def _draw_compare(painter: QPainter, size: float) -> None:
    painter.drawRoundedRect(QRectF(size * 0.18, size * 0.25, size * 0.38, size * 0.5), 2, 2)
    painter.drawRoundedRect(QRectF(size * 0.44, size * 0.18, size * 0.38, size * 0.5), 2, 2)


def _draw_trash(painter: QPainter, size: float) -> None:
    painter.drawRoundedRect(QRectF(size * 0.29, size * 0.31, size * 0.42, size * 0.5), 1.5, 1.5)
    painter.drawLine(QPointF(size * 0.22, size * 0.27), QPointF(size * 0.78, size * 0.27))
    painter.drawLine(QPointF(size * 0.41, size * 0.2), QPointF(size * 0.59, size * 0.2))
    painter.drawLine(QPointF(size * 0.43, size * 0.42), QPointF(size * 0.43, size * 0.68))
    painter.drawLine(QPointF(size * 0.57, size * 0.42), QPointF(size * 0.57, size * 0.68))


def _draw_settings(painter: QPainter, size: float) -> None:
    center = QPointF(size * 0.5, size * 0.5)
    painter.drawEllipse(center, size * 0.14, size * 0.14)
    painter.drawEllipse(center, size * 0.31, size * 0.31)
    for x1, y1, x2, y2 in (
        (0.5, 0.12, 0.5, 0.24),
        (0.5, 0.76, 0.5, 0.88),
        (0.12, 0.5, 0.24, 0.5),
        (0.76, 0.5, 0.88, 0.5),
        (0.23, 0.23, 0.31, 0.31),
        (0.69, 0.69, 0.77, 0.77),
        (0.23, 0.77, 0.31, 0.69),
        (0.69, 0.31, 0.77, 0.23),
    ):
        painter.drawLine(QPointF(size * x1, size * y1), QPointF(size * x2, size * y2))


def _draw_sheet(painter: QPainter, size: float) -> None:
    path = QPainterPath(QPointF(size * 0.26, size * 0.14))
    path.lineTo(size * 0.62, size * 0.14)
    path.lineTo(size * 0.78, size * 0.3)
    path.lineTo(size * 0.78, size * 0.84)
    path.lineTo(size * 0.26, size * 0.84)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawLine(QPointF(size * 0.62, size * 0.14), QPointF(size * 0.62, size * 0.3))
    painter.drawLine(QPointF(size * 0.62, size * 0.3), QPointF(size * 0.78, size * 0.3))
    for y in (0.45, 0.58, 0.71):
        painter.drawLine(QPointF(size * 0.36, size * y), QPointF(size * 0.68, size * y))


def _draw_tree(painter: QPainter, size: float) -> None:
    painter.drawLine(QPointF(size * 0.3, size * 0.3), QPointF(size * 0.3, size * 0.7))
    painter.drawLine(QPointF(size * 0.3, size * 0.5), QPointF(size * 0.67, size * 0.5))
    for x, y in ((0.3, 0.24), (0.3, 0.76), (0.72, 0.5)):
        painter.drawRoundedRect(
            QRectF(size * (x - 0.09), size * (y - 0.08), size * 0.18, size * 0.16), 2, 2
        )


def _draw_sort(painter: QPainter, size: float) -> None:
    for y, width in ((0.28, 0.52), (0.5, 0.36), (0.72, 0.2)):
        painter.drawLine(QPointF(size * 0.2, size * y), QPointF(size * (0.2 + width), size * y))
    painter.drawLine(QPointF(size * 0.78, size * 0.25), QPointF(size * 0.78, size * 0.75))
    painter.drawLine(QPointF(size * 0.68, size * 0.65), QPointF(size * 0.78, size * 0.75))
    painter.drawLine(QPointF(size * 0.88, size * 0.65), QPointF(size * 0.78, size * 0.75))


def _draw_brand(painter: QPainter, size: float) -> None:
    petal = QPainterPath(QPointF(4.0, 0.0))
    petal.cubicTo(QPointF(6.21, 0.0), QPointF(8.0, 1.79), QPointF(8.0, 4.0))
    petal.lineTo(8.0, 11.0)
    petal.cubicTo(QPointF(8.0, 12.66), QPointF(6.66, 14.0), QPointF(5.0, 14.0))
    petal.lineTo(4.0, 14.0)
    petal.cubicTo(QPointF(1.79, 14.0), QPointF(0.0, 12.21), QPointF(0.0, 10.0))
    petal.lineTo(0.0, 4.0)
    petal.cubicTo(QPointF(0.0, 1.79), QPointF(1.79, 0.0), QPointF(4.0, 0.0))
    petal.closeSubpath()

    painter.save()
    painter.scale(size / 24.0, size / 24.0)
    painter.setPen(Qt.PenStyle.NoPen)
    for x, y, angle, color in (
        (4.5, 2.0, 34.0, "#64748b"),
        (11.5, 8.0, -34.0, "#0f6cbd"),
    ):
        painter.save()
        painter.translate(x + 4.0, y + 7.0)
        painter.rotate(angle)
        painter.translate(-4.0, -7.0)
        painter.fillPath(petal, QColor(color))
        painter.restore()
    painter.restore()
