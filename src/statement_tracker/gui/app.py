"""The application and its window: Qt set up for Qt Quick, the QML loaded, and the objects it shows."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication, QIcon, QWindow
from PySide6.QtQml import QQmlApplicationEngine

from statement_tracker import APP_NAME, __version__
from statement_tracker.core.market_data.provider import PriceProvider
from statement_tracker.gui.theme import Theme
from statement_tracker.settings import Settings

QML_DIR = Path(__file__).with_name("qml")
APP_ICON = Path(__file__).parent.parent / "ui" / "icon.png"
"""The app's icon, drawn by packaging/make_icon.py."""
CONTROLS_STYLE = "Basic"
"""Qt Quick Controls' plainest style: small, and the same on every system, so the app's own look is drawn on it.

Set through Qt's environment variables, like the software drawing below, rather than through
PySide's QtQuick module: importing that module also loads PySide's QtOpenGL module (9 MB)."""


def default_provider() -> PriceProvider:
    from statement_tracker.core.market_data.yahoo_provider import YahooProvider

    return YahooProvider()


def utc_now() -> datetime:
    return datetime.now(UTC)


def make_application(argv: list[str]) -> QGuiApplication:
    """The application object, set up for Qt Quick. An existing one is set up and returned."""
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # Without a screen there may be no graphics driver: Qt Quick draws in software then.
        os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = CONTROLS_STYLE
    app = QGuiApplication.instance() or QGuiApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    return app


class AppWindow(QObject):
    """The window and what it shows, for one set of settings."""

    def __init__(
        self,
        settings: Settings,
        provider_factory: Callable[[], PriceProvider] = default_provider,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        super().__init__()
        app = make_application([])
        self.settings = settings
        self._provider_factory = provider_factory
        self._today = today
        self._now = now
        self.qml_warnings: list[str] = []
        """What the QML engine reported, kept for tests and for the smoke test's report."""
        self.engine = QQmlApplicationEngine()
        # What QML reads belongs to the engine: the engine destroys the window first, then its children,
        # so no binding is left reading an object already gone.
        self.theme = Theme(self.engine)
        self.theme.follow(app)
        self.engine.rootContext().setContextProperty("Theme", self.theme)
        self.engine.warnings.connect(lambda errors: self.qml_warnings.extend(error.toString() for error in errors))
        self.engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
        roots = self.engine.rootObjects()
        if not roots:
            raise RuntimeError("The window could not be loaded: " + "; ".join(self.qml_warnings))
        self.window: QWindow = roots[0]
        """The window: a QQuickWindow (shown as one wherever PySide's QtQuick module is loaded, as in the tests)."""
        self.window.setIcon(QIcon(str(APP_ICON)))

    def show(self) -> None:
        self.window.show()

    def close(self) -> None:
        self.window.close()
