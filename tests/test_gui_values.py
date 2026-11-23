"""Values that are not today's from Yahoo, in the new window. Rule numbers refer to tests/SPECIFICATION.md."""

from decimal import Decimal
from pathlib import Path

from fakes import SAMPLE, FakeProvider, write_statement
from PySide6.QtCore import Qt
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    double_click,
    english_computer,
    find,
    open_app,
    press,
    provider_with,
    row_items,
    rows,
    shows,
    type_text,
    wait_until,
    when_a_dialog_opens,
)

from statement_tracker.gui.home import ValueChoice
from statement_tracker.settings import Settings, TickerChoice

TWO_FUNDS = (
    "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 2000,EUR,1",
    "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,10,EUR 100.00,EUR 1001,EUR,1",
    "2025-01-20T10:00:00.000Z,WXYZ,BUY - MARKET,4,EUR 50.00,EUR 201,EUR,1",
)


def bond_without_a_price(app, tmp_path: Path):
    """Home with World fund priced at 120 and Bond fund (WXYZ, 4 shares) without a price."""
    settings = Settings.load(tmp_path / "settings.json")
    settings.ticker_choices["ABCD"] = TickerChoice("ABCD.DE", "World fund", "XETRA", "EUR", confirmed=True)
    settings.ticker_choices["WXYZ"] = TickerChoice("WXYZ.DE", "Bond fund", "XETRA", "EUR", confirmed=True)
    settings.save()
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")
    shell = open_app(tmp_path, provider, kept=write_statement(tmp_path, *TWO_FUNDS))
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def test_an_investment_without_a_price_is_left_out_and_its_value_can_be_entered(app, tmp_path: Path, english_computer) -> None:
    # Spec K8.
    shell = bond_without_a_price(app, tmp_path)
    assert rows(shell.window)[1] == ["Bond fund", "WXYZ · XETRA", "201.00", "No price today", "Not in the total", "Enter its value…"]
    asked = []

    def answer(choices, selected, currency):
        asked.append((selected, currency, [choice.ticker for choice in choices]))
        return "WXYZ", Decimal("204")

    shell.session.ask_value = answer
    click(find(shell.window, "Enter its value…"))

    assert asked == [("WXYZ", "EUR", ["WXYZ"])]
    assert rows(shell.window)[1][3:5] == ["204.00", "your value"]
    assert rows(shell.window)[-1][:3] == ["Total", "1,202.00", "1,404.00"]  # in the totals now
    assert not shows(shell.window, "has no price today")


def test_double_clicking_a_row_without_a_price_enters_its_value(app, tmp_path: Path) -> None:
    # Spec K8.
    shell = bond_without_a_price(app, tmp_path)
    asked = []
    shell.session.ask_value = lambda choices, selected, currency: asked.append(selected)

    double_click(find(shell.window, "No price today"))

    assert asked == ["WXYZ"]


def test_the_value_dialog_reads_either_decimal_separator_and_explains_the_rest(app, tmp_path: Path) -> None:
    # Spec K8 (Review Focus 5).
    shell = bond_without_a_price(app, tmp_path)
    shell.session.show_error = shell.errors.append
    choices = [ValueChoice("WXYZ", "Bond fund", Decimal("4"), None)]
    seen = []

    def type_and_confirm(text: str):
        def act() -> None:
            seen.append(shows(shell.window, "What is Bond fund worth now?", "For all 4 shares you hold"))
            type_text(shell.window, text)
            press(shell.window, Qt.Key.Key_Return)

        return act

    for typed in ("2.040,00", "2,040.00"):
        when_a_dialog_opens(shell, type_and_confirm(typed))
        assert shell.session.ask_value(choices, "WXYZ", "EUR") == ("WXYZ", Decimal("2040.00"))

    def wrong_then_right() -> None:
        type_and_confirm("abc")()
        when_a_dialog_opens(shell, type_and_confirm("12"))

    when_a_dialog_opens(shell, wrong_then_right)
    assert shell.session.ask_value(choices, "WXYZ", "EUR") == ("WXYZ", Decimal("12"))
    assert seen == [True, True, True, True]


def test_when_yahoo_cannot_be_reached_the_last_prices_are_used_and_dated(app, tmp_path: Path) -> None:
    # Spec K8.
    first = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)  # finds a price, and keeps it
    wait_until(app, lambda: not first.session.home.property("busy"))
    first.close()

    shell = open_app(tmp_path, FakeProvider(offline=True), kept=SAMPLE, spreadsheet=tmp_path / "mine.xlsx")
    wait_until(app, lambda: not shell.session.home.property("busy"))

    assert shows(shell.window, "Yahoo Finance can't be reached right now, so these values use the last prices found, from")
    assert shows(shell.window, "Try again", "589.31")
    assert rows(shell.window)[0][4].startswith("price from ")
    assert shows(shell.window, "Updating now writes these values, without a history row")
    assert not shows(shell.window, "Today's prices from Yahoo Finance")


def test_a_last_known_price_can_be_replaced_by_a_value(app, tmp_path: Path) -> None:
    # Spec K8.
    first = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not first.session.home.property("busy"))
    first.close()
    shell = open_app(tmp_path, FakeProvider(offline=True), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    asked = []
    shell.session.ask_value = lambda choices, selected, currency: asked.append(selected)

    double_click(row_items(shell.window)[0])

    assert asked == ["EQQB"]
