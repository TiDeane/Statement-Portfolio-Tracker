"""The window's colours, light and dark, as the design sets them. QML reads them from ``Theme``.

Light or dark follows the system and switches while the app is open, unless the user chose one in
Settings. Every pair of text and background colour reaches a contrast of 4.5:1.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

LIGHT = {
    "bg": "#F5F6F8",
    "surface": "#FFFFFF",
    "subtle": "#F1F3F5",
    "border": "#E3E6EA",
    "borderStrong": "#CDD2D9",
    "text": "#16181D",
    "muted": "#5B6270",
    "accent": "#107C41",  # the green of Excel and of the app's icon
    "accentText": "#FFFFFF",
    "accentSoft": "#E5F2EA",
    "accentInk": "#0B6234",
    "gain": "#0E7A3D",
    "loss": "#C42B1C",
    "warnBg": "#FFF4CE",
    "warnInk": "#6E4600",
    "warnBorder": "#F0D58C",
    "errBg": "#FDE7E9",
    "errInk": "#A4262C",
    "errBorder": "#F2B8BD",
    "okBg": "#E8F5EC",
    "okInk": "#0B6234",
    "okBorder": "#B9DEC6",
    "skeleton": "#E6E8EC",
}
DARK = {
    "bg": "#1B1C20",
    "surface": "#24262B",
    "subtle": "#2C2E34",
    "border": "#383B42",
    "borderStrong": "#4A4E57",
    "text": "#ECEDEF",
    "muted": "#A7ACB6",
    "accent": "#33C481",
    "accentText": "#0B1F14",
    "accentSoft": "#1E3A2B",
    "accentInk": "#6FD9A3",
    "gain": "#5FD49D",
    "loss": "#FF8A80",
    "warnBg": "#3A3016",
    "warnInk": "#F5C451",
    "warnBorder": "#5C4A1C",
    "errBg": "#3F2120",
    "errInk": "#FF9C94",
    "errBorder": "#6B2E2B",
    "okBg": "#1A3326",
    "okInk": "#6FD9A3",
    "okBorder": "#2D5A40",
    "skeleton": "#33363D",
}


def _colour(name: str):
    return lambda theme: (DARK if theme._dark else LIGHT)[name]


class Theme(QObject):
    """The current colours, one property per name in ``LIGHT``, plus ``dark``."""

    changed = Signal()

    for _name in LIGHT:
        locals()[_name] = Property(str, _colour(_name), notify=changed)
    del _name

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dark = False
        self._system_dark = False
        self._choice = "system"

    def _is_dark(self) -> bool:
        return self._dark

    dark = Property(bool, _is_dark, notify=changed)

    def set_dark(self, dark: bool) -> None:
        """The system is dark (or light) now: followed unless the user chose light or dark."""
        self._system_dark = dark
        self._apply()

    def set_choice(self, choice: str) -> None:
        """The user's choice in Settings: "system", "light" or "dark"."""
        self._choice = choice
        self._apply()

    def _apply(self) -> None:
        dark = self._choice == "dark" or (self._choice == "system" and self._system_dark)
        if dark != self._dark:
            self._dark = dark
            self.changed.emit()

    def follow(self, app: QGuiApplication) -> None:
        """Be light or dark as the system is, now and whenever the user switches it."""
        hints = app.styleHints()
        self.set_dark(hints.colorScheme() == Qt.ColorScheme.Dark)
        hints.colorSchemeChanged.connect(lambda scheme: self.set_dark(scheme == Qt.ColorScheme.Dark))
