"""The rows of Home's investments list, as QML shows them: every text already written out."""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPersistentModelIndex, Qt

from statement_tracker.core.models import Position
from statement_tracker.core.models import MarketPrice
from statement_tracker.gui.formatting import day_text, gain, money, share
from statement_tracker.settings import Settings
from statement_tracker.workflow import Report


@dataclass(frozen=True)
class HoldingRow:
    """One investment as Home's list shows it."""

    ticker: str
    name: str
    detail: str
    """"TICKER · exchange", or what of it is known."""
    invested: str
    worth: str
    worth_note: str
    """Under the value: "" for today's price, "price from <date>" or "your value"."""
    share: str
    share_fraction: float
    """The share of the total as 0 to 1, for its bar."""
    gain: str
    gain_up: bool
    status: str
    """"priced", "missing" (no value, left out of the totals) or "loading" (prices on their way)."""


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


ROLE_NAMES = {Qt.ItemDataRole.UserRole + number: _camel(field.name) for number, field in enumerate(fields(HoldingRow))}
_ROLE_FIELDS = {role: field.name for role, field in zip(ROLE_NAMES, fields(HoldingRow), strict=True)}


def name_and_detail(ticker: str, settings: Settings) -> tuple[str, str]:
    """The name shown first (the user's own, else Yahoo's, else the ticker) and the line under it."""
    name = settings.index_name(ticker)
    choice = settings.ticker_choices.get(ticker)
    exchange = choice.exchange if choice else None
    if not name:
        return ticker, exchange or ""
    return name, f"{ticker} · {exchange}" if exchange else ticker


def worth_note(price: MarketPrice | None) -> str:
    """What is written under a value that is not today's from Yahoo."""
    if price is None:
        return ""
    if price.entered:
        return "your value"
    if price.last_known:
        return f"price from {day_text(price.as_of.date())}" if price.as_of else "price from an earlier day"
    return ""


def holding_rows(report: Report, settings: Settings) -> list[HoldingRow]:
    """Home's rows for a valued portfolio, in statement order."""
    rows = []
    for holding in report.valuation.holdings:
        ticker = holding.position.ticker
        name, detail = name_and_detail(ticker, settings)
        priced = holding.market_value is not None
        allocation = holding.allocation_percent if holding.in_totals else None
        rows.append(
            HoldingRow(
                ticker=ticker,
                name=name,
                detail=detail,
                invested=money(holding.position.cost_basis),
                worth=money(holding.market_value) if priced else "",
                worth_note=worth_note(holding.price) if priced else "",
                share=share(allocation) if allocation is not None else "",
                share_fraction=float(allocation / 100) if allocation is not None else 0.0,
                gain=gain(holding.unrealized_pnl, holding.percent_change) if holding.unrealized_pnl is not None else "",
                gain_up=holding.unrealized_pnl is None or holding.unrealized_pnl >= 0,
                status="priced" if priced else "missing",
            )
        )
    return rows


def loading_rows(positions: tuple[Position, ...], settings: Settings) -> list[HoldingRow]:
    """Home's rows while prices are on their way: what was paid is known, the rest is not yet."""
    rows = []
    for position in positions:
        name, detail = name_and_detail(position.ticker, settings)
        rows.append(HoldingRow(position.ticker, name, detail, money(position.cost_basis), "", "", "", 0.0, "", True, "loading"))
    return rows


def total_row(report: Report) -> list[str]:
    """The Total row's texts: covering only what has a value, as the totals do."""
    valuation = report.valuation
    invested = valuation.invested_in_totals
    worth = valuation.total_market_value
    pnl = valuation.unrealized_pnl
    change = pnl / invested * 100 if pnl is not None and invested > 0 else None
    return [
        "Total",
        money(invested),
        money(worth) if worth is not None else "",
        share(Decimal(100)) if worth else "",
        gain(pnl, change) if pnl is not None else "",
    ]


class HoldingsModel(QAbstractListModel):
    """Home's list of investments."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[HoldingRow] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role not in _ROLE_FIELDS:
            return None
        return getattr(self._rows[index.row()], _ROLE_FIELDS[role])

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in ROLE_NAMES.items()}

    def set_rows(self, rows: list[HoldingRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    @property
    def rows(self) -> list[HoldingRow]:
        return list(self._rows)
