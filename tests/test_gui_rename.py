"""Renaming, undo and redo in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

import sys
from decimal import Decimal
from pathlib import Path

from fakes import SAMPLE
from openpyxl import load_workbook
from PySide6.QtCore import Qt
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    double_click,
    editor,
    find,
    open_app,
    press,
    provider_with,
    rows,
    type_text,
    wait_until,
)
from test_gui_values import bond_without_a_price

from statement_tracker.settings import Settings

RENAME_KEY = Qt.Key.Key_Return if sys.platform == "darwin" else Qt.Key.Key_F2
CTRL = Qt.KeyboardModifier.ControlModifier


def home(app, tmp_path: Path, spreadsheet: Path | None = None):
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, spreadsheet=spreadsheet)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def rename(shell, name: str | None, *, start=None) -> None:
    """Open the first investment's name for typing (double-click, or ``start``), type ``name`` and press
    Enter; None presses Esc instead."""
    (start or (lambda: double_click(find(shell.window, rows(shell.window)[0][0]))))()
    if name is None:
        press(shell.window, Qt.Key.Key_Escape)
        return
    if name:
        type_text(shell.window, name)  # replaces the name, which opens selected
    else:
        press(shell.window, Qt.Key.Key_Backspace)
    press(shell.window, Qt.Key.Key_Return)


def names(tmp_path: Path) -> dict[str, str]:
    return Settings.load(tmp_path / "settings.json").index_names


def test_an_investment_is_renamed_by_typing_on_its_name(app, tmp_path: Path) -> None:
    # Spec K10.
    shell = home(app, tmp_path)
    asked = []
    shell.session.ask_value = lambda *question: asked.append(question)

    double_click(find(shell.window, "Nasdaq fund"))
    assert editor(shell.window).property("text") == "Nasdaq fund"
    type_text(shell.window, " Tech fund ")
    press(shell.window, Qt.Key.Key_Return)

    assert rows(shell.window)[0][:2] == ["Tech fund", "EQQB · XETRA"]
    assert names(tmp_path) == {"EQQB": "Tech fund"}
    assert asked == [] and shell.errors == []

    rename(shell, None)  # Esc cancels
    assert rows(shell.window)[0][0] == "Tech fund"

    rename(shell, "")  # empty: back to the name from Yahoo
    assert rows(shell.window)[0][0] == "Nasdaq fund" and names(tmp_path) == {}


def test_the_systems_rename_key_opens_the_name_reached_with_the_keyboard(app, tmp_path: Path) -> None:
    # Spec K10: F2 (Return on a Mac).
    shell = home(app, tmp_path)

    def by_key() -> None:
        click(find(shell.window, "Nasdaq fund"))  # the name is reached (Tab reaches it too)
        press(shell.window, RENAME_KEY)

    rename(shell, "Tech fund", start=by_key)

    assert names(tmp_path) == {"EQQB": "Tech fund"}


def test_a_rename_before_any_update_leaves_the_spreadsheet_alone(app, tmp_path: Path) -> None:
    # Spec K10.
    sheet = tmp_path / "mine.xlsx"
    shell = home(app, tmp_path, spreadsheet=sheet)

    rename(shell, "My Nasdaq")

    assert not sheet.exists()


def test_a_rename_after_an_update_is_written_at_once(app, tmp_path: Path) -> None:
    # Spec K10.
    sheet = tmp_path / "mine.xlsx"
    shell = home(app, tmp_path, spreadsheet=sheet)
    click(find(shell.window, "Update my spreadsheet"))

    rename(shell, "My Nasdaq")

    assert load_workbook(sheet)["Current Holdings"]["A2"].value == "(EQQB) My Nasdaq"
    assert find(shell.window, "Your spreadsheet is up to date").isVisible()


def test_a_value_entered_after_an_update_is_written_at_once(app, tmp_path: Path) -> None:
    # Spec K10, K8.
    settings = Settings.load(tmp_path / "settings.json")
    settings.spreadsheet_path = tmp_path / "mine.xlsx"
    settings.save()
    shell = bond_without_a_price(app, tmp_path)
    click(find(shell.window, "Update my spreadsheet"))
    shell.session.ask_value = lambda choices, selected, currency: ("WXYZ", Decimal("204"))

    click(find(shell.window, "Enter its value…"))

    values = [row[3].value for row in load_workbook(tmp_path / "mine.xlsx")["Current Holdings"].iter_rows(min_row=2, max_row=3)]
    assert 204 in [round(value) for value in values if isinstance(value, (int, float))]


def test_ctrl_z_and_ctrl_y_undo_and_redo_names_and_values(app, tmp_path: Path) -> None:
    # Spec K10 (F7).
    shell = bond_without_a_price(app, tmp_path)
    shell.session.ask_value = lambda choices, selected, currency: ("WXYZ", Decimal("204"))
    click(find(shell.window, "Enter its value…"))
    rename(shell, "Equity fund")
    assert rows(shell.window)[0][0] == "Equity fund" and rows(shell.window)[1][3] == "204.00"

    press(shell.window, Qt.Key.Key_Z, CTRL)  # the name
    assert rows(shell.window)[0][0] == "World fund" and rows(shell.window)[1][3] == "204.00"

    press(shell.window, Qt.Key.Key_Z, CTRL)  # the value
    assert rows(shell.window)[1][3] == "No price today"

    press(shell.window, Qt.Key.Key_Y, CTRL)
    press(shell.window, Qt.Key.Key_Y, CTRL)
    assert rows(shell.window)[0][0] == "Equity fund" and rows(shell.window)[1][3] == "204.00"
