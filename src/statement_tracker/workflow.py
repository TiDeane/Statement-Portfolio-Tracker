"""The whole pipeline without any user interface: load, calculate, find symbols, price, value.

The command line and the windows both call this, so no screen is ever required.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from statement_tracker.core.calculator import buys_by_ticker, compute_portfolio, value_portfolio
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.core.exporters.excel import ExcelExporter
from statement_tracker.core.market_data.pricing import RateBook, exchange_pair, price_in_currency
from statement_tracker.core.market_data.provider import PriceProvider, PriceUnavailableError, Quote, SymbolInfo
from statement_tracker.core.models import HoldingValuation, MarketPrice, Portfolio, PortfolioValuation, Statement
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
    lookups: Lookups | None = field(default=None, repr=False, compare=False)
    """What was fetched, so that ``with_entered_prices`` can work the report out again."""


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
    entered_prices: Mapping[str, Decimal] | None = None,
) -> Report:
    """Load a statement and value its open positions at current prices.

    Ticker choices come, in this order, from ``symbol_overrides`` (the user said
    so explicitly), the saved settings, automatic matching, and ``chooser``.
    New choices are saved. A ticker without a symbol or a price is reported as
    unavailable with the reason; it is never estimated.

    Every price fetched is kept in ``price_cache`` (by default the one next to
    the settings file). When a price cannot be fetched, the one kept from an
    earlier run is used instead, marked as last known, and a note says from when.

    ``entered_prices`` (ticker -> price per share in the statement currency) are
    prices the user typed in. They are kept like those given to ``with_entered_prices``:
    used, ahead of last known prices, whenever Yahoo has no price for the ticker, and
    dropped as soon as Yahoo has one.

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

    # Notes are kept per ticker and put together in statement order at the end, so they read
    # the same however the prices arrive.
    ticker_notes: dict[str, list[str]] = {position.ticker: [] for position in portfolio.open_positions}
    unavailable: dict[str, str] = {}
    """Tickers left without a listing, with the reason."""
    settings_changed = False

    positions = portfolio.open_positions
    steps = price_steps(len(positions))
    if positions:
        report_progress(0, steps, "Getting ready to look up prices...")
        provider.prepare()

    # 1. Decide each ticker's listing, one by one: this may ask the user.
    decided: dict[str, tuple[str, bool]] = {}
    """Ticker -> (Yahoo symbol, whether the user chose it)."""
    failed: dict[str, PriceUnavailableError] = {}
    """Tickers whose listing could not be decided because Yahoo could not be reached."""
    for position in positions:
        ticker = position.ticker
        notes = ticker_notes[ticker]
        saved = settings.ticker_choices.get(ticker)
        # The user asked to choose this listing again: show the choice even if matching is sure.
        asking_again = ticker in settings.ask_again and ticker not in overrides and chooser is not None
        symbol: str | None = overrides.get(ticker) or (saved.symbol if saved and not asking_again else None)
        user_chose = ticker in overrides

        try:
            if symbol is None:
                report_progress(0, steps, f"Finding the stock exchange listing of {ticker}...")
                resolution = resolve_ticker(
                    ticker, buys.get(ticker, []), statement.currency, provider, settings.suffixes
                )
                if resolution.best is not None and not asking_again:
                    symbol = resolution.best.info.symbol
                    notes.append(f"{ticker} was matched to {_describe(resolution.best.info)}.")
                elif resolution.candidates and settings.always_use_first_listing and not asking_again:
                    first = resolution.candidates[0]
                    symbol = first.info.symbol
                    if first.is_match:
                        notes.append(
                            f"{ticker}: more than one listing fits, so the first one was used, as you asked: "
                            f"{_describe(first.info)}. Another can be chosen in Settings."
                        )
                    else:
                        # Not checked against the purchases: said plainly, so the user can look at it.
                        notes.append(
                            f"{ticker}: no listing could be matched to your purchases, so the first one found was "
                            f"used, as you asked: {_describe(first.info)}. Check that it is your fund; another "
                            "can be chosen in Settings."
                        )
                elif chooser is not None:
                    symbol = chooser(resolution)
                    user_chose = symbol is not None
                if asking_again:
                    # Asked once; skipping keeps the listing used before.
                    settings.ask_again.discard(ticker)
                    settings_changed = True
                    if symbol is None and saved is not None:
                        symbol = saved.symbol
                if symbol is None:
                    unavailable[ticker] = _needs_choice_reason(resolution)
                    continue
        except PriceUnavailableError as exc:
            failed[ticker] = exc
            continue
        decided[ticker] = (symbol, user_chose)

    # 2. Fetch every price at the same time, then each exchange rate needed, once.
    def prices_progress(done: int, total: int) -> None:
        # The bar goes from "getting ready" (step 0) to all prices in (the last step).
        report_progress(1 + done * (steps - 1) // total, steps, f"Getting the current prices ({done} of {total})...")

    quotes = _fetch_quotes(provider, {symbol for symbol, _ in decided.values()}, prices_progress)
    rates = _fetch_rates(provider, quotes.values(), statement.currency)

    # Prices typed in on the command line: kept like the ones typed in the window.
    held = {position.ticker for position in positions}
    entered_now = set()
    general_notes = list(portfolio.warnings)
    for ticker, price in (entered_prices or {}).items():
        if ticker in held:
            cache.enter(ticker, price, statement.currency, now)
            entered_now.add(ticker)
        else:
            general_notes.append(
                f"{ticker} is not an investment you still hold, so the price entered for it was not used."
            )

    # 3. Use them in statement order, exactly as one ticker at a time would.
    report_progress(steps, steps, "Adding everything up...")
    lookups = Lookups(
        statement,
        portfolio,
        decided,
        failed,
        unavailable,
        quotes,
        rates,
        {ticker: tuple(notes) for ticker, notes in ticker_notes.items()},
        tuple(general_notes),
    )
    report, remembered = _assemble(lookups, settings, cache, now, entered_now)
    if settings_changed or remembered:
        settings.save()
    cache.save()
    return report


def needs_price(holding: HoldingValuation) -> bool:
    """True if the user may type in a price for this holding: Yahoo had no current price for it."""
    return holding.price is None or holding.price.last_known or holding.price.entered


def with_entered_prices(
    report: Report,
    entered: Mapping[str, Decimal],
    settings: Settings,
    *,
    now: datetime | None = None,
    price_cache: PriceCache | None = None,
) -> Report:
    """Value ``report`` again with prices per share the user typed in, without contacting Yahoo.

    The prices (ticker -> price in the statement currency) are kept for later runs, and are
    used whenever Yahoo has no price for that investment, until it has one again.
    """
    if report.lookups is None:
        raise ValueError("This report was not made by build_report, so it cannot be worked out again.")
    now = now or datetime.now(UTC)
    cache = price_cache if price_cache is not None else PriceCache.beside(settings.path)
    currency = report.statement.currency
    for ticker, price in entered.items():
        cache.enter(ticker, price, currency, now)
    new_report, remembered = _assemble(report.lookups, settings, cache, now, set(entered))
    if remembered:
        settings.save()
    cache.save()
    return new_report


@dataclass(frozen=True)
class Lookups:
    """What a run found out from Yahoo, kept so that its report can be worked out again without it."""

    statement: Statement
    portfolio: Portfolio
    decided: Mapping[str, tuple[str, bool]]
    """Ticker -> (Yahoo symbol, whether the user chose it)."""
    failed: Mapping[str, PriceUnavailableError]
    """Tickers whose listing could not be decided because Yahoo could not be reached."""
    unmatched: Mapping[str, str]
    """Tickers left without a listing, with the reason."""
    quotes: Mapping[str, Quote | PriceUnavailableError]
    rates: RateBook
    matching_notes: Mapping[str, tuple[str, ...]]
    """Notes from deciding each ticker's listing."""
    general_notes: tuple[str, ...]


def _day(price: MarketPrice) -> str:
    """The local date a price was typed in on."""
    return price.as_of.astimezone().date().isoformat() if price.as_of else "an earlier day"


def _assemble(
    lookups: Lookups, settings: Settings, cache: PriceCache, now: datetime, entered_now: set[str]
) -> tuple[Report, bool]:
    """Turn what was fetched into prices and notes, in statement order. Returns the report and
    whether the settings changed. ``entered_now`` are the tickers whose price was typed in just now."""
    statement, portfolio = lookups.statement, lookups.portfolio
    currency = statement.currency
    prices: dict[str, MarketPrice] = {}
    unavailable: dict[str, str] = {}
    ticker_notes: dict[str, list[str]] = {}
    settings_changed = False

    for position in portfolio.open_positions:
        ticker = position.ticker
        notes = ticker_notes[ticker] = list(lookups.matching_notes.get(ticker, ()))
        saved = settings.ticker_choices.get(ticker)
        symbol, user_chose = lookups.decided.get(ticker, (None, False))
        entered = cache.entered(ticker, currency)
        if entered is not None:
            entered = replace(entered, symbol=symbol or "")

        if ticker in lookups.unmatched:
            if entered is not None:
                prices[ticker] = entered
                notes.append(
                    f"{ticker}: no Yahoo listing is used for it, so the price you entered on {_day(entered)} is used."
                )
            else:
                unavailable[ticker] = lookups.unmatched[ticker]
            continue
        try:
            if ticker in lookups.failed:
                raise lookups.failed[ticker]
            outcome = lookups.quotes[symbol]
            if isinstance(outcome, PriceUnavailableError):
                raise outcome
            quote = outcome
            price = price_in_currency(quote, currency, lookups.rates)
        except PriceUnavailableError as exc:
            # A price typed in is newer than the last one fetched: fetching one drops it.
            if entered is not None:
                prices[ticker] = entered
                notes.append(f"{ticker}: {exc} The price you entered on {_day(entered)} is used instead.")
                continue
            last_known = cache.last_known(symbol, currency) if symbol else None
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
        cache.remember(price, currency, now)
        if entered is not None:
            cache.forget_entered(ticker)
            if ticker in entered_now:
                notes.append(
                    f"{ticker}: Yahoo has a current price for {symbol}, so it is used instead of the price you entered."
                )
        if price.as_of is not None and now - price.as_of > STALE_PRICE_AGE:
            notes.append(
                f"{ticker}: the latest price Yahoo has for {symbol} is from {price.as_of.date().isoformat()}, "
                "so the current value may be out of date."
            )
        if price.converted:
            notes.append(
                f"{ticker}: the price is quoted in {price.quoted_currency} and was converted to "
                f"{currency} at the current exchange rate."
            )
        if saved is None or saved.symbol != symbol or (user_chose and not saved.confirmed):
            choice = TickerChoice(
                symbol, quote.info.name, quote.info.exchange, quote.info.currency, confirmed=user_chose
            )
            settings_changed |= settings.remember(ticker, choice)

    notes = list(lookups.general_notes)
    for position in portfolio.open_positions:
        notes.extend(ticker_notes[position.ticker])
    for ticker, reason in unavailable.items():
        notes.append(f"{ticker}: current value unavailable. {reason}")
    valuation = value_portfolio(portfolio, prices, unavailable)
    return Report(statement, valuation, tuple(notes), lookups), settings_changed


FETCH_WORKERS = 4
"""Prices fetched at the same time. Enough to hide each request's wait, few enough to stay polite to Yahoo."""


def _fetch_quotes(
    provider: PriceProvider, symbols: set[str], progress: Callable[[int, int], None]
) -> dict[str, Quote | PriceUnavailableError]:
    """Fetch the latest price of every symbol at the same time. A failure is kept, not raised.

    ``progress`` is called on this thread, not the workers', with (done, total) as each one arrives.
    """
    results: dict[str, Quote | PriceUnavailableError] = {}
    if not symbols:
        return results
    progress(0, len(symbols))
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(provider.quote, symbol): symbol for symbol in sorted(symbols)}
        for done, future in enumerate(as_completed(futures), start=1):
            try:
                results[futures[future]] = future.result()
            except PriceUnavailableError as exc:
                results[futures[future]] = exc
            progress(done, len(symbols))
    return results


def _fetch_rates(
    provider: PriceProvider, quotes: Iterable[Quote | PriceUnavailableError], target_currency: str
) -> RateBook:
    """Fetch, at the same time and once each, the exchange rates needed to express the quotes in ``target_currency``."""
    pairs = {
        pair
        for quote in quotes
        if isinstance(quote, Quote) and (pair := exchange_pair(quote, target_currency)) is not None
    }
    return RateBook(_fetch_quotes(provider, pairs, lambda done, total: None))
