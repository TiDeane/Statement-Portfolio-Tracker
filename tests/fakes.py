"""Test doubles and builders. Nothing here touches the network."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from statement_tracker.core.market_data.provider import (
    DailyRange,
    PriceUnavailableError,
    Quote,
    SymbolHistory,
    SymbolInfo,
    SymbolNotFoundError,
)
from statement_tracker.core.models import Statement, Transaction
from statement_tracker.core.parser import parse_rows

HEADER = "Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate"
SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "revolut_sample.csv"


def statement_from(*lines: str, header: str = HEADER) -> Statement:
    """Parse statement rows given as CSV lines (the header is added)."""
    rows = [(number, line.split(",")) for number, line in enumerate((header, *lines), start=1)]
    return parse_rows(rows)


def write_statement(folder: Path, *lines: str, header: str = HEADER) -> Path:
    """Write a statement CSV file and return its path."""
    path = folder / "statement.csv"
    path.write_text("\n".join((header, *lines)) + "\n", encoding="utf-8")
    return path


def ranges_around(buys: Iterable[Transaction], spread: str = "0.50") -> dict[date, tuple[Decimal, Decimal]]:
    """Build a synthetic price history whose daily ranges contain the given BUY prices."""
    margin = Decimal(spread)
    return {
        buy.timestamp.date(): (buy.price_per_share - margin, buy.price_per_share + margin)
        for buy in buys
        if buy.price_per_share is not None
    }


@dataclass
class Listing:
    info: SymbolInfo
    price: Decimal | None
    ranges: dict[date, tuple[Decimal, Decimal]]
    as_of: datetime | None = None


@dataclass
class FakeProvider:
    """A PriceProvider with canned listings that records every call."""

    listings: dict[str, Listing] = field(default_factory=dict)
    search_results: dict[str, Sequence[SymbolInfo]] = field(default_factory=dict)
    offline: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def add(
        self,
        symbol: str,
        currency: str,
        price: str | None = None,
        ranges: dict[date, tuple[Decimal, Decimal]] | None = None,
        name: str | None = None,
        exchange: str | None = None,
        timezone: str | None = "Europe/Berlin",
        as_of: datetime | None = None,
    ) -> None:
        info = SymbolInfo(symbol, name or f"{symbol} fund", exchange, currency, timezone)
        self.listings[symbol] = Listing(
            info, Decimal(price) if price is not None else None, ranges or {}, as_of
        )

    def _listing(self, kind: str, symbol: str) -> Listing:
        self.calls.append((kind, symbol))
        if self.offline:
            raise PriceUnavailableError("Prices could not be fetched (offline).")
        if symbol not in self.listings:
            raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.")
        return self.listings[symbol]

    def quote(self, symbol: str) -> Quote:
        listing = self._listing("quote", symbol)
        if listing.price is None:
            raise PriceUnavailableError(f"No current price for {symbol}.")
        return Quote(listing.info, listing.price, listing.info.currency or "", listing.as_of)

    def history(self, symbol: str, start: date, end: date) -> SymbolHistory:
        listing = self._listing("history", symbol)
        ranges = tuple(
            DailyRange(day, low, high) for day, (low, high) in sorted(listing.ranges.items()) if start <= day <= end
        )
        if not ranges:
            # Like Yahoo: a listing without prices in the period looks the same as a missing one.
            raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.")
        return SymbolHistory(listing.info, ranges)

    def search(self, query: str) -> Sequence[SymbolInfo]:
        self.calls.append(("search", query))
        if self.offline:
            raise PriceUnavailableError("Search could not be reached (offline).")
        return self.search_results.get(query, ())
