"""How the new window writes numbers, dates and colours. Rule numbers refer to tests/SPECIFICATION.md."""

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QLocale
from fakes import FakeProvider
from quick_driver import app, close_windows_afterwards, open_app  # noqa: F401

from statement_tracker.gui.formatting import day_text, gain, money, money_with_currency, parse_amount, percent, share
from statement_tracker.gui.theme import DARK, LIGHT, Theme

ENGLISH = QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
PORTUGUESE = QLocale(QLocale.Language.Portuguese, QLocale.Country.Portugal)


def spaced(text: str) -> str:
    """Thousands separated by any kind of space read as a plain space."""
    return text.replace(" ", " ").replace(" ", " ")


def test_amounts_follow_the_computers_locale() -> None:
    # Spec F4: numbers follow the computer's locale; the currency is the statement's.
    assert money(Decimal("12727.8"), ENGLISH) == "12,727.80"
    assert spaced(money(Decimal("12727.8"), PORTUGUESE)) == "12 727,80"
    assert money_with_currency(Decimal("541.49"), "EUR", ENGLISH) == "541.49 EUR"
    assert percent(Decimal("12.874"), ENGLISH) == "12.87 %"
    assert percent(Decimal("12.874"), PORTUGUESE) == "12,87 %"
    assert share(Decimal("56.007"), ENGLISH) == "56.0 %"


def test_a_gain_or_loss_has_a_sign_and_an_arrow() -> None:
    # Spec F4: a gain shows a sign and an arrow as well as a colour.
    assert gain(Decimal("1451.70"), Decimal("12.874"), ENGLISH) == "▲ +1,451.70 (+12.87 %)"
    assert gain(Decimal("-38.5"), Decimal("-1.9"), ENGLISH) == "▼ -38.50 (-1.90 %)"
    assert gain(Decimal("47.82"), None, ENGLISH) == "▲ +47.82"
    assert gain(Decimal("0"), Decimal("0"), ENGLISH) == "0.00"


def test_dates_are_figures_in_the_computers_order() -> None:
    # Spec F4: dates in figures, in the computer's order, with a four-digit year.
    assert day_text(date(2026, 11, 14), PORTUGUESE) == "14/11/2026"
    assert day_text(date(2026, 11, 14), QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)) == "11/14/2026"


def test_typed_amounts_take_either_decimal_separator() -> None:
    assert parse_amount("2.040,00") == Decimal("2040.00")
    assert parse_amount("2,040.00") == Decimal("2040.00")
    assert parse_amount("0") is None


def test_the_theme_has_the_designs_colours(app) -> None:
    # Spec F10: light and dark themes, in the design's colours.
    assert LIGHT["accent"] == "#107C41" and DARK["accent"] == "#33C481"
    assert LIGHT["muted"] == "#5B6270" and DARK["bg"] == "#1B1C20"
    assert LIGHT.keys() == DARK.keys()

    theme = Theme()
    theme.set_dark(False)
    assert theme.property("surface") == "#FFFFFF" and theme.property("dark") is False
    theme.set_dark(True)
    assert theme.property("surface") == "#24262B" and theme.property("dark") is True


def test_the_window_takes_its_colours_from_the_theme_and_switches_live(app, tmp_path) -> None:
    # Spec F10: light and dark themes, following the system while the app is open.
    shell = open_app(tmp_path, FakeProvider())
    shell.theme.set_dark(False)
    assert shell.window.property("color").name().upper() == LIGHT["bg"]

    shell.theme.set_dark(True)
    assert shell.window.property("color").name().upper() == DARK["bg"]
