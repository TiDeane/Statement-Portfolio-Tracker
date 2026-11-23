"""Home: the investments with today's prices, the statement they come from and the spreadsheet.
Exposed to QML as ``session.home``; every text is written out here."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from statement_tracker.gui.formatting import day_text, gain, money, time_text
from statement_tracker.gui.holdings_model import HoldingsModel, holding_rows, loading_rows, name_and_detail, total_row

from statement_tracker.gui.welcome import STATEMENT_FILES

if TYPE_CHECKING:
    from statement_tracker.gui.session import Session

UNAVAILABLE = "unavailable"


def listed(names: list[str]) -> str:
    """"A", "A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


class Home(QObject):
    """What Home shows, worked out from the session's report and run."""

    changed = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._session = session
        self._holdings = HoldingsModel(self)
        self._progress = (0, 0, "")
        session.reportChanged.connect(self._update)
        session.busyChanged.connect(self._update)
        session.progressed.connect(self._show_progress)

    # -- what is shown -------------------------------------------------------------

    def _report(self):
        return None if self._session.busy else self._session.report

    def _get_busy(self) -> bool:
        return self._session.busy

    def _get_progress_text(self) -> str:
        return self._progress[2]

    def _get_progress_fraction(self) -> float:
        done, total, _ = self._progress
        return done / total if total else 0.0

    def _get_worth(self) -> str:
        report = self._report()
        if report is None:
            return ""
        worth = report.valuation.total_market_value
        return money(worth) if worth is not None else UNAVAILABLE

    def _get_currency(self) -> str:
        report = self._report()
        return report.statement.currency if report else self._session.loading_currency

    def _get_gain(self) -> str:
        report = self._report()
        if report is None or report.valuation.unrealized_pnl is None:
            return ""
        pnl, invested = report.valuation.unrealized_pnl, report.valuation.invested_in_totals
        return gain(pnl, pnl / invested * 100 if invested > 0 else None)

    def _get_gain_up(self) -> bool:
        report = self._report()
        return report is None or report.valuation.unrealized_pnl is None or report.valuation.unrealized_pnl >= 0

    def _get_invested(self) -> str:
        """What was paid: known from the statement already while prices come in."""
        report = self._report()
        if report is not None:
            return money(report.valuation.invested_in_totals)
        positions = self._session.loading_positions
        return money(sum((position.cost_basis for position in positions), Decimal(0))) if positions else ""

    def _get_count(self) -> str:
        report = self._session.report
        positions = self._session.loading_positions if self._session.busy or report is None else report.valuation.holdings
        return str(len(positions))

    def _get_prices_line(self) -> str:
        report = self._report()
        if report is None or self._session.fetched_at is None:
            return ""
        return f"Today's prices from Yahoo Finance, {time_text(self._session.fetched_at)}"

    def _get_left_out_line(self) -> str:
        report = self._report()
        if report is None or not report.valuation.left_out:
            return ""
        settings = self._session.settings
        names = [name_and_detail(holding.position.ticker, settings)[0] for holding in report.valuation.left_out]
        if len(names) == 1:
            return f"{names[0]} has no price today, so these totals leave it out."
        return f"{listed(names)} have no price today, so these totals leave them out."

    def _get_total_row(self) -> list[str]:
        report = self._report()
        return total_row(report) if report and report.valuation.holdings else []

    def _get_statement_line(self) -> str:
        latest = self._session.statement_latest
        return f"Latest transaction {day_text(latest)}. Anything after it isn't included." if latest else ""

    busy = Property(bool, _get_busy, notify=changed)
    statementLine = Property(str, _get_statement_line, notify=changed)
    hasReport = Property(bool, lambda self: self._report() is not None, notify=changed)
    progressText = Property(str, _get_progress_text, notify=changed)
    progressFraction = Property(float, _get_progress_fraction, notify=changed)
    worthNow = Property(str, _get_worth, notify=changed)
    currency = Property(str, _get_currency, notify=changed)
    gainText = Property(str, _get_gain, notify=changed)
    gainUp = Property(bool, _get_gain_up, notify=changed)
    invested = Property(str, _get_invested, notify=changed)
    count = Property(str, _get_count, notify=changed)
    pricesLine = Property(str, _get_prices_line, notify=changed)
    leftOutLine = Property(str, _get_left_out_line, notify=changed)
    totalRow = Property(list, _get_total_row, notify=changed)
    holdings = Property(QObject, lambda self: self._holdings, constant=True)

    # -- updating ------------------------------------------------------------------

    def _update(self) -> None:
        report = self._report()
        if report is not None:
            self._holdings.set_rows(holding_rows(report, self._session.settings))
        else:
            self._holdings.set_rows(loading_rows(self._session.loading_positions, self._session.settings))
        if not self._session.busy:
            self._progress = (0, 0, "")
        self.changed.emit()

    def _show_progress(self, done: int, total: int, text: str) -> None:
        if self._session.busy:
            self._progress = (done, total, text)
            self.changed.emit()

    # -- actions -------------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Fetch today's prices again."""
        self._session.refresh()

    @Slot()
    def chooseStatement(self) -> None:
        """Use a newer statement, picked in the file chooser."""
        chosen = self._session.ask_open_file("Choose your Revolut statement", STATEMENT_FILES, self._session.start_folder())
        if chosen is not None:
            self._session.use_statement(chosen)
