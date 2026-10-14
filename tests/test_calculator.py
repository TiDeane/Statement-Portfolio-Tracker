"""Average-cost calculations on synthetic statements and on the sanitized sample."""

from decimal import Decimal

import pytest
from fakes import SAMPLE, statement_from

from statement_tracker.core.calculator import buys_by_ticker, compute_portfolio, value_portfolio
from statement_tracker.core.errors import (
    IncompleteStatementError,
    StatementRowError,
    UnknownTransactionTypeError,
)
from statement_tracker.core.models import MarketPrice
from statement_tracker.core.parser import load_statement
from statement_tracker.core.transactions import TransactionHandler, TransactionKind, default_registry

TOP_UP = "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 2000,EUR,1"
# 10 shares at 100.00 plus a fee of 1: the total, not quantity x price, is the cost.
BUY_WITH_FEE = "2025-01-06T10:00:00.000Z,ABCD,BUY - MARKET,10,EUR 100.00,EUR 1001,EUR,1"


def position(portfolio, ticker):
    return next(item for item in portfolio.positions if item.ticker == ticker)


def test_buy_with_fee_uses_total_amount_as_cost_basis() -> None:
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE))

    holding = position(portfolio, "ABCD")
    assert holding.shares == Decimal(10)
    assert holding.cost_basis == Decimal("1001")
    assert holding.average_cost == Decimal("100.1")
    assert portfolio.cash == Decimal("999")


def test_partial_sell_with_fee_realizes_gain_and_keeps_average_cost() -> None:
    # 4 shares at 120.00 minus a fee of 1: 479 received.
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,4,EUR 120.00,EUR 479,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell))

    holding = position(portfolio, "ABCD")
    assert holding.is_open
    assert holding.shares == Decimal(6)
    assert holding.realized_pnl == Decimal("78.6")  # 479 - 4 x 100.1
    assert holding.cost_basis == Decimal("600.6")
    assert holding.average_cost == Decimal("100.1")
    assert portfolio.cash == Decimal("1478")


def test_full_sell_closes_the_position() -> None:
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,10,EUR 120.00,EUR 1199,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell))

    assert portfolio.open_positions == ()
    closed = position(portfolio, "ABCD")
    assert closed.shares == 0
    assert closed.cost_basis == 0
    assert closed.realized_pnl == Decimal("198")
    assert portfolio.realized_pnl == Decimal("198")


def test_sell_leaving_only_rounding_noise_closes_the_position() -> None:
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,9.9999999,EUR 120.00,EUR 1199,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell))

    assert portfolio.open_positions == ()
    assert position(portfolio, "ABCD").realized_pnl == Decimal("198")
    assert portfolio.reconciliation_difference == 0


def test_buying_again_after_a_full_sell_starts_a_fresh_average() -> None:
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,10,EUR 120.00,EUR 1199,EUR,1"
    rebuy = "2025-03-03T10:00:00.000Z,ABCD,BUY - MARKET,5,EUR 80.00,EUR 401,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell, rebuy))

    holding = position(portfolio, "ABCD")
    assert holding.average_cost == Decimal("80.2")
    assert holding.realized_pnl == Decimal("198")


def test_dividend_counts_as_cash_and_is_recorded_per_ticker() -> None:
    dividend = "2025-02-03T10:00:00.000Z,ABCD,DIVIDEND,,,EUR 3.21,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, dividend))

    assert portfolio.dividends_by_ticker == {"ABCD": Decimal("3.21")}
    assert position(portfolio, "ABCD").dividends == Decimal("3.21")
    assert position(portfolio, "ABCD").cost_basis == Decimal("1001")
    assert portfolio.cash == Decimal("1002.21")


def test_dividend_on_a_closed_ticker_stays_in_the_totals() -> None:
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,10,EUR 120.00,EUR 1199,EUR,1"
    late_dividend = "2025-03-03T10:00:00.000Z,ABCD,DIVIDEND,,,EUR 2.50,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell, late_dividend))

    assert portfolio.open_positions == ()
    assert portfolio.total_dividends == Decimal("2.50")
    assert position(portfolio, "ABCD").dividends == Decimal("2.50")


def test_rows_are_replayed_in_time_order_not_file_order() -> None:
    sell = "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,4,EUR 120.00,EUR 479,EUR,1"
    portfolio = compute_portfolio(statement_from(sell, BUY_WITH_FEE, TOP_UP))

    assert position(portfolio, "ABCD").shares == Decimal(6)


def test_unknown_type_is_an_error_naming_the_row() -> None:
    split = "2025-02-03T10:00:00.000Z,ABCD,STOCK SPLIT,10,,EUR 0,EUR,1"

    with pytest.raises(UnknownTransactionTypeError) as error:
        compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, split))

    assert error.value.row == 4
    assert error.value.type_name == "STOCK SPLIT"
    assert "Row 4" in str(error.value)


def test_unknown_type_can_be_ignored_with_a_prominent_warning() -> None:
    split = "2025-02-03T10:00:00.000Z,ABCD,STOCK SPLIT,10,,EUR 0,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, split), ignore_unknown_types=True)

    assert position(portfolio, "ABCD").shares == Decimal(10)
    assert len(portfolio.warnings) == 1
    assert "RESULTS MAY BE WRONG" in portfolio.warnings[0]
    assert "STOCK SPLIT" in portfolio.warnings[0] and "rows 4" in portfolio.warnings[0]


@pytest.mark.parametrize(
    "sell",
    [
        "2025-02-03T10:00:00.000Z,WXYZ,SELL - MARKET,1,EUR 120.00,EUR 119,EUR,1",
        "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,10.5,EUR 120.00,EUR 1259,EUR,1",
    ],
)
def test_selling_more_than_was_bought_means_the_statement_is_incomplete(sell: str) -> None:
    with pytest.raises(IncompleteStatementError) as error:
        compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, sell))

    assert error.value.row == 4
    assert "full history" in str(error.value)


@pytest.mark.parametrize(
    "row",
    [
        "2025-02-03T10:00:00.000Z,,BUY - MARKET,1,EUR 10.00,EUR 10,EUR,1",
        "2025-02-03T10:00:00.000Z,ABCD,BUY - MARKET,,EUR 10.00,EUR 10,EUR,1",
        "2025-02-03T10:00:00.000Z,ABCD,CASH TOP-UP,,,EUR 10,EUR,1",
        "2025-02-03T10:00:00.000Z,,DIVIDEND,,,EUR 10,EUR,1",
        "2025-02-03T10:00:00.000Z,ABCD,DIVIDEND,3,,EUR 10,EUR,1",
    ],
)
def test_rows_that_do_not_fit_their_type_are_errors(row: str) -> None:
    with pytest.raises(StatementRowError) as error:
        compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, row))

    assert error.value.row == 4


def test_negative_cash_gives_a_warning() -> None:
    portfolio = compute_portfolio(statement_from(BUY_WITH_FEE))

    assert portfolio.cash == Decimal("-1001")
    assert any("negative" in warning for warning in portfolio.warnings)


def test_reconciliation_holds_for_a_mixed_statement() -> None:
    portfolio = compute_portfolio(
        statement_from(
            TOP_UP,
            BUY_WITH_FEE,
            "2025-01-20T10:00:00.000Z,WXYZ,BUY - MARKET,3.3333,EUR 30.00,EUR 101,EUR,1",
            "2025-02-03T10:00:00.000Z,ABCD,SELL - MARKET,3.7,EUR 120.00,EUR 443,EUR,1",
            "2025-02-10T10:00:00.000Z,WXYZ,DIVIDEND,,,EUR 0.77,EUR,1",
        )
    )

    assert abs(portfolio.reconciliation_difference) < Decimal("0.0000001")
    assert portfolio.warnings == ()


def test_reconciliation_warns_when_the_numbers_do_not_add_up() -> None:
    registry = default_registry()

    def take_cash(state, transaction) -> None:
        state.positions["ABCD"].cost_basis += transaction.total_amount  # deliberately inconsistent

    registry.register("BROKEN", TransactionHandler(TransactionKind.BUY, take_cash))
    broken = "2025-02-03T10:00:00.000Z,ABCD,BROKEN,,,EUR 5,EUR,1"
    portfolio = compute_portfolio(statement_from(TOP_UP, BUY_WITH_FEE, broken), registry)

    assert portfolio.reconciliation_difference == Decimal(5)
    assert any("do not add up" in warning for warning in portfolio.warnings)


def test_sample_matches_the_hand_computed_values() -> None:
    portfolio = compute_portfolio(load_statement(SAMPLE))

    assert portfolio.currency == "EUR"
    assert portfolio.net_deposits == Decimal("996.56")
    assert portfolio.cash == Decimal("504.76")
    assert portfolio.total_dividends == Decimal("3.86")
    assert portfolio.dividends_by_ticker == {"IUSA": Decimal("3.86")}
    assert portfolio.realized_pnl == Decimal("45.83")
    assert portfolio.reconciliation_difference == 0
    assert portfolio.warnings == ()

    (eqqb,) = portfolio.open_positions
    assert eqqb.ticker == "EQQB"
    assert eqqb.shares == Decimal("1.47328346")
    assert eqqb.cost_basis == Decimal("541.49")

    (iusa,) = portfolio.closed_positions
    assert iusa.ticker == "IUSA"
    assert iusa.realized_pnl == Decimal("45.83")
    assert iusa.dividends == Decimal("3.86")


def test_buys_by_ticker_lists_only_buy_rows_in_time_order() -> None:
    buys = buys_by_ticker(load_statement(SAMPLE))

    assert [buy.row for buy in buys["EQQB"]] == [3, 18]
    assert [buy.row for buy in buys["IUSA"]] == [5, 8, 10, 14]


def _two_holdings():
    return compute_portfolio(
        statement_from(
            TOP_UP,
            BUY_WITH_FEE,
            "2025-01-20T10:00:00.000Z,WXYZ,BUY - MARKET,4,EUR 50.00,EUR 201,EUR,1",
        )
    )


def test_valuation_gives_values_allocation_and_totals() -> None:
    prices = {
        "ABCD": MarketPrice(Decimal("120"), "ABCD.DE", "EUR"),
        "WXYZ": MarketPrice(Decimal("100"), "WXYZ.DE", "EUR"),
    }
    valuation = value_portfolio(_two_holdings(), prices)

    abcd, wxyz = valuation.holdings
    assert abcd.market_value == Decimal("1200")
    assert abcd.unrealized_pnl == Decimal("199")
    assert abcd.allocation_percent == Decimal("75")
    assert wxyz.market_value == Decimal("400")
    assert wxyz.allocation_percent == Decimal("25")
    assert abcd.invested_percent == Decimal("1001") / Decimal("1202") * 100
    assert abcd.invested_percent + wxyz.invested_percent == Decimal("100")
    assert wxyz.percent_change == Decimal("199") / Decimal("201") * 100
    assert valuation.total_market_value == Decimal("1600")
    assert valuation.unrealized_pnl == Decimal("398")
    assert valuation.net_worth == Decimal("2398")  # 1600 + cash 798
    assert valuation.gain_vs_deposits == Decimal("398")


def test_holdings_without_a_price_are_left_out_of_the_totals_and_nothing_is_estimated() -> None:
    prices = {"ABCD": MarketPrice(Decimal("120"), "ABCD.DE", "EUR")}
    valuation = value_portfolio(_two_holdings(), prices, {"WXYZ": "Yahoo has no data."})

    abcd, wxyz = valuation.holdings
    assert (abcd.in_totals, wxyz.in_totals) == (True, False)
    assert valuation.left_out == (wxyz,)
    assert wxyz.unavailable_reason == "Yahoo has no data."
    # The totals and shares cover ABCD alone.
    assert valuation.invested_in_totals == Decimal("1001")
    assert valuation.total_market_value == Decimal("1200")
    assert valuation.unrealized_pnl == Decimal("199")
    assert abcd.allocation_percent == Decimal("100") and abcd.invested_percent == Decimal("100")
    assert wxyz.invested_percent is None and wxyz.allocation_percent is None and wxyz.market_value is None
    # Net worth needs every value: still nothing estimated.
    assert valuation.net_worth is None and valuation.gain_vs_deposits is None


def test_without_any_price_the_totals_are_unavailable() -> None:
    nothing = value_portfolio(_two_holdings(), {})

    assert nothing.total_market_value is None and nothing.net_worth is None and nothing.left_out == ()
