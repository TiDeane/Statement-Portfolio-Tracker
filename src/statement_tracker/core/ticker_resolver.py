"""Finding the Yahoo symbol for a statement ticker. No mappings are shipped.

Statement tickers are base symbols (``ABCD``); Yahoo usually needs an exchange
suffix (``ABCD.DE``). Each candidate listing is checked against the user's own
BUY rows: the price paid must fall inside the listing's low-high range on the
trade date. One listing that fits is "confident", several are "ambiguous" (the
user picks), none is "unresolved" (the user searches or types a symbol).
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from statement_tracker.core.market_data.pricing import to_major_units
from statement_tracker.core.market_data.provider import (
    DailyRange,
    PriceProvider,
    PriceUnavailableError,
    SymbolHistory,
    SymbolInfo,
    SymbolNotFoundError,
)
from statement_tracker.core.models import Transaction

DEFAULT_SUFFIXES: tuple[str, ...] = (".DE", ".L", ".AS", ".MI", ".PA")
DEFAULT_TOLERANCE = Decimal("0.01")
"""The statement price is rounded and the broker's venue may differ slightly from Yahoo's listing."""
MAX_BUYS_CHECKED = 5
NEAREST_DAY_WINDOW = 7
"""How many days away a trading day may be when the trade date itself has no market data."""
CHECK_WORKERS = 4
"""Candidate listings checked at the same time."""


class Confidence(Enum):
    """How sure the resolver is about a ticker's Yahoo symbol."""

    CONFIDENT = "confident"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Candidate:
    """One Yahoo listing that might be the statement ticker."""

    info: SymbolInfo
    matched: int
    checked: int
    comparable: bool
    """False if the listing is quoted in another currency, so prices could not be compared."""

    @property
    def is_match(self) -> bool:
        """True if most of the checked BUY prices fit this listing's history."""
        return self.comparable and self.checked > 0 and self.matched * 2 > self.checked


@dataclass(frozen=True)
class Resolution:
    """The outcome for one ticker. Candidates are ordered best first."""

    ticker: str
    confidence: Confidence
    candidates: tuple[Candidate, ...]

    @property
    def best(self) -> Candidate | None:
        """The single fitting listing, when there is exactly one."""
        return self.candidates[0] if self.confidence is Confidence.CONFIDENT else None


def candidate_symbols(
    ticker: str, suffixes: Sequence[str], provider: PriceProvider
) -> dict[str, SymbolInfo | None]:
    """Return candidate Yahoo symbols in the order to try them: bare, suffixed, then search hits.

    The value is what the provider's search said about the symbol, or None for a
    symbol that is only a guess (bare or suffixed) and may not exist at all.
    """
    candidates: dict[str, SymbolInfo | None] = {ticker: None}
    for suffix in suffixes:
        candidates.setdefault(f"{ticker}{suffix}", None)
    try:
        found = provider.search(ticker)
    except PriceUnavailableError:
        found = ()  # search only adds candidates; the suffix list still works without it
    for info in found:
        if info.symbol.split(".")[0].upper() == ticker.upper():
            # Search knows the fund name even where the price history does not.
            candidates[info.symbol] = info
    return candidates


def trade_day(timestamp: datetime, timezone: str | None) -> date:
    """Return the exchange-local date of a statement timestamp (statements are in UTC)."""
    if timezone:
        try:
            return timestamp.astimezone(ZoneInfo(timezone)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timestamp.astimezone(UTC).date()


def price_fits(price: Decimal, day: date, ranges: Sequence[DailyRange], tolerance: Decimal) -> bool:
    """True if ``price`` is inside the low-high range of ``day`` or, on a non-trading day, of the nearest trading day."""
    if not ranges:
        return False
    nearest = min(abs((item.day - day).days) for item in ranges)
    if nearest > NEAREST_DAY_WINDOW:
        return False
    return any(
        item.low * (1 - tolerance) <= price <= item.high * (1 + tolerance)
        for item in ranges
        if abs((item.day - day).days) == nearest
    )


def resolve_ticker(
    ticker: str,
    buys: Sequence[Transaction],
    statement_currency: str,
    provider: PriceProvider,
    suffixes: Sequence[str] = DEFAULT_SUFFIXES,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> Resolution:
    """Classify a ticker as confident, ambiguous or unresolved from its BUY rows.

    Raises PriceUnavailableError if the provider cannot be reached, because
    then nothing can be said about the ticker.
    """
    evidence = [buy for buy in buys if buy.price_per_share is not None][-MAX_BUYS_CHECKED:]
    candidates: list[Candidate] = []
    if evidence:
        days = [buy.timestamp.astimezone(UTC).date() for buy in evidence]
        start = min(days) - timedelta(days=NEAREST_DAY_WINDOW + 1)
        end = max(days) + timedelta(days=NEAREST_DAY_WINDOW + 1)

        def check(symbol: str, searched: SymbolInfo | None) -> Candidate | None:
            """How well one listing fits the purchases; None if it is not a listing at all."""
            try:
                history = provider.history(symbol, start, end)
            except SymbolNotFoundError:
                if searched is None:
                    return None
                # Search says the listing exists, but it has no prices around the purchases
                # (rarely traded listings have gaps). Keep it as an option for the user.
                try:
                    history = SymbolHistory(provider.quote(symbol).info, ())
                except PriceUnavailableError:
                    return None
            info = history.info
            if searched is not None:
                info = replace(
                    info, name=info.name or searched.name, exchange=info.exchange or searched.exchange
                )
            comparable = bool(info.currency) and to_major_units(Decimal(1), info.currency)[1] == statement_currency
            matched = 0
            if comparable:
                ranges = [
                    DailyRange(
                        item.day,
                        to_major_units(item.low, info.currency)[0],
                        to_major_units(item.high, info.currency)[0],
                    )
                    for item in history.ranges
                ]
                matched = sum(
                    price_fits(buy.price_per_share, trade_day(buy.timestamp, info.timezone), ranges, tolerance)
                    for buy in evidence
                    if buy.price_per_share is not None
                )
            return Candidate(info, matched, len(evidence), comparable)

        # The listings are checked at the same time; their answers are used in the usual order.
        listings = list(candidate_symbols(ticker, suffixes, provider).items())
        with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
            checked = list(pool.map(lambda listing: check(*listing), listings))
        candidates = [candidate for candidate in checked if candidate is not None]

    # Best first: listings that fit, then same-currency listings, then other currencies.
    candidates.sort(key=lambda item: (not item.is_match, not item.comparable, -item.matched))
    fitting = sum(item.is_match for item in candidates)
    if fitting == 1:
        confidence = Confidence.CONFIDENT
    elif fitting > 1:
        confidence = Confidence.AMBIGUOUS
    else:
        confidence = Confidence.UNRESOLVED
    return Resolution(ticker, confidence, tuple(candidates))
