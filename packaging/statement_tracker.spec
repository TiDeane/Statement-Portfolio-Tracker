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
WINDOW_ICON = ROOT / "src" / "statement_tracker" / "gui" / "icon.png"
QML_FILES = ROOT / "src" / "statement_tracker" / "gui" / "qml"

# Qt pieces the app never loads. Dropping them trims the download.
UNUSED_QT_FRAGMENTS = (
    "opengl32sw",
    "Qt6Pdf",
    "Qt6VirtualKeyboard",
    "QtPdf",
    "QtVirtualKeyboard",
    "qtvirtualkeyboard",
    "qpdf",
    # Qt Quick libraries for parts of Qt Quick the window does not use: other control styles, 3D,
    # particles, timelines, vector images, the virtual keyboard.
    "Qt6QuickControls2Fusion",
    "Qt6QuickControls2Imagine",
    "Qt6QuickControls2Material",
    "Qt6QuickControls2Universal",
    "Qt6QuickControls2FluentWinUI3",
    "Qt6QuickControls2Windows",
    "Qt6QuickControls2MacOS",
    "Qt6QuickControls2IOS",
    "Qt6Quick3D",
    "Qt6QuickParticles",
    "Qt6QuickTimeline",
    "Qt6QuickVectorImage",
    "Qt6QuickEffects",
    "Qt6QuickTest",
    "Qt6QuickWidgets",
    # The window is Qt Quick: Qt Widgets (and the GTK theme plugin built on it) is never loaded.
    "Qt6Widgets",
    "QtWidgets",
    "platformthemes/libqgtk3",
    "Qt6QuickShapesDesignHelpers",
    "Qt6WaylandCompositor",
    # Qt Labs libraries, but for the folder list Qt's own file dialog shows (Linux, without a native one).
    "Qt6LabsStyleKit",
    "Qt6LabsPlatform",
    "Qt6LabsQmlModels",
    "Qt6LabsSynchronizer",
    "Qt6LabsAnimation",
    "Qt6LabsWavefrontMesh",
    "Qt6LabsSharedImage",
    "Qt6LabsSettings",
    "Qt6Test",
    "Qt6Sql",
    "Qt6QmlLocalStorage",
    "Qt6QmlNetwork",
    "Qt6QmlCore",
    "plugins/qmltooling/",  # QML debugging and profiling
    # Prices are fetched with Python's own HTTP client, never through Qt. Qt's network library and its
    # Python module ship, because Qt's QML engine and PySide's QtQml module need them, but not its TLS
    # backends or its network-status plugins.
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


# The QML modules the window imports (and what they need); every other one under Qt's qml folder is left out.
QML_MODULES = (
    "qml/QtQml/Base/",
    "qml/QtQml/Models/",
    "qml/QtQml/WorkerScript/",
    "qml/QtQuick/Controls/Basic/",
    "qml/QtQuick/Controls/impl/",
    "qml/QtQuick/Templates/",
    "qml/QtQuick/Layouts/",
    "qml/QtQuick/Shapes/",
    "qml/QtQuick/Dialogs/",
    "qml/QtQuick/Window/",
    "qml/Qt/labs/folderlistmodel/",  # Qt's own file dialog lists folders with it
)
QML_ROOT_FILES = ("qml/QtQml/", "qml/QtQuick/", "qml/QtQuick/Controls/")
"""Folders whose own files (plugin, qmldir, type info) are needed, but not all their subfolders."""


def _wanted_qml(destination: str) -> bool:
    if any(module in destination for module in QML_MODULES):
        return True
    folder = destination.rsplit("/", 1)[0] + "/"
    return any(folder.endswith(root) for root in QML_ROOT_FILES)


def _wanted(entry) -> bool:
    destination = str(entry[0]).replace("\\", "/")
    if "/translations/" in destination and "PySide6" in destination:
        return False  # the app is English only in v1
    if "PySide6/Qt/qml/" in destination or "PySide6/qml/" in destination:
        return _wanted_qml(destination)
    return not any(fragment in destination for fragment in UNUSED_QT_FRAGMENTS)


a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    # The window's icon and QML files, next to the code that loads them (statement_tracker/gui/app.py).
    datas=[(str(WINDOW_ICON), "statement_tracker/gui"), (str(QML_FILES), "statement_tracker/gui/qml")],
    # Heavy libraries the app does not use. Listed so that an installed copy (from another
    # package in the build environment) can never end up in the download.
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "pandas", "numpy", "yfinance", "curl_cffi", "lxml",
        "PySide6.QtWidgets",
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
