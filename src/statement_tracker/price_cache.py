"""The last price fetched for each listing, so an unreachable Yahoo still leaves a value to show.

Only Yahoo symbols, prices per share and their dates are kept: nothing from the
statement, no amounts. The file sits next to the settings file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from statement_tracker.core.models import MarketPrice

LAST_PRICES_FILE = "last_prices.json"


class PriceCache:
    """Last known prices by Yahoo symbol, each in the statement currency it was worked out in, stored as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
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
            prices = json.loads(path.read_text(encoding="utf-8")).get("prices", {})
            cache._entries = {str(symbol): entry for symbol, entry in prices.items() if isinstance(entry, dict)}
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

    def save(self) -> None:
        """Write the prices if any changed, replacing the file in one step. Failures are ignored."""
        if not self._changed:
            return
        data = {"prices": dict(sorted(self._entries.items()))}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            return  # not being able to keep prices for next time must never stop the user
        self._changed = False
