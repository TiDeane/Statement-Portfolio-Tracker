"""Errors that are shown to the user in plain language."""

from __future__ import annotations


class UserFacingError(Exception):
    """A problem explained as what happened and what to do next.

    ``details`` holds technical information for bug reports; it is never shown
    by default.
    """

    def __init__(self, what_happened: str, what_to_do: str, details: str = "") -> None:
        super().__init__(what_happened)
        self.what_happened = what_happened
        self.what_to_do = what_to_do
        self.details = details

    def __str__(self) -> str:
        return f"{self.what_happened}\n{self.what_to_do}"


class StatementFileError(UserFacingError):
    """The file could not be opened or read as text."""


REVOLUT_LAYOUT = (
    "In a statement as Revolut exports it, the columns are separated by commas, a date reads like "
    "2025-01-06T10:00:00.000Z, an amount like EUR 1,234.56 (with a full stop before the cents), and a "
    "quantity like 1.47328346. Saving the file in a spreadsheet program can change that: export the statement "
    "from Revolut again and choose that file without saving it first."
)
"""What to do when a statement's layout is not Revolut's, as when another program rewrote its dates, numbers
or column separators while saving it. (A save that only adds an invisible mark at the start, or other line
endings, changes no data; such files are read as usual.)"""

_SEPARATORS = {";": "semicolons", "\t": "tabs"}


class StatementFormatError(UserFacingError):
    """The file's columns are not a format this app knows."""

    def __init__(self, expected: tuple[str, ...], found: tuple[str, ...]) -> None:
        self.found = found
        # A spreadsheet program saving a CSV with the separator of the computer's own settings (";" where
        # the comma is the decimal sign) leaves the right headings in a single column.
        separator = next(
            (
                separator
                for separator in _SEPARATORS
                if len(found) == 1 and tuple(part.strip() for part in found[0].split(separator)) == expected
            ),
            None,
        )
        if separator is not None:
            super().__init__(
                f"This file has the columns of a Revolut stock statement, but they are separated by "
                f"{_SEPARATORS[separator]} instead of commas.",
                REVOLUT_LAYOUT,
            )
            return
        super().__init__(
            "This file does not look like a Revolut stock statement.\n"
            f"Expected columns: {', '.join(expected)}\n"
            f"Found columns: {', '.join(found) if found else '(none)'}",
            "Export the stock statement again as a CSV file and load that file. "
            "If Revolut changed its export format, please report it.",
        )


class StatementRowError(UserFacingError):
    """One row of the statement could not be understood."""

    def __init__(self, row: int, problem: str, what_to_do: str) -> None:
        self.row = row
        super().__init__(f"Row {row}: {problem}", what_to_do)


class UnknownTransactionTypeError(StatementRowError):
    """The row has a Type this app has not been taught to handle."""

    def __init__(self, row: int, type_name: str, known: tuple[str, ...]) -> None:
        self.type_name = type_name
        super().__init__(
            row,
            f'the transaction type "{type_name}" is not one this app understands '
            f"(known types: {', '.join(known)}).",
            "Please report this type so it can be supported. You can also choose to ignore "
            "unknown types, but the results may then be wrong.",
        )


class MixedCurrencyError(StatementRowError):
    """The statement contains more than one currency, or a currency conversion."""


class IncompleteStatementError(StatementRowError):
    """A sale of more shares than the statement shows were bought."""

    def __init__(self, row: int, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(
            row,
            f"{ticker} shares are sold that the statement never shows being bought.",
            "The statement looks incomplete. Export the full history, from your first "
            "transaction until today, and load that file.",
        )
