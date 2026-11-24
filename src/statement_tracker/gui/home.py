"""Home: the investments with today's prices, the statement they come from and the spreadsheet.
Exposed to QML as ``session.home``; every text is written out here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, QThreadPool, Signal, Slot

from statement_tracker.core.models import MarketPrice
from statement_tracker.gui.formatting import day_text, gain, money, shares_text, time_text
from statement_tracker.gui.holdings_model import HoldingsModel, holding_rows, loading_rows, name_and_detail, total_cells
from statement_tracker.gui.table import HEADINGS, arrange, filter_line, next_sort

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.gui.welcome import SPREADSHEET_FILES, STATEMENT_FILES, new_spreadsheet_name
from statement_tracker.gui.undo import ENTERED, NAME
from statement_tracker.gui.workers import Task
from statement_tracker.kept_statement import KeptStatement, is_kept_statement
from statement_tracker.settings import DEFAULT_TABLE_COLUMNS, TABLE_COLUMNS, TABLE_SHOWS
from statement_tracker.workflow import Report, needs_price, update_spreadsheet, with_entered_prices

if TYPE_CHECKING:
    from statement_tracker.gui.session import Session

UNAVAILABLE = "unavailable"
BACKUPS_OFF = "No backup copy will be made before it is changed: backups are turned off in Settings."
NO_HISTORY_ROW = (
    "Updating now writes these values, without a history row: Portfolio History only takes days with today's prices."
)
CELL_TEXTS = {
    "shares": ("shares",),
    "average_cost": ("average_cost",),
    "price": ("price",),
    "invested": ("invested",),
    "worth": ("worth", "worth_note"),
    "share": ("share",),
    "invested_share": ("invested_share",),
    "gain": ("gain",),
    "realized": ("realized",),
    "dividends": ("dividends",),
}
"""What each column of the table shows, by HoldingRow field."""
VALUE_NOTE = "It's marked \u201cyour value\u201d here and in the spreadsheet, and kept until Yahoo Finance has a price again."


@dataclass(frozen=True)
class ValueChoice:
    """An investment the user may type its current value in for."""

    ticker: str
    label: str
    """How the investment is named, e.g. "World fund"."""
    shares: Decimal
    price: MarketPrice | None
    """The price per share used now (last known or typed in before), or None if there is none."""


def value_question(choice: ValueChoice, currency: str) -> dict[str, str]:
    """The texts of the dialog that asks what ``choice`` is worth now."""
    hint = f"For all {shares_text(choice.shares)} shares you hold, as your Revolut app shows it."
    price = choice.price
    if price is not None and price.as_of is not None:
        worth = money(price.price * choice.shares)
        if price.entered:
            hint += f" You entered {worth} {currency} on {day_text(price.as_of.astimezone().date())}."
        else:
            hint += f" The last price found was worth {worth} {currency}, on {day_text(price.as_of.date())}."
    return {
        "title": f"What is {choice.label} worth now?",
        "subtitle": f"{choice.ticker} \u00b7 Yahoo Finance has no price for it today.",
        "hint": hint,
        "note": VALUE_NOTE,
        "currency": currency,
        "error": "",
    }


def listed(names: list[str]) -> str:
    """"A", "A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


STATEMENT_GONE = "This file has been moved or deleted since. The app uses the copy it kept."


def statement_place(statement: Path | None, kept: KeptStatement | None, settings_path: Path) -> tuple[str, str, str]:
    """Which statement file the values come from: its name, "In <folder>", and a note (or "").

    For the copy kept from last time, that is the file it was copied from, with a note if that file is no
    longer there. Empty without a statement, or for a copy whose origin was not recorded: the app's own
    copy, in its own folder, would tell the user nothing.
    """
    if statement is None:
        return "", "", ""
    if kept is not None and is_kept_statement(statement, settings_path):
        if kept.source is None:
            return "", "", ""
        return kept.source.name, f"In {kept.source.parent}", "" if kept.source.exists() else STATEMENT_GONE
    return statement.name, f"In {statement.resolve().parent}", ""


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
        self._rows: list = []
        """Every investment's row, in the usual order; the table shows them arranged (see ``_arrange``)."""
        self._shown: list[str] = []
        """The tickers the table shows, in its order."""
        self._search = ""
        """What is typed in the table's search box: not remembered."""
        self._save_later = False
        """A table choice was made while a fetch or an update could save the settings on its own thread."""
        self._progress = (0, 0, "")
        self._sheet_result = ""
        """What the last update of the spreadsheet did: "", "ok" or "error"."""
        self._sheet_title = ""
        self._sheet_lines: list[str] = []
        self._sheet_details = ""
        self._updated_at: datetime | None = None
        self._updated_on = None
        self._writing: Task | None = None
        """The spreadsheet being written, on the thread pool."""
        self._write_again = False
        """A change came in while writing: written once more when that ends."""
        """The day of the last successful update, by the same calendar the update itself used."""
        session.reportChanged.connect(self._clear_sheet_result)
        session.spreadsheetChanged.connect(self._other_spreadsheet)
        session.reportChanged.connect(self._update)
        session.settingsChanged.connect(self._update)
        session.busyChanged.connect(self._update)
        session.progressed.connect(self._show_progress)
        session.pageChanged.connect(self._create_if_asked)

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

    def _get_total_cells(self) -> dict[str, object]:
        """The Total row's texts by column; empty while there is no Total."""
        report = self._report()
        if report is None or not report.valuation.holdings or not self._shown:
            return {}
        return total_cells(report, self._shown, len(self._shown) < len(report.valuation.holdings))

    # -- the table's columns ---------------------------------------------------------

    def _get_widest(self) -> dict[str, str]:
        """The longest text of each column, in its rows and the Total: the window makes each column at
        least that wide, measured in the font it is drawn in, so no amount spills into the next one."""
        total = self._get_total_cells()
        widest = {}
        for column, names in CELL_TEXTS.items():
            texts = [str(getattr(row, name)) for row in self._rows for name in names]
            widest[column] = max([*texts, str(total.get(column, ""))], key=len)
        return widest

    def _get_columns(self) -> list[str]:
        return list(self._session.settings.table_columns)

    def _remember(self) -> None:
        """Save the table's choices; during a fetch or an update, which may save the settings on their own
        thread, once that ends."""
        if self._session.busy or self._writing is not None:
            self._save_later = True
        else:
            self._session.save_settings()

    def _save_if_waiting(self) -> None:
        if self._save_later and not self._session.busy and self._writing is None:
            self._save_later = False
            self._session.save_settings()

    @Slot(str, bool)
    def setColumnShown(self, key: str, shown: bool) -> None:
        """Show or hide a column of the table (the name is always shown); remembered."""
        settings = self._session.settings
        if key not in TABLE_COLUMNS or (key in settings.table_columns) == shown:
            return
        settings.table_columns = tuple(column for column in TABLE_COLUMNS
                                       if column == key and shown or column != key and column in settings.table_columns)
        if not shown and settings.table_sort and settings.table_sort[0] == key:
            settings.table_sort = None  # sorted by a column no longer shown: back to the usual order
            self._arrange()
        self._remember()
        self.changed.emit()

    @Slot()
    def resetColumns(self) -> None:
        """Back to the usual columns."""
        settings = self._session.settings
        settings.table_columns = DEFAULT_TABLE_COLUMNS
        if settings.table_sort and settings.table_sort[0] not in ("name", *DEFAULT_TABLE_COLUMNS):
            settings.table_sort = None
            self._arrange()
        self._remember()
        self.changed.emit()

    # -- the table's order -----------------------------------------------------------

    def _sort(self) -> tuple[str, bool] | None:
        return self._session.settings.table_sort

    @Slot(str)
    def sortBy(self, column: str) -> None:
        """A heading was clicked: sort by its column, reverse, or go back to the usual order; remembered."""
        settings = self._session.settings
        if column != "name" and column not in settings.table_columns:
            return
        settings.table_sort = next_sort(settings.table_sort, column)
        self._remember()
        self._arrange()
        self.changed.emit()

    def _arrange(self) -> None:
        settings = self._session.settings
        shown = arrange(self._rows, settings.table_sort, settings.table_show, self._search, priced=self._report() is not None)
        self._shown = [row.ticker for row in shown]
        self._holdings.set_rows(shown)

    # -- which investments the table shows -------------------------------------------

    def _get_filter_line(self) -> str:
        # While prices come in, Show waits for them and there is no Total yet: the line says neither.
        priced = self._report() is not None
        show = self._session.settings.table_show if priced else "all"
        return filter_line(len(self._shown), len(self._rows), show, self._search, total=priced)

    @Slot(str)
    def setShow(self, choice: str) -> None:
        """Show all investments, those gaining or those losing; remembered."""
        if choice not in TABLE_SHOWS:
            return
        self._session.settings.table_show = choice
        self._remember()
        self._arrange()
        self.changed.emit()

    @Slot(str)
    def setSearch(self, text: str) -> None:
        """Keep the investments whose name or ticker contains ``text``; not remembered."""
        self._search = text
        self._arrange()
        self.changed.emit()

    @Slot()
    def showAll(self) -> None:
        """Every investment again: Show back to all, and the search emptied."""
        self._search = ""
        self.setShow("all")

    def _statement_place(self) -> tuple[str, str, str]:
        session = self._session
        return statement_place(session.statement, session.kept, session.settings.path)

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
        if self._writing is not None:
            return "Updating your spreadsheet…"
        if self._sheet_result == "error":
            return "Not updated today"
        if self._updated_at is not None and self._updated_on == self._session.today():
            return f"Updated today at {time_text(self._updated_at)}"
        if self._session.busy:
            if self._session.new_spreadsheet == sheet and not sheet.exists():
                return "It will be created as soon as today's prices are in."
            return "Ready once today's prices are in"
        if not sheet.exists():
            return "It doesn't exist yet: updating creates it."
        changed = datetime.fromtimestamp(sheet.stat().st_mtime, UTC).astimezone().date()
        return f"Last changed {day_text(changed)}"

    hasSpreadsheet = Property(bool, lambda self: self._sheet() is not None, notify=changed)
    sheetName = Property(str, lambda self: self._sheet().name if self._sheet() else "", notify=changed)
    sheetLine = Property(str, _get_sheet_line, notify=changed)
    sheetButton = Property(str, lambda self: "Try again" if self._sheet_result == "error" else "Update my spreadsheet", notify=changed)
    canUpdate = Property(
        bool, lambda self: not self._session.busy and self._writing is None and self._session.report is not None, notify=changed
    )
    writing = Property(bool, lambda self: self._writing is not None, notify=changed)
    sheetResult = Property(str, lambda self: self._sheet_result, notify=changed)
    sheetResultTitle = Property(str, lambda self: self._sheet_title, notify=changed)
    sheetResultLines = Property(list, lambda self: self._sheet_lines, notify=changed)
    sheetHasDetails = Property(bool, lambda self: self._sheet_details != "", notify=changed)
    backupsOff = Property(
        str, lambda self: BACKUPS_OFF if self._sheet() is not None and self._session.settings.backups_kept == 0 else "",
        notify=changed,
    )

    # -- prices that are not today's from Yahoo -------------------------------------

    def _get_offline_text(self) -> str:
        report = self._report()
        if report is None or not report.valuation.uses_last_known_prices:
            return ""
        days = [holding.price.as_of for holding in report.valuation.holdings
                if holding.price is not None and holding.price.last_known and holding.price.as_of]
        when = f", from {day_text(min(days).date())}" if days else ""
        return f"Yahoo Finance can't be reached right now, so these values use the last prices found{when}."

    offlineText = Property(str, _get_offline_text, notify=changed)
    offlineSheetNote = Property(
        str, lambda self: NO_HISTORY_ROW if self._get_offline_text() and self._sheet() is not None else "", notify=changed
    )

    busy = Property(bool, _get_busy, notify=changed)
    statementLine = Property(str, _get_statement_line, notify=changed)
    statementName = Property(str, lambda self: self._statement_place()[0], notify=changed)
    statementFolder = Property(str, lambda self: self._statement_place()[1], notify=changed)
    statementNote = Property(str, lambda self: self._statement_place()[2], notify=changed)
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
    totalCells = Property("QVariantMap", _get_total_cells, notify=changed)
    columns = Property(list, _get_columns, notify=changed)
    columnKeys = Property(list, lambda self: ["name", *TABLE_COLUMNS], constant=True)
    widest = Property("QVariantMap", _get_widest, notify=changed)
    headings = Property("QVariantMap", lambda self: dict(HEADINGS), constant=True)
    sortColumn = Property(str, lambda self: self._sort()[0] if self._sort() else "", notify=changed)
    show = Property(str, lambda self: self._session.settings.table_show, notify=changed)
    showLabel = Property(str, lambda self: f"Show: {self._session.settings.table_show}", notify=changed)
    search = Property(str, lambda self: self._search, notify=changed)
    filterLine = Property(str, _get_filter_line, notify=changed)
    sortDescending = Property(bool, lambda self: bool(self._sort() and self._sort()[1]), notify=changed)
    holdings = Property(QObject, lambda self: self._holdings, constant=True)

    # -- updating ------------------------------------------------------------------

    def _update(self) -> None:
        report = self._report()
        if report is not None:
            self._rows = holding_rows(report, self._session.settings)
        else:
            self._rows = loading_rows(self._session.loading_positions, self._session.settings)
        self._arrange()
        if not self._session.busy:
            self._progress = (0, 0, "")
        self._save_if_waiting()
        self._create_if_asked()
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
        """Write the values shown to the spreadsheet, without fetching again, and say what was done.
        The writing happens off the window's thread, so the window stays responsive meanwhile."""
        report, sheet = self._session.report, self._sheet()
        if report is None or sheet is None or self._session.busy:
            return
        if self._writing is not None:
            self._write_again = True  # a change while writing: written once more afterwards
            return
        settings, today = self._session.settings, self._session.today()
        task = Task(lambda: update_spreadsheet(report, settings, sheet, today))
        task.signals.finished.connect(lambda exported: self._written(task, report, sheet, exported))
        task.signals.failed.connect(lambda error: self._not_written(task, error))
        self._writing = task
        self.changed.emit()
        QThreadPool.globalInstance().start(task)

    def _written(self, task: Task, report: Report, sheet: Path, exported: ExportResult) -> None:
        self._writing = None
        self._sheet_result = "ok"
        self._sheet_title = "Your spreadsheet was created" if exported.created else "Your spreadsheet is up to date"
        self._sheet_lines, self._sheet_details = result_lines(report, exported), ""
        self._updated_at, self._updated_on = self._session.now(), self._session.today()
        self._session.updated_this_session = sheet
        self._wrote()

    def _not_written(self, task: Task, error: object) -> None:
        self._writing = None
        if isinstance(error, UserFacingError):
            self._sheet_result, self._sheet_title = "error", "Your spreadsheet wasn't updated"
            self._sheet_lines, self._sheet_details = [error.what_happened, error.what_to_do], error.details
            self._wrote()
        else:
            self.changed.emit()
            self._session.unexpected(error)

    def _wrote(self) -> None:
        self._save_if_waiting()
        self.changed.emit()
        if self._write_again:
            self._write_again = False
            self.updateSpreadsheet()

    @Slot(str)
    def enterValue(self, ticker: str) -> None:
        """Let the user type in what the investment ``ticker`` is worth now, when Yahoo has no current
        price for it. Kept as a price per share; the values are worked out again without fetching."""
        report = self._session.report
        if report is None or self._session.busy:
            return
        holdings = report.valuation.holdings
        clicked = next((holding for holding in holdings if holding.position.ticker == ticker), None)
        if clicked is None or not needs_price(clicked):
            return
        settings = self._session.settings
        choices = [
            ValueChoice(holding.position.ticker, name_and_detail(holding.position.ticker, settings)[0],
                        holding.position.shares, holding.price)
            for holding in holdings
            if needs_price(holding)
        ]
        answer = self._session.ask_value(choices, ticker, report.statement.currency)
        if not answer:
            return
        ticker, value = answer
        shares = next(choice.shares for choice in choices if choice.ticker == ticker)
        self._session.history.record(f"the value entered for {ticker}", [ticker], {ENTERED})
        self._session.set_report(with_entered_prices(report, {ticker: value / shares}, settings, now=self._session.now()))
        self.rewrite_spreadsheet()

    @Slot(str, str)
    def rename(self, ticker: str, name: str) -> None:
        """Show ``name`` for the investment ``ticker`` from now on, here and in the spreadsheet. An empty
        name goes back to the fund's name from Yahoo Finance."""
        report = self._session.report
        if report is None or all(holding.position.ticker != ticker for holding in report.valuation.holdings):
            return
        name = name.strip()
        settings = self._session.settings
        if name == (settings.index_name(ticker) or ""):
            return  # nothing changed
        self._session.history.record(f"the new name of {ticker}", [ticker], {NAME})
        if name:
            settings.index_names[ticker] = name
        else:
            settings.index_names.pop(ticker, None)
        self._session.save_settings()
        self._session.settingsChanged.emit()
        self.rewrite_spreadsheet()

    def rewrite_spreadsheet(self) -> None:
        """Write a change to the spreadsheet at once, if it was updated while the app is open (Spec F10)."""
        if self._session.updated_this_session is not None and self._session.updated_this_session == self._sheet():
            self.updateSpreadsheet()

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
        chosen = self._session.ask_save_file("Where should the new spreadsheet be saved?", start / new_spreadsheet_name(self._session.today()))
        if chosen is not None:
            sheet = chosen if chosen.suffix.lower() == ".xlsx" else chosen.with_name(chosen.name + ".xlsx")
            self._session.use_spreadsheet(sheet)
            self._session.new_spreadsheet = sheet
            self._create_if_asked()

    def _create_if_asked(self) -> None:
        """Create the spreadsheet the user asked for ("Create a new one"), once the values are in: no need to
        press "Update my spreadsheet" for it. One that exists by then is left for the button. Asked for in
        Settings, it is created when Home shows again: nothing is written while Settings is open."""
        sheet = self._session.new_spreadsheet
        session = self._session
        if sheet is None or session.page != "home" or session.busy or session.report is None or self._writing is not None:
            return
        self._session.new_spreadsheet = None
        if sheet == self._sheet() and not sheet.exists():
            self.updateSpreadsheet()

    def _other_spreadsheet(self) -> None:
        """What was said of the spreadsheet before is not about this one."""
        self._clear_sheet_result()
        self._updated_at, self._updated_on = None, None
        self.changed.emit()

    def _clear_sheet_result(self) -> None:
        """New values: what an earlier update wrote is not what is shown any more."""
        self._sheet_result, self._sheet_title, self._sheet_lines, self._sheet_details = "", "", [], ""

    @Slot()
    def chooseStatement(self) -> None:
        """Use a newer statement, picked in the file chooser."""
        chosen = self._session.ask_open_file("Choose your Revolut statement", STATEMENT_FILES, self._session.start_folder())
        if chosen is not None:
            self._session.use_statement(chosen)
