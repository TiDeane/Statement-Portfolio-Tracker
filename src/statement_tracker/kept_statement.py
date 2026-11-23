"""A copy of the last statement read, kept next to the settings file.

With it, today's values can be looked up again without loading a new statement: the
holdings are the ones of that statement, so anything bought, sold or paid in since its
latest transaction is not included, and the user is told so.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.models import Statement
from statement_tracker.core.parser import load_statement

KEPT_STATEMENT_FILE = "last_statement.csv"


@dataclass(frozen=True)
class KeptStatement:
    """The statement kept from last time."""

    path: Path
    latest: date
    """The day of its latest transaction, in the computer's time zone."""


def kept_statement_path(settings_path: Path) -> Path:
    """Where the statement is kept for the settings file at ``settings_path``."""
    return settings_path.with_name(KEPT_STATEMENT_FILE)


def is_kept_statement(path: Path, settings_path: Path) -> bool:
    """True if ``path`` is the statement kept for the settings file at ``settings_path``."""
    kept = kept_statement_path(settings_path)
    try:
        return path.resolve() == kept.resolve()
    except OSError:
        return False


def latest_transaction_day(statement: Statement) -> date:
    """The day of the statement's latest transaction, in the computer's time zone."""
    return max(transaction.timestamp for transaction in statement.transactions).astimezone().date()


def keep_statement(path: Path, settings_path: Path) -> None:
    """Keep a copy of the statement at ``path``, replacing the one kept before, in one step.

    Not being able to keep it never stops a run: the next one just needs a statement again.
    """
    if is_kept_statement(path, settings_path):
        return
    target = kept_statement_path(settings_path)
    temporary = target.with_suffix(".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, temporary)
        os.replace(temporary, target)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)


def forget_kept_statement(settings_path: Path) -> None:
    """Delete the statement kept from last time, if there is one. Raises OSError if it cannot be deleted."""
    kept_statement_path(settings_path).unlink(missing_ok=True)


def find_kept_statement(settings_path: Path) -> KeptStatement | None:
    """The statement kept from last time, or None if there is none or it can no longer be read."""
    path = kept_statement_path(settings_path)
    if not path.exists():
        return None
    try:
        statement = load_statement(path)
    except (UserFacingError, OSError):
        return None
    if not statement.transactions:
        return None
    return KeptStatement(path, latest_transaction_day(statement))
