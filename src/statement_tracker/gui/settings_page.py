"""The Settings page: the investments the app keeps, the statement, the spreadsheet and its backups,
and about and privacy. Exposed to QML as ``session.settingsPage``. Every change is saved at once."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPersistentModelIndex, Property, Qt, Signal, Slot

from statement_tracker import __version__
from statement_tracker.core.exporters.excel import MAX_BACKUPS_KEPT
from statement_tracker.gui.formatting import day_text
from statement_tracker.gui.texts import PRIVACY_TEXT, RELEASES_URL
from statement_tracker.gui.welcome import SPREADSHEET_FILES, STATEMENT_FILES, new_spreadsheet_name
from statement_tracker.gui.home import statement_place
from statement_tracker.kept_statement import forget_kept_statement
from statement_tracker.price_cache import PriceCache
from statement_tracker.settings import APPEARANCES, Settings
from statement_tracker.gui.undo import ASK_AGAIN, EVERYTHING, NAME
from statement_tracker.workflow import with_entered_prices

if TYPE_CHECKING:
    from statement_tracker.gui.session import Session

NOTHING_REMEMBERED = "No investments are remembered yet. They appear here after your first run."
BACKUPS_HELP = (
    "Before the first change each day, a copy of the file is saved beside it. Once there are more than this, "
    "the oldest goes. 0 turns backups off."
)
DISCLAIMER = "Unofficial: not made by or affiliated with Revolut. Not financial advice. Prices come from Yahoo Finance and may be delayed or wrong."


@dataclass(frozen=True)
class InvestmentRow:
    """One investment as Settings lists it."""

    ticker: str
    name: str
    detail: str
    """"TICKER · symbol, exchange, currency", or what of it is known."""
    status: str
    edit_name: str
    """The user's own name, to start renaming from."""


ROLE_NAMES = {
    Qt.ItemDataRole.UserRole + number: "".join(part if index == 0 else part.title() for index, part in enumerate(field.name.split("_")))
    for number, field in enumerate(fields(InvestmentRow))
}
_ROLE_FIELDS = {role: field.name for role, field in zip(ROLE_NAMES, fields(InvestmentRow), strict=True)}


def investment_rows(settings: Settings, prices: PriceCache) -> list[InvestmentRow]:
    """Every investment the app keeps something about: a listing, a name or a value typed in."""
    entered = prices.entered_tickers()
    rows = []
    for ticker in sorted(set(settings.known_tickers()) | entered):
        choice = settings.ticker_choices.get(ticker)
        if ticker in settings.ask_again:
            status = "Asks you next time"
        elif choice is None:
            status = "Not matched yet"
        else:
            status = "Chosen by you" if choice.confirmed else "Matched automatically"
        if ticker in entered:
            status += "; value entered by you"
        listing = ", ".join(part for part in (choice.symbol, choice.exchange, choice.currency) if part) if choice else ""
        rows.append(
            InvestmentRow(
                ticker,
                settings.index_name(ticker) or ticker,
                f"{ticker} · {listing}" if listing else ticker,
                status,
                settings.index_names.get(ticker, ""),
            )
        )
    return rows


class InvestmentsModel(QAbstractListModel):
    """Settings' list of investments."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[InvestmentRow] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role not in _ROLE_FIELDS:
            return None
        return getattr(self._rows[index.row()], _ROLE_FIELDS[role])

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in ROLE_NAMES.items()}

    def set_rows(self, rows: list[InvestmentRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()


class SettingsPage(QObject):
    """What Settings shows, and what its buttons do."""

    changed = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._session = session
        self._investments = InvestmentsModel(self)
        self._count = 0
        self._touched = False
        """Something shown on Home was changed here: Home's values are worked out again on leaving."""
        session.settingsChanged.connect(self.refresh)
        session.reportChanged.connect(self.refresh)
        session.pageChanged.connect(self.refresh)

    @property
    def _settings(self) -> Settings:
        return self._session.settings

    def _prices(self) -> PriceCache:
        return PriceCache.beside(self._settings.path)

    def refresh(self) -> None:
        rows = investment_rows(self._settings, self._prices())
        self._count = len(rows)
        self._investments.set_rows(rows)
        self.changed.emit()

    # -- what is shown -------------------------------------------------------------

    def _statement_line(self) -> str:
        kept = self._session.kept
        return f"Latest transaction {day_text(kept.latest)}" if kept else "No statement is kept."

    def _statement_place(self) -> tuple[str, str, str]:
        kept = self._session.kept
        return statement_place(kept.path if kept else None, kept, self._settings.path)

    def _sheet_folder(self) -> str:
        sheet = self._settings.spreadsheet_path
        return f"In {sheet.parent}" if sheet else ""

    investments = Property(QObject, lambda self: self._investments, constant=True)
    hasInvestments = Property(bool, lambda self: self._count > 0, notify=changed)
    nothingRemembered = Property(str, lambda self: NOTHING_REMEMBERED, constant=True)
    alwaysFirst = Property(bool, lambda self: self._settings.always_use_first_listing, notify=changed)
    hasStatement = Property(bool, lambda self: self._session.kept is not None, notify=changed)
    statementLine = Property(str, _statement_line, notify=changed)
    statementName = Property(str, lambda self: self._statement_place()[0], notify=changed)
    statementFolder = Property(str, lambda self: self._statement_place()[1], notify=changed)
    statementNote = Property(str, lambda self: self._statement_place()[2], notify=changed)
    hasSpreadsheet = Property(bool, lambda self: self._settings.spreadsheet_path is not None, notify=changed)
    spreadsheetName = Property(
        str, lambda self: self._settings.spreadsheet_path.name if self._settings.spreadsheet_path else "", notify=changed
    )
    spreadsheetFolder = Property(str, _sheet_folder, notify=changed)
    backupsKept = Property(int, lambda self: self._settings.backups_kept, notify=changed)
    maxBackups = Property(int, lambda self: MAX_BACKUPS_KEPT, constant=True)
    backupsHelp = Property(str, lambda self: BACKUPS_HELP, constant=True)
    appearance = Property(str, lambda self: self._settings.appearance, notify=changed)
    version = Property(str, lambda self: f"Version {__version__}", constant=True)
    releasesUrl = Property(str, lambda self: RELEASES_URL, constant=True)
    privacyText = Property(str, lambda self: PRIVACY_TEXT, constant=True)
    disclaimer = Property(str, lambda self: DISCLAIMER, constant=True)

    # -- changing ------------------------------------------------------------------

    def _saved(self) -> None:
        self._touched = True
        self._session.save_settings()
        self._session.settingsChanged.emit()

    @Slot(str, str)
    def rename(self, ticker: str, name: str) -> None:
        name = name.strip()
        settings = self._settings
        if name == (settings.index_names.get(ticker) or ""):
            return
        self._session.history.record(f"the new name of {ticker}", [ticker], {NAME})
        if name:
            settings.index_names[ticker] = name
        else:
            settings.index_names.pop(ticker, None)
        self._saved()

    @Slot(str)
    def chooseAgain(self, ticker: str) -> None:
        """Have the next fetch ask which listing ``ticker`` is. Until then the current one is kept."""
        if ticker not in self._settings.ticker_choices:
            return
        self._session.history.record(f"choosing the listing of {ticker} next time", [ticker], {ASK_AGAIN}, clears_on_run=True)
        self._settings.ask_again.add(ticker)
        self._saved()

    @Slot(str)
    def forget(self, ticker: str) -> None:
        """Forget the listing, the name and the value entered for ``ticker``, after asking."""
        if not self._session.confirm(
            f"Forget {ticker}?\n\nThe next time prices are fetched, the app looks for its listing again, asking you if "
            "it cannot tell. The name you gave it and the value you entered for it are removed.",
            "Forget",
        ):
            return
        self._session.history.record(f"forgetting {ticker}", [ticker], EVERYTHING, clears_on_run=True)
        self._settings.forget(ticker)
        prices = self._prices()
        prices.forget_entered(ticker)
        prices.save()
        self._saved()

    @Slot()
    def forgetAll(self) -> None:
        """Forget every investment's listing, name and value entered, after asking."""
        tickers = [row.ticker for row in investment_rows(self._settings, self._prices())]
        if not tickers:
            return
        count = "your one investment" if len(tickers) == 1 else f"all {len(tickers)} investments"
        if not self._session.confirm(
            f"Forget {count}?\n\nTheir listings, the names you gave them and the values you entered are removed. The "
            "next time prices are fetched, the app looks for their listings again, asking you when it cannot tell.\n\n"
            "Your spreadsheet, your statement from last time and the last prices found on Yahoo Finance are kept.",
            "Forget all",
        ):
            return
        self._session.history.record("forgetting all investments", tickers, EVERYTHING, clears_on_run=True)
        self._settings.forget_all()
        prices = self._prices()
        prices.forget_all_entered()
        prices.save()
        self._saved()

    @Slot(bool)
    def setAlwaysFirst(self, on: bool) -> None:
        self._settings.always_use_first_listing = on  # not undoable: switching it again does that
        self._saved()

    @Slot(int)
    def setBackupsKept(self, count: int) -> None:
        self._settings.backups_kept = min(max(count, 0), MAX_BACKUPS_KEPT)
        self._session.save_settings()
        self._session.settingsChanged.emit()

    @Slot(str)
    def setAppearance(self, choice: str) -> None:
        """Light, dark, or as the computer is: applied at once and remembered."""
        if choice not in APPEARANCES:
            return
        self._settings.appearance = choice
        self._session.theme.set_choice(choice)
        self._session.save_settings()
        self.changed.emit()

    @Slot()
    def useNewerStatement(self) -> None:
        chosen = self._session.ask_open_file("Choose your Revolut statement", STATEMENT_FILES, self._session.start_folder())
        if chosen is not None:
            self._session.use_statement(chosen)
            self._session.goTo("home")

    @Slot()
    def forgetStatement(self) -> None:
        """Delete the app's copy of the statement, after asking. Not undoable: the copy is gone."""
        if self._session.kept is None or not self._session.confirm(
            "Forget your statement from last time?\n\nThe app's copy of it is deleted, and the app asks for a statement "
            "again. The next statement you use is kept in its place. Your investments, your spreadsheet and the "
            "statement file you downloaded are not changed.\n\nThis cannot be undone.",
            "Forget it",
        ):
            return
        try:
            forget_kept_statement(self._settings.path)
        except OSError:
            return
        self._session.forget_statement()

    @Slot()
    def openFolder(self) -> None:
        if self._settings.spreadsheet_path is not None:
            self._session.show_in_folder(self._settings.spreadsheet_path)

    @Slot()
    def chooseSpreadsheet(self) -> None:
        sheet = self._settings.spreadsheet_path
        start = sheet.parent if sheet else self._session.start_folder()
        chosen = self._session.ask_open_file("Choose your Excel spreadsheet", SPREADSHEET_FILES, start)
        if chosen is not None:
            self._session.use_spreadsheet(chosen)

    @Slot()
    def createSpreadsheet(self) -> None:
        chosen = self._session.ask_save_file("Where should the new spreadsheet be saved?", self._session.start_folder() / new_spreadsheet_name(self._session.today()))
        if chosen is not None:
            sheet = chosen if chosen.suffix.lower() == ".xlsx" else chosen.with_name(chosen.name + ".xlsx")
            self._session.use_spreadsheet(sheet)
            self._session.new_spreadsheet = sheet  # created by Home once it shows again

    @Slot()
    def stopUsingSpreadsheet(self) -> None:
        self._session.use_spreadsheet(None)

    @Slot()
    def back(self) -> None:
        """Back to Home, its values worked out again if anything shown there changed here (G5); to first
        launch when no statement is kept."""
        session = self._session
        if self._touched and session.report is not None and not session.busy:
            session.set_report(with_entered_prices(session.report, {}, self._settings, now=session.now(), remember_listings=False))
            session.home.rewrite_spreadsheet()
        self._touched = False
        session.goTo("home" if session.statement is not None else "welcome")
