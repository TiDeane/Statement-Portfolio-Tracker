"""The Revolut stock statement CSV layout. The only format verified against a real export."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from statement_tracker.core.errors import REVOLUT_LAYOUT, MixedCurrencyError, StatementRowError
from statement_tracker.core.models import Statement, Transaction
from statement_tracker.core.parser.profiles import Row, register_profile

_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z")
_PLAIN_NUMBER = re.compile(r"\d+(\.\d+)?")
_GROUPED_NUMBER = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")
_CURRENCY = re.compile(r"[A-Z]{3}")

_REPORT = "If the file came straight from Revolut, please report this so the format can be supported."
_LAYOUT = f"{REVOLUT_LAYOUT} {_REPORT}"
"""For a row whose layout is not Revolut's: most likely another program changed the file when saving it."""


def _parse_number(text: str) -> Decimal | None:
    """Parse ``1234.56`` or ``1,234.56``. Anything else is None, never a guess."""
    if _PLAIN_NUMBER.fullmatch(text):
        return Decimal(text)
    if _GROUPED_NUMBER.fullmatch(text):
        return Decimal(text.replace(",", ""))
    return None


class RevolutStocksV1:
    """Columns: Date, Ticker, Type, Quantity, Price per share, Total Amount, Currency, FX Rate."""

    name = "revolut_stocks_v1"
    expected_header = (
        "Date",
        "Ticker",
        "Type",
        "Quantity",
        "Price per share",
        "Total Amount",
        "Currency",
        "FX Rate",
    )

    def parse(self, rows: Iterable[Row]) -> Statement:
        """Parse the rows after the header. Stops at the first row it cannot read."""
        transactions: list[Transaction] = []
        statement_currency: str | None = None
        for row, cells in rows:
            if not any(cell.strip() for cell in cells):
                continue
            transaction = self._parse_row(row, [cell.strip() for cell in cells])
            if statement_currency is None:
                statement_currency = transaction.currency
            elif transaction.currency != statement_currency:
                raise MixedCurrencyError(
                    row,
                    f"this row is in {transaction.currency}, but earlier rows are in {statement_currency}.",
                    "Statements with more than one currency are not supported yet. " + _REPORT,
                )
            transactions.append(transaction)
        if statement_currency is None:
            raise StatementRowError(
                2, "the statement has no transactions.", "Export a statement that covers your full history."
            )
        return Statement(tuple(transactions), statement_currency, self.name)

    def _parse_row(self, row: int, cells: list[str]) -> Transaction:
        if len(cells) != len(self.expected_header):
            raise StatementRowError(
                row, f"expected {len(self.expected_header)} columns but found {len(cells)}.", _LAYOUT
            )
        date_text, ticker, type_name, quantity_text, price_text, total_text, currency, fx_text = cells

        if not _TIMESTAMP.fullmatch(date_text):
            raise StatementRowError(row, f'the date "{date_text}" is not in the expected format.', _LAYOUT)
        try:
            timestamp = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        except ValueError:
            raise StatementRowError(row, f'the date "{date_text}" is not a real date.', _LAYOUT) from None

        if not type_name:
            raise StatementRowError(row, "the Type column is empty.", _LAYOUT)
        if not _CURRENCY.fullmatch(currency):
            raise StatementRowError(row, f'the currency "{currency}" is not a three-letter code.', _LAYOUT)

        fx_rate = _parse_number(fx_text)
        if fx_rate is None:
            raise StatementRowError(row, f'the FX Rate "{fx_text}" is not a number.', _LAYOUT)
        if fx_rate != 1:
            raise MixedCurrencyError(
                row,
                f"the FX Rate is {fx_text}, which means a currency conversion.",
                "Rows with a currency conversion are not supported yet. " + _REPORT,
            )

        quantity = None
        if quantity_text:
            quantity = _parse_number(quantity_text)
            if quantity is None:
                raise StatementRowError(row, f'the quantity "{quantity_text}" is not a number.', _LAYOUT)

        price = self._parse_amount(row, "Price per share", price_text, currency) if price_text else None
        if not total_text:
            raise StatementRowError(row, "the Total Amount column is empty.", _LAYOUT)
        total = self._parse_amount(row, "Total Amount", total_text, currency)

        return Transaction(
            row=row,
            timestamp=timestamp,
            type=type_name,
            ticker=ticker or None,
            quantity=quantity,
            price_per_share=price,
            total_amount=total,
            currency=currency,
        )

    @staticmethod
    def _parse_amount(row: int, column: str, text: str, currency: str) -> Decimal:
        """Parse an amount such as ``EUR 355.45`` and check its currency code."""
        code, separator, number_text = text.partition(" ")
        number = _parse_number(number_text) if separator else None
        if number is None or not _CURRENCY.fullmatch(code):
            raise StatementRowError(
                row,
                f'the {column} "{text}" is not an amount this app can read '
                f'(expected something like "{currency} 1,234.56").',
                _LAYOUT,
            )
        if code != currency:
            raise MixedCurrencyError(
                row,
                f"the {column} is in {code}, but the row's currency is {currency}.",
                "Statements with more than one currency are not supported yet. " + _REPORT,
            )
        return number


register_profile(RevolutStocksV1())
