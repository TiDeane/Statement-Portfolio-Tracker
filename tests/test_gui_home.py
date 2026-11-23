"""Home in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

import threading
import time
from datetime import date
from pathlib import Path

from fakes import SAMPLE, SAMPLES, FakeProvider, ranges_around, write_statement
from quick_driver import (  # noqa: F401
    EQQB_BUYS,
    app,
    click,
    close_windows_afterwards,
    drop,
    english_computer,
    find,
    find_starting,
    open_app,
    provider_with,
    rows,
    shows,
    texts,
    wait_until,
)

from statement_tracker.core.parser import load_statement
from statement_tracker.gui.formatting import day_text
from statement_tracker.kept_statement import find_kept_statement
from statement_tracker.settings import Settings, TickerChoice

TWO_FUNDS = (
    "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 2000,EUR,1",
    "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,10,EUR 100.00,EUR 1001,EUR,1",
    "2025-01-20T10:00:00.000Z,WXYZ,BUY - MARKET,4,EUR 50.00,EUR 201,EUR,1",
)


def busy(shell) -> bool:
    return shell.session.home.property("busy")


def settled(app, shell) -> None:
    """Wait until the prices are in."""
    wait_until(app, lambda: not busy(shell))


def with_listings(tmp_path: Path, **listings: tuple[str, str]) -> None:
    """Remember a confirmed listing (symbol, name) for each ticker, as an earlier run would have."""
    settings = Settings.load(tmp_path / "settings.json")
    for ticker, (symbol, name) in listings.items():
        settings.ticker_choices[ticker] = TickerChoice(symbol, name, "XETRA", "EUR", confirmed=True)
    settings.save()


def test_home_opens_on_todays_values(app, tmp_path: Path) -> None:
    # Spec K1, K4, K5.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    settled(app, shell)

    assert shows(shell.window, "Your portfolio", "Worth now", "589.31", "EUR")  # 1.47328346 shares at 400
    assert shows(shell.window, "▲ +47.82 (+8.83 %)", "since you bought", "Invested", "541.49")
    assert shows(shell.window, "Today's prices from Yahoo Finance", "Refresh prices")
    eqqb, total = rows(shell.window)
    assert eqqb[:2] == ["Nasdaq fund", "EQQB · XETRA"]
    assert eqqb[2:] == ["541.49", "589.31", "100.0 %", "▲ +47.82 (+8.83 %)"]
    assert total == ["Total", "541.49", "589.31", "100.0 %", "▲ +47.82 (+8.83 %)"]
    for heading in ("Investment", "Invested", "Worth now", "Share of total", "Gain or loss"):
        assert heading in texts(shell.window)


def test_while_prices_come_in_the_amounts_wait_and_a_progress_bar_moves(app, tmp_path: Path) -> None:
    # Spec K4.
    let_go = threading.Event()

    class Slow(FakeProvider):
        """Yahoo taking its time: each price waits until the test lets it go."""

        def quote(self, symbol: str):
            let_go.wait(10)
            return super().quote(symbol)

    provider = Slow()
    provider.add("EQQB.DE", "EUR", price="400", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    shell = open_app(tmp_path, provider, kept=SAMPLE)
    wait_until(app, lambda: shows(shell.window, "current prices"))

    assert busy(shell)
    assert not shows(shell.window, "589.31")
    assert shows(shell.window, "541.49 EUR")  # what was paid is known from the statement already
    assert shell.session.home.property("progressFraction") > 0

    let_go.set()
    settled(app, shell)
    assert shows(shell.window, "589.31")


def test_refresh_prices_fetches_again(app, tmp_path: Path) -> None:
    # Spec K4.
    provider = provider_with("EQQB.DE")
    shell = open_app(tmp_path, provider, kept=SAMPLE)
    settled(app, shell)
    provider.add("EQQB.DE", "EUR", price="500", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")

    click(find(shell.window, "Refresh prices"))
    settled(app, shell)

    assert shows(shell.window, "736.64")  # 1.47328346 shares at 500


def test_totals_leave_out_what_has_no_price_and_say_so(app, tmp_path: Path, english_computer) -> None:
    # Spec K4, B8.
    with_listings(tmp_path, ABCD=("ABCD.DE", "World fund"), WXYZ=("WXYZ.DE", "Bond fund"))
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")  # none for WXYZ.DE
    shell = open_app(tmp_path, provider, kept=write_statement(tmp_path, *TWO_FUNDS))
    settled(app, shell)

    assert shows(shell.window, "Bond fund has no price today, so these totals leave it out.")
    assert rows(shell.window)[-1][:3] == ["Total", "1,001.00", "1,200.00"]  # World fund alone


def test_many_investments_scroll_and_long_names_are_cut_short(app, tmp_path: Path) -> None:
    # Spec K5 (Review Focus 4).
    tickers = [f"T{number:02d}" for number in range(20)]
    with_listings(tmp_path, **{ticker: (f"{ticker}.DE", f"Fund {ticker}") for ticker in tickers})
    settings = Settings.load(tmp_path / "settings.json")
    settings.index_names["T00"] = "A fund with a very long name that goes on and on " * 3
    settings.save()
    provider = FakeProvider()
    for ticker in tickers:
        provider.add(f"{ticker}.DE", "EUR", price="12")
    lines = ["2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 5000,EUR,1"] + [
        f"2025-01-06T10:00:{number:02d}.000Z,{ticker},BUY - MARKET,1,EUR 10.00,EUR 10,EUR,1"
        for number, ticker in enumerate(tickers)
    ]
    shell = open_app(tmp_path, provider, kept=write_statement(tmp_path, *lines))
    height = shell.window.height()
    settled(app, shell)

    assert len(rows(shell.window)) == 21  # twenty investments and the total
    assert shell.window.height() == height
    assert find_starting(shell.window, "A fund with a very long name").property("truncated") is True


LATER_DAY = date(2026, 11, 14)


def newer_statement(tmp_path: Path) -> Path:
    """The sample with one more EQQB buy, on LATER_DAY: 1.57328346 shares in all."""
    folder = tmp_path / "downloads"
    folder.mkdir(exist_ok=True)
    newer = folder / "newer.csv"
    newer.write_text(SAMPLE.read_text(encoding="utf-8").rstrip("\n") + "\n"
                     "2026-11-14T10:00:00.000Z,EQQB,BUY - MARKET,0.1,EUR 380.00,EUR 38.00,EUR,1\n", encoding="utf-8")
    return newer


class Slow(FakeProvider):
    """Yahoo taking its time: each price waits until the test lets it go."""

    def __init__(self) -> None:
        super().__init__()
        self.let_go = threading.Event()

    def quote(self, symbol: str):
        self.let_go.wait(10)
        return super().quote(symbol)


def slow_eqqb() -> Slow:
    provider = Slow()
    provider.add("EQQB.DE", "EUR", price="400", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    return provider


def test_home_says_which_statement_the_values_come_from(app, tmp_path: Path) -> None:
    # Spec K6.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    settled(app, shell)

    latest = max(t.timestamp for t in load_statement(SAMPLE).transactions).astimezone().date()
    assert shows(shell.window, "Your statement", f"Latest transaction {day_text(latest)}. Anything after it isn't included.")
    assert shows(shell.window, "Use a newer statement…", "or drop it on this window")


def test_a_newer_statement_replaces_the_kept_one(app, tmp_path: Path) -> None:
    # Spec K6, F14.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    settled(app, shell)

    drop(shell.window, newer_statement(tmp_path))
    settled(app, shell)

    assert shows(shell.window, f"Latest transaction {day_text(LATER_DAY)}", "629.31")  # 1.57328346 shares at 400
    assert find_kept_statement(tmp_path / "settings.json").latest == LATER_DAY


def test_use_a_newer_statement_asks_for_the_file(app, tmp_path: Path) -> None:
    # Spec K6.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    settled(app, shell)
    newer = newer_statement(tmp_path)
    shell.session.ask_open_file = lambda title, kinds, start: newer

    click(find(shell.window, "Use a newer statement…"))
    settled(app, shell)

    assert shows(shell.window, "629.31")


def test_a_statement_that_does_not_read_keeps_the_one_shown(app, tmp_path: Path) -> None:
    # Spec K6, K12.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    settled(app, shell)

    drop(shell.window, SAMPLES / "unknown_type.csv")
    settled(app, shell)

    assert len(shell.errors) == 1
    assert shows(shell.window, "589.31")
    assert find_kept_statement(tmp_path / "settings.json").latest != LATER_DAY


def test_a_new_statement_during_a_fetch_stops_that_fetch(app, tmp_path: Path) -> None:
    # Spec K6 (Review Focus 1).
    provider = slow_eqqb()
    shell = open_app(tmp_path, provider, kept=SAMPLE)
    wait_until(app, lambda: shows(shell.window, "current prices"))

    drop(shell.window, newer_statement(tmp_path))
    provider.let_go.set()
    settled(app, shell)

    assert shows(shell.window, "629.31") and not shows(shell.window, "589.31")
    assert shell.errors == []


def test_closing_the_window_during_a_fetch_saves_nothing(app, tmp_path: Path) -> None:
    # Spec K6 (Review Focus 1).
    provider = slow_eqqb()
    shell = open_app(tmp_path, provider, kept=SAMPLE)
    wait_until(app, lambda: shows(shell.window, "current prices"))

    shell.close()
    provider.let_go.set()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:  # time for the stopped run to end, and for anything it might do
        app.processEvents()
        time.sleep(0.01)

    assert not (tmp_path / "last_prices.json").exists()
    assert Settings.load(tmp_path / "settings.json").ticker_choices == {}
