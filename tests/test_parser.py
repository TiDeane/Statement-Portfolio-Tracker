"""Statement parsing with the revolut_stocks_v1 profile."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fakes import SAMPLE, statement_from, write_statement

from statement_tracker.core.errors import (
    MixedCurrencyError,
    StatementFileError,
    StatementFormatError,
    StatementRowError,
    UserFacingError,
)
from statement_tracker.core.parser import load_statement

BUY = "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,2,EUR 50.00,{total},EUR,1"


def test_sample_parses_completely() -> None:
    statement = load_statement(SAMPLE)

    assert len(statement.transactions) == 18
    assert statement.currency == "EUR"
    assert statement.profile == "revolut_stocks_v1"
    first_buy = statement.transactions[1]
    assert first_buy.row == 3
    assert first_buy.ticker == "EQQB"
    assert first_buy.quantity == Decimal("0.29371219")
    assert first_buy.price_per_share == Decimal("355.45")
    assert first_buy.total_amount == Decimal("104.40")


def test_top_up_has_no_ticker_quantity_or_price() -> None:
    top_up = load_statement(SAMPLE).transactions[0]

    assert (top_up.ticker, top_up.quantity, top_up.price_per_share) == (None, None, None)
    assert top_up.total_amount == Decimal("104.40")


def test_timestamps_with_three_and_six_fractional_digits_are_utc() -> None:
    statement = statement_from(
        "2025-01-06T10:00:00.482913Z,,CASH TOP-UP,,,EUR 10,EUR,1",
        "2025-01-06T10:00:01.460Z,,CASH TOP-UP,,,EUR 10,EUR,1",
    )

    assert statement.transactions[0].timestamp == datetime(2025, 1, 6, 10, 0, 0, 482913, tzinfo=UTC)
    assert statement.transactions[1].timestamp == datetime(2025, 1, 6, 10, 0, 1, 460000, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("EUR 123", "123"), ("EUR 355.45", "355.45"), ("EUR 1,234.56", "1234.56"), ("EUR 1,234,567", "1234567")],
)
def test_amounts_with_thousands_separators_are_parsed_exactly(tmp_path: Path, text: str, expected: str) -> None:
    path = write_statement(tmp_path, BUY.format(total=f'"{text}"'))

    assert load_statement(path).transactions[0].total_amount == Decimal(expected)


@pytest.mark.parametrize("text", ["EUR 1.234,56", "EUR 12,34", "EUR -5.00", "355.45", "EUR", "EUR 1e3", "€ 5.00"])
def test_unreadable_amount_stops_with_the_row_number(tmp_path: Path, text: str) -> None:
    path = write_statement(tmp_path, "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR,1", BUY.format(total=f'"{text}"'))

    with pytest.raises(StatementRowError) as error:
        load_statement(path)

    assert error.value.row == 3
    assert "Row 3" in str(error.value)
    assert "Total Amount" in str(error.value)


def test_header_mismatch_shows_expected_and_found_columns(tmp_path: Path) -> None:
    path = write_statement(tmp_path, "2025-01-06,ABCD,1", header="Date,Symbol,Amount")

    with pytest.raises(StatementFormatError) as error:
        load_statement(path)

    assert error.value.found == ("Date", "Symbol", "Amount")
    assert "Expected columns: Date, Ticker, Type" in str(error.value)
    assert "Found columns: Date, Symbol, Amount" in str(error.value)


def test_empty_file_is_a_header_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(StatementFormatError):
        load_statement(path)


def test_mixed_currencies_stop_with_the_row_number() -> None:
    with pytest.raises(MixedCurrencyError) as error:
        statement_from(
            "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR,1",
            "2025-01-07T09:00:00.000Z,,CASH TOP-UP,,,USD 100,USD,1",
        )

    assert error.value.row == 3
    assert "USD" in str(error.value) and "EUR" in str(error.value)


def test_amount_in_another_currency_than_the_row_is_an_error() -> None:
    with pytest.raises(MixedCurrencyError) as error:
        statement_from("2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,USD 100,EUR,1")

    assert error.value.row == 2


def test_fx_rate_other_than_one_is_an_error() -> None:
    with pytest.raises(MixedCurrencyError) as error:
        statement_from("2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR,1.0842")

    assert error.value.row == 2
    assert "FX Rate" in str(error.value)


def test_fx_rate_written_as_one_point_zero_is_accepted() -> None:
    assert statement_from("2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR,1.00").currency == "EUR"


@pytest.mark.parametrize("date_text", ["06/01/2025 09:00", "2025-01-06T09:00:00", "2025-13-40T09:00:00.000Z", ""])
def test_unreadable_date_stops_with_the_row_number(date_text: str) -> None:
    with pytest.raises(StatementRowError) as error:
        statement_from(f"{date_text},,CASH TOP-UP,,,EUR 100,EUR,1")

    assert error.value.row == 2


def test_row_with_missing_columns_is_an_error() -> None:
    with pytest.raises(StatementRowError) as error:
        statement_from("2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR")

    assert "columns" in str(error.value)


def test_statement_without_rows_is_an_error() -> None:
    with pytest.raises(StatementRowError):
        statement_from()


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = write_statement(tmp_path, "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 100,EUR,1", "", "")

    assert len(load_statement(path).transactions) == 1


def _separated_by(text: str, separator: str) -> str:
    """The statement as Excel saves it with another column separator, as on a computer set to use ";"."""
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out, delimiter=separator, lineterminator="\r\n")
    for row in csv.reader(io.StringIO(text)):
        writer.writerow(row)
    return out.getvalue()


def _dates_rewritten(text: str) -> str:
    """The statement with its dates rewritten the way Excel shows dates: 06/01/2025 10:00."""
    import re

    return re.sub(r"(\d{4})-(\d\d)-(\d\d)T(\d\d:\d\d):\d\d\.\d+Z", r"\3/\2/\1 \4", text)


@pytest.mark.parametrize(
    "saved",
    [
        lambda text: ("\ufeff" + text).encode("utf-8"),  # saved as "CSV UTF-8": an invisible mark at the start
        lambda text: text.replace("\n", "\r\n").encode("utf-8"),  # Windows line endings
        lambda text: ("\ufeff" + text.replace("\n", "\r\n")).encode("utf-8"),
        lambda text: text.encode("cp1252"),  # saved as plain "CSV" on Windows
    ],
    ids=["mark", "line endings", "mark and line endings", "windows encoding"],
)
def test_a_statement_saved_again_without_changing_its_data_is_read_as_usual(tmp_path: Path, saved) -> None:
    # Spec A1: what Excel changes when nothing in the data changed.
    path = tmp_path / "statement.csv"
    path.write_bytes(saved(SAMPLE.read_text(encoding="utf-8")))

    statement = load_statement(path)

    assert statement.transactions == load_statement(SAMPLE).transactions


@pytest.mark.parametrize(
    ("saved", "what"),
    [
        (lambda text: _separated_by(text, ";"), "they are separated by semicolons instead of commas"),
        (lambda text: _separated_by(text, "\t"), "they are separated by tabs instead of commas"),
        (_dates_rewritten, 'Row 2: the date "09/03/2025 13:09" is not in the expected format'),
    ],
    ids=["semicolons", "tabs", "dates"],
)
def test_a_statement_saved_with_another_layout_stops_and_says_what_it_should_look_like(
    tmp_path: Path, saved, what: str
) -> None:
    # Spec A1, A6: nothing is guessed from a changed file; the message says what is wrong and what a
    # statement from Revolut looks like.
    path = tmp_path / "statement.csv"
    path.write_text(saved(SAMPLE.read_text(encoding="utf-8")), encoding="utf-8")

    with pytest.raises(UserFacingError) as error:
        load_statement(path)

    assert what in error.value.what_happened
    advice = error.value.what_to_do
    for looks_like in ("separated by commas", "2025-01-06T10:00:00.000Z", "EUR 1,234.56", "1.47328346"):
        assert looks_like in advice
    assert "export the statement from Revolut again" in advice
    assert "Excel" not in error.value.what_happened + advice  # no guessing at which program it was


def test_missing_file_is_explained(tmp_path: Path) -> None:
    with pytest.raises(StatementFileError) as error:
        load_statement(tmp_path / "nowhere.csv")

    assert "could not be found" in str(error.value)


def test_binary_file_is_explained(tmp_path: Path) -> None:
    path = tmp_path / "statement.csv"
    path.write_bytes(b"\xff\xfe\x00\x01 not text")

    with pytest.raises(StatementFileError):
        load_statement(path)
