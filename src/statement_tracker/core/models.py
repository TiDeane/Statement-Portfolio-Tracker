"""Data shared by the parser, the calculator and the user interfaces. All money is Decimal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class Transaction:
    """One statement row, parsed but not yet interpreted."""

    row: int
    timestamp: datetime
    type: str
    ticker: str | None
    quantity: Decimal | None
    price_per_share: Decimal | None
    total_amount: Decimal
    currency: str


@dataclass(frozen=True)
class Statement:
    """A parsed statement in a single currency."""

    transactions: tuple[Transaction, ...]
    currency: str
    profile: str


@dataclass(frozen=True)
class Position:
    """What the statement says about one ticker."""

    ticker: str
    shares: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal
    dividends: Decimal

    @property
    def is_open(self) -> bool:
        """True while shares are still held."""
        return self.shares > ZERO

    @property
    def average_cost(self) -> Decimal | None:
        """Average cost per share, fees included; None for a closed position."""
        return self.cost_basis / self.shares if self.is_open else None


@dataclass(frozen=True)
class Portfolio:
    """Everything that can be derived from the statement alone, without prices."""

    currency: str
    positions: tuple[Position, ...]
    dividends_by_ticker: Mapping[str, Decimal]
    net_deposits: Decimal
    cash: Decimal
    warnings: tuple[str, ...] = ()

    @property
    def open_positions(self) -> tuple[Position, ...]:
        """Positions that still hold shares."""
        return tuple(position for position in self.positions if position.is_open)

    @property
    def closed_positions(self) -> tuple[Position, ...]:
        """Positions that were sold completely."""
        return tuple(position for position in self.positions if not position.is_open)

    @property
    def total_cost_basis(self) -> Decimal:
        """Cost basis of the open positions."""
        return sum((position.cost_basis for position in self.positions), ZERO)

    @property
    def realized_pnl(self) -> Decimal:
        """Realized gain or loss over all tickers, open or closed."""
        return sum((position.realized_pnl for position in self.positions), ZERO)

    @property
    def total_dividends(self) -> Decimal:
        """Dividends over all tickers, including closed ones."""
        return sum(self.dividends_by_ticker.values(), ZERO)

    @property
    def reconciliation_difference(self) -> Decimal:
        """Zero when: cost basis = net deposits + realized PnL + dividends - cash."""
        expected = self.net_deposits + self.realized_pnl + self.total_dividends - self.cash
        return self.total_cost_basis - expected


@dataclass(frozen=True)
class MarketPrice:
    """A price per share expressed in the statement currency."""

    price: Decimal
    symbol: str
    quoted_currency: str
    converted: bool = False
    as_of: datetime | None = None


@dataclass(frozen=True)
class HoldingValuation:
    """An open position with its current price, where one is available."""

    position: Position
    price: MarketPrice | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    percent_change: Decimal | None
    allocation_percent: Decimal | None
    """Share of the total current value; None unless every holding has a price."""
    invested_percent: Decimal | None = None
    """Share of the total amount invested in open holdings; needs no prices."""
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class PortfolioValuation:
    """Open holdings valued at current prices. Totals are None if any price is missing."""

    portfolio: Portfolio
    holdings: tuple[HoldingValuation, ...]
    total_market_value: Decimal | None
    unrealized_pnl: Decimal | None
    net_worth: Decimal | None
    gain_vs_deposits: Decimal | None
