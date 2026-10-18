"""Fifty believable statements, made at random from fixed seeds, checked against the rules every
statement must follow. Rule numbers refer to tests/SPECIFICATION.md. No network.

Each test goes through all its statements: they test one behaviour against many patterns of rows, so
they count as one test. A failure lists every statement that broke a rule, by its seed; a seed gives
the same statement every time, so ``random_statement(seed)`` in tests/fakes.py repeats it. Fifty is
enough: by then every kind of row and sequence of rows the generator makes has come up many times.
"""

import random
from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fakes import HEADER, computed, random_statement

from statement_tracker.core.calculator import compute_portfolio, value_portfolio
from statement_tracker.core.exporters.excel import ExcelExporter
from statement_tracker.core.models import MarketPrice
from statement_tracker.core.parser import load_statement

SEEDS = range(50)
CLOSE = Decimal("0.000001")
"""Close enough: the app and the plain replay may round the last of 28 digits differently."""


def write(folder: Path, lines: list[str], name: str = "statement.csv") -> Path:
    path = folder / name
    path.write_text("\n".join((HEADER, *lines)) + "\n", encoding="utf-8")
    return path


def close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= CLOSE


def for_each_statement(tmp_path: Path, seeds: Iterable[int], check: Callable[[Path, int], None]) -> None:
    """Run ``check`` on the statement of each seed, each in its own folder, and fail naming every seed that broke a rule."""
    broken = []
    for seed in seeds:
        folder = tmp_path / f"seed{seed}"
        folder.mkdir()
        try:
            check(folder, seed)
        except AssertionError as problem:
            broken.append(f"seed {seed}: {str(problem).splitlines()[0] if str(problem) else 'assertion failed'}")
        except Exception as problem:  # the app stopped on it: say on which statement, and how
            broken.append(f"seed {seed}: {type(problem).__name__}: {str(problem).splitlines()[0]}")
    assert not broken, f"{len(broken)} of {len(list(seeds))} statements broke a rule:\n" + "\n".join(broken)


def prices_for(seed: int, tickers: list[str]) -> dict[str, MarketPrice]:
    """Today's prices for some of the tickers, chosen by the seed: the others have none."""
    rng = random.Random(seed)
    priced = [ticker for ticker in tickers if rng.random() < 0.8]
    return {ticker: MarketPrice(Decimal(rng.randint(100, 90000)) / 100, f"{ticker}.DE", "EUR") for ticker in priced}


def adds_up_as_the_rules_say(folder: Path, seed: int) -> None:
    lines, expected = random_statement(seed)

    portfolio = compute_portfolio(load_statement(write(folder, lines)))

    assert portfolio.net_deposits == expected.deposits, "net deposits"
    assert close(portfolio.cash, expected.cash), "cash"
    held = {position.ticker: position for position in portfolio.open_positions}
    assert set(held) == set(expected.held), "what is listed"  # B3, B4: sold-out investments are not
    for ticker, position in held.items():
        assert position.shares == expected.shares[ticker], f"{ticker} shares"
        assert close(position.cost_basis, expected.cost_basis[ticker]), f"{ticker} cost basis"
        assert close(position.average_cost, expected.cost_basis[ticker] / expected.shares[ticker]), f"{ticker} average"
    every = {position.ticker: position for position in (*portfolio.open_positions, *portfolio.closed_positions)}
    for ticker in expected.shares:
        assert close(every[ticker].realized_pnl, expected.realized.get(ticker, Decimal(0))), f"{ticker} realized"
    assert close(portfolio.realized_pnl, sum(expected.realized.values(), Decimal(0))), "realized in all"
    assert portfolio.dividends_by_ticker == {t: amount for t, amount in expected.dividends.items() if amount}, "dividends"
    assert portfolio.total_dividends == sum(expected.dividends.values(), Decimal(0)), "dividends in all"
    assert abs(portfolio.reconciliation_difference) <= CLOSE, "the self-check"  # B9
    assert not any("do not add up" in warning for warning in portfolio.warnings), "a warning that it does not add up"


def does_not_depend_on_the_order_of_the_rows(folder: Path, seed: int) -> None:
    lines, _ = random_statement(seed)
    shuffled = list(lines)
    random.Random(seed).shuffle(shuffled)

    in_order = compute_portfolio(load_statement(write(folder, lines, "in_order.csv")))
    mixed = compute_portfolio(load_statement(write(folder, shuffled, "shuffled.csv")))

    assert mixed.open_positions == in_order.open_positions, "what is held"
    assert (mixed.cash, mixed.realized_pnl, mixed.total_dividends) == (
        in_order.cash, in_order.realized_pnl, in_order.total_dividends,
    ), "cash, realized gain or dividends"  # fmt: skip


def totals_cover_exactly_what_has_a_value(folder: Path, seed: int) -> None:
    lines, expected = random_statement(seed)
    portfolio = compute_portfolio(load_statement(write(folder, lines)))
    prices = prices_for(seed, expected.held)

    valuation = value_portfolio(portfolio, prices)

    valued = [holding for holding in valuation.holdings if holding.position.ticker in prices]
    left_out = [holding for holding in valuation.holdings if holding.position.ticker not in prices]
    for holding in valued:
        assert holding.market_value == holding.position.shares * prices[holding.position.ticker].price, "a value"
    if not valued:
        assert valuation.total_market_value is None and valuation.net_worth is None, "unavailable, not zero"
        return
    assert all(holding.market_value is None and not holding.in_totals for holding in left_out), "left out"
    total = sum((holding.market_value for holding in valued), Decimal(0))
    invested = sum((holding.position.cost_basis for holding in valued), Decimal(0))
    assert valuation.total_market_value == total, "the total value"
    assert close(valuation.invested_in_totals, invested), "the total invested"
    assert close(sum((holding.allocation_percent for holding in valued), Decimal(0)), Decimal(100)), "% of worth"
    assert close(sum((holding.invested_percent for holding in valued), Decimal(0)), Decimal(100)), "% of invested"
    assert valuation.net_worth == total + portfolio.cash, "net worth"  # nothing estimated for what has no value
    assert valuation.gain_vs_deposits == valuation.net_worth - portfolio.net_deposits, "gain vs deposits"


def spreadsheet_shows_what_the_app_shows(folder: Path, seed: int) -> None:
    lines, expected = random_statement(seed)
    portfolio = compute_portfolio(load_statement(write(folder, lines)))
    valuation = value_portfolio(portfolio, prices_for(seed, expected.held))
    path = folder / "portfolio.xlsx"

    ExcelExporter(path).export(valuation, date(2026, 10, 12))

    def same(shown: object, figure: Decimal, what: str, within: float = 1e-6) -> None:
        assert shown == pytest.approx(float(figure), abs=within), what

    holdings = computed(path, "Current Holdings")
    by_name = {row[0]: row for row in holdings[1:]}
    assert len(holdings) == len(valuation.holdings) + 2, "rows"  # header, one row each, Total
    for holding in valuation.holdings:
        row, ticker = by_name[holding.position.ticker], holding.position.ticker
        same(row[1], holding.position.cost_basis, f"{ticker} invested")
        if holding.market_value is None:
            assert row[3] == "unavailable", f"{ticker} current value"
        else:
            same(row[3], holding.market_value, f"{ticker} current value")
            same(row[4], holding.allocation_percent / 100, f"{ticker} % of current value", 1e-9)
    total = by_name["Total"]
    if valuation.total_market_value is None:
        assert total[3] == "unavailable", "the Total"
        return
    same(total[1], valuation.invested_in_totals, "Total invested")
    same(total[3], valuation.total_market_value, "Total current value")
    history = computed(path, "Portfolio History")[1]
    # cost basis, market value, unrealized, realized, ROI %, net worth, net deposits, gain vs deposits
    same(history[2], valuation.total_market_value, "history: market value")
    same(history[4], portfolio.realized_pnl, "history: realized")
    same(history[6], valuation.net_worth, "history: net worth")
    same(history[7], portfolio.net_deposits, "history: net deposits")
    same(history[8], valuation.gain_vs_deposits, "history: gain vs deposits")
    same(history[5], valuation.gain_vs_deposits / portfolio.net_deposits, "history: ROI %", 1e-9)


def test_every_statement_adds_up_as_the_rules_say(tmp_path: Path) -> None:
    # Spec A1-A4, B1-B7, B9.
    for_each_statement(tmp_path, SEEDS, adds_up_as_the_rules_say)


def test_the_order_of_the_rows_in_the_file_does_not_matter(tmp_path: Path) -> None:
    # Spec A4.
    for_each_statement(tmp_path, SEEDS[::5], does_not_depend_on_the_order_of_the_rows)


def test_totals_and_shares_cover_exactly_what_has_a_value(tmp_path: Path) -> None:
    # Spec B7, B8.
    for_each_statement(tmp_path, SEEDS[::2], totals_cover_exactly_what_has_a_value)


def test_the_spreadsheet_shows_the_same_figures_as_the_app(tmp_path: Path) -> None:
    # Spec H3, H4: what Excel works out from the sheets matches the app's own figures.
    for_each_statement(tmp_path, SEEDS[::5], spreadsheet_shows_what_the_app_shows)
