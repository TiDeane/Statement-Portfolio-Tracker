# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one-folder build on every OS, plus a .app bundle on macOS.

Build from the repo root:
    python -m PyInstaller packaging/statement_tracker.spec --noconfirm
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))

from statement_tracker import APP_NAME, __version__  # noqa: E402

EXE_NAME = "StatementPortfolioTracker"
BUNDLE_ID = "io.github.tideane.statementportfoliotracker"

# curl_cffi (yfinance's HTTP client) ships a native library and CA bundle that
# PyInstaller's import analysis does not find on its own.
curl_datas, curl_binaries, curl_hiddenimports = collect_all("curl_cffi")

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
)


def _wanted(entry) -> bool:
    destination = str(entry[0]).replace("\\", "/")
    if "/translations/" in destination and "PySide6" in destination:
        return False  # the app is English only in v1
    return not any(fragment in destination for fragment in UNUSED_QT_FRAGMENTS)


a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=curl_binaries,
    datas=[(str(ROOT / "samples" / "revolut_sample.csv"), "samples"), *curl_datas],
    hiddenimports=curl_hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
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
    console=False,
    upx=False,  # UPX-packed binaries trigger more antivirus false positives
)

coll = COLLECT(exe, a.binaries, a.datas, name=EXE_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier=BUNDLE_ID,
        version=__version__,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
        },
    )
