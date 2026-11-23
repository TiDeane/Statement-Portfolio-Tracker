"""What one open window works with: the settings, the statement, the page shown, and the user's answers.

The answers (which file, an error acknowledged, a yes or no) go through replaceable callables, so
that tests can stand in for the user's own answers, as they do for the Widgets window.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QStandardPaths, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.market_data.provider import PriceProvider
from statement_tracker.gui.dialog_host import DialogHost
from statement_tracker.kept_statement import KeptStatement, find_kept_statement
from statement_tracker.settings import Settings
from statement_tracker.ui.undo import ChangeHistory

PAGES = ("welcome", "home", "settings")


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

        # The user's answers. Replaced in tests, which stand in for the user.
        self.ask_open_file: Callable[[str, str, Path], Path | None] = self._ask_open_file
        self.ask_save_file: Callable[[str, Path], Path | None] = self._ask_save_file
        self.show_error: Callable[[UserFacingError], object] = self._show_error
        self.confirm: Callable[[str, str], bool] = self._confirm
        self.show_in_folder: Callable[[Path], object] = show_in_folder

        from statement_tracker.gui.welcome import Welcome  # it needs this module's Session

        self._welcome = Welcome(self)

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
        """Show Home, for the statement chosen."""
        self.goTo("home")

    welcome = Property(QObject, lambda self: self._welcome, constant=True)

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
            elif on_welcome and self._welcome.step == "statement":
                self._welcome.use_statement(path)

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
