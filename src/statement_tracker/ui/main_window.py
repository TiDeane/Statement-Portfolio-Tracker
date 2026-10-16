"""The main window: choose a statement, optionally a spreadsheet, press one button, read the result.

No calculations happen here. The window calls ``workflow`` and shows what comes back.
"""

from __future__ import annotations

import html
import sys
import threading
import traceback
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import shiboken6
from PySide6.QtCore import (
    QAbstractItemModel,
    QDate,
    QLocale,
    QModelIndex,
    QStandardPaths,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QCloseEvent, QColor, QDragEnterEvent, QDropEvent, QFont, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
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
from statement_tracker.ui.settings_dialog import SettingsDialog
from statement_tracker.ui.workers import QuestionBridge, Task
from statement_tracker.workflow import (
    Report,
    build_report,
    display_name,
    needs_price,
    update_spreadsheet,
    values_typed_in,
    with_entered_prices,
)

UNAVAILABLE = "unavailable"
NOT_IN_TOTAL = "not in total"
NO_STATEMENT = "No file chosen yet. You can also drag the file onto this window."

TABLE_HEADERS = ["Investment", "Invested", "% of invested", "Worth now", "% of worth now", "Gain or loss"]
NAME_COLUMN = 0
TICKER_ROLE = Qt.ItemDataRole.UserRole
"""Where an investment cell keeps its ticker, for renaming."""
RENAME_TIP = "Double-click to change the name shown, here and in the spreadsheet."
WORTH_COLUMN = 3
GAIN_COLUMN = 5
LAST_KNOWN_MARK = "*"
ENTERED_MARK = "(your value)"
"""Words, not a symbol: a small sign next to an amount is easily read as a plus."""
MISSING_PRICES = "Yahoo Finance has no current price for {}."
DOUBLE_CLICK_TO_ENTER = "Double-click to enter its value yourself."
LEFT_OUT_TIP = f"No current price, so it is left out of the totals. {DOUBLE_CLICK_TO_ENTER}"
WINDOW_WIDTH = 1000
MIN_WINDOW_WIDTH = 720
"""The window cannot be made narrower: below this the buttons and wrapped text get cramped."""
MIN_TABLE_HEIGHT = 115
"""Room for the header and two rows: the result table never gets smaller; more rows scroll."""

# The line at the top of each step: its text and the state the theme colours it by.
STEP_TO_DO = ("To do: choose your statement file.", "todo")
STEP_DONE = ("✓ Done", "ok")
STEP_OPTIONAL = ("Optional. You can skip this step.", "optional")
STEP_REMEMBERED = ("✓ Already done: remembered from last time.", "ok")
STEP_PICK_SPREADSHEET = ("To do: choose your spreadsheet or create a new one.", "todo")
PICK_SPREADSHEET = "Choose an Excel file you already have, or let the app create a new one."

Outcome = tuple[Report, ExportResult | None, UserFacingError | None]


def backup_text(spreadsheet: Path | None, kept: int) -> str:
    """What step 2 says about backup copies of ``spreadsheet``; empty when there is nothing to say."""
    if spreadsheet is None:
        return ""
    if kept == 0:
        return "No backup copy will be made before it is changed: backups are turned off in Settings."
    if not spreadsheet.exists():
        return ""  # a new file has nothing to back up yet
    newest = "only the most recent is kept" if kept == 1 else f"the {kept} most recent are kept"
    return f"Before it is changed, a backup copy of it is saved in the same folder (at most one a day); {newest}."


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


def waiting_for_you(ticker: str) -> str:
    """The status line while a run waits for the user to confirm a listing."""
    return f'Waiting for you: confirm which listing {ticker} is, in the "Confirm your investment" window.'


def _listed(names: list[str]) -> str:
    """Join names as a sentence does: "A", "A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _default_provider() -> PriceProvider:
    from statement_tracker.core.market_data.yahoo_provider import YahooProvider

    return YahooProvider()


class _NameDelegate(QStyledItemDelegate):
    """Edits an investment's name in its cell: the name alone, not the "(TICKER)" shown before it.

    Enter saves it through ``MainWindow.rename``, which redraws the table; Esc cancels.
    """

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self._window = window

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Leave empty to use the name from Yahoo Finance")
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        editor.setText(self._window._settings.index_name(index.data(TICKER_ROLE)) or "")  # type: ignore[attr-defined]

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex) -> None:
        if not shiboken6.isValid(self._window):
            return  # the window was closed with the editor open: nothing to save it into
        ticker, name = index.data(TICKER_ROLE), editor.text()  # type: ignore[attr-defined]
        # The table is redrawn once the editor has closed, not while it is closing.
        QTimer.singleShot(0, self._window, lambda: self._window.rename(ticker, name))


class RunStopped(Exception):
    """Ends a run the user stopped with "Back to the steps", at its next step."""


class MainWindow(QMainWindow):
    """Two pages in one window: the three steps, then the result table."""

    progressed = Signal(int, int, str)
    """Steps done, steps in total (0 = not known yet), what is happening. Safe to emit from any thread."""

    def __init__(
        self,
        settings: Settings,
        provider_factory: Callable[[], PriceProvider] = _default_provider,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__()
        self._settings = settings
        self._provider_factory = provider_factory
        self._today = today
        self._now = now
        self._report: Report | None = None
        """The result shown, kept so that a price typed in can be added to it without fetching again."""
        self._statement: Path | None = None
        self._spreadsheet: Path | None = settings.spreadsheet_path
        self._spreadsheet_from_last_time = settings.spreadsheet_path is not None
        self._wants_spreadsheet = False
        """"Update my Excel spreadsheet" is chosen but no file has been picked yet."""
        self._set_aside_spreadsheet: Path | None = None
        """The file used before "Don't use a spreadsheet" was chosen, restored if the user changes their mind."""
        self._tasks: list[Task] = []
        self._running: tuple[Task, threading.Event] | None = None
        """The run going on, and how to stop it."""
        self._stopped: list[Task] = []
        """Runs stopped by the user that the thread pool has not finished yet: kept alive until then."""
        self._locale = QLocale()
        self.ask_listing: Callable[[Resolution], str | None] = self._ask_listing
        self.show_error: Callable[[UserFacingError], object] = lambda error: dialogs.show_error(self, error)
        self.ask_retry: Callable[[UserFacingError], bool] = lambda error: dialogs.show_error(
            self, error, can_retry=True
        )
        self.show_settings: Callable[[SettingsDialog], object] = lambda dialog: dialog.exec()
        self.ask_value: Callable[[list[dialogs.ValueChoice], str, str], tuple[str, Decimal] | None] = (
            lambda choices, selected, currency: dialogs.ask_value(self, choices, selected, currency)
        )
        self._last_run: tuple[Path | None, date] = (None, today())
        self.progressed.connect(self._show_progress)
        self._bridge = QuestionBridge(self._ask_during_run, self)

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
        # The choice (none, or a spreadsheet) is a pair of radio buttons; choosing or creating the
        # file are plain actions under the second. Nothing that is an action is ever highlighted.
        self.no_spreadsheet_option = QRadioButton("&Don't use a spreadsheet: only show the results here")
        self.no_spreadsheet_option.clicked.connect(self._stop_using_spreadsheet)
        self.spreadsheet_option = QRadioButton("&Update my Excel spreadsheet")
        self.spreadsheet_option.clicked.connect(self._use_spreadsheet)
        spreadsheet_options = QButtonGroup(self)
        spreadsheet_options.addButton(self.no_spreadsheet_option)
        spreadsheet_options.addButton(self.spreadsheet_option)
        self.existing_spreadsheet_button = QPushButton("Choose my &spreadsheet...")
        self.existing_spreadsheet_button.setToolTip(
            "Pick an Excel file you already have. Your own sheets in it are not changed."
        )
        self.existing_spreadsheet_button.clicked.connect(self._choose_spreadsheet)
        self.new_spreadsheet_button = QPushButton("Create a &new one...")
        self.new_spreadsheet_button.setToolTip("Let the app create a new Excel file for you.")
        self.new_spreadsheet_button.clicked.connect(self._create_spreadsheet)
        spreadsheet_buttons = QHBoxLayout()
        spreadsheet_buttons.addWidget(self.existing_spreadsheet_button)
        spreadsheet_buttons.addWidget(self.new_spreadsheet_button)
        spreadsheet_buttons.addStretch(1)
        # The file and its buttons belong to "Update my Excel spreadsheet": indented under it, and only
        # shown while it is chosen (they mean nothing without a spreadsheet).
        self.spreadsheet_details = QWidget()
        spreadsheet_details = QVBoxLayout(self.spreadsheet_details)
        spreadsheet_details.setContentsMargins(26, 0, 0, 0)
        spreadsheet_details.addWidget(self.spreadsheet_label)
        self.backup_label = QLabel()
        self.backup_label.setObjectName("backup")
        self.backup_label.setWordWrap(True)
        self.backup_label.setToolTip("Change this in Settings.")
        spreadsheet_details.addWidget(self.backup_label)
        spreadsheet_details.addLayout(spreadsheet_buttons)
        spreadsheet_box = QGroupBox("Step 2 (optional): your Excel spreadsheet")
        self.spreadsheet_badge = QLabel()
        self.spreadsheet_badge.setObjectName("badge")
        spreadsheet_layout = QVBoxLayout(spreadsheet_box)
        spreadsheet_layout.addWidget(self.spreadsheet_badge)
        spreadsheet_layout.addWidget(self.no_spreadsheet_option)
        spreadsheet_layout.addWidget(self.spreadsheet_option)
        spreadsheet_layout.addWidget(self.spreadsheet_details)

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
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setItemDelegateForColumn(NAME_COLUMN, _NameDelegate(self))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        # It takes the room the result page has, never Qt's default preferred height, which would
        # make the window's contents taller than the window's minimum size.
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.table.setMinimumHeight(MIN_TABLE_HEIGHT)
        self.table.cellDoubleClicked.connect(self._cell_double_clicked)
        # Shown when some price is not a current one from Yahoo: fetch again, or type one in.
        self.price_bar = QWidget()
        self.price_bar_label = QLabel()
        self.price_bar_label.setWordWrap(True)
        self.retry_button = QPushButton("T&ry again")
        self.retry_button.setToolTip("Look up the prices on Yahoo Finance again.")
        self.retry_button.clicked.connect(self.start)
        self.enter_value_button = QPushButton("&Enter its value...")
        self.enter_value_button.setToolTip("Type in what an investment is worth now yourself.")
        self.enter_value_button.clicked.connect(lambda: self.enter_value())
        price_bar = QHBoxLayout(self.price_bar)
        price_bar.setContentsMargins(0, 0, 0, 0)
        price_bar.addWidget(self.price_bar_label, stretch=1)
        price_bar.addWidget(self.retry_button)
        price_bar.addWidget(self.enter_value_button)
        self.price_bar.setVisible(False)

        self.settings_button = QPushButton("Se&ttings")
        self.settings_button.setToolTip("Rename your investments, choose a listing again, or forget them.")
        self.settings_button.clicked.connect(self.open_settings)
        about_button = QPushButton("&About and privacy")
        about_button.clicked.connect(lambda: dialogs.show_about(self))
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.settings_button)
        footer.addWidget(about_button)

        # Two pages in the same window: the three steps, then the result. The window keeps its size.
        self.steps_page = QWidget()
        steps = QVBoxLayout(self.steps_page)
        steps.setContentsMargins(0, 0, 0, 0)
        steps.addWidget(intro)
        steps.addWidget(statement_box)
        steps.addWidget(spreadsheet_box)
        steps.addWidget(self.go_button)
        steps.addStretch(1)

        self.back_button = QPushButton("← &Back to the steps")
        self.back_button.setToolTip("Choose another statement or spreadsheet, or start again.")
        self.back_button.clicked.connect(self.show_steps)
        result_title = QLabel("Your investments")
        result_title.setObjectName("intro")
        result_header = QHBoxLayout()
        result_header.addWidget(result_title)
        result_header.addStretch(1)
        result_header.addWidget(self.back_button)
        self.result_page = QWidget()
        result = QVBoxLayout(self.result_page)
        result.setContentsMargins(0, 0, 0, 0)
        result.addLayout(result_header)
        result.addWidget(self.progress_bar)
        result.addWidget(self.status_label)
        result.addWidget(self.table, stretch=1)
        self._filler = QWidget()  # takes the table's place when there is nothing to list
        result.addWidget(self._filler, stretch=1)
        result.addWidget(self.price_bar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.steps_page)
        self.pages.addWidget(self.result_page)

        layout = QVBoxLayout()
        layout.addWidget(self.pages, stretch=1)
        layout.addLayout(footer)
        central = QWidget()
        central.setLayout(layout)
        self._content = central
        # The window has a minimum size (see _cap_size), but some window managers ignore it (Wayland's,
        # as under WSL). Then the contents scroll rather than being drawn over each other.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(central)
        scroll.viewport().setAutoFillBackground(False)  # the window's own background shows through
        central.setAutoFillBackground(False)
        self.setCentralWidget(scroll)

        # Buttons are highlighted only when reached with the Tab key, never just for
        # having been clicked or for being first in the window.
        for button in self.findChildren(QPushButton):
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        central.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        central.setFocus()

        self._set_headers()
        self._refresh()
        # As tall as the three steps need. The result page then uses the same window.
        self._cap_size()
        self.resize(WINDOW_WIDTH, self._content_height())

    # -- pages -------------------------------------------------------------------

    def show_steps(self) -> None:
        """Go back to the three steps. Step 3 fetches the prices again and shows the result page.

        While step 3 is running, this stops it first: nothing of that run is saved.
        """
        if self._busy():
            self.stop_run()
        self.pages.setCurrentWidget(self.steps_page)

    def stop_run(self) -> None:
        """Stop the run going on. It ends at its next step, before saving settings, prices or the
        spreadsheet; whatever it was still waiting for from Yahoo is thrown away when it comes."""
        if self._running is None or not self._busy():
            return
        task, stop = self._running
        stop.set()
        self._stopped.append(task)  # the thread pool still runs it until that next step: kept until then
        self._done()
        self._status("Stopped. Nothing was saved.", "ok")

    def _forget_task(self, task: Task) -> None:
        if task in self._stopped:
            self._stopped.remove(task)

    def _show_result_page(self) -> None:
        self.pages.setCurrentWidget(self.result_page)

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

    def _ask_during_run(self, resolution: Resolution) -> str | None:
        """Ask which listing a ticker is, saying meanwhile that the run waits for the user, not for Yahoo."""
        self._status(waiting_for_you(resolution.ticker), "busy")
        return self.ask_listing(resolution)

    def _ask_listing(self, resolution: Resolution) -> str | None:
        """Ask which listing a ticker is. "Always choose the first option" is saved at once.

        This runs while the background run waits for the answer, so nothing else is
        reading or saving the settings meanwhile; the rest of this run already follows it.
        """
        symbol, always_first = dialogs.ask_listing(self, resolution)
        if always_first and not self._settings.always_use_first_listing:
            self._settings.always_use_first_listing = True
            self._save_settings()
        return symbol

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
        """A dropped Excel file is the spreadsheet; any other file is the statement. The steps are shown,
        unless step 3 is running: a file dropped then does not stop it (only "Back to the steps" does)."""
        if not self._busy():
            self.show_steps()
        if path.suffix.lower() == ".xlsx":
            self.set_spreadsheet(path)
        else:
            self.set_statement(path)

    def _stop_using_spreadsheet(self) -> None:
        """"Don't use a spreadsheet" was chosen. The file is kept in mind for this session, in case it is chosen again."""
        if self._spreadsheet is not None:
            self._set_aside_spreadsheet = self._spreadsheet
        self._wants_spreadsheet = False
        self.set_spreadsheet(None)

    def _use_spreadsheet(self) -> None:
        """"Update my Excel spreadsheet" was chosen: back to the file set aside, or wait for one to be picked."""
        if self._spreadsheet is not None:
            return
        self._wants_spreadsheet = True
        if self._set_aside_spreadsheet is not None:
            self.set_spreadsheet(self._set_aside_spreadsheet)
        else:
            self._refresh()

    def _refresh(self) -> None:
        self.statement_label.setText(_file_text(self._statement) if self._statement else NO_STATEMENT)
        self.statement_label.setToolTip(str(self._statement) if self._statement else "")
        self._badge(self.statement_badge, *(STEP_DONE if self._statement else STEP_TO_DO))

        using = self._spreadsheet is not None or self._wants_spreadsheet
        waiting_for_file = using and self._spreadsheet is None
        self.no_spreadsheet_option.setChecked(not using)
        self.spreadsheet_option.setChecked(using)
        if self.spreadsheet_details.isHidden() == using:
            self.spreadsheet_details.setVisible(using)
            self._fit_height_to_steps()
        if self.centralWidget():
            # Files, buttons and their wrapped text change the room the steps need; measured once laid out.
            QTimer.singleShot(0, self, self._cap_size)
        if not using:
            self._badge(self.spreadsheet_badge, *STEP_OPTIONAL)
        elif waiting_for_file:
            self._badge(self.spreadsheet_badge, *STEP_PICK_SPREADSHEET)
        elif self._spreadsheet_from_last_time:
            self._badge(self.spreadsheet_badge, *STEP_REMEMBERED)
        else:
            self._badge(self.spreadsheet_badge, *STEP_DONE)
        if self._spreadsheet is None:
            self.spreadsheet_label.setText(PICK_SPREADSHEET)
        elif self._spreadsheet.exists():
            self.spreadsheet_label.setText(
                _file_text(self._spreadsheet, "It will be updated. Close it in Excel first.")
            )
        else:
            self.spreadsheet_label.setText(
                _file_text(self._spreadsheet, "It does not exist yet and will be created.")
            )
        self.spreadsheet_label.setToolTip(str(self._spreadsheet) if self._spreadsheet else "")
        self.backup_label.setText(backup_text(self._spreadsheet, self._settings.backups_kept))
        self.backup_label.setVisible(bool(self.backup_label.text()))
        theme.set_state(self.backup_label, "off" if self._settings.backups_kept == 0 else "on")
        self.go_button.setText(
            "Step 3: show my investments and update my spreadsheet"
            if self._spreadsheet
            else "Step 3: show my investments"
        )
        # With "Update my Excel spreadsheet" chosen but no file yet, there is nothing to update: wait for one.
        self.go_button.setEnabled(self._statement is not None and not waiting_for_file and not self._busy())
        self.settings_button.setEnabled(not self._busy())  # a run reads and saves the same settings
        self.back_button.setToolTip(
            "Stop looking up prices and go back to the steps. Nothing is saved."
            if self._busy()
            else "Choose another statement or spreadsheet, or start again."
        )
        self.retry_button.setEnabled(self._statement is not None and not waiting_for_file and not self._busy())
        self.enter_value_button.setEnabled(not self._busy())

    def open_settings(self) -> None:
        """Show the settings window. A result on show is worked out again if anything was changed there,
        without fetching: a forgotten price or a new name shows at once, here and in the spreadsheet."""
        dialog = SettingsDialog(self._settings, self)
        try:
            self.show_settings(dialog)
            changed = dialog.changed
        finally:
            dialog.deleteLater()  # a new one is made each time; this one must not linger as a child of the window
        self._refresh()  # step 2 says whether backups are made
        if changed and self._report is not None and not self._busy():
            report = with_entered_prices(self._report, {}, self._settings, now=self._now(), remember_listings=False)
            self._show_changed(report)

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
        steps_of_the_run = [0]  # the run's own total, once known, for the spreadsheet step after it
        stop = threading.Event()  # set by "Back to the steps" while the run is going

        def progress(done: int, total: int, text: str) -> None:
            # Called on the background thread at each step: where a stopped run ends, before it
            # saves anything. The signal carries the rest to the window's thread.
            if stop.is_set():
                raise RunStopped
            steps_of_the_run[0] = total
            self.progressed.emit(done, total + extra_steps if total else 0, text)

        def work() -> Outcome:
            typed, typed_at = values_typed_in(self._settings, spreadsheet)
            report = build_report(
                statement,
                self._provider_factory(),
                self._settings,
                chooser=self._bridge,
                progress=progress,
                typed_values=typed,
                typed_at=typed_at,
            )
            if spreadsheet is None:
                return report, None, None
            steps = steps_of_the_run[0]
            progress(steps, steps, "Updating your spreadsheet...")  # the last point a run can be stopped at
            try:
                return report, update_spreadsheet(report, self._settings, spreadsheet, today), None
            except UserFacingError as error:
                return report, None, error

        task = Task(work)
        # A stopped run's result, if it still comes, is not this window's to show any more.
        task.signals.finished.connect(lambda outcome: self._finished(outcome) if task in self._tasks else None)
        task.signals.failed.connect(lambda error: self._failed(error) if task in self._tasks else None)
        task.signals.finished.connect(lambda _: self._forget_task(task))
        task.signals.failed.connect(lambda _: self._forget_task(task))
        self._tasks.append(task)
        self._running = (task, stop)
        # The result page shows the progress, then the result. What an earlier run showed is cleared.
        self.table.setVisible(False)
        self._filler.setVisible(True)
        self.price_bar.setVisible(False)
        self._show_result_page()
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
        self._show_outcome(report, exported, export_error)

    def _cell_double_clicked(self, row: int, column: int) -> None:
        if column == NAME_COLUMN:
            return  # the name is being edited in its cell
        # Opened once the double-click itself is over, not from inside its handling.
        QTimer.singleShot(0, self, lambda: self.enter_value(row))

    def rename(self, ticker: str, name: str) -> None:
        """Show ``name`` next to ``ticker`` from now on, here and in the spreadsheet. An empty name goes
        back to the fund's name from Yahoo Finance. The spreadsheet of the last run is written again."""
        name = name.strip()
        if name == (self._settings.index_name(ticker) or ""):
            return  # nothing changed
        if name:
            self._settings.index_names[ticker] = name
        else:
            self._settings.index_names.pop(ticker, None)
        self._save_settings()
        if self._report is not None and not self._busy():
            self._show_changed(self._report)

    def enter_value(self, row: int | None = None) -> None:
        """Let the user type in what an investment Yahoo has no current price for is worth now.

        ``row`` is the table row asked about, if any. The value is the whole holding's, as the
        table shows it; it is kept as a price per share, so that it follows the shares held.
        The result and the spreadsheet are worked out again, without fetching anything.
        """
        report = self._report
        if report is None or self._busy():
            return
        holdings = report.valuation.holdings
        if row is not None and not (0 <= row < len(holdings) and needs_price(holdings[row])):
            return  # the Total row, or an investment with a current price
        choices = [
            dialogs.ValueChoice(
                ticker, display_name(self._settings, ticker), holding.position.shares, holding.price
            )
            for holding in holdings
            if needs_price(holding) and (ticker := holding.position.ticker)
        ]
        if not choices:
            return
        selected = holdings[row].position.ticker if row is not None else choices[0].ticker
        answer = self.ask_value(choices, selected, report.statement.currency)
        if answer is None:
            return
        ticker, value = answer
        shares = next(choice.shares for choice in choices if choice.ticker == ticker)
        price = value / shares
        self._show_changed(with_entered_prices(report, {ticker: price}, self._settings, now=self._now()))

    def _show_changed(self, report: Report) -> None:
        """Show ``report`` again after a change made here, and write it to the last run's spreadsheet."""
        spreadsheet, today = self._last_run[0], self._today()
        self._last_run = (spreadsheet, today)
        exported, export_error = None, None
        if spreadsheet is not None:
            try:
                exported = update_spreadsheet(report, self._settings, spreadsheet, today)
            except UserFacingError as error:
                export_error = error
        self._show_outcome(report, exported, export_error)

    def _show_outcome(
        self, report: Report, exported: ExportResult | None, export_error: UserFacingError | None
    ) -> None:
        """Show a result and the spreadsheet's update, offering to try saving it again."""
        self._report = report
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

        # The window shows no notes: the marks in the table explain themselves in their tooltips.
        if exported is not None:
            done = "created" if exported.created else "updated"
            self._status(f"Done. Your spreadsheet was {done}: {exported.destination}", "ok")
        elif export_error is not None:
            self._status("Your investments are shown below, but the spreadsheet was not updated.", "error")
        else:
            self._status("Done. Your investments are shown below.", "ok")
        if not report.valuation.holdings:
            self._status("Done. The statement has no investments that you still hold.", "ok")
        # Measured once what was just shown has been laid out: until then Qt still sizes it as hidden.
        QTimer.singleShot(0, self, self._cap_size)

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

    def _long_date(self, day: date) -> str:
        return self._locale.toString(QDate(day.year, day.month, day.day), QLocale.FormatType.LongFormat)

    def _worth_mark(self, price: MarketPrice | None) -> tuple[str, str | None]:
        """The mark after a holding's "Worth now", and its tooltip, saying where the price came from."""
        if price is None:
            return "", f"No current price. {DOUBLE_CLICK_TO_ENTER}"
        if price.last_known:
            if price.as_of is None:
                tip = "Last known price from an earlier day: Yahoo could not be reached."
            else:
                tip = f"Last known price, from {self._long_date(price.as_of.date())}: Yahoo could not be reached."
            return LAST_KNOWN_MARK, f"{tip} {DOUBLE_CLICK_TO_ENTER}"
        if price.entered:
            when = f" on {self._long_date(price.as_of.astimezone().date())}" if price.as_of else ""
            return ENTERED_MARK, (
                f"Value you entered{when}, used until Yahoo Finance has a price. Double-click to change it."
            )
        return "", None

    def _set_headers(self) -> None:
        """Column order follows the spreadsheet: each percentage sits next to the amount it is a share of."""
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        tooltips = (
            f"The fund or share you hold. {RENAME_TIP}",
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
                self._percent(holding.invested_percent) if holding.in_totals else NOT_IN_TOTAL,
                self._money(holding.market_value, currency),
                self._percent(holding.allocation_percent) if holding.in_totals else NOT_IN_TOTAL,
                self._gain(holding.unrealized_pnl, holding.percent_change, currency),
                holding.unrealized_pnl,
            )
            for holding in valuation.holdings
        ]
        if valuation.holdings:
            invested, gain = valuation.invested_in_totals, valuation.unrealized_pnl
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

        # "Worth now" at a price from an earlier run is marked with LAST_KNOWN_MARK, at one the user typed
        # in with ENTERED_MARK; the tooltip says which and from when. Each row: (mark, tooltip).
        worth_marks = [
            self._worth_mark(holding.price) if holding.in_totals else ("", LEFT_OUT_TIP)
            for holding in valuation.holdings
        ]
        left_out_rows = {index for index, holding in enumerate(valuation.holdings) if not holding.in_totals}
        if valuation.holdings:
            total_marks, total_tips = [], []
            if valuation.total_market_value is not None:
                if valuation.uses_last_known_prices:
                    total_marks.append(LAST_KNOWN_MARK)
                    total_tips.append("Includes last known prices from an earlier day, so this total is not up to date.")
                if valuation.uses_entered_prices:
                    total_marks.append(ENTERED_MARK)
                    total_tips.append("Includes values you entered yourself.")
            worth_marks.append((" ".join(total_marks), " ".join(total_tips) or None))

        colours = theme.current()
        self.table.setRowCount(len(rows))
        for row_number, (*texts, gain) in enumerate(rows):
            is_total = bool(valuation.holdings) and row_number == len(rows) - 1
            for column, text in enumerate(texts):
                mark, tip = worth_marks[row_number] if column == WORTH_COLUMN else ("", None)
                item = QTableWidgetItem(f"{text} {mark}" if mark else text)
                if column == NAME_COLUMN and not is_total:
                    # Only the name can be changed, by typing in its cell (see _NameDelegate).
                    item.setData(TICKER_ROLE, valuation.holdings[row_number].position.ticker)
                    item.setToolTip(RENAME_TIP)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if tip:
                    item.setToolTip(tip)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == GAIN_COLUMN and gain:
                    # The arrow and the colour belong to the gain or loss, never to the value itself.
                    item.setForeground(QBrush(QColor(colours.good if gain > 0 else colours.bad)))
                elif text in (UNAVAILABLE, NOT_IN_TOTAL) or row_number in left_out_rows:
                    item.setForeground(QBrush(QColor(colours.muted)))
                if column == WORTH_COLUMN and not is_total and valuation.holdings[row_number].price is None:
                    # In red, as in the spreadsheet: the value is missing, and a price can be entered here.
                    item.setBackground(QBrush(QColor(colours.missing)))
                    item.setForeground(QBrush(QColor(colours.text)))
                if is_total:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row_number, column, item)
        self.table.setVisible(bool(valuation.holdings))
        self._filler.setVisible(not valuation.holdings)
        missing = [holding.position.ticker for holding in valuation.holdings if needs_price(holding)]
        if missing:
            self.price_bar_label.setText(MISSING_PRICES.format(_listed(missing)))
        self.price_bar.setVisible(bool(missing))

    def _fit_height_to_steps(self) -> None:
        """Until the first result, keep the window as tall as the steps, shrinking as well as growing.

        Showing or hiding the spreadsheet buttons changes that height. After the first result the
        window is left at the size the user may have given it; it only grows if it must.
        """
        if self._report is not None or self._busy() or not self.centralWidget():  # also before the window is shown
            return
        # Measured once the shown or hidden buttons have been laid out, not before.
        QTimer.singleShot(0, self, self._resize_to_steps)

    def _resize_to_steps(self) -> None:
        if self._report is not None or self._busy():
            return
        self._cap_size()
        self.resize(self.width(), self._content_height())  # as when the window first opens

    def _content_height(self) -> int:
        """The height the window's contents would like, measured on them: the scroll area around
        them reports a capped size of its own."""
        self._content.layout().activate()
        return self._content.sizeHint().height()

    def _cap_size(self) -> None:
        """Keep the window from being made smaller than what it shows needs.

        Qt does not stop that by itself: below it, widgets are drawn over each other. Text that
        wraps needs the most height at the narrowest width allowed, so the minimum height is
        measured there and is then enough at every width. Called whenever what is shown changes.
        Where the window manager ignores this, the contents scroll instead.

        The minimum covers both pages, so the window does not jump in size between them.
        """
        layout = self._content.layout()
        margins = layout.contentsMargins()
        inner = MIN_WINDOW_WIDTH - margins.left() - margins.right()
        # Qt measures a stack of pages without their wrapped text, so each page is measured here.
        pages = (self.steps_page, self.result_page)
        for page in pages:
            page.layout().activate()
        self.pages.setMinimumHeight(max(page.layout().totalMinimumHeightForWidth(inner) for page in pages))
        layout.activate()
        self.setMinimumSize(MIN_WINDOW_WIDTH, layout.totalMinimumHeightForWidth(MIN_WINDOW_WIDTH))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Windows and macOS keep a window at its minimum size. Some Linux window managers do not
        # (Weston's, which WSL uses, ignores it): there, a window made too small grows back to it.
        minimum = self.minimumSize()
        if event.size().width() < minimum.width() or event.size().height() < minimum.height():
            QTimer.singleShot(0, self, self._back_to_minimum)

    def _back_to_minimum(self) -> None:
        self.resize(self.size().expandedTo(self.minimumSize()))

    def closeEvent(self, event: QCloseEvent) -> None:
        QThreadPool.globalInstance().waitForDone(3000)
        super().closeEvent(event)
