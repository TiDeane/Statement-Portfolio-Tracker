"""Format profiles: one per statement layout. Adding a profile never touches the calculator."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Protocol

from statement_tracker.core.errors import StatementFileError, StatementFormatError
from statement_tracker.core.models import Statement

Row = tuple[int, Sequence[str]]
"""A row number as the user sees it in the file (the header is row 1) and its cells."""


class FormatProfile(Protocol):
    """Knows one statement layout: its header and how to read its rows."""

    name: str
    expected_header: tuple[str, ...]

    def parse(self, rows: Iterable[Row]) -> Statement:
        """Turn the rows after the header into a Statement, or raise a UserFacingError."""
        ...


_PROFILES: list[FormatProfile] = []


def register_profile(profile: FormatProfile) -> None:
    """Make a format profile available to :func:`load_statement`."""
    _PROFILES.append(profile)


def known_profiles() -> tuple[FormatProfile, ...]:
    """Return the registered profiles, in registration order."""
    return tuple(_PROFILES)


def find_profile(header: Sequence[str]) -> FormatProfile:
    """Return the profile whose header matches exactly, or raise StatementFormatError."""
    found = tuple(header)
    for profile in _PROFILES:
        if profile.expected_header == found:
            return profile
    expected = _PROFILES[0].expected_header if _PROFILES else ()
    raise StatementFormatError(expected, found)


def parse_rows(rows: Iterable[Row]) -> Statement:
    """Parse rows whose first item is the header row."""
    iterator = iter(rows)
    _, header = next(iterator, (1, ()))
    return find_profile(header).parse(iterator)


def _read_csv(path: Path) -> Iterator[Row]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for cells in reader:
            yield reader.line_num, cells


def load_statement(path: Path) -> Statement:
    """Read a statement file and parse it with the matching format profile."""
    try:
        return parse_rows(_read_csv(path))
    except FileNotFoundError as exc:
        raise StatementFileError(
            f'The file "{path.name}" could not be found.',
            "Check that the file still exists and try again.",
            details=str(exc),
        ) from exc
    except OSError as exc:
        raise StatementFileError(
            f'The file "{path.name}" could not be opened.',
            "Check that you are allowed to read the file and that it is not open in another program.",
            details=str(exc),
        ) from exc
    except (UnicodeDecodeError, csv.Error) as exc:
        raise StatementFileError(
            f'The file "{path.name}" is not a readable CSV text file.',
            "Export the statement from Revolut as CSV (not PDF or Excel) and load that file.",
            details=str(exc),
        ) from exc


# Importing the profile modules registers them.
from statement_tracker.core.parser import revolut_stocks_v1  # noqa: E402, F401
