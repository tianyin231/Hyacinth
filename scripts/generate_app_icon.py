from pathlib import Path
from struct import pack

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "src" / "hyacinth" / "assets"
SVG_PATH = ASSET_DIR / "app-icon.svg"
PNG_PATH = ASSET_DIR / "app-icon.png"
ICO_PATH = ASSET_DIR / "app-icon.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        raise RuntimeError(f"无法生成 {size}x{size} PNG")
    return bytes(encoded.data())


def encode_ico(frames: list[tuple[int, bytes]]) -> bytes:
    header_size = 6 + len(frames) * 16
    offset = header_size
    entries: list[bytes] = []
    images: list[bytes] = []
    for size, image in frames:
        dimension = 0 if size == 256 else size
        entries.append(pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(image), offset))
        images.append(image)
        offset += len(image)
    return pack("<HHH", 0, 1, len(frames)) + b"".join(entries) + b"".join(images)


def main() -> None:
    renderer = QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"无法读取矢量图标：{SVG_PATH}")
    PNG_PATH.write_bytes(render_png(renderer, 512))
    frames = [(size, render_png(renderer, size)) for size in ICO_SIZES]
    ICO_PATH.write_bytes(encode_ico(frames))


if __name__ == "__main__":
    main()
