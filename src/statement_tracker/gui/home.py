"""Home: the investments with today's prices, the statement they come from and the spreadsheet.
Exposed to QML as ``session.home``; every text is written out here."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from statement_tracker.gui.formatting import day_text, gain, money, time_text
from statement_tracker.gui.holdings_model import HoldingsModel, holding_rows, loading_rows, name_and_detail, total_row

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.gui.welcome import NEW_SPREADSHEET_NAME, SPREADSHEET_FILES, STATEMENT_FILES
from statement_tracker.workflow import Report, update_spreadsheet

if TYPE_CHECKING:
    from statement_tracker.gui.session import Session

UNAVAILABLE = "unavailable"
BACKUPS_OFF = "No backup copy will be made before it is changed: backups are turned off in Settings."


def listed(names: list[str]) -> str:
    """"A", "A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def result_lines(report: Report, exported: ExportResult) -> list[str]:
    """What the spreadsheet card says an update did, line by line."""
    lines = []
    if exported.holdings_written:
        investments = "1 investment" if exported.holdings_written == 1 else f"{exported.holdings_written} investments"
        lines.append(f"Current Holdings: {investments} and the Total.")
    else:
        lines.append("Current Holdings: no investments you still hold.")
    valuation = report.valuation
    if exported.history == "skipped":
        if valuation.total_market_value is None:
            why = "no investment has a current value"
        elif valuation.uses_last_known_prices:
            why = "some prices are from an earlier day: Yahoo Finance could not be reached"
        else:
            why = "a value you entered is from an earlier day"
        lines.append(f"Portfolio History: no row for today, because {why}.")
    else:
        history = f"Portfolio History: today's row was {exported.history}"
        left_out = [holding.position.ticker for holding in valuation.left_out]
        if left_out:
            history += f". It leaves out {listed(left_out)}, which {'has' if len(left_out) == 1 else 'have'} no value"
        lines.append(history + ".")
    if exported.backup:
        lines.append(f"Backup copy of the file as it was before today's first update: {exported.backup}")
    return lines


class Home(QObject):
    """What Home shows, worked out from the session's report and run."""

    changed = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._session = session
        self._holdings = HoldingsModel(self)
        self._progress = (0, 0, "")
        self._sheet_result = ""
        """What the last update of the spreadsheet did: "", "ok" or "error"."""
        self._sheet_title = ""
        self._sheet_lines: list[str] = []
        self._sheet_details = ""
        self._updated_at: datetime | None = None
        self._updated_on = None
        """The day of the last successful update, by the same calendar the update itself used."""
        session.reportChanged.connect(self._clear_sheet_result)
        session.reportChanged.connect(self._update)
        session.settingsChanged.connect(self._update)
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

    # -- the spreadsheet card -------------------------------------------------------

    def _sheet(self) -> Path | None:
        return self._session.settings.spreadsheet_path

    def _get_sheet_line(self) -> str:
        sheet = self._sheet()
        if sheet is None:
            return ""
        if self._sheet_result == "error":
            return "Not updated today"
        if self._updated_at is not None and self._updated_on == self._session.today():
            return f"Updated today at {time_text(self._updated_at)}"
        if self._session.busy:
            return "Ready once today's prices are in"
        if not sheet.exists():
            return "It doesn't exist yet: updating creates it."
        changed = datetime.fromtimestamp(sheet.stat().st_mtime, UTC).astimezone().date()
        return f"Last changed {day_text(changed)}"

    hasSpreadsheet = Property(bool, lambda self: self._sheet() is not None, notify=changed)
    sheetName = Property(str, lambda self: self._sheet().name if self._sheet() else "", notify=changed)
    sheetLine = Property(str, _get_sheet_line, notify=changed)
    sheetButton = Property(str, lambda self: "Try again" if self._sheet_result == "error" else "Update my spreadsheet", notify=changed)
    canUpdate = Property(bool, lambda self: not self._session.busy and self._session.report is not None, notify=changed)
    sheetResult = Property(str, lambda self: self._sheet_result, notify=changed)
    sheetResultTitle = Property(str, lambda self: self._sheet_title, notify=changed)
    sheetResultLines = Property(list, lambda self: self._sheet_lines, notify=changed)
    sheetHasDetails = Property(bool, lambda self: self._sheet_details != "", notify=changed)
    backupsOff = Property(
        str, lambda self: BACKUPS_OFF if self._sheet() is not None and self._session.settings.backups_kept == 0 else "",
        notify=changed,
    )

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
    def updateSpreadsheet(self) -> None:
        """Write the values shown to the spreadsheet, without fetching again, and say what was done."""
        report, sheet = self._session.report, self._sheet()
        if report is None or sheet is None or self._session.busy:
            return
        try:
            exported = update_spreadsheet(report, self._session.settings, sheet, self._session.today())
        except UserFacingError as error:
            self._sheet_result, self._sheet_title = "error", "Your spreadsheet wasn't updated"
            self._sheet_lines, self._sheet_details = [error.what_happened, error.what_to_do], error.details
        else:
            self._sheet_result = "ok"
            self._sheet_title = "Your spreadsheet was created" if exported.created else "Your spreadsheet is up to date"
            self._sheet_lines, self._sheet_details = result_lines(report, exported), ""
            self._updated_at, self._updated_on = self._session.now(), self._session.today()
        self.changed.emit()

    @Slot()
    def openFolder(self) -> None:
        sheet = self._sheet()
        if sheet is not None:
            self._session.show_in_folder(sheet)

    @Slot()
    def copyDetails(self) -> None:
        self._session.copyText(self._sheet_details)

    @Slot()
    def chooseSpreadsheet(self) -> None:
        start = self._sheet().parent if self._sheet() else self._session.start_folder()
        chosen = self._session.ask_open_file("Choose your Excel spreadsheet", SPREADSHEET_FILES, start)
        if chosen is not None:
            self._session.use_spreadsheet(chosen)

    @Slot()
    def createSpreadsheet(self) -> None:
        start = self._sheet().parent if self._sheet() else self._session.start_folder()
        chosen = self._session.ask_save_file("Where should the new spreadsheet be saved?", start / NEW_SPREADSHEET_NAME)
        if chosen is not None:
            self._session.use_spreadsheet(chosen if chosen.suffix.lower() == ".xlsx" else chosen.with_name(chosen.name + ".xlsx"))

    def _clear_sheet_result(self) -> None:
        """New values: what an earlier update wrote is not what is shown any more."""
        self._sheet_result, self._sheet_title, self._sheet_lines, self._sheet_details = "", "", [], ""

    @Slot()
    def chooseStatement(self) -> None:
        """Use a newer statement, picked in the file chooser."""
        chosen = self._session.ask_open_file("Choose your Revolut statement", STATEMENT_FILES, self._session.start_folder())
        if chosen is not None:
            self._session.use_statement(chosen)
