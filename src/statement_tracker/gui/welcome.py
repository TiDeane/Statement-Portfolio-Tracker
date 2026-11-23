"""First launch: the statement, then whether to keep a spreadsheet up to date. Exposed to QML as
``session.welcome``. Each step shows what was picked and moves on only with its button."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from statement_tracker.core.errors import UserFacingError
from statement_tracker.gui.formatting import day_text
from statement_tracker.gui.texts import ALL_TIME_NOTE, REVOLUT_STEPS
from statement_tracker.workflow import StatementSummary, read_statement

if TYPE_CHECKING:
    from statement_tracker.gui.session import Session

STATEMENT_FILES = "Statement files (*.csv)"
SPREADSHEET_FILES = "Excel spreadsheets (*.xlsx)"
NEW_SPREADSHEET_NAME = "My investments.xlsx"


def statement_facts(summary: StatementSummary) -> list[str]:
    """The two lines first launch shows about a statement that was read."""
    transactions = "1 transaction" if summary.transactions == 1 else f"{summary.transactions} transactions"
    if summary.held == 0:
        held = "No investments you still hold"
    elif summary.held == 1:
        held = "1 investment you still hold"
    else:
        held = f"{summary.held} investments you still hold"
    return [f"{transactions}, the latest on {day_text(summary.latest)}", held]


class Welcome(QObject):
    """What first launch shows, and what its buttons do."""

    changed = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._session = session
        self._step = "statement"
        self._statement: Path | None = None
        self._facts: list[str] = []
        self._choice = ""
        """Step 2's option: "existing", "new" or "none"; "" until one is chosen."""
        self._spreadsheet: Path | None = None

    def reset(self) -> None:
        """Start afresh: step 1, nothing chosen (first launch shown again after the statement is forgotten)."""
        self._step, self._statement, self._facts, self._choice, self._spreadsheet = "statement", None, [], "", None
        self.changed.emit()

    # -- what is shown -------------------------------------------------------------

    def _get_step(self) -> str:
        return self._step

    def _get_chosen(self) -> bool:
        return self._statement is not None

    def _get_name(self) -> str:
        return self._statement.name if self._statement else ""

    def _get_facts(self) -> list[str]:
        return self._facts

    def _can_continue(self) -> bool:
        return self._statement is not None if self._step == "statement" else self._choice != ""

    def _get_choice(self) -> str:
        return self._choice

    def _get_sheet_name(self) -> str:
        return self._spreadsheet.name if self._spreadsheet else ""

    def _get_sheet_folder(self) -> str:
        return f"in {self._spreadsheet.parent}" if self._spreadsheet else ""

    step = Property(str, _get_step, notify=changed)
    """"statement" or "spreadsheet"."""
    statementChosen = Property(bool, _get_chosen, notify=changed)
    statementName = Property(str, _get_name, notify=changed)
    statementFacts = Property(list, _get_facts, notify=changed)
    canContinue = Property(bool, _can_continue, notify=changed)
    spreadsheetChoice = Property(str, _get_choice, notify=changed)
    spreadsheetName = Property(str, _get_sheet_name, notify=changed)
    spreadsheetFolder = Property(str, _get_sheet_folder, notify=changed)
    revolutSteps = Property(list, lambda self: list(REVOLUT_STEPS), constant=True)
    allTimeNote = Property(str, lambda self: ALL_TIME_NOTE, constant=True)

    @property
    def statement(self) -> Path | None:
        """The statement read in step 1, if any."""
        return self._statement

    # -- step 1 ----------------------------------------------------------------------

    @Slot()
    def chooseStatement(self) -> None:
        chosen = self._session.ask_open_file("Choose your Revolut statement", STATEMENT_FILES, self._session.start_folder())
        if chosen is not None:
            self.use_statement(chosen)

    def use_statement(self, path: Path) -> None:
        """Read ``path``; if it reads, it is the statement chosen. If not, say why and keep what was there."""
        self._session.remember_folder(path.parent)
        try:
            summary = read_statement(path)
        except UserFacingError as error:
            self._session.show_error(error)
            return
        self._statement = path
        self._facts = statement_facts(summary)
        self.changed.emit()

    @Slot()
    def next(self) -> None:
        """Continue: on to the spreadsheet, unless one is remembered already; from step 2, to Home."""
        if not self._can_continue():
            return
        if self._step == "spreadsheet":
            self._finish()
        elif self._session.settings.spreadsheet_path is not None:
            self._finish()  # upgrading from version 1.3 or earlier: the spreadsheet is known
        else:
            self._step = "spreadsheet"
            self.changed.emit()

    # -- step 2 ----------------------------------------------------------------------

    def _sheet_folder(self) -> Path:
        if self._spreadsheet is not None and self._spreadsheet.parent.exists():
            return self._spreadsheet.parent
        return self._session.start_folder()

    @Slot()
    def chooseExisting(self) -> None:
        chosen = self._session.ask_open_file("Choose your Excel spreadsheet", SPREADSHEET_FILES, self._sheet_folder())
        if chosen is not None:
            self.use_spreadsheet(chosen)

    def use_spreadsheet(self, path: Path) -> None:
        """An Excel file the user has, chosen or dropped."""
        self._choice, self._spreadsheet = "existing", path
        self.changed.emit()

    @Slot()
    def chooseNew(self) -> None:
        chosen = self._session.ask_save_file("Where should the new spreadsheet be saved?", self._sheet_folder() / NEW_SPREADSHEET_NAME)
        if chosen is not None:
            self._choice = "new"
            self._spreadsheet = chosen if chosen.suffix.lower() == ".xlsx" else chosen.with_name(chosen.name + ".xlsx")
            self.changed.emit()

    @Slot()
    def chooseNone(self) -> None:
        self._choice, self._spreadsheet = "none", None
        self.changed.emit()

    @Slot()
    def back(self) -> None:
        self._step = "statement"
        self.changed.emit()

    def _finish(self) -> None:
        """Remember the spreadsheet chosen (if step 2 was shown) and open Home for the statement."""
        if self._step == "spreadsheet":
            self._session.settings.spreadsheet_path = self._spreadsheet if self._choice != "none" else None
            self._session.save_settings()
        self._session.statement = self._statement
        self._session.open_home()
