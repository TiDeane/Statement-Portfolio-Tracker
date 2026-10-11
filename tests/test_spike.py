"""Phase 0 spike tests. No Qt and no network here."""

from pathlib import Path

import pytest

from statement_tracker import spike

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "revolut_sample.csv"


def test_sample_loads_with_expected_row_count() -> None:
    assert spike.count_statement_rows(SAMPLE) == 18


def test_bundled_sample_path_points_at_the_sample_when_run_from_source() -> None:
    assert spike.bundled_sample_path() == SAMPLE


def test_header_mismatch_names_expected_and_found_columns(tmp_path: Path) -> None:
    statement = tmp_path / "other.csv"
    statement.write_text("Date,Symbol,Amount\n2025-01-01,ABC,1\n", encoding="utf-8")

    with pytest.raises(spike.HeaderMismatchError) as error:
        spike.count_statement_rows(statement)

    assert error.value.found == ("Date", "Symbol", "Amount")
    assert "Price per share" in str(error.value)
    assert "Symbol" in str(error.value)


def test_empty_file_is_a_header_mismatch(tmp_path: Path) -> None:
    statement = tmp_path / "empty.csv"
    statement.write_text("", encoding="utf-8")

    with pytest.raises(spike.HeaderMismatchError):
        spike.count_statement_rows(statement)


def test_heavy_dependencies_import_and_openpyxl_round_trips() -> None:
    assert spike.import_yfinance().version
    assert spike.import_openpyxl().version
    assert spike.openpyxl_roundtrip()
