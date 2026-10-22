"""Render Junction SVG master into PNG preview and multiresolution ICO.

Requires PySide6 (QtSvg) and Pillow. Run from the repository root:

    .\\.venv\\Scripts\\python.exe tools\\render_junction_icon.py
"""

from __future__ import annotations

import struct
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "assets" / "icons" / "junction.svg"
ICO_PATH = ROOT / "assets" / "icons" / "Junction.ico"
PNG_PATH = ROOT / "assets" / "icons" / "junction-256.png"
PKG_ICO = ROOT / "src" / "fileforge" / "resources" / "icons" / "Junction.ico"
PKG_PNG = ROOT / "src" / "fileforge" / "resources" / "icons" / "junction-256.png"

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render_svg(svg_bytes: bytes, size: int) -> Image.Image:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {SVG_PATH}")
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        if not image.save(str(temp_path), "PNG"):
            raise RuntimeError(f"Failed to encode PNG at {size}px")
        return Image.open(temp_path).convert("RGBA")
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    if not SVG_PATH.is_file():
        raise SystemExit(f"Missing SVG master: {SVG_PATH}")

    app = QApplication.instance() or QApplication(sys.argv)
    _ = app  # keep reference for Qt lifetime

    svg_bytes = SVG_PATH.read_bytes()
    frames = {size: _render_svg(svg_bytes, size) for size in ICO_SIZES}

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PKG_ICO.parent.mkdir(parents=True, exist_ok=True)

    frames[256].save(PNG_PATH, format="PNG")
    frames[256].save(PKG_PNG, format="PNG")

    # Write a Vista+ PNG-compressed multiresolution ICO from per-size SVG renders.
    _write_png_ico(ICO_PATH, [frames[size] for size in ICO_SIZES])
    PKG_ICO.write_bytes(ICO_PATH.read_bytes())

    embedded = _list_ico_sizes(ICO_PATH)
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")
    print(f"Wrote {PKG_PNG}")
    print(f"Wrote {PKG_ICO}")
    print(f"ICO frames: {embedded}")
    missing = [size for size in ICO_SIZES if (size, size) not in embedded]
    if missing:
        print(f"WARNING: missing ICO sizes {missing}")
        return 1
    return 0


def _write_png_ico(path: Path, images: list[Image.Image]) -> None:
    """Write a multiresolution ICO using PNG payloads (Windows Vista+)."""
    entries: list[tuple[int, int, bytes]] = []
    for image in images:
        width, height = image.size
        payload = BytesIO()
        image.save(payload, format="PNG")
        entries.append((width, height, payload.getvalue()))

    count = len(entries)
    offset = 6 + (16 * count)
    header = struct.pack("<HHH", 0, 1, count)
    directory = bytearray()
    blobs = bytearray()
    for width, height, data in entries:
        w_byte = 0 if width >= 256 else width
        h_byte = 0 if height >= 256 else height
        directory.extend(
            struct.pack("<BBBBHHII", w_byte, h_byte, 0, 0, 1, 32, len(data), offset)
        )
        blobs.extend(data)
        offset += len(data)
    path.write_bytes(header + directory + blobs)


def _list_ico_sizes(path: Path) -> list[tuple[int, int]]:
    """Parse ICONDIRENTRY records (Pillow may only expose one PNG frame)."""
    data = path.read_bytes()
    _reserved, itype, count = struct.unpack_from("<HHH", data, 0)
    if itype != 1:
        raise RuntimeError(f"Not an ICO file: {path}")
    sizes: list[tuple[int, int]] = []
    offset = 6
    for _ in range(count):
        width, height, _colors, _res, _planes, _bitcount, _nbytes, _off = struct.unpack_from(
            "<BBBBHHII", data, offset
        )
        sizes.append((256 if width == 0 else width, 256 if height == 0 else height))
        offset += 16
    return sizes


if __name__ == "__main__":
    raise SystemExit(main())
