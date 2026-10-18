"""The last price fetched for each listing, so an unreachable Yahoo still leaves a value to show.

Also the prices the user typed in themselves, kept until Yahoo has a price again.

Only Yahoo symbols, tickers, prices per share and their dates are kept: nothing
from the statement, no amounts. The file sits next to the settings file.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from statement_tracker.core.models import MarketPrice

LAST_PRICES_FILE = "last_prices.json"


def _read(entries: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(entries, dict):
        return {}
    return {str(key): entry for key, entry in entries.items() if isinstance(entry, dict)}


class PriceCache:
    """Last known prices by Yahoo symbol and entered prices by ticker, each in the statement
    currency it was worked out in, stored as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self._entered: dict[str, dict[str, Any]] = {}
        self._written: dict[str, dict[str, Any]] = {}
        self._changed = False

    @classmethod
    def beside(cls, settings_path: Path) -> PriceCache:
        """Load the cache kept in the same folder as the settings file at ``settings_path``."""
        return cls.load(settings_path.with_name(LAST_PRICES_FILE))

    @classmethod
    def load(cls, path: Path) -> PriceCache:
        """Load saved prices. A missing or damaged file gives an empty cache: it can only ever help."""
        cache = cls(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cache._entries = _read(data.get("prices"))
            cache._entered = _read(data.get("entered"))
            cache._written = _read(data.get("written"))
        except (OSError, ValueError, AttributeError):
            pass
        return cache

    def remember(self, price: MarketPrice, currency: str, fetched_at: datetime) -> None:
        """Keep a freshly fetched price, worked out in ``currency``, replacing the one kept before."""
        self._entries[price.symbol] = {
            "currency": currency,
            "price": str(price.price),
            "quoted_currency": price.quoted_currency,
            "converted": price.converted,
            "as_of": (price.as_of or fetched_at).isoformat(),
        }
        self._changed = True

    def last_known(self, symbol: str, currency: str) -> MarketPrice | None:
        """Return the kept price of ``symbol`` in ``currency``, marked as last known, or None if there is none."""
        entry = self._entries.get(symbol)
        if entry is None or entry.get("currency") != currency:
            return None
        try:
            return MarketPrice(
                Decimal(str(entry["price"])),
                symbol,
                str(entry["quoted_currency"]),
                converted=bool(entry.get("converted")),
                as_of=datetime.fromisoformat(str(entry["as_of"])),
                last_known=True,
            )
        except (KeyError, ValueError, InvalidOperation):
            return None

    def enter(self, ticker: str, price: Decimal, currency: str, entered_at: datetime) -> None:
        """Keep a price per share the user typed in for ``ticker``, in ``currency``, replacing any before."""
        self._entered[ticker] = {"currency": currency, "price": str(price), "entered_at": entered_at.isoformat()}
        self._changed = True

    def entered(self, ticker: str, currency: str) -> MarketPrice | None:
        """Return the price the user typed in for ``ticker`` in ``currency``, or None if there is none.

        Its symbol is empty: the caller knows which listing, if any, the ticker uses.
        """
        entry = self._entered.get(ticker)
        if entry is None or entry.get("currency") != currency:
            return None
        try:
            return MarketPrice(
                Decimal(str(entry["price"])),
                "",
                currency,
                as_of=datetime.fromisoformat(str(entry["entered_at"])),
                entered=True,
            )
        except (KeyError, ValueError, InvalidOperation):
            return None

    def forget_entered(self, ticker: str) -> None:
        """Drop the price typed in for ``ticker``: Yahoo has one again, or the user asked."""
        if self._entered.pop(ticker, None) is not None:
            self._changed = True

    def wrote(self, spreadsheet: Path, values: Mapping[str, Decimal | None]) -> None:
        """Keep the current values just written to ``spreadsheet``, by ticker (None for "unavailable"),
        so that values typed there later can be told from the app's own."""
        self._written[str(spreadsheet)] = {
            ticker: None if value is None else str(value) for ticker, value in values.items()
        }
        self._changed = True

    def written(self, spreadsheet: Path) -> dict[str, Decimal | None] | None:
        """The values last written to ``spreadsheet``, or None if it is not known what they were."""
        record = self._written.get(str(spreadsheet))
        if record is None:
            return None
        try:
            return {str(ticker): None if value is None else Decimal(str(value)) for ticker, value in record.items()}
        except (InvalidOperation, AttributeError):
            return None

    def entered_tickers(self) -> set[str]:
        """The tickers with a price typed in, in any currency."""
        return set(self._entered)

    def entered_entry(self, ticker: str) -> dict[str, Any] | None:
        """A copy of what is kept about the price typed in for ``ticker``, to give back to ``put_entered``."""
        entry = self._entered.get(ticker)
        return None if entry is None else dict(entry)

    def put_entered(self, ticker: str, entry: Mapping[str, Any] | None) -> None:
        """Keep for ``ticker`` what ``entered_entry`` gave, or no price typed in for None."""
        if entry is None:
            self.forget_entered(ticker)
        elif self._entered.get(ticker) != entry:
            self._entered[ticker] = dict(entry)
            self._changed = True

    def forget_all_entered(self) -> None:
        """Drop every price typed in. The last prices fetched from Yahoo are kept."""
        if self._entered:
            self._entered.clear()
            self._changed = True

    def save(self) -> None:
        """Write the prices if any changed, replacing the file in one step. Failures are ignored."""
        if not self._changed:
            return
        data: dict[str, Any] = {"prices": dict(sorted(self._entries.items()))}
        if self._entered:
            data["entered"] = dict(sorted(self._entered.items()))
        if self._written:
            data["written"] = dict(sorted(self._written.items()))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            return  # not being able to keep prices for next time must never stop the user
        self._changed = False
