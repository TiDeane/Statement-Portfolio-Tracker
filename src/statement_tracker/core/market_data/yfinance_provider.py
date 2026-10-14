"""Yahoo Finance through the unofficial yfinance library.

This is the only module that imports yfinance, and it does so on first use,
because the import is slow (it loads pandas and numpy). yfinance is unofficial
and may break when Yahoo changes; Yahoo's terms apply to the data.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import Any

from statement_tracker.core.market_data.provider import (
    DailyRange,
    PriceUnavailableError,
    Quote,
    SymbolHistory,
    SymbolInfo,
    SymbolNotFoundError,
)


def _decimal(value: Any) -> Decimal | None:
    """Convert a provider float to Decimal; None for missing or NaN values."""
    if value is None:
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return Decimal(repr(number))


class YFinanceProvider:
    """PriceProvider backed by Yahoo Finance. Sends only symbols and dates to Yahoo."""

    def __init__(self) -> None:
        self._yfinance: ModuleType | None = None

    def _module(self) -> ModuleType:
        if self._yfinance is None:
            import yfinance

            # yfinance logs every missing symbol; we report problems ourselves.
            logging.getLogger("yfinance").setLevel(logging.CRITICAL)
            self._yfinance = yfinance
        return self._yfinance

    def prepare(self) -> None:
        """Load yfinance (and with it pandas and numpy): several seconds on a cold start."""
        self._module()

    def _fetch(self, symbol: str, **period: Any) -> tuple[Any, dict[str, Any]]:
        """Return (daily price table, metadata) for a symbol from one Yahoo request."""
        yfinance = self._module()
        try:
            ticker = yfinance.Ticker(symbol)
            with warnings.catch_warnings():
                # yfinance 1.x deprecates raise_errors in favour of a global switch, but that
                # switch reports an unknown symbol as a bare HTTP error. Keep the precise errors.
                warnings.simplefilter("ignore", DeprecationWarning)
                frame = ticker.history(
                    interval="1d", auto_adjust=False, actions=False, raise_errors=True, **period
                )
            metadata = ticker.history_metadata or {}
        except yfinance.exceptions.YFRateLimitError as exc:
            raise PriceUnavailableError(
                "Yahoo is limiting requests right now. Try again in a few minutes."
            ) from exc
        except (yfinance.exceptions.YFTickerMissingError, yfinance.exceptions.YFTzMissingError) as exc:
            raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.") from exc
        except Exception as exc:
            raise PriceUnavailableError(
                f"Prices could not be fetched from Yahoo ({type(exc).__name__}). "
                "Check your internet connection and try again."
            ) from exc
        return frame, metadata

    @staticmethod
    def _info(symbol: str, metadata: dict[str, Any]) -> SymbolInfo:
        return SymbolInfo(
            symbol=symbol,
            name=metadata.get("longName") or metadata.get("shortName"),
            exchange=metadata.get("fullExchangeName") or metadata.get("exchangeName"),
            currency=metadata.get("currency"),
            timezone=metadata.get("exchangeTimezoneName"),
        )

    def quote(self, symbol: str) -> Quote:
        """Return the latest price Yahoo has for ``symbol``."""
        frame, metadata = self._fetch(symbol, period="5d")
        price = _decimal(metadata.get("regularMarketPrice"))
        if price is None and len(frame):
            price = _decimal(frame["Close"].iloc[-1])
        currency = metadata.get("currency")
        if price is None or not currency:
            raise PriceUnavailableError(f"Yahoo returned no current price for {symbol}.")

        as_of = metadata.get("regularMarketTime")
        if hasattr(as_of, "to_pydatetime"):
            as_of = as_of.to_pydatetime()
        elif isinstance(as_of, (int, float)):
            as_of = datetime.fromtimestamp(as_of, tz=UTC)
        elif not isinstance(as_of, datetime):
            as_of = None
        if as_of is not None and as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=UTC)
        return Quote(self._info(symbol, metadata), price, currency, as_of)

    def history(self, symbol: str, start: date, end: date) -> SymbolHistory:
        """Return unadjusted daily low/high ranges from ``start`` to ``end`` inclusive."""
        frame, metadata = self._fetch(
            symbol, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat()
        )
        ranges = []
        for timestamp, row in frame.iterrows():
            low, high = _decimal(row["Low"]), _decimal(row["High"])
            if low is not None and high is not None:
                ranges.append(DailyRange(timestamp.date(), low, high))
        return SymbolHistory(self._info(symbol, metadata), tuple(ranges))

    def search(self, query: str) -> Sequence[SymbolInfo]:
        """Return Yahoo's symbol search results, or nothing if this yfinance has no search."""
        search = getattr(self._module(), "Search", None)
        if search is None:
            return ()
        try:
            quotes = search(query, max_results=10).quotes
        except Exception as exc:
            raise PriceUnavailableError(
                f"Yahoo's symbol search could not be reached ({type(exc).__name__})."
            ) from exc
        return tuple(
            SymbolInfo(
                symbol=item["symbol"],
                name=item.get("longname") or item.get("shortname"),
                exchange=item.get("exchDisp") or item.get("exchange"),
            )
            for item in quotes
            if item.get("symbol")
        )
