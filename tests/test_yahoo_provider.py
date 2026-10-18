"""The direct Yahoo provider, fed made-up Yahoo answers through a fake transport. No network."""

import json
import ssl
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from statement_tracker.core.market_data import yahoo_provider
from statement_tracker.core.market_data.provider import DailyRange, PriceUnavailableError, SymbolNotFoundError
from statement_tracker.core.market_data.yahoo_provider import YahooProvider


def epoch(*parts: int) -> int:
    return int(datetime(*parts, tzinfo=UTC).timestamp())


def chart(meta: Mapping[str, object], timestamps=(), lows=(), highs=(), closes=()) -> dict:
    """A chart answer shaped like Yahoo's."""
    return {
        "chart": {
            "result": [
                {
                    "meta": dict(meta),
                    "timestamp": list(timestamps),
                    "indicators": {"quote": [{"low": list(lows), "high": list(highs), "close": list(closes)}]},
                }
            ],
            "error": None,
        }
    }


XETRA = {
    "currency": "EUR",
    "longName": "Example World Equity UCITS ETF",
    "fullExchangeName": "XETRA",
    "exchangeTimezoneName": "Europe/Berlin",
    "regularMarketPrice": 101.25,
    "regularMarketTime": epoch(2026, 10, 9, 15, 35),
}


class FakeTransport:
    """Answers every request with one prepared reply, and remembers what was asked."""

    def __init__(self, status: int = 200, payload: object = None, body: bytes | None = None, error: Exception | None = None):
        self.status, self.error = status, error
        self.body = body if body is not None else json.dumps(payload).encode()
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, params: Mapping[str, str]) -> tuple[int, bytes]:
        self.requests.append((url, dict(params)))
        if self.error is not None:
            raise self.error
        return self.status, self.body


def test_quote_reads_price_currency_time_and_listing() -> None:
    transport = FakeTransport(payload=chart(XETRA))

    quote = YahooProvider(transport).quote("ABCD.DE")

    assert quote.price == Decimal("101.25") and quote.currency == "EUR"
    assert quote.as_of == datetime(2026, 10, 9, 15, 35, tzinfo=UTC)
    assert (quote.info.symbol, quote.info.name, quote.info.exchange, quote.info.timezone) == (
        "ABCD.DE", "Example World Equity UCITS ETF", "XETRA", "Europe/Berlin",
    )  # fmt: skip
    url, params = transport.requests[0]
    assert url == "https://query1.finance.yahoo.com/v8/finance/chart/ABCD.DE"
    assert params["range"] == "5d" and params["interval"] == "1d"


def test_quote_falls_back_to_the_last_close_and_keeps_pence() -> None:
    meta = {**XETRA, "currency": "GBp", "regularMarketPrice": None, "exchangeTimezoneName": "Europe/London"}
    transport = FakeTransport(payload=chart(meta, timestamps=[1, 2, 3], closes=[4100.0, 4120.5, None]))

    quote = YahooProvider(transport).quote("ABCD.L")

    assert (quote.price, quote.currency) == (Decimal("4120.5"), "GBp")  # pence; converting is pricing.py's job


def test_symbols_are_escaped_in_the_address() -> None:
    transport = FakeTransport(payload=chart({**XETRA, "currency": "EUR"}))

    YahooProvider(transport).quote("USDEUR=X")

    assert transport.requests[0][0].endswith("/chart/USDEUR%3DX")


def test_history_dates_bars_in_the_exchange_time_zone_and_skips_gaps() -> None:
    # 23:30 UTC on 3 March is already 4 March in Tokyo.
    late = epoch(2025, 3, 3, 23, 30)
    meta = {**XETRA, "exchangeTimezoneName": "Asia/Tokyo"}
    payload = chart(
        meta,
        timestamps=[epoch(2025, 2, 27, 0, 0), late, epoch(2025, 3, 5, 0, 0), epoch(2025, 3, 10, 0, 0)],
        lows=[90.0, 99.5, None, 101.0],
        highs=[91.0, 100.5, 102.0, 103.0],
    )
    transport = FakeTransport(payload=payload)

    history = YahooProvider(transport).history("ABCD.T", date(2025, 3, 1), date(2025, 3, 7))

    # 27 February is before the period; 5 March has no low; 10 March is after the period.
    assert history.ranges == (DailyRange(date(2025, 3, 4), Decimal("99.5"), Decimal("100.5")),)
    params = transport.requests[0][1]
    # A day of margin before and two after, so bars dated in the exchange's zone are not cut off.
    assert params["period1"] == str(epoch(2025, 2, 28, 0, 0)) and params["period2"] == str(epoch(2025, 3, 9, 0, 0))


def test_history_without_prices_in_the_period_counts_as_no_data() -> None:
    transport = FakeTransport(payload=chart(XETRA, timestamps=[], lows=[], highs=[]))

    with pytest.raises(SymbolNotFoundError):
        YahooProvider(transport).history("ABCD.DU", date(2025, 3, 1), date(2025, 3, 7))


@pytest.mark.parametrize(
    "transport",
    [
        FakeTransport(status=404, payload={"chart": {"result": None, "error": {"code": "Not Found"}}}),
        FakeTransport(status=200, payload={"chart": {"result": None, "error": {"code": "Not Found"}}}),
    ],
)
def test_an_unknown_symbol_is_reported_as_not_found(transport: FakeTransport) -> None:
    with pytest.raises(SymbolNotFoundError, match="Yahoo has no data for NOPE.XX"):
        YahooProvider(transport).quote("NOPE.XX")


@pytest.mark.parametrize(
    ("transport", "message"),
    [
        (FakeTransport(status=429, body=b"Too Many Requests"), "Yahoo is limiting requests right now"),
        (FakeTransport(status=500, body=b"oops"), "HTTP 500"),
        (FakeTransport(error=TimeoutError("timed out")), "Check your internet connection"),
        (FakeTransport(error=OSError("no route")), "Check your internet connection"),
        (FakeTransport(body=b"<html>not json</html>"), "could not read"),
        (FakeTransport(payload=["not", "an", "object"]), "could not read"),
    ],
)
def test_failures_become_plain_language_errors(transport: FakeTransport, message: str) -> None:
    with pytest.raises(PriceUnavailableError, match=message) as error:
        YahooProvider(transport).quote("ABCD.DE")

    assert not isinstance(error.value, SymbolNotFoundError)


def test_search_lists_the_listings_found() -> None:
    payload = {
        "quotes": [
            {"symbol": "ABCD.DE", "longname": "Example fund", "exchDisp": "XETRA"},
            {"symbol": "ABCD.MI", "shortname": "Example", "exchange": "MIL"},
            {"longname": "No symbol, left out"},
        ]
    }
    transport = FakeTransport(payload=payload)

    found = YahooProvider(transport).search("ABCD")

    assert [(info.symbol, info.name, info.exchange) for info in found] == [
        ("ABCD.DE", "Example fund", "XETRA"),
        ("ABCD.MI", "Example", "MIL"),
    ]
    assert transport.requests[0][1]["q"] == "ABCD"


def test_search_failures_say_it_was_the_search() -> None:
    with pytest.raises(PriceUnavailableError, match="symbol search could not be reached"):
        YahooProvider(FakeTransport(status=429, body=b"")).search("ABCD")


def test_certificates_include_certifis_bundle() -> None:
    assert isinstance(yahoo_provider._context(), ssl.SSLContext)
    assert yahoo_provider._context() is yahoo_provider._context()  # built once


class FakeSocket:
    """Records how a connection is attempted; refuses addresses listed in ``down``."""

    attempts: list[tuple[str, float | None]] = []
    down: set[str] = set()

    def __init__(self, family, kind, protocol) -> None:  # noqa: ANN001
        self.timeout: float | None = None
        self.closed = False

    def settimeout(self, timeout: float | None) -> None:
        self.timeout = timeout

    def connect(self, address: tuple) -> None:
        FakeSocket.attempts.append((address[0], self.timeout))
        if address[0] in FakeSocket.down:
            raise TimeoutError("timed out")

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def two_families(monkeypatch: pytest.MonkeyPatch) -> type[FakeSocket]:
    """Yahoo's addresses as Windows gives them, IPv6 first; connections faked."""
    import socket

    infos = [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2a00::1", 443, 0, 0)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2a00::2", 443, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.0.0.1", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.0.0.2", 443)),
    ]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: list(infos))
    monkeypatch.setattr(socket, "socket", FakeSocket)
    FakeSocket.attempts, FakeSocket.down = [], set()
    return FakeSocket


def test_ipv4_is_tried_first_so_a_broken_ipv6_costs_nothing(two_families: type[FakeSocket]) -> None:
    connection = yahoo_provider.connect_preferring_ipv4(("query1.finance.yahoo.com", 443), 15)

    # The first IPv4 address answers: IPv6 is not even tried.
    assert two_families.attempts == [("188.0.0.1", yahoo_provider.CONNECT_SECONDS)]
    assert connection.timeout == 15  # once connected, the usual wait for the answer


def test_each_address_gets_a_short_wait_and_ipv6_is_the_fallback(two_families: type[FakeSocket]) -> None:
    two_families.down = {"188.0.0.1", "188.0.0.2"}  # a network where IPv4 does not get through

    connection = yahoo_provider.connect_preferring_ipv4(("query1.finance.yahoo.com", 443), 15)

    assert [address for address, _ in two_families.attempts] == ["188.0.0.1", "188.0.0.2", "2a00::1"]
    assert {timeout for _, timeout in two_families.attempts} == {yahoo_provider.CONNECT_SECONDS}
    assert connection.timeout == 15


def test_tests_cannot_reach_yahoo_and_the_app_says_to_check_the_connection() -> None:
    # Spec J3: the real provider, with its real connection, as the app uses it. tests/conftest.py blocks it.
    import socket

    from conftest import NO_NETWORK

    with pytest.raises(OSError, match=NO_NETWORK):
        socket.create_connection(("query1.finance.yahoo.com", 443))
    with pytest.raises(PriceUnavailableError, match="Check your internet connection"):
        YahooProvider().quote("ABCD.DE")


def test_no_address_answering_is_an_error_saying_so(two_families: type[FakeSocket]) -> None:
    two_families.down = {"188.0.0.1", "188.0.0.2", "2a00::1", "2a00::2"}

    with pytest.raises(OSError):
        yahoo_provider.connect_preferring_ipv4(("query1.finance.yahoo.com", 443), 15)
    assert len(two_families.attempts) == 4
