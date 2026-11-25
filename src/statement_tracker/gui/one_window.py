"""One copy of the app at a time: opening it again shows the window that is open.

Two copies would read and write the same settings and spreadsheet. The first copy listens under a name
made from the settings file's path (so per user); a later one that reaches it asks it to show its window
and closes. Qt's local sockets: a named pipe on Windows, a socket file in the temporary folder elsewhere.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

WAIT_MS = 1000
"""How long a later copy waits to reach the first."""


def window_name(settings_path: Path) -> str:
    """What the copy of the app using the settings file at ``settings_path`` listens on."""
    digest = hashlib.sha256(str(settings_path.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"StatementPortfolioTracker-{digest}"


class OneWindow(QObject):
    """Makes sure only one copy of the app is open for ``name``."""

    showWanted = Signal()
    """The app was opened again: its window should show itself."""

    def __init__(self, name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._server: QLocalServer | None = None

    def claim(self) -> bool:
        """True if no other copy is open: this one then listens for later ones. False if one is, after asking
        it to show its window: this copy should close."""
        other = QLocalSocket()
        other.connectToServer(self._name)
        if other.waitForConnected(WAIT_MS):  # reaching it is the whole request
            _let_the_other_come_forward()
            other.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)  # what a copy that crashed left (not on Windows)
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)  # this user's copies only
        if not server.listen(self._name):
            return True  # opens anyway, as it did before there was a check
        server.newConnection.connect(self._asked)
        self._server = server
        return True

    def release(self) -> None:
        """Stop listening (a copy that ends stops by itself)."""
        if self._server is not None:
            self._server.close()
            self._server = None

    def _asked(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            connection.disconnected.connect(connection.deleteLater)
            connection.disconnectFromServer()
        self.showWanted.emit()


def _let_the_other_come_forward() -> None:
    """On Windows, only the program the user just started may bring a window to the front: let the first copy."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
