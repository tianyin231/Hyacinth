from pathlib import Path
from struct import unpack_from

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from hyacinth.app_icon import application_icon

ASSET_DIR = Path(__file__).parents[1] / "src" / "hyacinth" / "assets"


def test_app_icon_png_is_transparent_and_uses_approved_colors() -> None:
    image = QImage(str(ASSET_DIR / "app-icon.png"))

    assert not image.isNull()
    assert image.size().width() == 512
    assert image.size().height() == 512
    assert image.hasAlphaChannel()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(181, 128).name() == "#64748b"
    assert image.pixelColor(330, 320).name() == "#0f6cbd"


def test_windows_icon_contains_all_required_sizes() -> None:
    data = (ASSET_DIR / "app-icon.ico").read_bytes()
    reserved, kind, count = unpack_from("<HHH", data)
    sizes = []
    for index in range(count):
        width, height = unpack_from("<BB", data, 6 + index * 16)
        sizes.append((256 if width == 0 else width, 256 if height == 0 else height))

    assert (reserved, kind) == (0, 1)
    assert sizes == [(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)]


def test_application_icon_loads_packaged_png(qapp: QApplication) -> None:
    icon = application_icon()

    assert not icon.isNull()
    assert not icon.pixmap(16, 16).isNull()
    assert not icon.pixmap(256, 256).isNull()
