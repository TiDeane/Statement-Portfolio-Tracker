"""The UI-free pipeline and the command line, with a mocked provider and a temporary settings file."""

import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fakes import SAMPLE, FakeProvider, ranges_around, write_statement

from statement_tracker import cli
from statement_tracker.core.calculator import buys_by_ticker
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.market_data.pricing import price_in_currency, to_major_units
from statement_tracker.core.market_data.provider import PriceUnavailableError, Quote, SymbolInfo
from statement_tracker.core.parser import load_statement
from statement_tracker.core.ticker_resolver import resolve_ticker
from statement_tracker.settings import Settings, TickerChoice
from statement_tracker.workflow import build_report

EQQB_BUYS = buys_by_ticker(load_statement(SAMPLE))["EQQB"]

TWO_HOLDINGS = (
    "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 2000,EUR,1",
    "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,10,EUR 100.00,EUR 1001,EUR,1",
    "2025-01-20T10:00:00.000Z,WXYZ,BUY - MARKET,4,EUR 50.00,EUR 201,EUR,1",
)


def sample_provider() -> FakeProvider:
    provider = FakeProvider()
    provider.add("EQQB.DE", "EUR", price="400", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    return provider


def run_cli(*arguments: str, provider: FakeProvider, settings: Path) -> tuple[int, str, str]:
    output, errors = io.StringIO(), io.StringIO()
    code = cli.main([*arguments, "--settings", str(settings), "--no-prompt"], provider, output, errors)
    return code, output.getvalue(), errors.getvalue()


def test_cli_prints_one_row_per_open_holding_for_the_sample(tmp_path: Path) -> None:
    code, output, errors = run_cli(str(SAMPLE), provider=sample_provider(), settings=tmp_path / "settings.json")

    assert code == 0
    assert output == (
        "Index,Invested (EUR),% of Invested,Current Value (EUR approx.),% of Current Value,Gain/Loss (EUR),% Up/Down\n"
        "EQQB,541.49,100.00,589.31,100.00,47.82,8.83\n"  # 1.47328346 shares x 400
        "Total,541.49,100.00,589.31,100.00,47.82,8.83\n"
    )
    assert "EQQB was matched to EQQB.DE (Nasdaq fund, XETRA, EUR)" in errors
    assert "IUSA" not in output  # fully sold


def test_cli_shows_each_holdings_share_of_the_total_current_value(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")
    provider.add("WXYZ.DE", "EUR", price="100")
    statement = write_statement(tmp_path, *TWO_HOLDINGS)

    code, output, _ = run_cli(
        str(statement), "--symbol", "ABCD=ABCD.DE", "--symbol", "WXYZ=WXYZ.DE",
        provider=provider, settings=tmp_path / "settings.json",
    )  # fmt: skip

    assert code == 0
    # 1001 and 201 out of 1202 invested; 1200 and 400 out of a total current value of 1600.
    assert output.splitlines() == [
        "Index,Invested (EUR),% of Invested,Current Value (EUR approx.),% of Current Value,Gain/Loss (EUR),% Up/Down",
        "ABCD,1001.00,83.28,1200.00,75.00,199.00,19.88",
        "WXYZ,201.00,16.72,400.00,25.00,199.00,99.00",
        "Total,1202.00,100.00,1600.00,100.00,398.00,33.11",
    ]


def test_cli_details_add_the_columns_needed_to_check_the_numbers(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120", as_of=datetime(2026, 10, 9, 15, 35, tzinfo=UTC))
    provider.add("WXYZ.DE", "EUR", price="100")
    statement = write_statement(
        tmp_path,
        *TWO_HOLDINGS,
        "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,4,EUR 120.00,EUR 479,EUR,1",
        "2025-02-10T10:00:00.000Z,ABCD,DIVIDEND,,,EUR 3.21,EUR,1",
    )

    code, output, _ = run_cli(
        str(statement), "--details", "--symbol", "ABCD=ABCD.DE", "--symbol", "WXYZ=WXYZ.DE",
        provider=provider, settings=tmp_path / "settings.json",
    )  # fmt: skip

    assert code == 0
    assert output.splitlines() == [
        "Index,Invested (EUR),% of Invested,Current Value (EUR approx.),% of Current Value,Gain/Loss (EUR),"
        "% Up/Down,Shares,Average cost (EUR),Price used (EUR),Yahoo symbol,Price time,Realized gain (EUR),"
        "Dividends (EUR)",
        "ABCD,600.60,74.93,720.00,64.29,119.40,19.88,6,100.1000,120.0000,ABCD.DE,2026-10-09T15:35+00:00,78.60,3.21",
        "WXYZ,201.00,25.07,400.00,35.71,199.00,99.00,4,50.2500,100.0000,WXYZ.DE,unavailable,0.00,0.00",
        "Total,801.60,100.00,1120.00,100.00,318.40,39.72,,,,,,,",
    ]


def test_cli_table_output_is_aligned(tmp_path: Path) -> None:
    code, output, _ = run_cli(
        str(SAMPLE), "--table", provider=sample_provider(), settings=tmp_path / "settings.json"
    )

    lines = output.splitlines()
    assert code == 0
    assert lines[0].split() == [
        "Index", "Invested", "(EUR)", "%", "of", "Invested", "Current", "Value", "(EUR", "approx.)",
        "%", "of", "Current", "Value", "Gain/Loss", "(EUR)", "%", "Up/Down",
    ]  # fmt: skip
    assert lines[1].split() == ["EQQB", "541.49", "100.00", "589.31", "100.00", "47.82", "8.83"]
    assert lines[2].split() == ["Total", "541.49", "100.00", "589.31", "100.00", "47.82", "8.83"]
    assert len(lines[0]) == len(lines[1]) == len(lines[2])


def test_missing_price_leaves_what_depends_on_it_unavailable(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")
    provider.add("WXYZ.DE", "EUR", price=None)
    statement = write_statement(tmp_path, *TWO_HOLDINGS)

    code, output, errors = run_cli(
        str(statement), "--symbol", "ABCD=ABCD.DE", "--symbol", "WXYZ=WXYZ.DE",
        provider=provider, settings=tmp_path / "settings.json",
    )  # fmt: skip

    assert code == 0
    # No total current value without WXYZ, so no shares of it either; the shares of the amount invested remain.
    assert output.splitlines()[1:] == [
        "ABCD,1001.00,83.28,1200.00,unavailable,199.00,19.88",
        "WXYZ,201.00,16.72,unavailable,unavailable,unavailable,unavailable",
        "Total,1202.00,100.00,unavailable,unavailable,unavailable,unavailable",
    ]
    assert "WXYZ: current value unavailable. No current price for WXYZ.DE." in errors


def test_ambiguous_ticker_is_left_unavailable_without_a_chooser(tmp_path: Path) -> None:
    provider = sample_provider()
    provider.add("EQQB.MI", "EUR", price="401", ranges=ranges_around(EQQB_BUYS))

    code, output, errors = run_cli(str(SAMPLE), provider=provider, settings=tmp_path / "settings.json")

    assert code == 0
    assert output.splitlines()[1] == "EQQB,541.49,100.00,unavailable,unavailable,unavailable,unavailable"
    assert "More than one listing fits EQQB" in errors
    assert "EQQB.DE, EQQB.MI" in errors
    assert not (tmp_path / "settings.json").exists()


def test_chooser_decides_an_ambiguous_ticker_and_the_choice_is_confirmed(tmp_path: Path) -> None:
    provider = sample_provider()
    provider.add("EQQB.MI", "EUR", price="401", ranges=ranges_around(EQQB_BUYS))
    settings = Settings.load(tmp_path / "settings.json")

    report = build_report(SAMPLE, provider, settings, chooser=lambda resolution: "EQQB.MI")

    assert report.valuation.holdings[0].price.symbol == "EQQB.MI"
    saved = Settings.load(tmp_path / "settings.json").ticker_choices["EQQB"]
    assert (saved.symbol, saved.confirmed) == ("EQQB.MI", True)


def test_matched_ticker_is_remembered_so_the_next_run_skips_matching(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    run_cli(str(SAMPLE), provider=sample_provider(), settings=settings_path)

    saved = Settings.load(settings_path).ticker_choices["EQQB"]
    assert (saved.symbol, saved.name, saved.exchange, saved.currency, saved.confirmed) == (
        "EQQB.DE", "Nasdaq fund", "XETRA", "EUR", False,
    )  # fmt: skip

    second = sample_provider()
    code, output, _ = run_cli(str(SAMPLE), provider=second, settings=settings_path)

    assert code == 0
    assert output.splitlines()[1] == "EQQB,541.49,100.00,589.31,100.00,47.82,8.83"
    assert second.calls == [("quote", "EQQB.DE")]


def test_confirmed_choice_is_never_replaced_by_automatic_matching(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "settings.json")
    settings.remember("EQQB", TickerChoice("EQQB.MI", confirmed=True))
    provider = sample_provider()
    provider.add("EQQB.MI", "EUR", price="401")

    report = build_report(SAMPLE, provider, settings)

    assert report.valuation.holdings[0].price.symbol == "EQQB.MI"
    assert settings.remember("EQQB", TickerChoice("EQQB.DE", confirmed=False)) is False
    assert settings.ticker_choices["EQQB"].symbol == "EQQB.MI"


def test_symbol_given_by_the_user_replaces_a_saved_choice(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    provider = sample_provider()
    provider.add("EQQB.MI", "EUR", price="401")
    run_cli(str(SAMPLE), provider=provider, settings=settings_path)

    run_cli(str(SAMPLE), "--symbol", "EQQB=EQQB.MI", provider=provider, settings=settings_path)

    saved = Settings.load(settings_path).ticker_choices["EQQB"]
    assert (saved.symbol, saved.confirmed) == ("EQQB.MI", True)


def test_symbol_that_yahoo_does_not_know_is_not_saved(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"

    code, output, errors = run_cli(
        str(SAMPLE), "--symbol", "EQQB=NOPE.XX", provider=sample_provider(), settings=settings_path
    )

    assert code == 0
    assert output.splitlines()[1] == "EQQB,541.49,100.00,unavailable,unavailable,unavailable,unavailable"
    assert "Yahoo has no data for NOPE.XX" in errors
    assert not settings_path.exists()


def test_unreachable_provider_leaves_values_unavailable(tmp_path: Path) -> None:
    code, output, errors = run_cli(
        str(SAMPLE), provider=FakeProvider(offline=True), settings=tmp_path / "settings.json"
    )

    assert code == 0
    assert output.splitlines()[1] == "EQQB,541.49,100.00,unavailable,unavailable,unavailable,unavailable"
    assert "offline" in errors


def test_last_known_price_is_used_when_yahoo_cannot_be_reached(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    online = sample_provider()
    online.listings["EQQB.DE"].as_of = datetime(2026, 10, 9, 17, 35, tzinfo=UTC)
    build_report(SAMPLE, online, Settings.load(settings_path))

    report = build_report(SAMPLE, FakeProvider(offline=True), Settings.load(settings_path))

    holding = report.valuation.holdings[0]
    assert holding.price is not None and holding.price.last_known
    assert (holding.price.price, holding.price.symbol) == (Decimal("400"), "EQQB.DE")
    assert holding.market_value == Decimal("1.47328346") * 400
    assert report.valuation.uses_last_known_prices
    assert report.valuation.total_market_value is not None
    assert (
        "EQQB: Prices could not be fetched (offline). The last price fetched for EQQB.DE, from 2026-10-09, "
        "is used instead, so this value and the totals are not up to date."
    ) in report.notes


def test_cli_marks_the_time_of_a_last_known_price(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    online = sample_provider()
    online.listings["EQQB.DE"].as_of = datetime(2026, 10, 9, 17, 35, tzinfo=UTC)
    run_cli(str(SAMPLE), provider=online, settings=settings_path)

    code, output, errors = run_cli(
        str(SAMPLE), "--details", provider=FakeProvider(offline=True), settings=settings_path
    )

    assert code == 0
    assert output.splitlines()[1].startswith("EQQB,541.49,100.00,589.31,100.00,47.82,8.83,")
    assert ",2026-10-09T17:35+00:00 (last known)," in output.splitlines()[1]
    assert "is used instead" in errors


def test_a_fresh_price_replaces_the_last_known_one(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    build_report(SAMPLE, sample_provider(), Settings.load(settings_path))
    newer = sample_provider()
    newer.listings["EQQB.DE"].price = Decimal("410")
    build_report(SAMPLE, newer, Settings.load(settings_path))

    report = build_report(SAMPLE, FakeProvider(offline=True), Settings.load(settings_path))

    assert report.valuation.holdings[0].price.price == Decimal("410")


def test_last_known_price_in_another_statement_currency_is_not_used(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    build_report(SAMPLE, sample_provider(), Settings.load(settings_path))
    usd = write_statement(
        tmp_path,
        "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,USD 2000,USD,1",
        "2025-01-06T10:00:00.000Z,EQQB,BUY - MARKET,1,USD 400.00,USD 401,USD,1",
    )

    report = build_report(usd, FakeProvider(offline=True), Settings.load(settings_path))

    assert report.valuation.holdings[0].market_value is None


def test_a_damaged_last_prices_file_is_ignored(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    (tmp_path / "last_prices.json").write_text("{not json", encoding="utf-8")

    report = build_report(SAMPLE, sample_provider(), Settings.load(settings_path))

    assert report.valuation.holdings[0].market_value is not None
    assert "EQQB.DE" in (tmp_path / "last_prices.json").read_text(encoding="utf-8")


def test_price_in_another_currency_is_converted_and_labelled(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.add("EQQB", "USD", price="500")
    provider.add("USDEUR=X", "EUR", price="0.9")

    code, output, errors = run_cli(
        str(SAMPLE), "--symbol", "EQQB=EQQB", provider=provider, settings=tmp_path / "settings.json"
    )

    assert code == 0
    assert output.splitlines()[1] == "EQQB,541.49,100.00,662.98,100.00,121.49,22.44"  # 1.47328346 x 500 x 0.9
    assert "quoted in USD and was converted to EUR" in errors


def test_progress_is_reported_for_each_investment(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")
    provider.add("WXYZ.DE", "EUR", price="100")
    seen: list[tuple[int, int, str]] = []

    build_report(
        write_statement(tmp_path, *TWO_HOLDINGS),
        provider,
        Settings.load(tmp_path / "settings.json"),
        symbol_overrides={"ABCD": "ABCD.DE", "WXYZ": "WXYZ.DE"},
        progress=lambda done, total, text: seen.append((done, total, text)),
    )

    assert seen == [
        (0, 0, "Reading your statement..."),
        (0, 2, "Getting the current price of ABCD (1 of 2)..."),
        (1, 2, "Getting the current price of WXYZ (2 of 2)..."),
        (2, 2, "Adding everything up..."),
    ]


def test_old_latest_price_is_pointed_out(tmp_path: Path) -> None:
    now = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    settings = Settings.load(tmp_path / "settings.json")
    fresh, stale = sample_provider(), FakeProvider()
    fresh.listings["EQQB.DE"].as_of = datetime(2026, 10, 9, 17, 35, tzinfo=UTC)  # Friday close, read on Monday
    stale.add("EQQB.DU", "EUR", price="400", as_of=datetime(2026, 9, 28, 12, 0, tzinfo=UTC))

    fresh_report = build_report(SAMPLE, fresh, settings, now=now)
    stale_report = build_report(SAMPLE, stale, settings, symbol_overrides={"EQQB": "EQQB.DU"}, now=now)

    assert not any("out of date" in note for note in fresh_report.notes)
    assert "EQQB: the latest price Yahoo has for EQQB.DU is from 2026-09-28" in " ".join(stale_report.notes)
    assert stale_report.valuation.holdings[0].market_value is not None


def test_pence_are_converted_to_pounds() -> None:
    assert to_major_units(Decimal("4120"), "GBp") == (Decimal("41.2"), "GBP")
    assert to_major_units(Decimal("4120"), "GBX") == (Decimal("41.2"), "GBP")
    assert to_major_units(Decimal("41.2"), "GBP") == (Decimal("41.2"), "GBP")

    provider = FakeProvider()
    provider.add("GBPEUR=X", "EUR", price="1.2")
    quote = Quote(SymbolInfo("ABCD.L"), Decimal("4000"), "GBp")

    same = price_in_currency(quote, "GBP", provider)
    converted = price_in_currency(quote, "EUR", provider)

    assert (same.price, same.converted) == (Decimal("40"), False)
    assert (converted.price, converted.converted, converted.quoted_currency) == (Decimal("48.0"), True, "GBp")


def test_missing_exchange_rate_makes_the_price_unavailable() -> None:
    quote = Quote(SymbolInfo("ABCD"), Decimal("500"), "USD")

    with pytest.raises(PriceUnavailableError):
        price_in_currency(quote, "EUR", FakeProvider())


def test_cli_explains_a_wrong_file_without_a_stack_trace(tmp_path: Path) -> None:
    statement = write_statement(tmp_path, "2025-01-06,ABCD,1", header="Date,Symbol,Amount")

    code, output, errors = run_cli(str(statement), provider=FakeProvider(), settings=tmp_path / "settings.json")

    assert code == 2
    assert output == ""
    assert "does not look like a Revolut stock statement" in errors
    assert "Found columns: Date, Symbol, Amount" in errors
    assert "Traceback" not in errors


def test_cli_stops_on_an_unknown_type_unless_told_to_ignore_it(tmp_path: Path) -> None:
    statement = write_statement(
        tmp_path, *TWO_HOLDINGS, "2025-02-03T10:00:00.000Z,ABCD,STOCK SPLIT,10,,EUR 0,EUR,1"
    )
    provider = FakeProvider()
    provider.add("ABCD.DE", "EUR", price="120")
    provider.add("WXYZ.DE", "EUR", price="100")
    symbols = ("--symbol", "ABCD=ABCD.DE", "--symbol", "WXYZ=WXYZ.DE")

    code, output, errors = run_cli(str(statement), *symbols, provider=provider, settings=tmp_path / "s.json")
    assert code == 2
    assert output == ""
    assert 'Row 5: the transaction type "STOCK SPLIT"' in errors

    code, output, errors = run_cli(
        str(statement), *symbols, "--ignore-unknown-types", provider=provider, settings=tmp_path / "s.json"
    )
    assert code == 0
    assert len(output.splitlines()) == 4  # header, two holdings, Total
    assert "RESULTS MAY BE WRONG" in errors


def test_cli_rejects_a_malformed_symbol_option(tmp_path: Path) -> None:
    code, _, errors = run_cli(
        str(SAMPLE), "--symbol", "EQQB", provider=sample_provider(), settings=tmp_path / "settings.json"
    )

    assert code == 2
    assert "TICKER=YAHOOSYMBOL" in errors


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("2\n", "EQQB.MI"), ("EQQB.SW\n", "EQQB.SW"), ("\n", None), ("9\n", None), ("", None)],
)
def test_terminal_prompt_accepts_a_number_a_symbol_or_nothing(
    monkeypatch: pytest.MonkeyPatch, typed: str, expected: str | None
) -> None:
    provider = sample_provider()
    provider.add("EQQB.MI", "EUR", price="401", ranges=ranges_around(EQQB_BUYS), exchange="Milan")
    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider)
    monkeypatch.setattr("sys.stdin", io.StringIO(typed))
    shown = io.StringIO()

    assert cli._prompting_chooser(shown)(resolution) == expected
    assert "More than one listing fits EQQB" in shown.getvalue()
    assert "1. EQQB.DE  Nasdaq fund, XETRA, EUR  [2 of 2 of your purchases fit its prices]" in shown.getvalue()
    assert "2. EQQB.MI" in shown.getvalue()


def test_damaged_settings_file_is_explained(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(UserFacingError) as error:
        Settings.load(settings_path)

    assert "saved settings could not be read" in str(error.value)
