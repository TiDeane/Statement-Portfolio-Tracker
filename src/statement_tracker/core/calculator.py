"""Portfolio calculations. Pure functions: no files, no network, no clock."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal

from statement_tracker.core.errors import UnknownTransactionTypeError
from statement_tracker.core.models import (
    ZERO,
    HoldingValuation,
    MarketPrice,
    Portfolio,
    PortfolioValuation,
    Position,
    Statement,
    Transaction,
)
from statement_tracker.core.transactions import (
    PortfolioState,
    TransactionKind,
    TransactionRegistry,
    default_registry,
)

RECONCILIATION_TOLERANCE = Decimal("0.01")
HUNDRED = Decimal(100)


def _in_time_order(statement: Statement) -> list[Transaction]:
    # Stable sort: rows with the same timestamp keep their order in the file.
    return sorted(statement.transactions, key=lambda transaction: transaction.timestamp)


def compute_portfolio(
    statement: Statement,
    registry: TransactionRegistry | None = None,
    ignore_unknown_types: bool = False,
) -> Portfolio:
    """Replay the statement with the average cost method.

    Raises UnknownTransactionTypeError for a Type the registry does not know,
    unless ``ignore_unknown_types`` is set; skipped rows are then listed in the
    portfolio's warnings because the results may be wrong.
    """
    registry = registry or default_registry()
    state = PortfolioState()
    skipped: dict[str, list[int]] = {}

    for transaction in _in_time_order(statement):
        handler = registry.get(transaction.type)
        if handler is None:
            if not ignore_unknown_types:
                raise UnknownTransactionTypeError(transaction.row, transaction.type, registry.known_types())
            skipped.setdefault(transaction.type, []).append(transaction.row)
            continue
        handler.apply(state, transaction)

    tickers = sorted(set(state.positions) | set(state.dividends))
    positions = tuple(
        Position(
            ticker=ticker,
            shares=state.positions[ticker].shares if ticker in state.positions else ZERO,
            cost_basis=state.positions[ticker].cost_basis if ticker in state.positions else ZERO,
            realized_pnl=state.positions[ticker].realized_pnl if ticker in state.positions else ZERO,
            dividends=state.dividends.get(ticker, ZERO),
        )
        for ticker in tickers
    )
    portfolio = Portfolio(
        currency=statement.currency,
        positions=positions,
        dividends_by_ticker=dict(state.dividends),
        net_deposits=state.net_deposits,
        cash=state.cash,
    )

    warnings: list[str] = []
    for type_name, rows in skipped.items():
        row_list = ", ".join(str(row) for row in sorted(rows))
        warnings.append(
            f'RESULTS MAY BE WRONG: ignored {len(rows)} row(s) of unknown type "{type_name}" (rows {row_list}).'
        )
    if portfolio.cash < ZERO:
        warnings.append(
            "The cash derived from the statement is negative, so the statement may be missing deposits."
        )
    if abs(portfolio.reconciliation_difference) > RECONCILIATION_TOLERANCE:
        warnings.append(
            "The numbers in the statement do not add up (invested amount differs from deposits, "
            f"gains, dividends and cash by {portfolio.reconciliation_difference}). Results may be wrong."
        )
    return replace(portfolio, warnings=tuple(warnings))


def buys_by_ticker(
    statement: Statement, registry: TransactionRegistry | None = None
) -> dict[str, list[Transaction]]:
    """Return each ticker's BUY rows in time order, for checking prices against market history."""
    registry = registry or default_registry()
    buys: dict[str, list[Transaction]] = {}
    for transaction in _in_time_order(statement):
        handler = registry.get(transaction.type)
        if handler is not None and handler.kind is TransactionKind.BUY and transaction.ticker:
            buys.setdefault(transaction.ticker, []).append(transaction)
    return buys


def value_portfolio(
    portfolio: Portfolio,
    prices: Mapping[str, MarketPrice],
    unavailable: Mapping[str, str] | None = None,
    leave_out_unpriced: bool = False,
) -> PortfolioValuation:
    """Value the open positions at the given prices (already in the statement currency).

    A ticker missing from ``prices`` is shown as unavailable, with the reason from
    ``unavailable`` when there is one. Totals and shares of the current value need
    every price, so a single missing price leaves them as None: nothing is estimated.
    Shares of the amount invested come from the statement alone and are always there.

    With ``leave_out_unpriced``, holdings without a price are left out of the totals
    instead, and the totals and shares (of the amount invested too) cover the rest.
    Net worth and gain vs deposits still need every value, so they stay None.
    """
    unavailable = unavailable or {}
    open_positions = portfolio.open_positions
    values: dict[str, Decimal] = {
        position.ticker: position.shares * prices[position.ticker].price
        for position in open_positions
        if position.ticker in prices
    }
    complete = len(values) == len(open_positions)
    leaving_out = leave_out_unpriced and not complete and bool(values)
    total = sum(values.values(), ZERO) if complete or leaving_out else None
    left_out = [position for position in open_positions if leaving_out and position.ticker not in values]
    invested = portfolio.total_cost_basis - sum((position.cost_basis for position in left_out), ZERO)

    holdings = []
    for position in open_positions:
        value = values.get(position.ticker)
        in_totals = not leaving_out or value is not None
        unrealized = value - position.cost_basis if value is not None else None
        holdings.append(
            HoldingValuation(
                position=position,
                price=prices.get(position.ticker),
                market_value=value,
                unrealized_pnl=unrealized,
                percent_change=(
                    unrealized / position.cost_basis * HUNDRED
                    if unrealized is not None and position.cost_basis > ZERO
                    else None
                ),
                allocation_percent=(value / total * HUNDRED if value is not None and total else None),
                invested_percent=(
                    position.cost_basis / invested * HUNDRED if in_totals and invested > ZERO else None
                ),
                unavailable_reason=(
                    None if value is not None else unavailable.get(position.ticker, "No price available.")
                ),
                in_totals=in_totals,
            )
        )

    unrealized_total = total - invested if total is not None else None
    net_worth = total + portfolio.cash if total is not None and complete else None
    return PortfolioValuation(
        portfolio=portfolio,
        holdings=tuple(holdings),
        total_market_value=total,
        unrealized_pnl=unrealized_total,
        net_worth=net_worth,
        gain_vs_deposits=net_worth - portfolio.net_deposits if net_worth is not None else None,
    )
