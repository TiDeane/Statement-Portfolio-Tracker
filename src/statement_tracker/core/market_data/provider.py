"""The interface every market data source implements."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


class PriceUnavailableError(Exception):
    """The data could not be fetched right now (no connection, rate limit, provider change)."""


class SymbolNotFoundError(PriceUnavailableError):
    """The provider answered, and it has no such symbol."""


@dataclass(frozen=True)
class SymbolInfo:
    """What a provider knows about one listing."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    timezone: str | None = None
    isin: str | None = None


@dataclass(frozen=True)
class Quote:
    """The latest price of a listing, in the currency the provider quotes it in."""

    info: SymbolInfo
    price: Decimal
    currency: str
    as_of: datetime | None = None


@dataclass(frozen=True)
class DailyRange:
    """Lowest and highest traded price on one trading day (exchange-local date)."""

    day: date
    low: Decimal
    high: Decimal


@dataclass(frozen=True)
class SymbolHistory:
    """Daily ranges of a listing over a period, with what is known about the listing."""

    info: SymbolInfo
    ranges: tuple[DailyRange, ...]


class PriceProvider(Protocol):
    """A source of prices. Implementations raise PriceUnavailableError, never return guesses."""

    def quote(self, symbol: str) -> Quote:
        """Return the latest price of ``symbol``."""
        ...

    def history(self, symbol: str, start: date, end: date) -> SymbolHistory:
        """Return daily low/high ranges for ``start`` to ``end`` inclusive, not adjusted for dividends."""
        ...

    def search(self, query: str) -> Sequence[SymbolInfo]:
        """Return listings matching a ticker or name. Empty if search is not supported."""
        ...
