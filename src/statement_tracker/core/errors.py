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


class StatementFormatError(UserFacingError):
    """The file's columns are not a format this app knows."""

    def __init__(self, expected: tuple[str, ...], found: tuple[str, ...]) -> None:
        self.found = found
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
