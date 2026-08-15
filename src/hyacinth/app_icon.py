from importlib.resources import files

from PySide6.QtGui import QIcon, QPixmap


def application_icon() -> QIcon:
    data = files("hyacinth").joinpath("assets/app-icon.png").read_bytes()
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return QIcon()
    return QIcon(pixmap)
