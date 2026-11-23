"""Drives the Qt Quick window offscreen as a user does, for the window tests.

The tests click, double-click, type, press keys and drop files, and read only what the window
shows: the ``text`` of visible items. Nothing here reaches into the window's Python objects
except to stand in for the user's own answers (file dialogs and the like), as ``test_ui.py``
does for the Widgets window. Prices come from ``fakes.FakeProvider``; no network.

Drops are real drag-and-drop events sent to the window, delivered by Qt Quick to the
window's ``DropArea`` as a file dragged from the file manager would be.
"""

from __future__ import annotations

import gc
import os
import shutil
import time
import warnings
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QtQuick = pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)

from fakes import SAMPLE, FakeProvider, ranges_around  # noqa: E402
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QTimer, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from statement_tracker.core.calculator import buys_by_ticker  # noqa: E402
from statement_tracker.core.parser import load_statement  # noqa: E402
from statement_tracker.gui.app import AppWindow  # noqa: E402
from statement_tracker.settings import Settings  # noqa: E402

TODAY = date(2026, 10, 12)
EQQB_BUYS = buys_by_ticker(load_statement(SAMPLE))["EQQB"]


@pytest.fixture(scope="module")
def app():
    # A QApplication, not only a QGuiApplication, while the Widgets window and its tests still exist:
    # one process has one application object, and the Widgets tests need this kind.
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(autouse=True)
def close_windows_afterwards(app):
    """Close and destroy each test's windows when it ends, so none is destroyed in the middle of a later test.

    Any warning from the QML engine meanwhile, up to and including the windows' destruction, fails the
    test: QML reports its errors (a misspelt name, a binding reading something gone) only that way."""
    opened: list[AppWindow] = []
    _OPENED.append(opened)
    qml_warnings: list[str] = []
    previous = qInstallMessageHandler(
        lambda kind, context, message: qml_warnings.append(message) if ".qml:" in message else None
    )
    try:
        yield
        _OPENED.remove(opened)
        for shell in opened:
            shell.close()
            shell.deleteLater()
        QGuiApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        gc.collect()
    finally:
        qInstallMessageHandler(previous)
    assert qml_warnings == [], "the QML engine warned:\n" + "\n".join(qml_warnings)


_OPENED: list[list[AppWindow]] = []


def provider_with(*symbols: str) -> FakeProvider:
    """A provider that knows ``symbols`` as listings of the sample's EQQB, at 400 EUR."""
    provider = FakeProvider()
    for symbol in symbols:
        provider.add(symbol, "EUR", price="400", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    return provider


def open_app(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    today: date = TODAY,
    now: datetime | None = None,
    kept: Path | None = None,
    spreadsheet: Path | None = None,
    real_dialogs: bool = False,
) -> AppWindow:
    """The app as it opens, on its own settings in ``tmp_path``, shown.

    ``kept`` is the statement kept from last time; ``spreadsheet`` the one remembered. Unless
    ``real_dialogs``, error messages are collected in ``shell.errors`` instead of shown.
    """
    settings_path = tmp_path / "settings.json"
    if kept is not None:
        shutil.copyfile(kept, tmp_path / "last_statement.csv")
    if spreadsheet is not None:
        settings = Settings.load(settings_path)
        settings.spreadsheet_path = spreadsheet
        settings.save()
    extra = {"now": lambda: now} if now else {}
    shell = AppWindow(Settings.load(settings_path), lambda: provider, lambda: today, **extra)
    shell.errors = []
    session = getattr(shell, "session", None)
    if session is not None and not real_dialogs:
        session.show_error = shell.errors.append
    if _OPENED:
        _OPENED[-1].append(shell)
    shell.show()
    settle(QGuiApplication.instance())
    return shell


def settle(app) -> None:
    """Let work queued for "once the current event is handled" run."""
    for _ in range(4):
        app.processEvents()


def wait_until(app, condition: Callable[[], bool], seconds: float = 20) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert condition(), "waited in vain"


# -- reading what is shown -------------------------------------------------------------------------


def _items(window: QQuickWindow) -> list[QQuickItem]:
    found: list[QQuickItem] = []
    pending = [window.contentItem()]
    while pending:
        item = pending.pop()
        found.append(item)
        pending.extend(item.childItems())
    return found


def _shown(item: QQuickItem) -> bool:
    return item.isVisible() and item.opacity() > 0 and item.width() > 0 and item.height() > 0


def _text(item: QQuickItem) -> str | None:
    value = item.property("text")
    return value if isinstance(value, str) and value else None


def _with_text(window: QQuickWindow) -> list[QQuickItem]:
    """Visible items that show a text, without the parts of a control that repeat its own text
    (a button's label shows the button's text: the button is what counts)."""
    showing = [item for item in _items(window) if _shown(item) and _text(item)]
    kept = set(showing)

    def repeats_an_ancestor(item: QQuickItem) -> bool:
        parent = item.parentItem()
        while parent is not None:
            if parent in kept and _text(parent) == _text(item):
                return True
            parent = parent.parentItem()
        return False

    return [item for item in showing if not repeats_an_ancestor(item)]


def _place(item: QQuickItem) -> tuple[float, float]:
    point = item.mapToScene(QPointF(0, 0))
    return round(point.y()), point.x()


def texts(window: QQuickWindow) -> list[str]:
    """Every text shown, from top to bottom, then left to right."""
    return [_text(item) for item in sorted(_with_text(window), key=_place)]


def shows(window: QQuickWindow, *parts: str) -> bool:
    """True if every one of ``parts`` appears in something the window shows."""
    shown = texts(window)
    return all(any(part in text for text in shown) for part in parts)


def find_all(window: QQuickWindow, text: str) -> list[QQuickItem]:
    return [item for item in _with_text(window) if _text(item) == text]


def find(window: QQuickWindow, text: str) -> QQuickItem:
    """The one visible item showing exactly ``text``."""
    found = find_all(window, text)
    assert len(found) == 1, f"{len(found)} visible items show {text!r}; shown: {texts(window)}"
    return found[0]


def rows(window: QQuickWindow) -> list[list[str]]:
    """The texts of each row of the investments list, left to right, top to bottom."""
    shown = set(_with_text(window))
    result = []
    for row in sorted((item for item in _items(window) if item.objectName() == "investmentRow" and _shown(item)), key=_place):
        cells = [item for item in shown if _inside(item, row)]
        result.append([_text(item) for item in sorted(cells, key=lambda item: (_place(item)[1], _place(item)[0]))])
    return result


def _inside(item: QQuickItem, container: QQuickItem) -> bool:
    parent = item.parentItem()
    while parent is not None:
        if parent is container:
            return True
        parent = parent.parentItem()
    return False


# -- acting as the user ----------------------------------------------------------------------------


def _centre(item: QQuickItem) -> QPoint:
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


def _window_of(item: QQuickItem) -> QQuickWindow:
    """The open window ``item`` is in. Found from the root item: ``item.window()`` is avoided, as the
    wrapper PySide makes for it can take the window down with it when the item's wrapper is collected."""
    root = item
    while root.parentItem() is not None:
        root = root.parentItem()
    for shells in _OPENED:
        for shell in shells:
            if shell.window.contentItem() == root:
                return shell.window
    raise AssertionError("the item is not in a window opened by open_app")


def click(item: QQuickItem) -> None:
    QTest.mouseClick(_window_of(item), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(item))
    settle(QGuiApplication.instance())


def double_click(item: QQuickItem) -> None:
    QTest.mouseDClick(_window_of(item), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(item))
    settle(QGuiApplication.instance())


def press(window: QQuickWindow, key: Qt.Key, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(window, key, modifiers)
    settle(QGuiApplication.instance())


def type_text(window: QQuickWindow, text: str) -> None:
    """Type ``text`` into whatever has the keyboard focus."""
    for character in text:
        key = Qt.Key(ord(character.upper())) if character.isalnum() and character.isascii() else Qt.Key.Key_unknown
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QGuiApplication.sendEvent(window, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier, character))
    settle(QGuiApplication.instance())


def drop(window: QQuickWindow, *paths: Path) -> None:
    """Drag files from the file manager and drop them on the middle of the window."""
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    where = QPointF(window.width() / 2, window.height() / 2)
    action, buttons, keys = Qt.DropAction.CopyAction, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    with warnings.catch_warnings():  # PySide6 marks the only constructors it has as deprecated
        warnings.simplefilter("ignore", DeprecationWarning)
        events = (
            QDragEnterEvent(where.toPoint(), action, data, buttons, keys),
            QDragMoveEvent(where.toPoint(), action, data, buttons, keys),
            QDropEvent(where, action, data, buttons, keys),
        )
    for event in events:
        QGuiApplication.sendEvent(window, event)
    settle(QGuiApplication.instance())


def when_a_dialog_opens(shell: AppWindow, act: Callable[[], object]) -> None:
    """Run ``act`` (the user's clicks) once the next dialog shows. The call that opens a dialog waits for
    its answer, so the test sets this up first, then makes that call."""

    def opened(*_args: object) -> None:
        shell.session.dialogs.opened.disconnect(opened)
        QTimer.singleShot(0, lambda: (settle(QGuiApplication.instance()), act()))

    shell.session.dialogs.opened.connect(opened)
