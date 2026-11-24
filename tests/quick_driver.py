"""Drives the Qt Quick window offscreen as a user does, for the window tests.

The tests click, double-click, type, press keys and drop files, and read only what the window
shows: the ``text`` of visible items. Nothing here reaches into the window's Python objects
except to stand in for the user's own answers (file dialogs and the like). Prices come from ``fakes.FakeProvider``; no network.

Drops are real drag-and-drop events sent to the window, delivered by Qt Quick to the
window's ``DropArea`` as a file dragged from the file manager would be.
"""

from __future__ import annotations

import gc
import os
import shutil
import sys
import time
import warnings
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    # Offscreen, Qt on Windows finds no fonts of its own and draws every letter as a box, wider than real
    # text: layouts then overflow and clicks miss. The system's fonts make the window look as it does.
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
QtQuick = pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)

from fakes import SAMPLE, FakeProvider, ranges_around  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, QPointF, Qt, QTimer, QUrl, qInstallMessageHandler  # noqa: E402
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
    return _application()


def _application():
    """The application, set up for the tests: on Windows, with the font Windows draws its windows in.
    (Offscreen, Qt there knows no system font; the fonts folder it is given has many, and the first one
    is not that.)"""
    from statement_tracker.gui.app import make_application

    application = make_application([])
    if sys.platform == "win32":
        from PySide6.QtGui import QFont

        application.setFont(QFont("Segoe UI"))
    return application


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
    stuck = list(_STUCK)
    _STUCK.clear()
    assert qml_warnings == [], "the QML engine warned:\n" + "\n".join(qml_warnings)
    assert stuck == [], "\n".join(stuck)


_OPENED: list[list[AppWindow]] = []
"""The windows each running test opened, closed by ``close_windows_afterwards``."""
_UNMANAGED: list[AppWindow] = []
"""Windows opened outside a test (a script taking screenshots): never closed by the driver."""


@pytest.fixture
def english_computer():
    """A computer set up for English in the United Kingdom: "1,001.00" and "14/11/2026"."""
    from PySide6.QtCore import QLocale

    before = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom))
    yield
    QLocale.setDefault(before)


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
    ask_listing: Callable | None = None,
) -> AppWindow:
    """The app as it opens, on its own settings in ``tmp_path``, shown.

    ``kept`` is the statement kept from last time; ``spreadsheet`` the one remembered. Unless
    ``real_dialogs``, error messages are collected in ``shell.errors`` instead of shown, and a question
    about a listing is answered by ``ask_listing`` (set before the app starts fetching), else skipped
    and noted in ``shell.questions``.
    """
    _application()  # before the window, so that it is drawn in the tests' font from the start
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
    shell.questions = []
    session = shell.session
    if not real_dialogs:
        session.show_error = shell.errors.append
        session.ask_listing = ask_listing or (lambda resolution: (shell.questions.append(resolution.ticker), (None, False))[1])
    (_OPENED[-1] if _OPENED else _UNMANAGED).append(shell)
    shell.show()
    settle(QGuiApplication.instance())
    return shell


def opening_app() -> AppWindow:
    """The app ``open_app`` opened last: for answers given while it is still opening."""
    return (_OPENED[-1] if _OPENED else _UNMANAGED)[-1]


def settle(app) -> None:
    """Let work queued for "once the current event is handled" run, and Qt Quick lay out what changed
    (it does so on its next frame, a few milliseconds later)."""
    for _ in range(6):
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()


def wait_until(app, condition: Callable[[], bool], seconds: float = 20) -> None:
    """Wait until ``condition`` holds and still holds once the window has settled: what was true only of
    the state before a change just made (not handled yet) does not count, and what is shown is laid out."""
    deadline = time.monotonic() + seconds
    while True:
        app.processEvents()
        if condition():
            settle(app)
            if condition():
                return
        if time.monotonic() >= deadline:
            break
        time.sleep(0.01)
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


def find_starting(window: QQuickWindow, start: str) -> QQuickItem:
    """The one visible item whose text starts with ``start`` (for texts too long to spell out)."""
    found = [item for item in _with_text(window) if _text(item).startswith(start)]
    assert len(found) == 1, f"{len(found)} visible items start with {start!r}"
    return found[0]


def editor(window: QQuickWindow) -> QQuickItem:
    """The text field open for typing an investment's name."""
    found = [item for item in _items(window) if item.objectName() == "nameEditor" and _shown(item)]
    assert len(found) == 1, f"{len(found)} name editors are open"
    return found[0]


def heading(window: QQuickWindow, text: str) -> QQuickItem:
    """The heading reading ``text`` in the investments list (not the same words elsewhere on Home)."""
    headers = [item for item in _items(window) if item.objectName() == "investmentHeader" and _shown(item)]
    found = [item for item in _with_text(window) if _text(item) == text and any(_inside(item, header) for header in headers)]
    assert len(found) == 1, f"{len(found)} headings read {text!r}"
    return found[0]


def field(window: QQuickWindow, placeholder: str) -> QQuickItem:
    """The visible text field whose empty state reads ``placeholder``."""
    found = [item for item in _items(window) if item.property("placeholderText") == placeholder and _shown(item)]
    assert len(found) == 1, f"{len(found)} fields read {placeholder!r}"
    return found[0]


def row_items(window: QQuickWindow) -> list[QQuickItem]:
    """The rows of the investments list (the Total last), top to bottom, to click or double-click."""
    return sorted((item for item in _items(window) if item.objectName() == "investmentRow" and _shown(item)), key=_place)


def rows(window: QQuickWindow) -> list[list[str]]:
    """The texts of each row of the investments list, left to right, top to bottom."""
    shown = set(_with_text(window))
    result = []
    for row in sorted((item for item in _items(window) if item.objectName() == "investmentRow" and _shown(item)), key=_place):
        cells = [item for item in shown if _inside(item, row)]
        result.append([_text(item) for item in sorted(cells, key=lambda item: _cell_place(item, row))])
    return result


def _cell_place(item: QQuickItem, row: QQuickItem) -> tuple[float, float]:
    """Where a text sits in its row: its column's left edge, then its own height (a note under a value
    comes after it, however it is aligned)."""
    cell = item
    while cell.parentItem() is not None and cell.parentItem().parentItem() is not row:
        cell = cell.parentItem()
    return cell.mapToScene(QPointF(0, 0)).x(), item.mapToScene(QPointF(0, 0)).y()


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
    for shells in [*_OPENED, _UNMANAGED]:
        for shell in shells:
            if shell.window.contentItem() == root:
                return shell.window
    raise AssertionError("the item is not in a window opened by open_app")


def scroll_to(item: QQuickItem) -> None:
    """Scroll the page (any scrolling area around ``item``, down or sideways) until ``item`` is in view, as a
    user would."""
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentX") is not None and parent.property("contentWidth") is not None:
            content = parent.property("contentItem")
            left = item.mapToItem(content, QPointF(0, 0)).x()
            shown_from, width = parent.property("contentX"), parent.width()
            if left < shown_from or left + item.width() > shown_from + width:
                limit = max(0.0, parent.property("contentWidth") - width)
                parent.setProperty("contentX", max(0.0, min(left + item.width() - width, limit)))
                settle(QGuiApplication.instance())
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            top = item.mapToItem(content, QPointF(0, 0)).y()
            shown_from, height = parent.property("contentY"), parent.height()
            if top < shown_from or top + item.height() > shown_from + height:
                limit = max(0.0, parent.property("contentHeight") - height)
                parent.setProperty("contentY", max(0.0, min(top - height / 3, limit)))
                settle(QGuiApplication.instance())
        parent = parent.parentItem()


def _shell_of(window: QQuickWindow) -> AppWindow | None:
    for shells in [*_OPENED, _UNMANAGED]:
        for shell in shells:
            if shell.window == window:
                return shell
    return None


def _finish_quick_work(window: QQuickWindow) -> None:
    """Wait, as a user watching the moving bar does, for what a click or a drop started in the background:
    reading a statement on first launch, writing the spreadsheet. (A fetch is waited for by the tests.)"""
    shell = _shell_of(window)
    if shell is None:
        return
    session = shell.session
    wait_until(
        QGuiApplication.instance(),
        lambda: not session.welcome.property("reading") and not session.home.property("writing"),
    )


def click(item: QQuickItem, wait: bool = True) -> None:
    """Click ``item``; unless ``wait`` is False, wait for what it started in the background (see above)."""
    scroll_to(item)
    window = _window_of(item)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _centre(item))
    settle(QGuiApplication.instance())
    if wait:
        _finish_quick_work(window)


def double_click(item: QQuickItem) -> None:
    scroll_to(item)
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


def drop(window: QQuickWindow, *paths: Path, wait: bool = True) -> None:
    """Drag files from the file manager and drop them on the middle of the window; unless ``wait`` is False,
    wait for what that started in the background."""
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
    if wait:
        _finish_quick_work(window)


def when_a_dialog_opens(shell: AppWindow, act: Callable[[], object]) -> None:
    """Run ``act`` (the user's clicks) once the next dialog shows. The call that opens a dialog waits for
    its answer, so the test sets this up first, then makes that call.

    A dialog still open after ``act`` (a click that missed, say) is closed, and the test fails when it
    ends, instead of waiting for an answer forever."""
    dialogs = shell.session.dialogs

    shown_before: list[list[str]] = []

    def opened(*_args: object) -> None:
        dialogs.opened.disconnect(opened)
        shown_before.append(texts(shell.window))
        QTimer.singleShot(0, run)

    def run() -> None:
        # Shown once its texts are: Qt Quick draws a new popup on one of its next frames.
        deadline = time.monotonic() + 2
        while texts(shell.window) == shown_before[0] and time.monotonic() < deadline:
            settle(QGuiApplication.instance())
        settle(QGuiApplication.instance())
        before = _ASKED[0]
        try:
            act()
        finally:
            settle(QGuiApplication.instance())
            if dialogs.property("isOpen") and _ASKED[0] == before:
                _STUCK.append(f"a dialog was left open: {texts(shell.window)}")
                dialogs.cancel()
            # Answering the dialog ended its wait (a QEventLoop) while this ran inside it, and the events
            # processed here since can use up the wake-up that ending it sends (on Windows). An offscreen
            # window has nothing else to wake it, so the wait would sleep on for ever: wake it once more.
            QCoreApplication.postEvent(QGuiApplication.instance(), QEvent(QEvent.Type.User))

    dialogs.opened.connect(opened)
    dialogs.opened.connect(_count_asked)


_ASKED = [0]
"""How many dialogs have opened: a dialog that opens another (asking again) is not stuck."""

_STUCK: list[str] = []


def _count_asked(*_args: object) -> None:
    _ASKED[0] += 1
