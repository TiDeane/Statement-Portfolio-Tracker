"""A copy of the last statement read, kept next to the settings file.

With it, today's values can be looked up again without loading a new statement: the
holdings are the ones of that statement, so anything bought, sold or paid in since its
latest transaction is not included, and the user is told so. Beside it, a small record of
where the statement was read from, so the user can be told which file it was.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.files import replace as replace_file
from statement_tracker.core.models import Statement
from statement_tracker.core.parser import load_statement

KEPT_STATEMENT_FILE = "last_statement.csv"
KEPT_SOURCE_FILE = "last_statement.json"
"""Where the kept statement was read from: {"read_from": "<path>"}."""


@dataclass(frozen=True)
class KeptStatement:
    """The statement kept from last time."""

    path: Path
    latest: date
    """The day of its latest transaction, in the computer's time zone."""
    source: Path | None = None
    """The file it was copied from, or None if that was not recorded (a copy kept by an earlier version)."""

    def is_copy_of(self, statement: Path) -> bool:
        """True if this is the copy of ``statement``: the statement was read from there."""
        return self.source is not None and self.source.resolve() == statement.resolve()


def kept_statement_path(settings_path: Path) -> Path:
    """Where the statement is kept for the settings file at ``settings_path``."""
    return settings_path.with_name(KEPT_STATEMENT_FILE)


def _source_record(settings_path: Path) -> Path:
    return settings_path.with_name(KEPT_SOURCE_FILE)


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
    """Keep a copy of the statement at ``path``, replacing the one kept before, in one step, and record
    where it was read from.

    Not being able to keep it never stops a run: the next one just needs a statement again. Not being
    able to record where it came from leaves it unrecorded, never paired with another file's.
    """
    if is_kept_statement(path, settings_path):
        return
    target = kept_statement_path(settings_path)
    temporary = target.with_suffix(".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, temporary)
        replace_file(temporary, target)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)
        return
    record = _source_record(settings_path)
    try:
        written = record.with_suffix(".tmp")
        written.write_text(json.dumps({"read_from": str(path.resolve())}), encoding="utf-8")
        replace_file(written, record)
    except OSError:
        with contextlib.suppress(OSError):
            record.unlink(missing_ok=True)


def forget_kept_statement(settings_path: Path) -> None:
    """Delete the statement kept from last time, if there is one, and the record of where it came from.
    Raises OSError if the statement cannot be deleted."""
    kept_statement_path(settings_path).unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        _source_record(settings_path).unlink(missing_ok=True)


def _read_source(settings_path: Path) -> Path | None:
    try:
        recorded = json.loads(_source_record(settings_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    read_from = recorded.get("read_from") if isinstance(recorded, dict) else None
    return Path(read_from) if isinstance(read_from, str) and read_from else None


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
    return KeptStatement(path, latest_transaction_day(statement), _read_source(settings_path))
