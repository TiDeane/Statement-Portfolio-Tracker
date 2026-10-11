"""Turning a provider quote into a price in the statement currency."""

from __future__ import annotations

from decimal import Decimal

from statement_tracker.core.market_data.provider import PriceProvider, PriceUnavailableError, Quote
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


def price_in_currency(quote: Quote, target_currency: str, provider: PriceProvider) -> MarketPrice:
    """Express a quote in ``target_currency``, converting at the current rate if needed.

    Raises PriceUnavailableError if the exchange rate cannot be fetched.
    """
    price, currency = to_major_units(quote.price, quote.currency)
    if currency == target_currency:
        return MarketPrice(price, quote.info.symbol, quote.currency, converted=False, as_of=quote.as_of)

    pair = f"{currency}{target_currency}=X"
    rate = provider.quote(pair)
    if rate.currency != target_currency or rate.price <= 0:
        raise PriceUnavailableError(f"No usable exchange rate from {currency} to {target_currency}.")
    return MarketPrice(
        price * rate.price, quote.info.symbol, quote.currency, converted=True, as_of=quote.as_of
    )
