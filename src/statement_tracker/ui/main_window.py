"""The main window: choose a statement, optionally a spreadsheet, press one button, read the result.

No calculations happen here. The window calls ``workflow`` and shows what comes back.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QThreadPool
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
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
from statement_tracker.core.ticker_resolver import Resolution
from statement_tracker.settings import Settings
from statement_tracker.ui import dialogs
from statement_tracker.ui.workers import QuestionBridge, Task
from statement_tracker.workflow import Report, build_report, display_name, update_spreadsheet

UNAVAILABLE = "unavailable"
NO_STATEMENT = "No file chosen yet. You can also drag the file onto this window."
NO_SPREADSHEET = "No spreadsheet. The results will only be shown here."

Outcome = tuple[Report, ExportResult | None, UserFacingError | None]


def _default_provider() -> PriceProvider:
    from statement_tracker.core.market_data.yfinance_provider import YFinanceProvider

    return YFinanceProvider()


class MainWindow(QMainWindow):
    """Three steps and a result table."""

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
        self._tasks: list[Task] = []
        self._locale = QLocale()
        self.ask_listing: Callable[[Resolution], str | None] = lambda resolution: dialogs.ask_listing(self, resolution)
        self.show_error: Callable[[UserFacingError], None] = lambda error: dialogs.show_error(self, error)
        self._bridge = QuestionBridge(lambda resolution: self.ask_listing(resolution), self)

        self.setWindowTitle(APP_NAME)
        self.setAcceptDrops(True)
        self.resize(760, 720)

        intro = QLabel("See how your investments are doing in three steps.")
        intro_font = QFont(intro.font())
        intro_font.setPointSize(intro_font.pointSize() + 3)
        intro.setFont(intro_font)

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
        statement_layout = QVBoxLayout(statement_box)
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
        spreadsheet_layout = QVBoxLayout(spreadsheet_box)
        spreadsheet_layout.addWidget(self.spreadsheet_label)
        spreadsheet_layout.addLayout(spreadsheet_buttons)

        # Step 3
        self.go_button = QPushButton()
        go_font = QFont(self.go_button.font())
        go_font.setPointSize(go_font.pointSize() + 2)
        go_font.setBold(True)
        self.go_button.setFont(go_font)
        self.go_button.setMinimumHeight(44)
        self.go_button.setEnabled(False)
        self.go_button.clicked.connect(self.start)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        # Result
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.notes_label = QLabel("")
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
        layout.addWidget(self.status_label)
        layout.addWidget(self.table, stretch=1)
        self._filler = QWidget()  # takes the table's place until there is a result, so the steps stay at the top
        layout.addWidget(self._filler, stretch=1)
        layout.addWidget(self.notes_label)
        layout.addLayout(footer)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._set_headers("EUR", by_value=True)
        self.table.setVisible(False)
        self._refresh()

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
        folder = self._settings.last_folder
        return str(folder) if folder and folder.exists() else str(Path.home())

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
        self.statement_label.setText(str(self._statement) if self._statement else NO_STATEMENT)
        if self._spreadsheet is None:
            self.spreadsheet_label.setText(NO_SPREADSHEET)
        elif self._spreadsheet.exists():
            self.spreadsheet_label.setText(f"{self._spreadsheet}\nIt will be updated. Close it in Excel first.")
        else:
            self.spreadsheet_label.setText(f"{self._spreadsheet}\nIt does not exist yet and will be created.")
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

        def work() -> Outcome:
            report = build_report(statement, self._provider_factory(), self._settings, chooser=self._bridge)
            if spreadsheet is None:
                return report, None, None
            try:
                return report, update_spreadsheet(report, self._settings, spreadsheet, today), None
            except UserFacingError as error:
                return report, None, error

        task = Task(work)
        task.signals.finished.connect(self._finished)
        task.signals.failed.connect(self._failed)
        self._tasks.append(task)
        self.status_label.setText("Working... reading your statement and fetching current prices.")
        self._refresh()
        QThreadPool.globalInstance().start(task)

    def _done(self) -> None:
        self._tasks.clear()
        self._refresh()

    def _failed(self, error: object) -> None:
        self._done()
        self.status_label.setText("That did not work. Nothing was changed.")
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

        notes = list(report.notes)
        if exported is not None:
            done = "created" if exported.created else "updated"
            self.status_label.setText(f"Done. Your spreadsheet was {done}: {exported.destination}")
            notes.extend(exported.notes)
        elif export_error is not None:
            self.status_label.setText("Your investments are shown below, but the spreadsheet was not updated.")
        else:
            self.status_label.setText("Done. Your investments are shown below.")
        if not report.valuation.holdings:
            self.status_label.setText("Done. The statement has no investments that you still hold.")
        self.notes_label.setText("\n".join(f"Note: {note}" for note in notes))
        if export_error is not None:
            self.show_error(export_error)

    # -- showing the result ------------------------------------------------------

    def _money(self, value: Decimal | None, currency: str) -> str:
        if value is None:
            return UNAVAILABLE
        return f"{self._locale.toString(float(value), 'f', 2)} {currency}"

    def _percent(self, value: Decimal | None) -> str:
        if value is None:
            return UNAVAILABLE
        return f"{self._locale.toString(float(value), 'f', 2)} %"

    def _set_headers(self, currency: str, by_value: bool) -> None:
        share = "Share of total" if by_value else "Share of total invested"
        self.table.setHorizontalHeaderLabels(["Investment", "Invested", "Worth now", share])
        tooltips = (
            "The fund or share you hold.",
            "What you paid for what you still hold, fees included.",
            "What it would be worth at the latest price from Yahoo Finance. Approximate.",
            "How much of all your investments this one is, by what they are worth now."
            if by_value
            else "How much of the money you invested went into this one. Shown because not every current "
            "price is available.",
        )
        for column, tooltip in enumerate(tooltips):
            self.table.horizontalHeaderItem(column).setToolTip(tooltip)

    def _show_report(self, report: Report) -> None:
        valuation = report.valuation
        currency = report.statement.currency
        by_value = all(holding.allocation_percent is not None for holding in valuation.holdings)
        self._set_headers(currency, by_value)

        rows: list[tuple[str, str, str, str]] = [
            (
                display_name(self._settings, holding.position.ticker),
                self._money(holding.position.cost_basis, currency),
                self._money(holding.market_value, currency),
                self._percent(holding.allocation_percent if by_value else holding.invested_percent),
            )
            for holding in valuation.holdings
        ]
        if valuation.holdings:
            rows.append(
                (
                    "Total",
                    self._money(valuation.portfolio.total_cost_basis, currency),
                    self._money(valuation.total_market_value, currency),
                    self._percent(Decimal(100)),
                )
            )

        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            is_total = bool(valuation.holdings) and row_number == len(rows) - 1
            for column, text in enumerate(row):
                item = QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if is_total:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row_number, column, item)
        self.table.setVisible(bool(valuation.holdings))
        self._filler.setVisible(not valuation.holdings)

    def closeEvent(self, event: QCloseEvent) -> None:
        QThreadPool.globalInstance().waitForDone(3000)
        super().closeEvent(event)
