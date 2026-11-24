"""The rows of Home's investments list, as QML shows them: every text already written out."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field, fields
from decimal import Decimal

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPersistentModelIndex, Qt

from statement_tracker.core.models import Position
from statement_tracker.core.models import MarketPrice
from statement_tracker.gui.formatting import day_text, gain, money, share, shares_text
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
    edit_name: str = ""
    """The name to start typing from when renaming: the one shown, unless that is only the ticker."""
    shares: str = ""
    average_cost: str = ""
    """Per share, fees included."""
    price: str = ""
    """Per share, in the statement's currency; "" without one."""
    invested_share: str = ""
    """Its part of what was paid for the investments held."""
    realized: str = ""
    """Gained or lost on sales of it."""
    realized_tone: str = ""
    """"up", "down", or "" when nothing was gained or lost on sales."""
    dividends: str = ""
    sort_values: Mapping[str, Decimal | str | None] = field(default_factory=dict, compare=False)
    """What the table sorts by, per column ("name": the name in lower case); None where there is no value.
    Not shown, so not one of the model's roles."""


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


_SHOWN_FIELDS = [one for one in fields(HoldingRow) if one.name != "sort_values"]
ROLE_NAMES = {Qt.ItemDataRole.UserRole + number: _camel(one.name) for number, one in enumerate(_SHOWN_FIELDS)}
_ROLE_FIELDS = {role: one.name for role, one in zip(ROLE_NAMES, _SHOWN_FIELDS, strict=True)}


def _tone(amount: Decimal) -> str:
    return "up" if amount > 0 else "down" if amount < 0 else ""


def _statement_columns(position: Position, invested_percent: Decimal | None) -> dict[str, object]:
    """What the statement alone tells about an investment: known before any price comes in."""
    average = position.average_cost
    return {
        "shares": shares_text(position.shares),
        "average_cost": money(average) if average is not None else "",
        "invested": money(position.cost_basis),
        "invested_share": share(invested_percent) if invested_percent is not None else "",
        "realized": gain(position.realized_pnl, None),
        "realized_tone": _tone(position.realized_pnl),
        "dividends": money(position.dividends),
    }


def _sort_values(name: str, position: Position, invested_percent: Decimal | None, price: Decimal | None,
                 worth: Decimal | None, allocation: Decimal | None, pnl: Decimal | None) -> dict[str, Decimal | str | None]:
    return {
        "name": name.casefold(),
        "shares": position.shares,
        "average_cost": position.average_cost,
        "price": price,
        "invested": position.cost_basis,
        "worth": worth,
        "share": allocation,
        "invested_share": invested_percent,
        "gain": pnl,
        "realized": position.realized_pnl,
        "dividends": position.dividends,
    }


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
    """Home's rows for a valued portfolio, in the usual order (by ticker)."""
    rows = []
    for holding in report.valuation.holdings:
        ticker = holding.position.ticker
        name, detail = name_and_detail(ticker, settings)
        priced = holding.market_value is not None
        allocation = holding.allocation_percent if holding.in_totals else None
        price = holding.price.price if priced and holding.price is not None else None
        rows.append(
            HoldingRow(
                ticker=ticker,
                name=name,
                detail=detail,
                worth=money(holding.market_value) if priced else "",
                worth_note=worth_note(holding.price) if priced else "",
                share=share(allocation) if allocation is not None else "",
                share_fraction=float(allocation / 100) if allocation is not None else 0.0,
                gain=gain(holding.unrealized_pnl, holding.percent_change) if holding.unrealized_pnl is not None else "",
                gain_up=holding.unrealized_pnl is None or holding.unrealized_pnl >= 0,
                status="priced" if priced else "missing",
                edit_name=settings.index_name(ticker) or "",
                price=money(price) if price is not None else "",
                sort_values=_sort_values(name, holding.position, holding.invested_percent, price,
                                         holding.market_value, allocation, holding.unrealized_pnl),
                **_statement_columns(holding.position, holding.invested_percent),
            )
        )
    return rows


def loading_rows(positions: tuple[Position, ...], settings: Settings) -> list[HoldingRow]:
    """Home's rows while prices are on their way: what was paid is known, the rest is not yet."""
    paid = sum((position.cost_basis for position in positions), Decimal(0))
    rows = []
    for position in positions:
        name, detail = name_and_detail(position.ticker, settings)
        invested_percent = position.cost_basis / paid * 100 if paid > 0 else None
        rows.append(HoldingRow(
            ticker=position.ticker, name=name, detail=detail, worth="", worth_note="", share="", share_fraction=0.0,
            gain="", gain_up=True, status="loading",
            sort_values=_sort_values(name, position, invested_percent, None, None, None, None),
            **_statement_columns(position, invested_percent),
        ))
    return rows


def total_cells(report: Report, tickers: Collection[str], filtered: bool) -> dict[str, object]:
    """The Total row's texts by column, for the investments ``tickers``: all of them, or (``filtered``) those
    the table shows. Amounts cover only what has a value, as the totals do; a filtered Total's shares say
    what part of the whole they are. Shares and the per-share columns are not added up."""
    valuation = report.valuation
    shown = [holding for holding in valuation.holdings if holding.position.ticker in tickers]
    counted = [holding for holding in shown if holding.in_totals]
    invested = sum((holding.position.cost_basis for holding in counted), Decimal(0))
    values = [holding.market_value for holding in counted if holding.market_value is not None]
    worth = sum(values, Decimal(0)) if values else None
    gains = [holding.unrealized_pnl for holding in counted if holding.unrealized_pnl is not None]
    pnl = sum(gains, Decimal(0)) if gains else None
    realized = sum((holding.position.realized_pnl for holding in shown), Decimal(0))
    whole = valuation.total_market_value

    def part(amount: Decimal | None, of: Decimal | None) -> str:
        if not filtered:
            return share(Decimal(100)) if amount else ""
        return f"{share(amount / of * 100)} of all" if amount is not None and of else ""

    invested_shares = [holding.invested_percent for holding in shown if holding.invested_percent is not None]
    return {
        "name": f"Total of the {len(shown)} shown" if filtered else "Total",
        "shares": "",
        "average_cost": "",
        "price": "",
        "invested": money(invested),
        "worth": money(worth) if worth is not None else "",
        "share": part(worth, whole),
        "invested_share": part(sum(invested_shares, Decimal(0)), Decimal(100)) if invested_shares else "",
        "gain": gain(pnl, pnl / invested * 100 if invested > 0 else None) if pnl is not None else "",
        "gain_up": pnl is None or pnl >= 0,
        "realized": gain(realized, None),
        "realized_tone": _tone(realized),
        "dividends": money(sum((holding.position.dividends for holding in shown), Decimal(0))),
    }


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
