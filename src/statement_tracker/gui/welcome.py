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

    # -- what is shown -------------------------------------------------------------

    def _get_step(self) -> str:
        return self._step

    def _get_chosen(self) -> bool:
        return self._statement is not None

    def _get_name(self) -> str:
        return self._statement.name if self._statement else ""

    def _get_facts(self) -> list[str]:
        return self._facts

    step = Property(str, _get_step, notify=changed)
    """"statement" or "spreadsheet"."""
    statementChosen = Property(bool, _get_chosen, notify=changed)
    statementName = Property(str, _get_name, notify=changed)
    statementFacts = Property(list, _get_facts, notify=changed)
    canContinue = Property(bool, _get_chosen, notify=changed)
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
        """Continue: on to the spreadsheet."""
        if self._statement is None:
            return
        self._step = "spreadsheet"
        self.changed.emit()
