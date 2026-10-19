"""Draw the app's icon and write it in every format the packaged apps need.

Run it again after changing the drawing; the files it writes are committed, so building the app never
runs it. It uses only Qt, which the app already depends on:

    QT_QPA_PLATFORM=offscreen .venv/bin/python packaging/make_icon.py

Writes, next to this script, in ``icon/``:

- ``app.ico``: Windows, for the program and its installer (16 to 256 pixels);
- ``app.icns``: macOS, for the app bundle (16 to 1024 pixels);
- ``app.png``: 512 pixels, for anything else that takes a picture;

and the same 512-pixel picture as ``src/statement_tracker/ui/icon.png``, which the running app shows as
its window's icon (in the title bar, the taskbar on Linux, the Dock when run from source on a Mac).

The drawing: a rounded square in the app's green (the green of Excel, ``ui/theme.py``) with a white line
rising to an arrow over three faint bars, a portfolio going up. Below 48 pixels the bars are left out
and the line is drawn thicker, so the icon stays readable in a taskbar or a title bar.
"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

OUT = Path(__file__).resolve().parent / "icon"
WINDOW_ICON = Path(__file__).resolve().parents[1] / "src" / "statement_tracker" / "ui" / "icon.png"
GREEN_LIGHT = QColor("#21A366")
GREEN_DARK = QColor("#0B5E31")
"""The theme's accent (#107C41) lies between these: lighter at the top left, darker at the bottom right."""

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_TYPES = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07", 256: b"ic08", 512: b"ic09", 1024: b"ic10"}
"""The macOS icon entries that hold a PNG picture of each size."""


def draw(size: int) -> QImage:
    """The icon at ``size`` pixels square, with a transparent background."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    small = size < 48

    def at(x: float, y: float) -> QPointF:
        return QPointF(x * size, y * size)

    # The tile: a rounded square, a little inside the edges as icons on every system are.
    margin = 0.04 * size if small else 0.06 * size
    tile = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    gradient = QLinearGradient(tile.topLeft(), tile.bottomRight())
    gradient.setColorAt(0, GREEN_LIGHT)
    gradient.setColorAt(1, GREEN_DARK)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    radius = tile.width() * 0.22
    painter.drawRoundedRect(tile, radius, radius)

    # Three faint bars, growing: only where there is room for them.
    if not small:
        painter.setBrush(QColor(255, 255, 255, 70))
        base, width = 0.80, 0.12
        for left, height in ((0.22, 0.20), (0.44, 0.30), (0.66, 0.44)):
            bar = QRectF(left * size, (base - height) * size, width * size, height * size)
            painter.drawRoundedRect(bar, 0.02 * size, 0.02 * size)

    # The line, rising to an arrow at the top right.
    points = [at(0.20, 0.68), at(0.40, 0.50), at(0.54, 0.59), at(0.74, 0.36)]
    thickness = max(1.6, (0.12 if small else 0.075) * size)
    pen = QPen(QColor("white"), thickness)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    line = QPainterPath(points[0])
    for point in points[1:]:
        line.lineTo(point)
    painter.drawPath(line)

    # The arrowhead, pointing the way the last stretch of the line goes.
    tip_from, tip_to = points[-2], points[-1]
    angle = math.atan2(tip_to.y() - tip_from.y(), tip_to.x() - tip_from.x())
    length, spread = (0.26 if small else 0.20) * size, math.radians(32)
    tip = QPointF(tip_to.x() + math.cos(angle) * length * 0.45, tip_to.y() + math.sin(angle) * length * 0.45)
    head = QPainterPath(tip)
    for side in (spread, -spread):
        head.lineTo(tip.x() - math.cos(angle + side) * length, tip.y() - math.sin(angle + side) * length)
    head.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawPath(head)
    painter.end()
    return image


def png(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def bitmap(image: QImage) -> bytes:
    """``image`` as a Windows icon bitmap: 32-bit colour with alpha, rows bottom up, then an empty mask."""
    image = image.convertToFormat(QImage.Format.Format_ARGB32)  # stored as blue, green, red, alpha
    width, height = image.width(), image.height()
    pixels = bytes(image.constBits())
    rows = b"".join(pixels[y * image.bytesPerLine() : y * image.bytesPerLine() + width * 4] for y in reversed(range(height)))
    mask = bytes(((width + 31) // 32 * 4) * height)  # transparency comes from the alpha; the mask is unused
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, len(rows) + len(mask), 0, 0, 0, 0)
    return header + rows + mask


def ico(images: dict[int, QImage]) -> bytes:
    """A Windows icon: the 256-pixel picture as a PNG, the smaller ones as bitmaps, as icon tools write them
    so that every program that reads icons, not only Windows itself, can read them all."""
    pictures = {size: png(image) if size >= 256 else bitmap(image) for size, image in images.items()}
    header = struct.pack("<HHH", 0, 1, len(pictures))
    entries, data = b"", b""
    offset = 6 + 16 * len(pictures)
    for size, picture in sorted(pictures.items()):
        side = 0 if size >= 256 else size  # 0 stands for 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(picture), offset + len(data))
        data += picture
    return header + entries + data


def icns(pictures: dict[int, bytes]) -> bytes:
    """A macOS icon holding each picture as a PNG entry."""
    body = b"".join(
        ICNS_TYPES[size] + struct.pack(">I", 8 + len(picture)) + picture for size, picture in sorted(pictures.items())
    )
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 - kept alive while Qt draws
    OUT.mkdir(exist_ok=True)
    images = {size: draw(size) for size in sorted(set(ICO_SIZES) | set(ICNS_TYPES))}
    pictures = {size: png(image) for size, image in images.items()}
    (OUT / "app.ico").write_bytes(ico({size: images[size] for size in ICO_SIZES}))
    (OUT / "app.icns").write_bytes(icns({size: pictures[size] for size in ICNS_TYPES}))
    (OUT / "app.png").write_bytes(pictures[512])
    WINDOW_ICON.write_bytes(pictures[512])
    for path in (OUT / "app.ico", OUT / "app.icns", OUT / "app.png", WINDOW_ICON):
        print(f"{path}: {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
