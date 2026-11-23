"""What one open window works with: the settings, the statement, the page shown, and the user's answers.

The answers (which file, an error acknowledged, a yes or no) go through replaceable callables, so
that tests can stand in for the user's own answers.
"""

from __future__ import annotations

import sys
import threading
import traceback
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QStandardPaths, QThreadPool, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.market_data.provider import PriceProvider
from statement_tracker.core.models import Position
from statement_tracker.core.ticker_resolver import Confidence, Resolution
from statement_tracker.gui.dialog_host import DialogHost
from statement_tracker.kept_statement import KeptStatement, find_kept_statement
from statement_tracker.settings import Settings
from statement_tracker.gui.undo import ChangeHistory
from statement_tracker.gui.workers import QuestionBridge, Task
from statement_tracker.workflow import Report, build_report, read_statement, values_typed_in, with_entered_prices

PAGES = ("welcome", "home", "settings")
UNEXPECTED = UserFacingError(
    "Something unexpected went wrong.",
    'Please report this problem. "Copy details" copies the information needed to fix it.',
)


def listing_question(resolution: Resolution, currency: str) -> dict:
    """The texts and options of the dialog asking which listing ``resolution.ticker`` is."""
    ticker = resolution.ticker
    if resolution.confidence is Confidence.AMBIGUOUS:
        intro = (f"{ticker} is traded on more than one stock exchange. They're usually the same fund at almost the "
                 "same price. Pick the one whose name and currency match your Revolut app. You're only asked once.")
    elif resolution.confidence is Confidence.CONFIDENT:
        intro = (f"Choose which fund {ticker} is. The one that fits your purchases is chosen; you can also type a "
                 "Yahoo Finance symbol.")
    elif resolution.candidates:
        intro = f"The app could not tell for sure which fund {ticker} is. Pick the one that matches yours, if it is in the list."
    else:
        intro = (f"The app could not find {ticker} on Yahoo Finance, so it cannot look up its price. If you know its "
                 "Yahoo Finance symbol (for example ABCD.DE), type it below. Otherwise skip it: it is then shown without "
                 "a price, and you can enter its value yourself.")
    options = []
    for candidate in resolution.candidates:
        info = candidate.info
        quoted = info.currency or ""
        converted = f"in {quoted}, converted to {currency}" if quoted and currency and quoted != currency else quoted
        detail = " \u00b7 ".join(part for part in (info.exchange, converted, info.symbol) if part)
        options.append({"name": info.name or info.symbol, "detail": detail, "symbol": info.symbol, "match": candidate.is_match})
    return {
        "title": f"Which one is {ticker}?",
        "intro": intro,
        "options": options,
        "fieldLabel": "Not in the list? Type its Yahoo Finance symbol" if options else "Its Yahoo Finance symbol",
        "useLabel": "Use this listing" if options else "Use this symbol",
    }


class RunStopped(Exception):
    """A run the user stopped (or replaced) before it finished: nothing of it is saved or shown."""


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


def show_in_folder(path: Path) -> None:
    """Open the folder that holds ``path`` in the system's file manager, with the file selected where the
    system can do that (Windows Explorer, the macOS Finder); elsewhere, just the folder."""
    if sys.platform == "win32":
        # Two arguments, so that a path with spaces reaches Explorer as one: /select, "C:\...\My file.xlsx".
        QProcess.startDetached("explorer", ["/select,", str(path)])
    elif sys.platform == "darwin":
        QProcess.startDetached("open", ["-R", str(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


class Session(QObject):
    """The state behind the window. Exposed to QML as ``session``."""

    pageChanged = Signal()
    busyChanged = Signal()
    reportChanged = Signal()
    settingsChanged = Signal()
    spreadsheetChanged = Signal()
    """Another spreadsheet (or none) is to be updated from now on."""
    """Something shown changed in the settings: the spreadsheet chosen, the backups, a name."""
    progressed = Signal(int, int, str)
    """A run's progress: steps done, steps in all (0 while unknown), what is being done."""

    def __init__(
        self,
        settings: Settings,
        provider_factory: Callable[[], PriceProvider],
        today: Callable[[], date],
        now: Callable[[], datetime],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.provider_factory = provider_factory
        self.today = today
        self.now = now
        self.history = ChangeHistory(settings)
        """Changes to investments, for Ctrl+Z: shared by Home and Settings."""
        self.dialogs = DialogHost(self)
        self.kept: KeptStatement | None = find_kept_statement(settings.path)
        self.statement: Path | None = self.kept.path if self.kept else None
        """The statement Home works out: the one kept from last time, or the one first launch chose."""
        self._page = "home" if self.kept else "welcome"
        self.report: Report | None = None
        """What the last finished run worked out."""
        self.fetched_at: datetime | None = None
        self.loading_positions: tuple[Position, ...] = ()
        """The investments of the run going on, listed while their prices come in."""
        self.loading_currency = ""
        self.statement_latest: date | None = self.kept.latest if self.kept else None
        """The day of the latest transaction in the statement Home shows."""
        self._running: tuple[Task, threading.Event] | None = None
        self._alive: set[Task] = set()
        """Runs the thread pool has not finished yet, stopped ones included: kept alive until then."""
        self._bridge = QuestionBridge(self._ask_during_run, self)
        self.updated_this_session: Path | None = None
        """The spreadsheet updated while the app is open: changes made since are written to it at once."""

        # The user's answers. Replaced in tests, which stand in for the user.
        self.ask_open_file: Callable[[str, str, Path], Path | None] = self._ask_open_file
        self.ask_save_file: Callable[[str, Path], Path | None] = self._ask_save_file
        self.show_error: Callable[[UserFacingError], object] = self._show_error
        self.confirm: Callable[[str, str], bool] = self._confirm
        self.show_in_folder: Callable[[Path], object] = show_in_folder
        self.ask_listing: Callable[[Resolution], tuple[str | None, bool]] = self._ask_listing
        self.ask_value: Callable[[list, str, str], tuple[str, Decimal] | None] = self._ask_value
        """What an investment is worth now: (ticker, value of the whole holding), or None."""
        """Which listing an investment is: (symbol or None to skip, "always take the first")."""

        from statement_tracker.gui.welcome import Welcome  # it needs this module's Session

        from statement_tracker.gui.home import Home
        from statement_tracker.gui.settings_page import SettingsPage

        self._welcome = Welcome(self)
        self._home = Home(self)
        self._settings_page = SettingsPage(self)

    # -- pages -------------------------------------------------------------------

    def _get_page(self) -> str:
        return self._page

    page = Property(str, _get_page, notify=pageChanged)

    @Slot(str)
    def goTo(self, page: str) -> None:
        if page not in PAGES:
            raise ValueError(page)
        if page != self._page:
            self._page = page
            self.pageChanged.emit()

    def open_home(self) -> None:
        """Show Home, and fetch today's prices for the statement chosen."""
        self.goTo("home")
        self.refresh()

    def start(self) -> None:
        """The window is showing: on Home, fetch today's prices."""
        if self._page == "home":
            self.refresh()

    welcome = Property(QObject, lambda self: self._welcome, constant=True)
    home = Property(QObject, lambda self: self._home, constant=True)
    settingsPage = Property(QObject, lambda self: self._settings_page, constant=True)

    @Slot()
    def showHelp(self) -> None:
        """Where the statement comes from, the privacy text and the version."""
        from statement_tracker import __version__
        from statement_tracker.gui.texts import ALL_TIME_NOTE, PRIVACY_TEXT, RELEASES_URL, REVOLUT_STEPS

        self.dialogs.ask("help", {
            "steps": list(REVOLUT_STEPS),
            "allTime": ALL_TIME_NOTE,
            "privacy": PRIVACY_TEXT,
            "version": f"Statement Portfolio Tracker, version {__version__}",
            "releases": RELEASES_URL,
        })

    def forget_statement(self) -> None:
        """The statement kept was forgotten (in Settings): the app asks for one again."""
        self.kept, self.statement, self.statement_latest = None, None, None
        self._welcome.reset()
        self.settingsChanged.emit()

    # -- runs ----------------------------------------------------------------------

    def _get_busy(self) -> bool:
        return self._running is not None

    busy = Property(bool, _get_busy, notify=busyChanged)

    def refresh(self) -> None:
        """Fetch today's prices for the statement, again if they were fetched before."""
        if self.statement is not None:
            self.start_run(self.statement)

    def use_statement(self, statement: Path) -> bool:
        """A newer statement, chosen or dropped on Home: fetch its prices; it becomes the one kept.
        One that does not read is explained, and the statement shown stays (False)."""
        self.remember_folder(statement.parent)
        if not self.start_run(statement):
            return False
        self.statement = statement
        return True

    def start_run(self, statement: Path) -> bool:
        """Read ``statement``, fetch prices and work out the report, without freezing the window.
        A run going on is stopped first: nothing of it is saved or shown. False if the statement
        does not read (the user is told why, and nothing changes)."""
        try:
            summary = read_statement(statement)
        except UserFacingError as error:
            self.show_error(error)
            return False
        self.stop_run()
        self.loading_positions, self.loading_currency = summary.positions, summary.currency
        self.statement_latest = summary.latest
        stop = threading.Event()
        spreadsheet = self.settings.spreadsheet_path

        def progress(done: int, total: int, text: str) -> None:
            # On the run's thread, at each step: where a stopped run ends, before it saves anything.
            if stop.is_set():
                raise RunStopped
            self.progressed.emit(done, total, text)

        def work() -> Report:
            typed, typed_at = values_typed_in(self.settings, spreadsheet)
            return build_report(
                statement,
                self.provider_factory(),
                self.settings,
                chooser=self._bridge,
                progress=progress,
                typed_values=typed,
                typed_at=typed_at,
            )

        task = Task(work)
        task.signals.finished.connect(lambda report: self._finished(task, report))
        task.signals.failed.connect(lambda error: self._failed(task, error))
        self._running = (task, stop)
        self._alive.add(task)
        self.busyChanged.emit()
        QThreadPool.globalInstance().start(task)
        return True

    @Slot()
    def stopRun(self) -> None:
        """The window is closing."""
        self.stop_run()

    def stop_run(self) -> None:
        """Stop the run going on, if any, at its next step. Nothing of it is saved or shown."""
        if self._running is not None:
            self._running[1].set()
            self._running = None
            self.busyChanged.emit()

    def _is_current(self, task: Task) -> bool:
        return self._running is not None and self._running[0] is task

    def _finished(self, task: Task, report: Report) -> None:
        self._alive.discard(task)
        if not self._is_current(task):
            return  # stopped: not this window's to show any more
        self._running = None
        self.report = report
        self.fetched_at = self.now()
        self.kept = find_kept_statement(self.settings.path)  # the run kept its statement
        self.history.run_finished()
        self.reportChanged.emit()
        self.busyChanged.emit()

    def _failed(self, task: Task, error: object) -> None:
        self._alive.discard(task)
        if not self._is_current(task) or isinstance(error, RunStopped):
            return
        self._running = None
        self.history.run_finished()  # it may have saved listings before failing
        self.busyChanged.emit()
        if not isinstance(error, UserFacingError):
            details = "".join(traceback.format_exception(error)) if isinstance(error, BaseException) else repr(error)
            error = UserFacingError(UNEXPECTED.what_happened, UNEXPECTED.what_to_do, details=details)
        self.show_error(error)

    @Slot()
    def undo(self) -> None:
        """Take back the last change to an investment, made on Home or in Settings (not during a fetch)."""
        self._went_back(self.history.undo)

    @Slot()
    def redo(self) -> None:
        """Make the last change undone again."""
        self._went_back(self.history.redo)

    def _went_back(self, step: Callable[[], str | None]) -> None:
        if self.busy or self._page == "welcome" or step() is None:
            return
        self.save_settings()
        if self.report is not None:
            self.set_report(with_entered_prices(self.report, {}, self.settings, now=self.now(), remember_listings=False))
            self._home.rewrite_spreadsheet()
        self.settingsChanged.emit()

    def set_report(self, report: Report) -> None:
        """Show ``report``, worked out again from the last run without fetching (a value entered, say)."""
        self.report = report
        self.reportChanged.emit()

    def _ask_during_run(self, resolution: Resolution) -> str | None:
        """Which listing an investment is, asked while a run waits (Home says it waits for the user).
        "Always take the first" is saved at once: the rest of this run already follows it."""
        self.progressed.emit(0, 0, f"Waiting for you: which listing {resolution.ticker} is.")
        symbol, always_first = self.ask_listing(resolution)
        if always_first and not self.settings.always_use_first_listing:
            self.settings.always_use_first_listing = True
            self.save_settings()
        return symbol

    # -- files ---------------------------------------------------------------------

    def start_folder(self) -> Path:
        """Where file dialogs open: the last folder used, else a sensible first guess."""
        folder = self.settings.last_folder
        if folder and folder.exists():
            return folder
        return default_start_folder()

    def remember_folder(self, folder: Path) -> None:
        """Open file dialogs in ``folder`` from now on."""
        if self.settings.last_folder != folder:
            self.settings.last_folder = folder
            self.save_settings()

    def use_spreadsheet(self, path: Path | None) -> None:
        """Update this spreadsheet from now on (chosen, created or dropped), or none."""
        changed = path != self.settings.spreadsheet_path
        if changed:
            self.updated_this_session = None
        self.settings.spreadsheet_path = path
        self.save_settings()
        if changed:
            self.spreadsheetChanged.emit()
        self.settingsChanged.emit()

    def save_settings(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass  # not being able to remember a choice must never stop the user

    # -- from the window ---------------------------------------------------------

    @Slot(list)
    def dropFiles(self, urls: list) -> None:
        """Files dropped on the window, as file URLs: an Excel file is a spreadsheet, anything else a statement."""
        for url in urls:
            path = Path(QUrl(url).toLocalFile())
            on_welcome = self._page == "welcome"
            if path.suffix.lower() == ".xlsx":
                if on_welcome and self._welcome.step == "spreadsheet":
                    self._welcome.use_spreadsheet(path)
                elif self._page == "home":
                    self.use_spreadsheet(path)
            elif on_welcome and self._welcome.step == "statement":
                self._welcome.use_statement(path)
            elif self._page == "home":
                self.use_statement(path)

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    # -- the user's answers, in the window's own dialogs -------------------------

    def _show_error(self, error: UserFacingError) -> None:
        self.dialogs.ask(
            "message",
            {"title": error.what_happened, "text": error.what_to_do, "details": error.details, "confirm": "OK", "cancel": ""},
        )

    def _confirm(self, question: str, confirm: str) -> bool:
        """Ask a yes-or-no question. Its first paragraph is the dialog's title, the rest its text."""
        title, _, text = question.partition("\n\n")
        answer = self.dialogs.ask("message", {"title": title, "text": text, "details": "", "confirm": confirm, "cancel": "Cancel"})
        return answer is not None

    def _ask_value(self, choices: list, selected: str, currency: str) -> tuple[str, Decimal] | None:
        """Ask what the ``selected`` investment is worth now, until an amount above zero is typed or the
        dialog is cancelled."""
        from statement_tracker.gui.formatting import parse_amount
        from statement_tracker.gui.home import value_question

        choice = next(choice for choice in choices if choice.ticker == selected)
        question = value_question(choice, currency)
        while True:
            answer = self.dialogs.ask("value", question)
            if answer is None:
                return None
            value = parse_amount(str(answer.get("text", "")))
            if value is not None:
                return choice.ticker, value
            question = {**question, "error": "Type an amount above zero, like 2,040.00."}

    def _ask_listing(self, resolution: Resolution) -> tuple[str | None, bool]:
        """Ask which listing an investment is, in the window's dialog."""
        answer = self.dialogs.ask("listing", listing_question(resolution, self.loading_currency))
        if answer is None:
            return None, False
        return (str(answer.get("symbol") or "").strip() or None), bool(answer.get("always"))

    def _ask_open_file(self, title: str, kinds: str, start: Path) -> Path | None:
        answer = self.dialogs.ask(
            "openFile", {"title": title, "nameFilters": [kinds, "All files (*)"], "folder": QUrl.fromLocalFile(str(start))}
        )
        return Path(QUrl(answer["file"]).toLocalFile()) if answer else None

    def _ask_save_file(self, title: str, start: Path) -> Path | None:
        answer = self.dialogs.ask(
            "saveFile",
            {"title": title, "nameFilters": ["Excel spreadsheets (*.xlsx)"], "folder": QUrl.fromLocalFile(str(start.parent)),
             "file": QUrl.fromLocalFile(str(start))},
        )
        return Path(QUrl(answer["file"]).toLocalFile()) if answer else None
