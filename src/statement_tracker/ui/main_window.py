"""The main window: choose a statement, optionally a spreadsheet, press one button, read the result.

No calculations happen here. The window calls ``workflow`` and shows what comes back.
"""

from __future__ import annotations

import html
import sys
import traceback
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QStandardPaths, Qt, QThreadPool, Signal
from PySide6.QtGui import QBrush, QCloseEvent, QColor, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from statement_tracker import APP_NAME
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.core.market_data.provider import PriceProvider
from statement_tracker.core.models import MarketPrice
from statement_tracker.core.ticker_resolver import Resolution
from statement_tracker.settings import Settings
from statement_tracker.ui import dialogs, theme
from statement_tracker.ui.workers import QuestionBridge, Task
from statement_tracker.workflow import Report, build_report, display_name, update_spreadsheet

UNAVAILABLE = "unavailable"
NO_STATEMENT = "No file chosen yet. You can also drag the file onto this window."
NO_SPREADSHEET = "No spreadsheet. The results will only be shown here."

TABLE_HEADERS = ["Investment", "Invested", "% of invested", "Worth now", "% of worth now", "Gain or loss"]
WORTH_COLUMN = 3
GAIN_COLUMN = 5
LAST_KNOWN_MARK = "*"
LAST_KNOWN_NOTE = (
    f"Values marked {LAST_KNOWN_MARK} use the last price fetched on an earlier day, because Yahoo could not "
    "be reached. Try again later for up-to-date values."
)
WINDOW_WIDTH = 1000
MAX_SCREEN_SHARE = 0.8
"""When the result table appears, the window grows to at most this share of the screen's usable height."""
MIN_TABLE_HEIGHT = 115
"""Room for the header and two rows, kept even on a screen too small for the limit above."""

# The line at the top of each step: its text and the state the theme colours it by.
STEP_TO_DO = ("To do: choose your statement file.", "todo")
STEP_DONE = ("✓ Done", "ok")
STEP_OPTIONAL = ("Optional. You can skip this step.", "optional")
STEP_REMEMBERED = ("✓ Already done: remembered from last time.", "ok")

Outcome = tuple[Report, ExportResult | None, UserFacingError | None]


def default_start_folder() -> Path:
    """Return the folder file dialogs open in before the user has picked anything.

    Run from source, that is the folder the app was started from (the project
    folder during development). The installed app has no such folder, so it
    opens in Downloads, where an exported statement usually lands.
    """
    if not getattr(sys, "frozen", False):
        return Path.cwd()
    downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return Path(downloads) if downloads and Path(downloads).exists() else Path.home()


def _file_text(path: Path, remark: str = "") -> str:
    """Show a chosen file as its name in bold with the folder underneath, instead of one long path."""
    lines = [f"<b>{html.escape(path.name)}</b>", f"in {html.escape(str(path.parent))}"]
    if remark:
        lines.append(html.escape(remark))
    return "<br>".join(lines)


def _default_provider() -> PriceProvider:
    from statement_tracker.core.market_data.yfinance_provider import YFinanceProvider

    return YFinanceProvider()


class MainWindow(QMainWindow):
    """Three steps and a result table."""

    progressed = Signal(int, int, str)
    """Steps done, steps in total (0 = not known yet), what is happening. Safe to emit from any thread."""

    def __init__(
        self,
        settings: Settings,
        provider_factory: Callable[[], PriceProvider] = _default_provider,
        today: Callable[[], date] = date.today,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._provider_factory = provider_factory
        self._today = today
        self._statement: Path | None = None
        self._spreadsheet: Path | None = settings.spreadsheet_path
        self._spreadsheet_from_last_time = settings.spreadsheet_path is not None
        self._tasks: list[Task] = []
        self._locale = QLocale()
        self.ask_listing: Callable[[Resolution], str | None] = lambda resolution: dialogs.ask_listing(self, resolution)
        self.show_error: Callable[[UserFacingError], object] = lambda error: dialogs.show_error(self, error)
        self.ask_retry: Callable[[UserFacingError], bool] = lambda error: dialogs.show_error(
            self, error, can_retry=True
        )
        self._last_run: tuple[Path | None, date] = (None, today())
        self.progressed.connect(self._show_progress)
        self._bridge = QuestionBridge(lambda resolution: self.ask_listing(resolution), self)

        self.setWindowTitle(APP_NAME)
        self.setAcceptDrops(True)

        intro = QLabel("See how your investments are doing in three steps.")
        intro.setObjectName("intro")  # object names are what ui/theme.py styles

        # Step 1
        self.statement_label = QLabel(NO_STATEMENT)
        self.statement_label.setWordWrap(True)
        self.choose_statement_button = QPushButton("&Choose statement file...")
        self.choose_statement_button.clicked.connect(self._choose_statement)
        help_button = QPushButton("&Where do I get this file?")
        help_button.clicked.connect(
            lambda: dialogs.show_text(self, "Where do I get this file?", dialogs.WHERE_IS_THE_FILE_TEXT)
        )
        statement_buttons = QHBoxLayout()
        statement_buttons.addWidget(self.choose_statement_button)
        statement_buttons.addWidget(help_button)
        statement_buttons.addStretch(1)
        statement_box = QGroupBox("Step 1: your Revolut statement")
        self.statement_badge = QLabel()
        self.statement_badge.setObjectName("badge")
        statement_layout = QVBoxLayout(statement_box)
        statement_layout.addWidget(self.statement_badge)
        statement_layout.addWidget(self.statement_label)
        statement_layout.addLayout(statement_buttons)

        # Step 2
        self.spreadsheet_label = QLabel()
        self.spreadsheet_label.setWordWrap(True)
        existing_button = QPushButton("Choose my &spreadsheet...")
        existing_button.setToolTip("Pick an Excel file you already have. Your own sheets in it are not changed.")
        existing_button.clicked.connect(self._choose_spreadsheet)
        new_button = QPushButton("Create a &new one...")
        new_button.setToolTip("Let the app create a new Excel file for you.")
        new_button.clicked.connect(self._create_spreadsheet)
        self.no_spreadsheet_button = QPushButton("&Don't use a spreadsheet")
        self.no_spreadsheet_button.clicked.connect(lambda: self.set_spreadsheet(None))
        spreadsheet_buttons = QHBoxLayout()
        for button in (existing_button, new_button, self.no_spreadsheet_button):
            spreadsheet_buttons.addWidget(button)
        spreadsheet_buttons.addStretch(1)
        spreadsheet_box = QGroupBox("Step 2 (optional): your Excel spreadsheet")
        self.spreadsheet_badge = QLabel()
        self.spreadsheet_badge.setObjectName("badge")
        spreadsheet_layout = QVBoxLayout(spreadsheet_box)
        spreadsheet_layout.addWidget(self.spreadsheet_badge)
        spreadsheet_layout.addWidget(self.spreadsheet_label)
        spreadsheet_layout.addLayout(spreadsheet_buttons)

        # Step 3
        self.go_button = QPushButton()
        self.go_button.setObjectName("primary")
        go_font = QFont(self.go_button.font())
        go_font.setPointSize(go_font.pointSize() + 2)
        self.go_button.setFont(go_font)
        self.go_button.setMinimumHeight(48)
        self.go_button.setEnabled(False)
        self.go_button.clicked.connect(self.start)
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)

        # Result
        self.table = QTableWidget(0, len(TABLE_HEADERS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.notes_label = QLabel("")
        self.notes_label.setObjectName("notes")
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        about_button = QPushButton("&About and privacy")
        about_button.clicked.connect(lambda: dialogs.show_about(self))
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(about_button)

        layout = QVBoxLayout()
        layout.addWidget(intro)
        layout.addWidget(statement_box)
        layout.addWidget(spreadsheet_box)
        layout.addWidget(self.go_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table, stretch=1)
        self._filler = QWidget()  # takes the table's place until there is a result, so the steps stay at the top
        layout.addWidget(self._filler, stretch=1)
        layout.addWidget(self.notes_label)
        layout.addLayout(footer)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Buttons are highlighted only when reached with the Tab key, never just for
        # having been clicked or for being first in the window.
        for button in self.findChildren(QPushButton):
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        central.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        central.setFocus()

        self._set_headers()
        self.table.setVisible(False)
        self._refresh()
        # Start only as tall as the three steps need; the window grows when there is a result to show.
        self.resize(WINDOW_WIDTH, self.sizeHint().height())

    # -- choosing files ----------------------------------------------------------

    def set_statement(self, path: Path) -> None:
        """Use ``path`` as the statement and remember its folder for next time."""
        self._statement = path
        if self._settings.last_folder != path.parent:
            self._settings.last_folder = path.parent
            self._save_settings()
        self._refresh()

    def set_spreadsheet(self, path: Path | None) -> None:
        """Use ``path`` as the spreadsheet to update, or None for no spreadsheet. Remembered."""
        self._spreadsheet = path
        self._spreadsheet_from_last_time = False
        if self._settings.spreadsheet_path != path:
            self._settings.spreadsheet_path = path
            self._save_settings()
        self._refresh()

    def _save_settings(self) -> None:
        try:
            self._settings.save()
        except OSError:
            pass  # not being able to remember a choice must never stop the user

    def _start_folder(self) -> str:
        """Where file dialogs open: the last folder used, else a sensible first guess."""
        folder = self._settings.last_folder
        if folder and folder.exists():
            return str(folder)
        return str(default_start_folder())

    def _choose_statement(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose your Revolut statement", self._start_folder(), "Statement files (*.csv);;All files (*)"
        )
        if chosen:
            self.set_statement(Path(chosen))

    def _spreadsheet_folder(self) -> str:
        if self._spreadsheet and self._spreadsheet.parent.exists():
            return str(self._spreadsheet.parent)
        return self._start_folder()

    def _choose_spreadsheet(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose your Excel spreadsheet", self._spreadsheet_folder(), "Excel spreadsheets (*.xlsx)"
        )
        if chosen:
            self.set_spreadsheet(Path(chosen))

    def _create_spreadsheet(self) -> None:
        suggestion = str(Path(self._spreadsheet_folder()) / "My investments.xlsx")
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Where should the new spreadsheet be saved?", suggestion, "Excel spreadsheets (*.xlsx)"
        )
        if chosen:
            path = Path(chosen)
            self.set_spreadsheet(path if path.suffix.lower() == ".xlsx" else path.with_name(path.name + ".xlsx"))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.drop_file(Path(url.toLocalFile()))
        event.acceptProposedAction()

    def drop_file(self, path: Path) -> None:
        """A dropped Excel file is the spreadsheet; any other file is the statement."""
        if path.suffix.lower() == ".xlsx":
            self.set_spreadsheet(path)
        else:
            self.set_statement(path)

    def _refresh(self) -> None:
        self.statement_label.setText(_file_text(self._statement) if self._statement else NO_STATEMENT)
        self.statement_label.setToolTip(str(self._statement) if self._statement else "")
        self._badge(self.statement_badge, *(STEP_DONE if self._statement else STEP_TO_DO))
        if self._spreadsheet is None:
            self._badge(self.spreadsheet_badge, *STEP_OPTIONAL)
        elif self._spreadsheet_from_last_time:
            self._badge(self.spreadsheet_badge, *STEP_REMEMBERED)
        else:
            self._badge(self.spreadsheet_badge, *STEP_DONE)
        if self._spreadsheet is None:
            self.spreadsheet_label.setText(NO_SPREADSHEET)
        elif self._spreadsheet.exists():
            self.spreadsheet_label.setText(
                _file_text(self._spreadsheet, "It will be updated. Close it in Excel first.")
            )
        else:
            self.spreadsheet_label.setText(
                _file_text(self._spreadsheet, "It does not exist yet and will be created.")
            )
        self.spreadsheet_label.setToolTip(str(self._spreadsheet) if self._spreadsheet else "")
        self.no_spreadsheet_button.setEnabled(self._spreadsheet is not None)
        self.go_button.setText(
            "Step 3: show my investments and update my spreadsheet"
            if self._spreadsheet
            else "Step 3: show my investments"
        )
        self.go_button.setEnabled(self._statement is not None and not self._busy())

    # -- running -----------------------------------------------------------------

    def _busy(self) -> bool:
        return bool(self._tasks)

    def start(self) -> None:
        """Read the statement, fetch prices and update the spreadsheet, without freezing the window."""
        if self._statement is None or self._busy():
            return
        statement, spreadsheet, today = self._statement, self._spreadsheet, self._today()
        self._last_run = (spreadsheet, today)
        extra_steps = 1 if spreadsheet else 0  # updating the spreadsheet comes after the prices

        def progress(done: int, total: int, text: str) -> None:
            # Called on the background thread; the signal carries it to the window's thread.
            self.progressed.emit(done, total + extra_steps if total else 0, text)

        def work() -> Outcome:
            report = build_report(
                statement, self._provider_factory(), self._settings, chooser=self._bridge, progress=progress
            )
            if spreadsheet is None:
                return report, None, None
            steps = len(report.valuation.holdings)
            self.progressed.emit(steps, steps + 1, "Updating your spreadsheet...")
            try:
                return report, update_spreadsheet(report, self._settings, spreadsheet, today), None
            except UserFacingError as error:
                return report, None, error

        task = Task(work)
        task.signals.finished.connect(self._finished)
        task.signals.failed.connect(self._failed)
        self._tasks.append(task)
        self._show_progress(0, 0, "Starting...")
        self._refresh()
        QThreadPool.globalInstance().start(task)

    def _show_progress(self, done: int, total: int, text: str) -> None:
        """Move the progress bar and say what is happening. A total of 0 means "not known yet"."""
        if not self._busy():
            return  # a late message from a run that has already finished
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_bar.setVisible(True)
        self._status(text, "busy")

    def _done(self) -> None:
        self._tasks.clear()
        self.progress_bar.setVisible(False)
        self._refresh()

    @staticmethod
    def _badge(label: QLabel, text: str, state: str) -> None:
        """Show whether a step is done, still to do, or can be skipped."""
        label.setText(text)
        theme.set_state(label, state)

    def _status(self, text: str, state: str) -> None:
        """Show the status line; ``state`` (busy, ok, error) picks its colour in the theme."""
        self.status_label.setText(text)
        theme.set_state(self.status_label, state)

    def _failed(self, error: object) -> None:
        self._done()
        self._status("That did not work. Nothing was changed.", "error")
        if not isinstance(error, UserFacingError):
            details = "".join(traceback.format_exception(error)) if isinstance(error, BaseException) else repr(error)
            error = UserFacingError(
                "Something unexpected went wrong.",
                'Please report this problem. "Copy details" copies the information needed to fix it.',
                details=details,
            )
        self.show_error(error)

    def _finished(self, outcome: object) -> None:
        report, exported, export_error = outcome  # type: ignore[misc]
        self._done()
        self._show_report(report)

        # The spreadsheet could not be saved (usually: still open in Excel). Offer to try just
        # that part again, as often as needed, without reading the statement or fetching prices again.
        spreadsheet, today = self._last_run
        while export_error is not None and spreadsheet is not None:
            self._status("Your investments are shown below, but the spreadsheet was not updated.", "error")
            if not self.ask_retry(export_error):
                break
            try:
                exported, export_error = update_spreadsheet(report, self._settings, spreadsheet, today), None
            except UserFacingError as error:
                export_error = error

        notes = list(report.notes)
        if report.valuation.uses_last_known_prices:
            notes.insert(0, LAST_KNOWN_NOTE)
        if exported is not None:
            done = "created" if exported.created else "updated"
            self._status(f"Done. Your spreadsheet was {done}: {exported.destination}", "ok")
            notes.extend(exported.notes)
        elif export_error is not None:
            self._status("Your investments are shown below, but the spreadsheet was not updated.", "error")
        else:
            self._status("Done. Your investments are shown below.", "ok")
        if not report.valuation.holdings:
            self._status("Done. The statement has no investments that you still hold.", "ok")
        self.notes_label.setText("\n".join(f"Note: {note}" for note in notes))

    # -- showing the result ------------------------------------------------------

    def _money(self, value: Decimal | None, currency: str) -> str:
        if value is None:
            return UNAVAILABLE
        return f"{self._locale.toString(float(value), 'f', 2)} {currency}"

    def _percent(self, value: Decimal | None) -> str:
        if value is None:
            return UNAVAILABLE
        return f"{self._locale.toString(float(value), 'f', 2)} %"

    def _gain(self, amount: Decimal | None, percent: Decimal | None, currency: str) -> str:
        """Format a gain or loss with an arrow and a sign, e.g. "▲ +199,00 EUR (+19,88 %)"."""
        if amount is None:
            return UNAVAILABLE
        if amount == 0:
            return self._money(amount, currency)
        arrow, sign = ("▲", "+") if amount > 0 else ("▼", "-")
        text = f"{arrow} {sign}{self._money(abs(amount), currency)}"
        if percent is not None:
            text += f" ({sign}{self._percent(abs(percent))})"
        return text

    def _last_known_tip(self, price: MarketPrice) -> str:
        if price.as_of is None:
            return "Last known price from an earlier day: Yahoo could not be reached."
        day = price.as_of.date()
        shown = self._locale.toString(QDate(day.year, day.month, day.day), QLocale.FormatType.LongFormat)
        return f"Last known price, from {shown}: Yahoo could not be reached."

    def _set_headers(self) -> None:
        """Column order follows the spreadsheet: each percentage sits next to the amount it is a share of."""
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        tooltips = (
            "The fund or share you hold.",
            "What you paid for what you still hold, fees included.",
            "How much of all the money you invested went into this one.",
            "What it would be worth at the latest price from Yahoo Finance. Approximate.",
            "How much of all your investments this one is, by what they are worth now.",
            "Worth now minus what you invested, and that difference as a percentage of what you invested.",
        )
        for column, tooltip in enumerate(tooltips):
            self.table.horizontalHeaderItem(column).setToolTip(tooltip)

    def _show_report(self, report: Report) -> None:
        valuation = report.valuation
        currency = report.statement.currency

        # Each row: the six texts, then the gain or loss itself (None if unknown) for its colour.
        rows: list[tuple[str, str, str, str, str, str, Decimal | None]] = [
            (
                display_name(self._settings, holding.position.ticker),
                self._money(holding.position.cost_basis, currency),
                self._percent(holding.invested_percent),
                self._money(holding.market_value, currency),
                self._percent(holding.allocation_percent),
                self._gain(holding.unrealized_pnl, holding.percent_change, currency),
                holding.unrealized_pnl,
            )
            for holding in valuation.holdings
        ]
        if valuation.holdings:
            invested, gain = valuation.portfolio.total_cost_basis, valuation.unrealized_pnl
            whole = Decimal(100)
            rows.append(
                (
                    "Total",
                    self._money(invested, currency),
                    self._percent(whole if invested > 0 else None),
                    self._money(valuation.total_market_value, currency),
                    self._percent(whole if valuation.total_market_value else None),
                    self._gain(gain, gain / invested * 100 if gain is not None and invested > 0 else None, currency),
                    gain,
                )
            )

        # A value at a price from an earlier run is marked with LAST_KNOWN_MARK, and its tooltip says from when.
        last_known: list[str | None] = [
            self._last_known_tip(holding.price) if holding.price is not None and holding.price.last_known else None
            for holding in valuation.holdings
        ]
        if valuation.holdings:
            last_known.append(
                "Includes last known prices from an earlier day, so this total is not up to date."
                if valuation.uses_last_known_prices and valuation.total_market_value is not None
                else None
            )

        colours = theme.current()
        self.table.setRowCount(len(rows))
        for row_number, (*texts, gain) in enumerate(rows):
            is_total = bool(valuation.holdings) and row_number == len(rows) - 1
            for column, text in enumerate(texts):
                tip = last_known[row_number] if column == WORTH_COLUMN else None
                item = QTableWidgetItem(f"{text} {LAST_KNOWN_MARK}" if tip else text)
                if tip:
                    item.setToolTip(tip)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == GAIN_COLUMN and gain:
                    # The arrow and the colour belong to the gain or loss, never to the value itself.
                    item.setForeground(QBrush(QColor(colours.good if gain > 0 else colours.bad)))
                elif text == UNAVAILABLE:
                    item.setForeground(QBrush(QColor(colours.muted)))
                if is_total:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row_number, column, item)
        self.table.setVisible(bool(valuation.holdings))
        self._filler.setVisible(not valuation.holdings)
        if valuation.holdings:
            self._grow_to_fit_table()

    def _grow_to_fit_table(self) -> None:
        """Make the window tall enough to show every row, up to a share of the screen's height.

        The limit adapts to the screen (MAX_SCREEN_SHARE of its usable height); rows that
        do not fit are reached by scrolling the table. The window only ever grows here: a
        size the user chose by hand is never reduced.
        """
        table = self.table
        wanted = table.horizontalHeader().height() + 2 * table.frameWidth() + 2
        wanted += sum(table.rowHeight(row) for row in range(table.rowCount()))
        table.setMinimumHeight(wanted)
        self.centralWidget().layout().activate()
        target = self.sizeHint().height()

        screen = self.screen()
        available = int(screen.availableGeometry().height() * MAX_SCREEN_SHARE) if screen else target
        if target > available:
            # Too many rows for this screen: stop at the limit and let the table scroll. On a
            # very small screen the table still keeps a couple of rows, even if that goes
            # slightly past the limit.
            table.setMinimumHeight(max(MIN_TABLE_HEIGHT, wanted - (target - available)))
            self.centralWidget().layout().activate()
            target = max(available, self.minimumSizeHint().height())
        if target > self.height():
            self.resize(self.width(), target)

    def closeEvent(self, event: QCloseEvent) -> None:
        QThreadPool.globalInstance().waitForDone(3000)
        super().closeEvent(event)
