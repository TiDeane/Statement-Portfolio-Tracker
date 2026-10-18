"""Each sample in samples/ does what samples/README.md says it is for. No network."""

from decimal import Decimal

import pytest
from fakes import SAMPLES

from statement_tracker.core.calculator import compute_portfolio
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.parser import load_statement


def test_every_sample_is_listed_in_the_samples_readme() -> None:
    listed = (SAMPLES / "README.md").read_text(encoding="utf-8")

    assert {path.name for path in SAMPLES.glob("*.csv")} == {
        "revolut_sample.csv", "long_history.csv", "unpriced_investment.csv", "unknown_type.csv",
        "incomplete_history.csv",
    }  # fmt: skip
    for path in SAMPLES.glob("*.csv"):
        assert f"`{path.name}`" in listed


def test_long_history_holds_five_funds_after_selling_and_buying_again() -> None:
    portfolio = compute_portfolio(load_statement(SAMPLES / "long_history.csv"))

    assert sorted(position.ticker for position in portfolio.open_positions) == ["EQQB", "IUSA", "SXR8", "VUAA", "VWCE"]
    assert portfolio.realized_pnl != 0 and portfolio.total_dividends > 0
    assert Decimal(0) < portfolio.cash < portfolio.net_deposits  # most of the money is invested
    assert abs(portfolio.reconciliation_difference) < Decimal("0.000001") and portfolio.warnings == ()
    rows = (SAMPLES / "long_history.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) > 150 and rows[1].startswith("2022-01") and rows[-1].startswith("2025-")


def test_unpriced_investment_has_two_investments() -> None:
    portfolio = compute_portfolio(load_statement(SAMPLES / "unpriced_investment.csv"))

    assert [position.ticker for position in portfolio.open_positions] == ["EQQB", "ZQXJ"]
    assert portfolio.warnings == ()


@pytest.mark.parametrize(
    ("name", "words"),
    [
        ("unknown_type.csv", ("Row 4", "STOCK SPLIT")),
        ("incomplete_history.csv", ("Row 4", "full history")),
    ],
)
def test_samples_with_a_problem_stop_with_a_message_naming_the_row(name: str, words: tuple[str, ...]) -> None:
    with pytest.raises(UserFacingError) as error:
        compute_portfolio(load_statement(SAMPLES / name))

    for word in words:
        assert word in str(error.value)
