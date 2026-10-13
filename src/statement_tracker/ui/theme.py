"""Colours and the application-wide stylesheet, in a light and a dark version.

The window and every dialog share this look. The version follows the operating
system's light or dark mode and switches when the user changes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True)
class Palette:
    """The colours of one mode."""

    background: str
    card: str
    text: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    on_accent: str
    table_header: str
    good: str
    bad: str


LIGHT = Palette(
    background="#F4F6FB",
    card="#FFFFFF",
    text="#1B1F2A",
    muted="#5B6474",
    border="#D5DBE7",
    accent="#107C41",  # the green of Excel
    accent_hover="#0B5E31",
    on_accent="#FFFFFF",
    table_header="#E1F1E7",
    good="#1B7F4F",
    bad="#C0392B",
)
DARK = Palette(
    background="#15171C",
    card="#1F232B",
    text="#E8EAF0",
    muted="#A3ABBA",
    border="#373D4A",
    accent="#33C481",  # Excel's lighter green, readable on dark
    accent_hover="#5FD49D",
    on_accent="#0E1116",
    table_header="#1D3328",
    good="#4CC38A",
    bad="#FF7B72",
)

_current = LIGHT


def current() -> Palette:
    """Return the colours in use, for the few things a stylesheet cannot colour (table cells)."""
    return _current


def stylesheet(colours: Palette) -> str:
    """Build the stylesheet for one set of colours."""
    c = colours
    return f"""
    QMainWindow, QDialog, QMessageBox {{ background: {c.background}; }}
    QWidget {{ color: {c.text}; }}
    QLabel#intro {{ font-size: 15pt; font-weight: 600; }}
    QLabel#notes {{ color: {c.muted}; }}
    QGroupBox QLabel#badge {{ font-weight: 600; }}
    QLabel#badge[state="todo"] {{ color: {c.text}; }}
    QLabel#badge[state="optional"] {{ color: {c.muted}; }}
    QLabel#badge[state="ok"] {{ color: {c.good}; }}
    QLabel#status {{ font-weight: 600; }}
    QLabel#status[state="busy"] {{ color: {c.accent}; }}
    QLabel#status[state="ok"] {{ color: {c.good}; }}
    QLabel#status[state="error"] {{ color: {c.bad}; }}

    QGroupBox {{
        background: {c.card};
        border: 1px solid {c.border};
        border-radius: 10px;
        /* Room above the box for its title, so the title never sits on the border. */
        margin-top: 30px;
        padding: 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 2px;
        top: 4px;
        padding: 0 2px;
        color: {c.accent};
    }}
    QGroupBox QLabel, QGroupBox QPushButton {{ font-weight: normal; }}

    QPushButton {{
        background: {c.card};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ border-color: {c.accent}; }}
    QPushButton:focus {{ border: 2px solid {c.accent}; padding: 5px 13px; }}
    QPushButton:disabled {{ color: {c.muted}; background: {c.background}; }}
    QPushButton#primary {{
        background: {c.accent};
        color: {c.on_accent};
        border: none;
        border-radius: 8px;
        font-weight: 700;
        padding: 10px 16px;
    }}
    QPushButton#primary:hover {{ background: {c.accent_hover}; }}
    QPushButton#primary:focus {{ border: 2px solid {c.text}; padding: 8px 14px; }}
    QPushButton#primary:disabled {{ background: {c.border}; color: {c.muted}; }}

    QTableWidget {{
        background: {c.card};
        alternate-background-color: {c.background};
        border: 1px solid {c.border};
        border-radius: 8px;
        gridline-color: {c.border};
        selection-background-color: {c.table_header};
        selection-color: {c.text};
    }}
    QHeaderView::section {{
        background: {c.table_header};
        color: {c.text};
        border: none;
        border-bottom: 1px solid {c.border};
        padding: 8px;
        font-weight: 600;
    }}
    QLineEdit {{
        background: {c.card};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 6px 8px;
    }}
    QLineEdit:focus {{ border-color: {c.accent}; }}
    QRadioButton {{ spacing: 8px; padding: 3px 0; }}

    /* The rest styles Qt's own file chooser, which Linux shows when the desktop offers none. */
    QTreeView, QListView {{
        background: {c.card};
        alternate-background-color: {c.background};
        border: 1px solid {c.border};
        border-radius: 6px;
        selection-background-color: {c.table_header};
        selection-color: {c.text};
        outline: 0;
    }}
    QTreeView::item, QListView::item {{ padding: 4px 2px; }}
    QTreeView::item:hover, QListView::item:hover {{ background: {c.table_header}; }}
    QTreeView::item:selected, QListView::item:selected {{ background: {c.table_header}; color: {c.text}; }}
    QComboBox {{
        background: {c.card};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    QComboBox:focus {{ border-color: {c.accent}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {c.card};
        border: 1px solid {c.border};
        selection-background-color: {c.table_header};
        selection-color: {c.text};
    }}
    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px;
    }}
    QToolButton:hover {{ border-color: {c.accent}; }}
    QToolButton:checked, QToolButton:pressed {{ background: {c.table_header}; }}
    QSplitter::handle {{ background: transparent; }}
    QMenu {{ background: {c.card}; border: 1px solid {c.border}; padding: 4px; }}
    QMenu::item {{ padding: 5px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {c.table_header}; color: {c.text}; }}

    QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
    QScrollBar::handle {{ background: {c.border}; border-radius: 4px; }}
    QScrollBar::handle:vertical {{ min-height: 28px; }}
    QScrollBar::handle:horizontal {{ min-width: 28px; }}
    QScrollBar::handle:hover {{ background: {c.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QToolTip {{ background: {c.card}; color: {c.text}; border: 1px solid {c.border}; padding: 4px; }}
    """


def apply(app: QApplication, dark: bool | None = None) -> Palette:
    """Style the whole application. ``dark`` forces a mode; by default the system's mode is used."""
    global _current
    if dark is None:
        dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    _current = DARK if dark else LIGHT
    app.setPalette(_palette(_current))
    app.setStyleSheet(stylesheet(_current))
    return _current


def _palette(colours: Palette) -> QPalette:
    """The same colours as a Qt palette, for the parts a stylesheet does not reach (icons, arrows)."""
    c = colours
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c.background,
        QPalette.ColorRole.WindowText: c.text,
        QPalette.ColorRole.Base: c.card,
        QPalette.ColorRole.AlternateBase: c.background,
        QPalette.ColorRole.Text: c.text,
        QPalette.ColorRole.Button: c.card,
        QPalette.ColorRole.ButtonText: c.text,
        QPalette.ColorRole.ToolTipBase: c.card,
        QPalette.ColorRole.ToolTipText: c.text,
        QPalette.ColorRole.PlaceholderText: c.muted,
        QPalette.ColorRole.Highlight: c.accent,
        QPalette.ColorRole.HighlightedText: c.on_accent,
        QPalette.ColorRole.Link: c.accent,
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c.muted))
    return palette


def follow_system(app: QApplication) -> None:
    """Apply the system's mode now and again whenever the user switches it."""
    apply(app)
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply(app))


def set_state(widget: QWidget, state: str) -> None:
    """Set the ``state`` a stylesheet rule can match (e.g. ok, error) and redraw the widget."""
    widget.setProperty("state", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
