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


class _Text(str):
    """A text cell: arithmetic on it is an error, as in Excel (#VALUE!)."""

    def _error(self, *_: object) -> _Text:
        return ERROR

    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _error


ERROR = _Text("#VALUE!")


def computed(path: Path, sheet_name: str) -> list[list[object]]:
    """Return a sheet's rows as Excel would show them, working out its formulas.

    Knows only what the app's sheets use: IF, OR, AND, N, ISNUMBER, COUNT, SUM, SUMPRODUCT, arithmetic,
    comparisons, cell references and ranges (``$`` ignored). Numbers come back as floats.
    """
    import re

    from openpyxl import load_workbook
    from openpyxl.utils import column_index_from_string

    sheet = load_workbook(path)[sheet_name]
    done: dict[tuple[int, int], object] = {}

    def value(column: str, row: int) -> object:
        key = (row, column_index_from_string(column))
        if key not in done:
            raw = sheet.cell(row=key[0], column=key[1]).value
            if isinstance(raw, str) and raw.startswith("="):
                done[key] = evaluate(raw[1:])
            elif isinstance(raw, (int, float, Decimal)) and not isinstance(raw, bool):
                done[key] = float(raw)
            else:
                done[key] = _Text(raw) if raw is not None else None
        return done[key]

    def cells(first: str, first_row: int, last: str, last_row: int) -> list[object]:
        return [value(first, row) for row in range(first_row, last_row + 1)]

    def is_number(item: object) -> object:
        if isinstance(item, list):
            return [is_number(each) for each in item]
        return isinstance(item, float)

    functions = {
        "IF": lambda condition, then, otherwise: then if condition else otherwise,
        "OR": lambda *items: any(items),
        "AND": lambda *items: all(items),
        "N": lambda item: item if isinstance(item, float) else 0.0,
        "ISNUMBER": is_number,
        "COUNT": lambda items: sum(isinstance(item, float) for item in items),
        "SUM": lambda items: sum(item for item in items if isinstance(item, float)),
        "SUMPRODUCT": lambda left, right: sum(a * b for a, b in zip(left, right) if isinstance(a, float)),
        "_cells": cells,
        "_value": value,
    }

    def evaluate(formula: str) -> object:
        text = formula.replace("$", "").replace("--", "")
        text = re.sub(r"\b([A-Z]+)(\d+):([A-Z]+)(\d+)\b", r"_cells('\1',\2,'\3',\4)", text)
        text = re.sub(r"\b([A-Z]{1,2})(\d+)\b", r"_value('\1',\2)", text)
        text = re.sub(r"(?<![<>!=])=(?!=)", "==", text)
        try:
            result = eval(text, {"__builtins__": {}}, functions)  # noqa: S307 - our own formulas, in tests
        except ZeroDivisionError:
            return ERROR
        if isinstance(result, (bool, int)):
            return float(result)
        return _Text(result) if isinstance(result, str) else result

    return [
        [value(column_letter, row) for column_letter in (chr(ord("A") + index) for index in range(sheet.max_column))]
        for row in range(1, sheet.max_row + 1)
    ]


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
    prepared: int = 0

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

    def prepare(self) -> None:
        self.prepared += 1

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
