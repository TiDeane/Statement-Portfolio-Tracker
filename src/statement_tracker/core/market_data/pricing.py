"""Turning a provider quote into a price in the statement currency."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from statement_tracker.core.market_data.provider import PriceUnavailableError, Quote
from statement_tracker.core.models import MarketPrice

# Some exchanges quote in a hundredth of the currency, e.g. London in pence.
_MINOR_UNITS: dict[str, tuple[str, Decimal]] = {
    "GBp": ("GBP", Decimal(100)),
    "GBX": ("GBP", Decimal(100)),
}


def to_major_units(amount: Decimal, currency: str) -> tuple[Decimal, str]:
    """Convert pence to pounds; other currencies are returned unchanged."""
    if currency in _MINOR_UNITS:
        major, factor = _MINOR_UNITS[currency]
        return amount / factor, major
    return amount, currency


class QuoteSource(Protocol):
    """Anything that can give a symbol's latest price: a provider, or a RateBook of prices already fetched."""

    def quote(self, symbol: str) -> Quote: ...


class RateBook:
    """Exchange rates fetched beforehand, each once, handed out like a provider would."""

    def __init__(self, fetched: Mapping[str, Quote | PriceUnavailableError]) -> None:
        self._fetched = dict(fetched)

    def quote(self, symbol: str) -> Quote:
        """Return the rate fetched for ``symbol``, or raise the error its fetch ended with."""
        outcome = self._fetched.get(symbol)
        if outcome is None:
            raise PriceUnavailableError(f"No exchange rate was fetched for {symbol}.")
        if isinstance(outcome, PriceUnavailableError):
            raise outcome
        return outcome


def exchange_pair(quote: Quote, target_currency: str) -> str | None:
    """The Yahoo symbol of the exchange rate needed to express ``quote`` in ``target_currency``, if any."""
    currency = to_major_units(quote.price, quote.currency)[1]
    return None if currency == target_currency else f"{currency}{target_currency}=X"


def price_in_currency(quote: Quote, target_currency: str, rates: QuoteSource) -> MarketPrice:
    """Express a quote in ``target_currency``, converting at the current rate from ``rates`` if needed.

    Raises PriceUnavailableError if the exchange rate cannot be fetched.
    """
    price, currency = to_major_units(quote.price, quote.currency)
    pair = exchange_pair(quote, target_currency)
    if pair is None:
        return MarketPrice(price, quote.info.symbol, quote.currency, converted=False, as_of=quote.as_of)

    rate = rates.quote(pair)
    if rate.currency != target_currency or rate.price <= 0:
        raise PriceUnavailableError(f"No usable exchange rate from {currency} to {target_currency}.")
    return MarketPrice(
        price * rate.price, quote.info.symbol, quote.currency, converted=True, as_of=quote.as_of
    )
