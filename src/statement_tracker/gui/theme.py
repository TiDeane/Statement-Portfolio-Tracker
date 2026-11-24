"""The window's colours, light and dark, as the design sets them. QML reads them from ``Theme``.

Light or dark follows the system and switches while the app is open, unless the user chose one in
Settings. Every pair of text and background colour reaches a contrast of 4.5:1. The window's title
bar and frame follow too: on Linux (Wayland) Qt draws them itself, from the application's palette; on
Windows the system draws them, in the light or dark Qt asks for.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette

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


QT_COLOURS = (
    (QPalette.ColorRole.Window, "bg"),
    (QPalette.ColorRole.WindowText, "text"),
    (QPalette.ColorRole.Base, "surface"),
    (QPalette.ColorRole.AlternateBase, "subtle"),
    (QPalette.ColorRole.Text, "text"),
    (QPalette.ColorRole.Button, "surface"),
    (QPalette.ColorRole.ButtonText, "text"),
    (QPalette.ColorRole.Light, "subtle"),
    (QPalette.ColorRole.Midlight, "border"),
    (QPalette.ColorRole.Mid, "borderStrong"),
    (QPalette.ColorRole.Dark, "muted"),
    (QPalette.ColorRole.Shadow, "borderStrong"),
    (QPalette.ColorRole.Highlight, "accent"),
    (QPalette.ColorRole.HighlightedText, "accentText"),
    (QPalette.ColorRole.PlaceholderText, "muted"),
    (QPalette.ColorRole.ToolTipBase, "surface"),
    (QPalette.ColorRole.ToolTipText, "text"),
)
"""The application palette's roles and the colours they take: the same as Main.qml gives its window."""
SCHEMES = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}
"""The user's choice, as asked of the system; "system" asks for nothing (Qt.ColorScheme.Unknown)."""


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
        self._app: QGuiApplication | None = None
        """The application whose own palette follows (once ``follow`` is called)."""
        self._painted: bool | None = None
        """Whether the application's palette was last made dark, or None before it was set."""

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
        if self._app is not None:
            # Asked of the system, for the title bar it draws (Windows). Back on "system", the system's
            # own light or dark is read again: it was not followed while the user's choice was asked for.
            hints = self._app.styleHints()
            hints.setColorScheme(SCHEMES.get(choice, Qt.ColorScheme.Unknown))
            if choice == "system":
                self._system_dark = hints.colorScheme() == Qt.ColorScheme.Dark
        self._apply()

    def _scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        # While the user's choice is asked for, the scheme reported is that choice, not the system's.
        if self._choice == "system":
            self.set_dark(scheme == Qt.ColorScheme.Dark)

    def _apply(self) -> None:
        dark = self._choice == "dark" or (self._choice == "system" and self._system_dark)
        if dark != self._dark:
            self._dark = dark
            self.changed.emit()
        if self._app is not None and self._painted is not dark:
            # The application's palette, for what Qt draws outside QML: on Linux, the title bar and frame.
            colours = DARK if dark else LIGHT
            palette = QPalette(self._app.palette())
            for role, name in QT_COLOURS:
                palette.setColor(role, QColor(colours[name]))
            self._app.setPalette(palette)
            self._painted = dark

    def follow(self, app: QGuiApplication) -> None:
        """Be light or dark as the system is, now and whenever the user switches it, and give the
        window's title bar and frame the same light or dark (see the module's docstring)."""
        self._app = app
        hints = app.styleHints()
        self.set_dark(hints.colorScheme() == Qt.ColorScheme.Dark)
        hints.colorSchemeChanged.connect(self._scheme_changed)
