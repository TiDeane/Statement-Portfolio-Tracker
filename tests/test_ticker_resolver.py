"""Ticker matching against a mocked provider.

The synthetic price histories are built around the sample's own (date, price)
pairs. The sample's dates are shifted, so it is never checked against real
market data.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fakes import SAMPLE, FakeProvider, ranges_around, statement_from

from statement_tracker.core.calculator import buys_by_ticker
from statement_tracker.core.market_data.provider import DailyRange, PriceUnavailableError, SymbolInfo
from statement_tracker.core.parser import load_statement
from statement_tracker.core.ticker_resolver import (
    Confidence,
    candidate_symbols,
    price_fits,
    resolve_ticker,
    trade_day,
)

EQQB_BUYS = buys_by_ticker(load_statement(SAMPLE))["EQQB"]
FAR_AWAY = {buy.timestamp.date(): (Decimal("10"), Decimal("11")) for buy in EQQB_BUYS}


def test_one_fitting_listing_is_confident() -> None:
    provider = FakeProvider()
    provider.add("EQQB.DE", "EUR", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    provider.add("EQQB.MI", "EUR", ranges=FAR_AWAY)
    provider.add("EQQB.L", "GBp", ranges=ranges_around(EQQB_BUYS))

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.CONFIDENT
    assert resolution.best is not None
    assert resolution.best.info.symbol == "EQQB.DE"
    assert resolution.best.info.name == "Nasdaq fund"
    assert (resolution.best.matched, resolution.best.checked) == (2, 2)
    assert [candidate.info.symbol for candidate in resolution.candidates] == ["EQQB.DE", "EQQB.MI", "EQQB.L"]


def test_two_fitting_listings_are_ambiguous() -> None:
    provider = FakeProvider()
    provider.add("EQQB.DE", "EUR", ranges=ranges_around(EQQB_BUYS))
    provider.add("EQQB.MI", "EUR", ranges=ranges_around(EQQB_BUYS, spread="0.80"))

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.AMBIGUOUS
    assert resolution.best is None
    assert [candidate.info.symbol for candidate in resolution.candidates] == ["EQQB.DE", "EQQB.MI"]
    assert all(candidate.is_match for candidate in resolution.candidates)


def test_no_fitting_listing_is_unresolved() -> None:
    provider = FakeProvider()
    provider.add("EQQB.DE", "EUR", ranges=FAR_AWAY)
    provider.add("EQQB.L", "GBp", ranges=ranges_around(EQQB_BUYS))

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.UNRESOLVED
    assert resolution.best is None
    assert [candidate.info.symbol for candidate in resolution.candidates] == ["EQQB.DE", "EQQB.L"]


def test_ticker_unknown_to_the_provider_is_unresolved_without_candidates() -> None:
    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", FakeProvider())

    assert resolution.confidence is Confidence.UNRESOLVED
    assert resolution.candidates == ()


def test_listing_in_another_currency_is_never_a_match() -> None:
    provider = FakeProvider()
    provider.add("EQQB", "USD", ranges=ranges_around(EQQB_BUYS))

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.UNRESOLVED
    assert resolution.candidates[0].comparable is False


def test_confident_needs_most_of_the_buys_to_fit() -> None:
    statement = statement_from(
        "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,1,EUR 100.00,EUR 100,EUR,1",
        "2025-02-03T10:00:00.000Z,ABCD,BUY - MARKET,1,EUR 110.00,EUR 110,EUR,1",
        "2025-03-03T10:00:00.000Z,ABCD,BUY - MARKET,1,EUR 120.00,EUR 120,EUR,1",
    )
    buys = buys_by_ticker(statement)["ABCD"]
    two_of_three = ranges_around(buys[:2]) | {date(2025, 3, 3): (Decimal("50"), Decimal("51"))}
    one_of_three = ranges_around(buys[:1]) | {
        date(2025, 2, 3): (Decimal("50"), Decimal("51")),
        date(2025, 3, 3): (Decimal("50"), Decimal("51")),
    }
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", ranges=two_of_three)
    provider.add("ABCD.PA", "EUR", ranges=one_of_three)

    resolution = resolve_ticker("ABCD", buys, "EUR", provider)

    assert resolution.confidence is Confidence.CONFIDENT
    assert resolution.best.info.symbol == "ABCD.DE"
    assert (resolution.best.matched, resolution.best.checked) == (2, 3)
    assert resolution.candidates[1].is_match is False


def test_pence_listing_is_compared_in_pounds() -> None:
    statement = statement_from(
        "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,1,GBP 41.20,GBP 41.20,GBP,1",
    )
    buys = buys_by_ticker(statement)["ABCD"]
    provider = FakeProvider()
    provider.add("ABCD.L", "GBp", ranges={date(2025, 1, 6): (Decimal("4100"), Decimal("4150"))}, timezone="Europe/London")

    resolution = resolve_ticker("ABCD", buys, "GBP", provider)

    assert resolution.confidence is Confidence.CONFIDENT
    assert resolution.best.info.symbol == "ABCD.L"


def test_search_results_add_listings_beyond_the_suffix_list() -> None:
    provider = FakeProvider()
    provider.add("EQQB.SW", "EUR", ranges=ranges_around(EQQB_BUYS))
    provider.search_results["EQQB"] = [
        SymbolInfo("EQQB.SW", name="Nasdaq fund", exchange="Swiss"),
        SymbolInfo("EQQBX", name="Something else"),
    ]

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.CONFIDENT
    assert resolution.best.info.symbol == "EQQB.SW"
    assert ("history", "EQQBX") not in provider.calls


def test_candidates_are_tried_bare_first_then_suffixes_then_search() -> None:
    provider = FakeProvider()
    provider.search_results["ABCD"] = [SymbolInfo("ABCD.SW"), SymbolInfo("ABCD.DE", name="Known name")]

    candidates = candidate_symbols("ABCD", (".DE", ".L"), provider)

    assert list(candidates) == ["ABCD", "ABCD.DE", "ABCD.L", "ABCD.SW"]
    assert candidates["ABCD.DE"].name == "Known name"
    assert candidates["ABCD"] is None and candidates["ABCD.L"] is None


def test_listing_known_to_search_but_without_prices_near_the_purchases_stays_an_option() -> None:
    provider = FakeProvider()
    provider.add("EQQB.DU", "EUR", price="400", ranges={}, exchange="Dusseldorf")
    provider.add("EQQB.PA", "EUR", price="400", ranges={})  # only a guess from the suffix list
    provider.search_results["EQQB"] = [SymbolInfo("EQQB.DU", name="Nasdaq fund", exchange="Dusseldorf")]

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)

    assert resolution.confidence is Confidence.UNRESOLVED
    assert [candidate.info.symbol for candidate in resolution.candidates] == ["EQQB.DU"]
    assert (resolution.candidates[0].matched, resolution.candidates[0].comparable) == (0, True)


def test_unreachable_provider_is_reported_not_treated_as_unresolved() -> None:
    provider = FakeProvider(offline=True)

    with pytest.raises(PriceUnavailableError):
        resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)


def test_trade_on_a_non_trading_day_is_checked_against_the_nearest_trading_day() -> None:
    friday = DailyRange(date(2025, 3, 7), Decimal("90"), Decimal("95"))
    monday = DailyRange(date(2025, 3, 10), Decimal("100"), Decimal("105"))
    sunday = date(2025, 3, 9)
    tolerance = Decimal("0.01")

    assert price_fits(Decimal("102"), sunday, [friday, monday], tolerance)
    assert not price_fits(Decimal("92"), sunday, [friday, monday], tolerance)
    assert price_fits(Decimal("92"), date(2025, 3, 7), [friday, monday], tolerance)


def test_price_just_outside_the_range_fits_within_the_tolerance_only() -> None:
    day = DailyRange(date(2025, 3, 7), Decimal("100"), Decimal("105"))

    assert price_fits(Decimal("99.50"), day.day, [day], Decimal("0.01"))
    assert price_fits(Decimal("105.90"), day.day, [day], Decimal("0.01"))
    assert not price_fits(Decimal("98.90"), day.day, [day], Decimal("0.01"))
    assert not price_fits(Decimal("106.20"), day.day, [day], Decimal("0.01"))


def test_no_market_data_near_the_trade_date_does_not_fit() -> None:
    old = DailyRange(date(2024, 1, 2), Decimal("100"), Decimal("105"))

    assert not price_fits(Decimal("102"), date(2025, 3, 7), [old], Decimal("0.01"))
    assert not price_fits(Decimal("102"), date(2025, 3, 7), [], Decimal("0.01"))


def test_trade_day_uses_the_exchange_time_zone() -> None:
    late_evening_utc = datetime(2025, 3, 6, 23, 30, tzinfo=UTC)

    assert trade_day(late_evening_utc, "Europe/Berlin") == date(2025, 3, 7)
    assert trade_day(late_evening_utc, "America/New_York") == date(2025, 3, 6)
    assert trade_day(late_evening_utc, None) == date(2025, 3, 6)
    assert trade_day(late_evening_utc, "Not/AZone") == date(2025, 3, 6)
