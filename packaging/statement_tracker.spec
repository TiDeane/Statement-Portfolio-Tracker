# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one-folder build on every OS, plus a .app bundle on macOS.

Build from the repo root:
    python -m PyInstaller packaging/statement_tracker.spec --noconfirm
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))

from statement_tracker import APP_NAME, __version__  # noqa: E402

EXE_NAME = "StatementPortfolioTracker"
BUNDLE_ID = "io.github.tideane.statementportfoliotracker"
ICONS = ROOT / "packaging" / "icon"  # drawn by packaging/make_icon.py
WINDOW_ICON = ROOT / "src" / "statement_tracker" / "ui" / "icon.png"

# Qt pieces a Widgets-only app never loads. Dropping them trims the download.
UNUSED_QT_FRAGMENTS = (
    "opengl32sw",
    "Qt6Pdf",
    "Qt6Qml",
    "Qt6Quick",
    "Qt6VirtualKeyboard",
    "QtPdf",
    "QtQml",
    "QtQuick",
    "QtVirtualKeyboard",
    "qtvirtualkeyboard",
    "qpdf",
    # Prices are fetched with Python's own HTTP client, never through Qt, so Qt's networking,
    # its TLS backends and its network-status plugins are never loaded.
    "QtNetwork",
    "Qt6Network",
    "plugins/tls/",
    "plugins/networkinformation/",
    # The app shows no pictures. Kept: SVG and ICO, which icons and icon themes can use.
    "imageformats/libqgif",
    "imageformats/qgif",
    "imageformats/libqjpeg",
    "imageformats/qjpeg",
    "imageformats/libqtiff",
    "imageformats/qtiff",
    "imageformats/libqwebp",
    "imageformats/qwebp",
    "imageformats/libqtga",
    "imageformats/qtga",
    "imageformats/libqwbmp",
    "imageformats/qwbmp",
    "imageformats/libqicns",
    "imageformats/qicns",
)


def _wanted(entry) -> bool:
    destination = str(entry[0]).replace("\\", "/")
    if "/translations/" in destination and "PySide6" in destination:
        return False  # the app is English only in v1
    return not any(fragment in destination for fragment in UNUSED_QT_FRAGMENTS)


a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    # The window's icon, next to the code that loads it (statement_tracker/ui/main_window.py).
    datas=[(str(WINDOW_ICON), "statement_tracker/ui")],
    # Heavy libraries the app does not use. Listed so that an installed copy (from another
    # package in the build environment) can never end up in the download.
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "pandas", "numpy", "yfinance", "curl_cffi", "lxml",
        "PySide6.QtNetwork",
    ],
    noarchive=False,
)
a.binaries = [entry for entry in a.binaries if _wanted(entry)]
a.datas = [entry for entry in a.datas if _wanted(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=EXE_NAME,
    # The program's icon in Explorer, the taskbar and its shortcuts (Windows); the bundle's is set below.
    icon=str(ICONS / ("app.icns" if sys.platform == "darwin" else "app.ico")),
    console=False,
    upx=False,  # UPX-packed binaries trigger more antivirus false positives
)

coll = COLLECT(exe, a.binaries, a.datas, name=EXE_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ICONS / "app.icns"),
        bundle_identifier=BUNDLE_ID,
        version=__version__,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
        },
    )
