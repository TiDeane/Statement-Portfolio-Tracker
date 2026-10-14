"""The whole pipeline without any user interface: load, calculate, find symbols, price, value.

The command line and the windows both call this, so no screen is ever required.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from statement_tracker.core.calculator import buys_by_ticker, compute_portfolio, value_portfolio
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.core.exporters.excel import ExcelExporter
from statement_tracker.core.market_data.pricing import price_in_currency
from statement_tracker.core.market_data.provider import PriceProvider, PriceUnavailableError, SymbolInfo
from statement_tracker.core.models import MarketPrice, PortfolioValuation, Statement
from statement_tracker.core.parser import load_statement
from statement_tracker.core.ticker_resolver import Confidence, Resolution, resolve_ticker
from statement_tracker.price_cache import PriceCache
from statement_tracker.settings import Settings, TickerChoice

STALE_PRICE_AGE = timedelta(days=5)
"""A latest price older than this (longer than a holiday weekend) is pointed out to the user."""

Progress = Callable[[int, int, str], None]
"""Told how far the work is: steps done, steps in total (0 while unknown), and a short description."""

Chooser = Callable[[Resolution], str | None]
"""Asks the user which listing a ticker is. Returns a Yahoo symbol, or None to leave it open."""


@dataclass(frozen=True)
class Report:
    """A valued portfolio plus the plain-language notes the user should see."""

    statement: Statement
    valuation: PortfolioValuation
    notes: tuple[str, ...]


def price_steps(holdings: int) -> int:
    """Progress steps for pricing ``holdings`` investments: getting ready, then one per investment."""
    return holdings + 1 if holdings else 0


def display_name(settings: Settings, ticker: str) -> str:
    """Return "(TICKER) Name" when a name is known for the ticker, else the ticker alone."""
    name = settings.index_name(ticker)
    return f"({ticker}) {name}" if name else ticker


def update_spreadsheet(report: Report, settings: Settings, path: Path, today: date) -> ExportResult:
    """Write the report to the Excel workbook at ``path`` and remember that workbook."""
    names = {}
    for holding in report.valuation.holdings:
        name = settings.index_name(holding.position.ticker)
        if name:
            names[holding.position.ticker] = name
    exporter = ExcelExporter(path, settings.holdings_sheet, settings.history_sheet, names)
    result = exporter.export(report.valuation, today)
    if settings.spreadsheet_path != path:
        settings.spreadsheet_path = path
        settings.save()
    return result


def _describe(info: SymbolInfo) -> str:
    parts = [part for part in (info.name, info.exchange, info.currency) if part]
    return f"{info.symbol} ({', '.join(parts)})" if parts else info.symbol


def _needs_choice_reason(resolution: Resolution) -> str:
    symbols = ", ".join(candidate.info.symbol for candidate in resolution.candidates) or "none found"
    if resolution.confidence is Confidence.AMBIGUOUS:
        return f"More than one listing fits {resolution.ticker}; one has to be chosen (candidates: {symbols})."
    return f"No listing could be matched to {resolution.ticker} automatically (candidates: {symbols})."


def build_report(
    statement_path: Path,
    provider: PriceProvider,
    settings: Settings,
    *,
    chooser: Chooser | None = None,
    symbol_overrides: Mapping[str, str] | None = None,
    ignore_unknown_types: bool = False,
    now: datetime | None = None,
    progress: Progress | None = None,
    price_cache: PriceCache | None = None,
) -> Report:
    """Load a statement and value its open positions at current prices.

    Ticker choices come, in this order, from ``symbol_overrides`` (the user said
    so explicitly), the saved settings, automatic matching, and ``chooser``.
    New choices are saved. A ticker without a symbol or a price is reported as
    unavailable with the reason; it is never estimated.

    Every price fetched is kept in ``price_cache`` (by default the one next to
    the settings file). When a price cannot be fetched, the one kept from an
    earlier run is used instead, marked as last known, and a note says from when.

    ``progress`` is called as work advances with (steps done, steps in total,
    what is happening now). The total is 0 until the statement has been read.
    """
    report_progress = progress or (lambda done, total, text: None)
    report_progress(0, 0, "Reading your statement...")
    statement = load_statement(statement_path)
    portfolio = compute_portfolio(statement, ignore_unknown_types=ignore_unknown_types)
    buys = buys_by_ticker(statement)
    overrides = dict(symbol_overrides or {})
    now = now or datetime.now(UTC)
    cache = price_cache if price_cache is not None else PriceCache.beside(settings.path)

    notes: list[str] = list(portfolio.warnings)
    prices: dict[str, MarketPrice] = {}
    unavailable: dict[str, str] = {}
    settings_changed = False

    positions = portfolio.open_positions
    steps = price_steps(len(positions))
    if positions:
        # Loading the price library takes seconds on a cold start: its own step, so the bar does not stall.
        report_progress(0, steps, "Getting ready to look up prices...")
        provider.prepare()
    for number, position in enumerate(positions):
        ticker = position.ticker
        report_progress(
            number + 1, steps, f"Getting the current price of {ticker} ({number + 1} of {len(positions)})..."
        )
        saved = settings.ticker_choices.get(ticker)
        symbol: str | None = overrides.get(ticker) or (saved.symbol if saved else None)
        user_chose = ticker in overrides

        try:
            if symbol is None:
                resolution = resolve_ticker(
                    ticker, buys.get(ticker, []), statement.currency, provider, settings.suffixes
                )
                if resolution.best is not None:
                    symbol = resolution.best.info.symbol
                    notes.append(f"{ticker} was matched to {_describe(resolution.best.info)}.")
                elif chooser is not None:
                    symbol = chooser(resolution)
                    user_chose = symbol is not None
                if symbol is None:
                    unavailable[ticker] = _needs_choice_reason(resolution)
                    continue

            quote = provider.quote(symbol)
            price = price_in_currency(quote, statement.currency, provider)
        except PriceUnavailableError as exc:
            last_known = cache.last_known(symbol, statement.currency) if symbol else None
            if last_known is None:
                unavailable[ticker] = str(exc)
                continue
            prices[ticker] = last_known
            day = last_known.as_of.date().isoformat() if last_known.as_of else "an earlier day"
            notes.append(
                f"{ticker}: {exc} The last price fetched for {symbol}, from {day}, is used instead, "
                "so this value and the totals are not up to date."
            )
            continue

        prices[ticker] = price
        cache.remember(price, statement.currency, now)
        if price.as_of is not None and now - price.as_of > STALE_PRICE_AGE:
            notes.append(
                f"{ticker}: the latest price Yahoo has for {symbol} is from {price.as_of.date().isoformat()}, "
                "so the current value may be out of date."
            )
        if price.converted:
            notes.append(
                f"{ticker}: the price is quoted in {price.quoted_currency} and was converted to "
                f"{statement.currency} at the current exchange rate."
            )
        if saved is None or saved.symbol != symbol or (user_chose and not saved.confirmed):
            choice = TickerChoice(
                symbol, quote.info.name, quote.info.exchange, quote.info.currency, confirmed=user_chose
            )
            settings_changed |= settings.remember(ticker, choice)

    report_progress(steps, steps, "Adding everything up...")
    if settings_changed:
        settings.save()
    cache.save()
    for ticker, reason in unavailable.items():
        notes.append(f"{ticker}: current value unavailable. {reason}")
    return Report(statement, value_portfolio(portfolio, prices, unavailable), tuple(notes))
