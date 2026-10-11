"""Transaction types: a registry from the statement's Type text to the code that applies it.

An unknown Type is never guessed. It is an error unless the caller chose to ignore unknown types.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from statement_tracker.core.errors import IncompleteStatementError, StatementRowError
from statement_tracker.core.models import ZERO, Transaction

SHARE_TOLERANCE = Decimal("0.000001")
"""Shares left over below this are rounding noise: the position counts as closed."""

_REPORT = "If the file came straight from Revolut, please report this so it can be supported."


class TransactionKind(Enum):
    """What a transaction type means, independent of how a statement spells it."""

    DEPOSIT = "deposit"
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"


@dataclass
class PositionState:
    """Running totals for one ticker while the statement is replayed."""

    shares: Decimal = ZERO
    cost_basis: Decimal = ZERO
    realized_pnl: Decimal = ZERO


@dataclass
class PortfolioState:
    """Running totals for the whole statement while it is replayed."""

    positions: dict[str, PositionState] = field(default_factory=dict)
    dividends: dict[str, Decimal] = field(default_factory=dict)
    net_deposits: Decimal = ZERO
    cash: Decimal = ZERO


@dataclass(frozen=True)
class TransactionHandler:
    """How one transaction type changes the portfolio."""

    kind: TransactionKind
    apply: Callable[[PortfolioState, Transaction], None]


class TransactionRegistry:
    """Maps a statement's Type text (e.g. ``BUY - MARKET``) to its handler."""

    def __init__(self) -> None:
        self._handlers: dict[str, TransactionHandler] = {}

    def register(self, type_name: str, handler: TransactionHandler) -> None:
        """Teach the registry a Type. A new statement format may register its own spellings."""
        self._handlers[type_name] = handler

    def get(self, type_name: str) -> TransactionHandler | None:
        """Return the handler for a Type, or None if the Type is unknown."""
        return self._handlers.get(type_name)

    def known_types(self) -> tuple[str, ...]:
        """Return the Types this registry understands."""
        return tuple(self._handlers)


def _require_empty(transaction: Transaction, *columns: str) -> None:
    values = {
        "Ticker": transaction.ticker,
        "Quantity": transaction.quantity,
        "Price per share": transaction.price_per_share,
    }
    for column in columns:
        if values[column] is not None:
            raise StatementRowError(
                transaction.row,
                f'a "{transaction.type}" row is expected to have an empty {column} column.',
                _REPORT,
            )


def _require_ticker(transaction: Transaction) -> str:
    if not transaction.ticker:
        raise StatementRowError(
            transaction.row, f'a "{transaction.type}" row needs a Ticker, but it is empty.', _REPORT
        )
    return transaction.ticker


def _require_quantity(transaction: Transaction) -> Decimal:
    if transaction.quantity is None or transaction.quantity <= ZERO:
        raise StatementRowError(
            transaction.row, f'a "{transaction.type}" row needs a Quantity above zero.', _REPORT
        )
    return transaction.quantity


def _apply_deposit(state: PortfolioState, transaction: Transaction) -> None:
    _require_empty(transaction, "Ticker", "Quantity", "Price per share")
    state.net_deposits += transaction.total_amount
    state.cash += transaction.total_amount


def _apply_buy(state: PortfolioState, transaction: Transaction) -> None:
    ticker = _require_ticker(transaction)
    quantity = _require_quantity(transaction)
    position = state.positions.setdefault(ticker, PositionState())
    # Total Amount already includes any fee, so the fee becomes part of the cost.
    position.shares += quantity
    position.cost_basis += transaction.total_amount
    state.cash -= transaction.total_amount


def _apply_sell(state: PortfolioState, transaction: Transaction) -> None:
    ticker = _require_ticker(transaction)
    quantity = _require_quantity(transaction)
    position = state.positions.get(ticker)
    held = position.shares if position else ZERO
    if position is None or quantity > held + SHARE_TOLERANCE:
        raise IncompleteStatementError(transaction.row, ticker)

    remaining = held - quantity
    if remaining <= SHARE_TOLERANCE:
        cost_of_sold = position.cost_basis
        remaining = ZERO
    else:
        cost_of_sold = position.cost_basis * quantity / held
    # Total Amount is what was received, fee already taken off.
    position.realized_pnl += transaction.total_amount - cost_of_sold
    position.cost_basis -= cost_of_sold
    position.shares = remaining
    state.cash += transaction.total_amount


def _apply_dividend(state: PortfolioState, transaction: Transaction) -> None:
    ticker = _require_ticker(transaction)
    _require_empty(transaction, "Quantity", "Price per share")
    # Kept apart from positions so dividends of sold tickers are never dropped.
    state.dividends[ticker] = state.dividends.get(ticker, ZERO) + transaction.total_amount
    state.cash += transaction.total_amount


def default_registry() -> TransactionRegistry:
    """Return a registry with the transaction types verified in real statements."""
    registry = TransactionRegistry()
    registry.register("CASH TOP-UP", TransactionHandler(TransactionKind.DEPOSIT, _apply_deposit))
    registry.register("BUY - MARKET", TransactionHandler(TransactionKind.BUY, _apply_buy))
    registry.register("SELL - MARKET", TransactionHandler(TransactionKind.SELL, _apply_sell))
    registry.register("DIVIDEND", TransactionHandler(TransactionKind.DIVIDEND, _apply_dividend))
    return registry
