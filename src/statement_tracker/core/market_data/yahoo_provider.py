"""Yahoo Finance, read directly from the two public web endpoints the app needs.

The chart endpoint gives the latest price of a listing and its daily low/high
ranges; the search endpoint finds listings by ticker. Both are unofficial and
may change; Yahoo's terms apply to the data. Only symbols and dates are sent.

The answers are turned into the provider types by pure functions, so they are
tested without a network. Fetching goes through a small transport function,
which tests replace.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from statement_tracker.core.market_data.provider import (
    DailyRange,
    PriceUnavailableError,
    Quote,
    SymbolHistory,
    SymbolInfo,
    SymbolNotFoundError,
)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
TIMEOUT_SECONDS = 15
CONNECT_SECONDS = 5
"""Longest wait for one address to accept a connection, before the next one is tried."""
HEADERS = {
    # Yahoo turns away requests that do not look like they come from a browser.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

Transport = Callable[[str, Mapping[str, str]], tuple[int, bytes]]
"""Fetches a URL with query parameters; returns (HTTP status, body). Raises OSError when unreachable."""


_ssl_context: ssl.SSLContext | None = None


def _context() -> ssl.SSLContext:
    """Certificates to check Yahoo's with: the system's, plus certifi's bundle.

    A packaged app cannot always find the system's own (macOS, some Linux systems);
    certifi's bundle travels with the app. Built once, on first use.
    """
    global _ssl_context
    if _ssl_context is None:
        import certifi

        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        _ssl_context = context
    return _ssl_context


def connect_preferring_ipv4(
    address: tuple[str, int], timeout: object = None, source_address: object = None, **_: object
) -> socket.socket:
    """Open a connection to ``address``, trying its IPv4 addresses before its IPv6 ones.

    Python tries addresses in the order the system gives, IPv6 first on Windows. Where IPv6
    is offered but its traffic stops getting through (seen on Windows, while the same
    connection worked over IPv4), every request then waited a whole timeout per IPv6 address
    before falling back. So IPv4 is tried first, and no address gets more than
    CONNECT_SECONDS to answer; IPv6 stays the fallback, for a network that only has IPv6.
    Once connected, ``timeout`` applies to waiting for the answer, as usual.
    """
    host, port = address
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    infos.sort(key=lambda info: info[0] != socket.AF_INET)  # IPv4 first, the system's order kept otherwise
    read_timeout = timeout if isinstance(timeout, (int, float)) else None
    connect_timeout = min(CONNECT_SECONDS, read_timeout) if read_timeout is not None else CONNECT_SECONDS
    last_error: OSError = OSError(f"No address found for {host}.")
    for family, kind, protocol, _, socket_address in infos:
        connection = socket.socket(family, kind, protocol)
        try:
            connection.settimeout(connect_timeout)
            connection.connect(socket_address)
        except OSError as error:
            connection.close()
            last_error = error
            continue
        connection.settimeout(read_timeout)
        return connection
    raise last_error


class _HTTPSConnection(http.client.HTTPSConnection):
    """Python's HTTPS connection, connecting with ``connect_preferring_ipv4``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = connect_preferring_ipv4


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(_HTTPSConnection, req, context=self._context)  # type: ignore[attr-defined]


_opener: urllib.request.OpenerDirector | None = None


def urllib_transport(url: str, params: Mapping[str, str]) -> tuple[int, bytes]:
    """Fetch with Python's own HTTP client. HTTP errors are returned, not raised."""
    global _opener
    if _opener is None:
        _opener = urllib.request.build_opener(_HTTPSHandler(context=_context()))
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=HEADERS)
    try:
        with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _decimal(value: Any) -> Decimal | None:
    """Convert a number from Yahoo to Decimal; None for missing or NaN values."""
    if value is None or isinstance(value, bool):
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return Decimal(repr(number))


def _info(symbol: str, meta: Mapping[str, Any]) -> SymbolInfo:
    return SymbolInfo(
        symbol=symbol,
        name=meta.get("longName") or meta.get("shortName"),
        exchange=meta.get("fullExchangeName") or meta.get("exchangeName"),
        currency=meta.get("currency"),
        timezone=meta.get("exchangeTimezoneName"),
    )


def _chart_result(symbol: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """The chart answer's single result, or SymbolNotFoundError when Yahoo has nothing for the symbol."""
    chart = payload.get("chart") or {}
    results = chart.get("result") or []
    if not results:
        raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.")
    return results[0]


def _local_day(timestamp: int, meta: Mapping[str, Any]) -> date:
    """The exchange-local date of a daily bar's timestamp (seconds since 1970, UTC)."""
    moment = datetime.fromtimestamp(timestamp, tz=UTC)
    zone = meta.get("exchangeTimezoneName")
    if zone:
        try:
            return moment.astimezone(ZoneInfo(zone)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return (moment + timedelta(seconds=int(meta.get("gmtoffset") or 0))).date()


def parse_quote(symbol: str, payload: Mapping[str, Any]) -> Quote:
    """Turn a chart answer into the latest price of the listing."""
    result = _chart_result(symbol, payload)
    meta = result.get("meta") or {}
    price = _decimal(meta.get("regularMarketPrice"))
    if price is None:
        closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        price = next((value for value in map(_decimal, reversed(closes)) if value is not None), None)
    currency = meta.get("currency")
    if price is None or not currency:
        raise PriceUnavailableError(f"Yahoo returned no current price for {symbol}.")
    market_time = meta.get("regularMarketTime")
    as_of = datetime.fromtimestamp(market_time, tz=UTC) if isinstance(market_time, (int, float)) else None
    return Quote(_info(symbol, meta), price, currency, as_of)


def parse_history(symbol: str, payload: Mapping[str, Any], start: date, end: date) -> SymbolHistory:
    """Turn a chart answer into daily low/high ranges from ``start`` to ``end`` inclusive.

    A listing without any prices in the period is reported like a missing one, as Yahoo does.
    """
    result = _chart_result(symbol, payload)
    meta = result.get("meta") or {}
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    lows, highs = quote.get("low") or [], quote.get("high") or []
    ranges = []
    for index, timestamp in enumerate(result.get("timestamp") or []):
        low = _decimal(lows[index]) if index < len(lows) else None
        high = _decimal(highs[index]) if index < len(highs) else None
        day = _local_day(timestamp, meta)
        if low is not None and high is not None and start <= day <= end:
            ranges.append(DailyRange(day, low, high))
    if not ranges:
        raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.")
    return SymbolHistory(_info(symbol, meta), tuple(ranges))


def parse_search(payload: Mapping[str, Any]) -> tuple[SymbolInfo, ...]:
    """Turn a search answer into the listings it found."""
    return tuple(
        SymbolInfo(
            symbol=item["symbol"],
            name=item.get("longname") or item.get("shortname"),
            exchange=item.get("exchDisp") or item.get("exchange"),
        )
        for item in payload.get("quotes") or []
        if item.get("symbol")
    )


def _epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


class YahooProvider:
    """PriceProvider reading Yahoo Finance's public endpoints. Sends only symbols and dates to Yahoo."""

    def __init__(self, transport: Transport = urllib_transport) -> None:
        self._transport = transport

    def prepare(self) -> None:
        """Nothing slow to set up: there is no library to load."""

    def _get(self, url: str, params: Mapping[str, str], symbol: str | None = None) -> Mapping[str, Any]:
        """Fetch and decode a Yahoo answer, turning every failure into a plain-language error."""
        try:
            status, body = self._transport(url, params)
        except (OSError, socket.timeout) as exc:
            raise PriceUnavailableError(
                f"Prices could not be fetched from Yahoo ({type(exc).__name__}). "
                "Check your internet connection and try again."
            ) from exc
        if status == 429:
            raise PriceUnavailableError("Yahoo is limiting requests right now. Try again in a few minutes.")
        if status == 404 and symbol is not None:
            raise SymbolNotFoundError(f"Yahoo has no data for {symbol}.")
        if status != 200:
            raise PriceUnavailableError(
                f"Prices could not be fetched from Yahoo (HTTP {status}). Try again in a few minutes."
            )
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise PriceUnavailableError(
                "Yahoo sent an answer the app could not read. Try again in a few minutes."
            ) from exc
        if not isinstance(payload, dict):
            raise PriceUnavailableError("Yahoo sent an answer the app could not read. Try again in a few minutes.")
        return payload

    def quote(self, symbol: str) -> Quote:
        """Return the latest price Yahoo has for ``symbol``."""
        params = {"range": "5d", "interval": "1d", "includePrePost": "false"}
        return parse_quote(symbol, self._get(CHART_URL.format(symbol=urllib.parse.quote(symbol)), params, symbol))

    def history(self, symbol: str, start: date, end: date) -> SymbolHistory:
        """Return unadjusted daily low/high ranges from ``start`` to ``end`` inclusive."""
        # A day of margin on each side: bars are dated in the exchange's time zone, not UTC.
        params = {
            "period1": str(_epoch(start - timedelta(days=1))),
            "period2": str(_epoch(end + timedelta(days=2))),
            "interval": "1d",
            "includePrePost": "false",
        }
        payload = self._get(CHART_URL.format(symbol=urllib.parse.quote(symbol)), params, symbol)
        return parse_history(symbol, payload, start, end)

    def search(self, query: str) -> Sequence[SymbolInfo]:
        """Return Yahoo's symbol search results for a ticker or name."""
        params = {"q": query, "quotesCount": "10", "newsCount": "0"}
        try:
            return parse_search(self._get(SEARCH_URL, params))
        except PriceUnavailableError as exc:
            raise PriceUnavailableError(f"Yahoo's symbol search could not be reached. {exc}") from exc
