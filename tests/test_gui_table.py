"""Home's investments table: choosing columns, sorting, Show and search, driven as a user would.
Rule numbers refer to tests/SPECIFICATION.md."""

import threading
from pathlib import Path

from fakes import FakeProvider, write_statement
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    double_click,
    _items,
    english_computer,
    field,
    find,
    find_all,
    heading,
    open_app,
    press,
    rows,
    scroll_to,
    settle,
    shows,
    type_text,
    wait_until,
)
from PySide6.QtCore import Qt
from test_gui_home import with_listings

from statement_tracker.gui.app import AppWindow
from statement_tracker.settings import Settings

THREE_FUNDS = (
    "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 3000,EUR,1",
    "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,10,EUR 100.00,EUR 1000,EUR,1",
    "2025-01-06T10:01:00.000Z,WXYZ,BUY - MARKET,10,EUR 50.00,EUR 500,EUR,1",
    "2025-01-06T10:02:00.000Z,EFGH,BUY - MARKET,10,EUR 80.00,EUR 800,EUR,1",
)
"""10 shares each: World fund 1,000.00, now 120 a share (1,200.00); Bond fund 500.00, now 45 (450.00); Tech fund
800.00, now 135 (1,350.00). Listed by ticker: World (ABCD), Tech (EFGH), Bond (WXYZ); by worth: Tech, World, Bond."""
PRICES = {"ABCD": "120", "WXYZ": "45", "EFGH": "135"}
USUAL_FIRST_ROW = ["World fund", "ABCD · XETRA", "1,000.00", "1,200.00", "40.0 %", "▲ +200.00 (+20.00 %)"]


def prices_of(**prices: str | None) -> FakeProvider:
    """Today's prices of the three funds (``WXYZ=None``: Bond fund has none today)."""
    provider = FakeProvider()
    for ticker, price in {**PRICES, **prices}.items():
        if price is not None:
            provider.add(f"{ticker}.DE", "EUR", price=price)
    return provider


def table(app, tmp_path: Path, **prices: str | None) -> AppWindow:
    """Home on the three funds, with their prices in."""
    with_listings(tmp_path, ABCD=("ABCD.DE", "World fund"), WXYZ=("WXYZ.DE", "Bond fund"), EFGH=("EFGH.DE", "Tech fund"))
    shell = open_app(tmp_path, prices_of(**prices), kept=write_statement(tmp_path, *THREE_FUNDS))
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def reopened(app, tmp_path: Path, **prices: str | None) -> AppWindow:
    """The app opened again on the same settings and the statement it kept."""
    shell = open_app(tmp_path, prices_of(**prices))
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def names(shell: AppWindow) -> list[str]:
    return [row[0] for row in rows(shell.window)]


def column_choice(shell: AppWindow, label: str):
    """The tick box of ``label`` in the open Columns menu."""
    found = [item for item in find_all(shell.window, label) if item.objectName() == "columnChoice"]
    assert len(found) == 1, f"{len(found)} column choices read {label!r}"
    return found[0]


# -- choosing columns -------------------------------------------------------------------------------


def test_the_usual_columns_show_until_more_are_chosen(app, tmp_path: Path, english_computer) -> None:
    # Spec F5.
    shell = table(app, tmp_path)

    assert rows(shell.window)[0] == USUAL_FIRST_ROW
    assert names(shell) == ["World fund", "Tech fund", "Bond fund", "Total"]  # by ticker, as always


def test_columns_can_be_added_hidden_and_reset_and_are_remembered(app, tmp_path: Path, english_computer) -> None:
    # Spec F5.
    shell = table(app, tmp_path)

    click(find(shell.window, "Columns"))
    click(column_choice(shell, "Shares"))
    click(column_choice(shell, "Price per share"))
    click(column_choice(shell, "Share of total"))
    click(column_choice(shell, "Investment"))  # always shown: nothing happens
    assert column_choice(shell, "Investment").property("checked")
    assert shows(shell.window, "always shown")

    chosen = ["World fund", "ABCD · XETRA", "10", "120.00", "1,000.00", "1,200.00", "▲ +200.00 (+20.00 %)"]
    assert rows(shell.window)[0] == chosen
    assert rows(shell.window)[-1] == ["Total", "2,300.00", "3,000.00", "▲ +700.00 (+30.43 %)"]  # no shares, no price

    again = reopened(app, tmp_path)
    assert rows(again.window)[0] == chosen

    click(find(again.window, "Columns"))
    click(find(again.window, "Reset columns"))
    assert rows(again.window)[0] == USUAL_FIRST_ROW


def test_every_column_fits_by_scrolling_sideways_on_a_small_window(app, tmp_path: Path, english_computer) -> None:
    # Spec F5 (Review Focus 3).
    shell = table(app, tmp_path)
    shell.window.setWidth(720)
    settle(app)

    click(find(shell.window, "Columns"))
    for label in ("Shares", "Average cost per share", "Price per share", "Share of invested", "Gain from sales",
                  "Dividends received"):
        click(column_choice(shell, label))
    click(find(shell.window, "Columns"))  # closes the menu

    assert shell.window.width() == 720
    last = heading(shell.window, "Dividends received")
    scroll_to(last)
    right = last.mapToScene(last.boundingRect().topRight()).x()
    assert right <= shell.window.width()
    assert rows(shell.window)[0] == [
        "World fund", "ABCD · XETRA", "10", "100.00", "120.00", "1,000.00", "1,200.00", "40.0 %", "43.5 %",
        "▲ +200.00 (+20.00 %)", "0.00", "0.00",
    ]
    assert rows(shell.window)[-1] == [
        "Total", "2,300.00", "3,000.00", "100.0 %", "100.0 %", "▲ +700.00 (+30.43 %)", "0.00", "0.00",
    ]


# -- sorting --------------------------------------------------------------------------------------------


def test_clicking_a_heading_sorts_reverses_and_goes_back(app, tmp_path: Path) -> None:
    # Spec F5 (Review Focus 4: amounts compare as numbers, "1,350.00" above "450.00").
    shell = table(app, tmp_path)

    click(heading(shell.window, "Worth now"))
    assert names(shell) == ["Tech fund", "World fund", "Bond fund", "Total"]
    click(heading(shell.window, "Worth now"))
    assert names(shell) == ["Bond fund", "World fund", "Tech fund", "Total"]
    click(heading(shell.window, "Worth now"))
    assert names(shell) == ["World fund", "Tech fund", "Bond fund", "Total"]  # the usual order, by ticker

    click(heading(shell.window, "Investment"))
    assert names(shell) == ["Bond fund", "Tech fund", "World fund", "Total"]  # names A to Z first


def test_the_sort_is_remembered_and_hiding_its_column_undoes_it(app, tmp_path: Path) -> None:
    # Spec F5.
    shell = table(app, tmp_path)
    click(heading(shell.window, "Gain or loss"))
    assert names(shell) == ["Tech fund", "World fund", "Bond fund", "Total"]

    again = reopened(app, tmp_path)
    assert names(again) == ["Tech fund", "World fund", "Bond fund", "Total"]

    click(find(again.window, "Columns"))
    click(column_choice(again, "Gain or loss"))
    assert names(again) == ["World fund", "Tech fund", "Bond fund", "Total"]


def test_investments_without_a_price_sort_last(app, tmp_path: Path) -> None:
    # Spec F5 (Review Focus 4).
    shell = table(app, tmp_path, WXYZ=None)

    click(heading(shell.window, "Worth now"))
    assert names(shell) == ["Tech fund", "World fund", "Bond fund", "Total"]
    click(heading(shell.window, "Worth now"))
    assert names(shell) == ["World fund", "Tech fund", "Bond fund", "Total"]


def test_renaming_and_entering_a_value_in_a_sorted_table_act_on_the_one_clicked(app, tmp_path: Path) -> None:
    # Spec F5, F10 (Review Focus 2).
    shell = table(app, tmp_path)
    click(heading(shell.window, "Worth now"))
    click(heading(shell.window, "Worth now"))  # smallest first: Bond fund on top
    double_click(find(shell.window, "Bond fund"))
    type_text(shell.window, "Bonds")
    press(shell.window, Qt.Key.Key_Return)
    assert names(shell) == ["Bonds", "World fund", "Tech fund", "Total"]

    priceless = table(app, tmp_path / "unpriced", WXYZ=None)
    click(heading(priceless.window, "Worth now"))  # Bond fund, without a price, last
    asked = []
    priceless.session.ask_value = lambda choices, selected, currency: asked.append(selected)
    click(find(priceless.window, "Enter its value…"))
    assert asked == ["WXYZ"]


# -- Show and search -------------------------------------------------------------------------------------


def choose_show(shell: AppWindow, choice: str) -> None:
    click(find(shell.window, shell.session.home.property("showLabel")))
    click(find(shell.window, choice))


def search_for(shell: AppWindow, text: str) -> None:
    click(field(shell.window, "Search by name or ticker"))
    press(shell.window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    type_text(shell.window, text)


def test_show_gaining_or_losing_and_the_total_covers_only_those(app, tmp_path: Path, english_computer) -> None:
    # Spec F5.
    shell = table(app, tmp_path)

    choose_show(shell, "Gaining")
    assert names(shell) == ["World fund", "Tech fund", "Total of the 2 shown"]
    assert rows(shell.window)[-1] == ["Total of the 2 shown", "1,800.00", "2,550.00", "85.0 % of all", "▲ +750.00 (+41.67 %)"]
    assert shows(shell.window, "Show: gaining",
                 "Showing the 2 of your 3 investments that are gaining. The Total below covers only these.")
    assert shows(shell.window, "3,000.00")  # Worth now, at the top: the whole portfolio

    choose_show(shell, "Losing")
    assert rows(shell.window) == [["Bond fund", "WXYZ · XETRA", "500.00", "450.00", "15.0 %", "▼ -50.00 (-10.00 %)"],
                                  ["Total of the 1 shown", "500.00", "450.00", "15.0 % of all", "▼ -50.00 (-10.00 %)"]]

    click(find(shell.window, "Show all"))
    assert names(shell) == ["World fund", "Tech fund", "Bond fund", "Total"]
    assert shows(shell.window, "Show: all")


def test_show_is_remembered_and_says_so_when_nothing_matches(app, tmp_path: Path) -> None:
    # Spec F5 (Review Focus 1).
    shell = table(app, tmp_path)
    choose_show(shell, "Gaining")

    again = reopened(app, tmp_path, ABCD="90", EFGH="70")  # nothing is up today
    assert names(again) == []
    assert shows(again.window, "Show: gaining", "None of your 3 investments match.")

    click(find(again.window, "Show all"))
    assert names(again) == ["World fund", "Tech fund", "Bond fund", "Total"]


def test_an_investment_without_a_price_is_neither_gaining_nor_losing(app, tmp_path: Path) -> None:
    # Spec F5.
    shell = table(app, tmp_path, WXYZ=None)

    choose_show(shell, "Gaining")
    assert names(shell) == ["World fund", "Tech fund", "Total of the 2 shown"]
    choose_show(shell, "Losing")
    assert names(shell) == []
    choose_show(shell, "All investments")
    assert names(shell) == ["World fund", "Tech fund", "Bond fund", "Total"]


def test_search_finds_by_name_or_ticker_and_is_not_remembered(app, tmp_path: Path) -> None:
    # Spec F5.
    shell = table(app, tmp_path)

    search_for(shell, "tech")
    assert names(shell) == ["Tech fund", "Total of the 1 shown"]
    assert shows(shell.window, "Showing the 1 of your 3 investments that matches \u201ctech\u201d.")
    search_for(shell, "efgh")
    assert names(shell) == ["Tech fund", "Total of the 1 shown"]

    again = reopened(app, tmp_path)
    assert field(again.window, "Search by name or ticker").property("text") == ""
    assert names(again) == ["World fund", "Tech fund", "Bond fund", "Total"]

    choose_show(again, "Gaining")
    search_for(again, "w")
    assert names(again) == ["World fund", "Total of the 1 shown"]
    assert shows(again.window, "Showing the 1 of your 3 investments that is gaining and matches \u201cw\u201d.")
    click(find(again.window, "Show all"))
    assert field(again.window, "Search by name or ticker").property("text") == ""
    assert names(again) == ["World fund", "Tech fund", "Bond fund", "Total"]


def test_entering_a_value_in_a_filtered_table_acts_on_the_one_clicked(app, tmp_path: Path) -> None:
    # Spec F5, F8 (Review Focus 2).
    shell = table(app, tmp_path, WXYZ=None)
    search_for(shell, "bond")
    asked = []
    shell.session.ask_value = lambda choices, selected, currency: asked.append(selected)

    click(find(shell.window, "Enter its value…"))
    assert asked == ["WXYZ"]


class HeldBack(FakeProvider):
    """Prices that arrive only once the test lets them go."""

    def __init__(self) -> None:
        super().__init__()
        self.let_go = threading.Event()

    def quote(self, symbol):
        self.let_go.wait(5)
        return super().quote(symbol)


def test_while_prices_come_in_every_investment_is_listed(app, tmp_path: Path) -> None:
    # Spec F5.
    shell = table(app, tmp_path)
    choose_show(shell, "Gaining")
    provider = HeldBack()
    for ticker, price in PRICES.items():
        provider.add(f"{ticker}.DE", "EUR", price=price)

    again = open_app(tmp_path, provider)
    try:
        assert names(again) == ["World fund", "Tech fund", "Bond fund"]  # no values yet: Show waits for them
    finally:
        provider.let_go.set()
    wait_until(app, lambda: not again.session.home.property("busy"))
    assert names(again) == ["World fund", "Tech fund", "Total of the 2 shown"]


# -- the review's findings ----------------------------------------------------------------------------------


def scene_rect(item):
    from PySide6.QtCore import QRectF

    return item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))


def test_the_columns_panel_opens_clear_of_its_button_and_closes_with_it(app, tmp_path: Path, english_computer) -> None:
    # Spec F5: on the window as it opens, clicking Columns again closes the panel and changes nothing.
    shell = table(app, tmp_path)
    button = find(shell.window, "Columns")

    click(button)
    choices = [item for item in find_all(shell.window, "Shares") if item.objectName() == "columnChoice"]
    assert choices
    for label in ("Investment", "Shares", "Share of total", "Dividends received", "Reset columns"):
        item = column_choice(shell, label) if label != "Reset columns" else find(shell.window, label)
        assert not scene_rect(item).intersects(scene_rect(button)), f"{label} covers the Columns button"
    click(button)
    assert not [item for item in find_all(shell.window, "Shares") if item.objectName() == "columnChoice"]
    assert rows(shell.window)[0] == USUAL_FIRST_ROW


def test_the_columns_panel_works_from_the_keyboard(app, tmp_path: Path) -> None:
    # Spec F5, F11: Tab reaches every tick box, Space ticks it, Esc closes the panel.
    shell = table(app, tmp_path)
    click(find(shell.window, "Columns"))

    press(shell.window, Qt.Key.Key_Tab)
    focused = shell.window.activeFocusItem()
    assert (focused.objectName(), focused.property("text")) == ("columnChoice", "Shares")
    press(shell.window, Qt.Key.Key_Space)
    assert heading(shell.window, "Shares")
    focused = shell.window.activeFocusItem()
    assert (focused.objectName(), focused.property("text")) == ("columnChoice", "Shares")
    press(shell.window, Qt.Key.Key_Escape)
    assert not [item for item in find_all(shell.window, "Shares") if item.objectName() == "columnChoice"]


def test_the_toolbar_moves_under_the_title_on_a_small_window(app, tmp_path: Path) -> None:
    # Spec F5: on a narrow window the search box and buttons wrap under the title, inside the card.
    shell = table(app, tmp_path)
    shell.window.setWidth(720)
    settle(app)
    choose_show(shell, "Gaining")

    card = next(item for item in _items(shell.window) if item.objectName() == "investmentsCard")
    columns = scene_rect(find(shell.window, "Columns"))
    assert columns.right() <= scene_rect(card).right() - 19
    title = scene_rect(find(shell.window, "Your investments"))
    assert scene_rect(field(shell.window, "Search by name or ticker")).top() >= title.bottom()


def test_long_numbers_fit_their_columns(app, tmp_path: Path, english_computer) -> None:
    # Spec F5: Shares with all its decimals, and a large loss inside its own column.
    with_listings(tmp_path, ABCD=("ABCD.DE", "World fund"))
    statement = write_statement(tmp_path, "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 12000,EUR,1",
                                "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,31.47328346,EUR 367.53,EUR 11567.21,EUR,1")
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="11.18")
    shell = open_app(tmp_path, provider, kept=statement)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    click(find(shell.window, "Columns"))
    for label in ("Shares", "Average cost per share", "Price per share", "Share of invested", "Gain from sales",
                  "Dividends received"):
        click(column_choice(shell, label))
    click(find(shell.window, "Columns"))

    shares = find(shell.window, "31.47328346")
    assert not shares.property("truncated")
    loss = find_all(shell.window, "▼ -11,215.34 (-96.96 %)")[0]
    assert loss.width() <= loss.parentItem().width()


def test_table_choices_made_during_a_fetch_are_saved_once_it_ends(app, tmp_path: Path) -> None:
    # Spec F5: a fetch may save the settings itself, so the table's choices wait for it to end.
    table(app, tmp_path)
    provider = HeldBack()
    for ticker, price in PRICES.items():
        provider.add(f"{ticker}.DE", "EUR", price=price)
    again = open_app(tmp_path, provider)
    try:
        click(heading(again.window, "Investment"))
        assert names(again) == ["Bond fund", "Tech fund", "World fund"]  # sorted at once
        assert Settings.load(tmp_path / "settings.json").table_sort is None  # not saved during the fetch
    finally:
        provider.let_go.set()
    wait_until(app, lambda: not again.session.home.property("busy"))
    assert Settings.load(tmp_path / "settings.json").table_sort == ("name", False)
