"""Excel export with openpyxl.

Only two sheets are ever written, and only if they are recognisably ours; every
other sheet in the user's workbook is left exactly as it is. The holdings sheet
is rewritten each run; the history sheet gets one row per date.

Saving rewrites the whole file. openpyxl keeps values, formulas, styles,
conditional formatting and charts through that, but drops pictures (without
Pillow), shapes and text boxes, so a backup copy is made before the first write
to an existing workbook.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from statement_tracker import APP_NAME
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.base import ExportResult
from statement_tracker.core.models import PortfolioValuation

DEFAULT_HOLDINGS_SHEET = "Current Holdings"
DEFAULT_HISTORY_SHEET = "Portfolio History"
UNAVAILABLE = "unavailable"
TOTAL_LABEL = "Total"

HOLDINGS_HEADER = (
    "Index",
    "Invested",
    "% of Invested",
    "Current Value",
    "% of Current Value",
    "% Up/Down",
    "Dividends",
    "Currency",
)
# Headers this app wrote in earlier versions. A sheet with one of these is still ours,
# so it is rewritten in the current layout instead of being refused.
_EARLIER_HOLDINGS_HEADERS = (
    (
        "Index",
        "Invested",
        "Current Value",
        "Share of Current Value",
        "Share of Invested",
        "% Up/Down",
        "Dividends",
        "Currency",
    ),
    ("Index", "Invested", "Current Value", "Current %", "Invested %", "% Up/Down", "Dividends", "Currency"),
    (
        "Index",
        "Invested",
        "Current Value",
        "Current %",
        "Invested %",
        "Shares",
        "Average Cost",
        "Current Price",
        "Unrealized PnL",
        "% Up/Down",
        "Dividends",
        "Yahoo Symbol",
        "Price Time",
        "Currency",
    ),
)
HISTORY_HEADER = (
    "Date",
    "Total Cost Basis",
    "Total Market Value",
    "Unrealized PnL",
    "Realized PnL",
    "ROI %",
    "Net Worth",
    "Net Deposits",
    "Gain vs Deposits",
)
_MONEY_FORMAT = "0.00"
_PERCENT_FORMAT = "0.00%"
_DATE_FORMAT = "yyyy-mm-dd"
# Column number -> number format. Columns not listed keep Excel's general format.
_VALUE_COLUMN = HOLDINGS_HEADER.index("Current Value") + 1
_HOLDINGS_FORMATS = {
    2: _MONEY_FORMAT,
    3: _PERCENT_FORMAT,
    4: _MONEY_FORMAT,
    5: _PERCENT_FORMAT,
    6: _PERCENT_FORMAT,
    7: _MONEY_FORMAT,
}
_HEADER_ROW_HEIGHT = 30
_ROW_HEIGHT = 24
"""Points. Excel's default is 15; taller rows are easier to read."""
_HISTORY_FORMATS = {1: _DATE_FORMAT, 6: _PERCENT_FORMAT} | {
    column: _MONEY_FORMAT for column in (2, 3, 4, 5, 7, 8, 9)
}
_HEADER_FILL_COLOUR = "1F4E78"
_HEADER_TEXT_COLOUR = "FFFFFF"
_BORDER_COLOUR = "000000"
_HUNDRED = Decimal(100)


def _cell(value: Decimal | None) -> Decimal | str:
    """A number for Excel, or the word "unavailable": never a blank that formulas read as zero."""
    return UNAVAILABLE if value is None else value


def _percent(value: Decimal | None) -> Decimal | str:
    """A percentage as Excel stores it (21.08% is 0.2108), shown with a % sign by the cell format."""
    return UNAVAILABLE if value is None else value / _HUNDRED


def _comment(text: str) -> Any:
    from openpyxl.comments import Comment

    return Comment(text, APP_NAME, width=220, height=70)


def _shown_length(value: Any, number_format: str | None) -> int:
    """Roughly how many characters Excel shows for a cell, for sizing columns."""
    if value is None:
        return 0
    if isinstance(value, (date, datetime)):
        return 10
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        if number_format == _PERCENT_FORMAT:
            return len(f"{value * 100:.2f}%")
        if number_format == _MONEY_FORMAT:
            return len(f"{value:.2f}")
    return len(str(value))


def _style(sheet: Any, formats: dict[int, str], bold_last_row: bool = False) -> None:
    """Coloured bold header, black outline on every cell, number formats, columns wide enough for their text."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import column_index_from_string, get_column_letter

    edge = Side(style="thin", color=_BORDER_COLOUR)
    border = Border(left=edge, right=edge, top=edge, bottom=edge)
    header_fill = PatternFill(fill_type="solid", start_color=_HEADER_FILL_COLOUR, end_color=_HEADER_FILL_COLOUR)
    header_font = Font(bold=True, color=_HEADER_TEXT_COLOUR)

    for column in range(1, sheet.max_column + 1):
        number_format = formats.get(column)
        widest = 0
        for row in range(1, sheet.max_row + 1):
            cell = sheet.cell(row=row, column=column)
            cell.border = border
            if row == 1:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                widest = max(widest, len(str(cell.value or "")))
            else:
                if number_format:
                    cell.number_format = number_format
                cell.font = Font(bold=bold_last_row and row == sheet.max_row)
                cell.alignment = Alignment(vertical="center")
                widest = max(widest, _shown_length(cell.value, number_format))
        sheet.column_dimensions[get_column_letter(column)].width = widest + 3
    for row in range(1, sheet.max_row + 1):
        sheet.row_dimensions[row].height = _HEADER_ROW_HEIGHT if row == 1 else _ROW_HEIGHT
    # Forget widths of columns an earlier, wider layout used.
    for letter in list(sheet.column_dimensions):
        if column_index_from_string(letter) > sheet.max_column:
            del sheet.column_dimensions[letter]
    sheet.freeze_panes = "A2"


class ExcelExporter:
    """Writes "Current Holdings" and "Portfolio History" into an .xlsx workbook."""

    def __init__(
        self,
        path: Path,
        holdings_sheet: str = DEFAULT_HOLDINGS_SHEET,
        history_sheet: str = DEFAULT_HISTORY_SHEET,
        index_names: Mapping[str, str] | None = None,
    ) -> None:
        self.path = path
        self.index_names = dict(index_names or {})
        """Names to show next to tickers in the Index column, e.g. "(ABCD) World fund"."""
        self.holdings_sheet = holdings_sheet
        self.history_sheet = history_sheet

    def export(self, valuation: PortfolioValuation, today: date) -> ExportResult:
        """Update the workbook, creating it (or our sheets) if missing."""
        if self.path.suffix.lower() != ".xlsx":
            raise UserFacingError(
                f'"{self.path.name}" is not an .xlsx spreadsheet.',
                "Choose an Excel workbook whose name ends in .xlsx (not .xls, .xlsm or .csv).",
            )
        workbook, created = self._open()
        first_write = not created and not (
            self.holdings_sheet in workbook.sheetnames or self.history_sheet in workbook.sheetnames
        )

        holdings = self._sheet(workbook, self.holdings_sheet, HOLDINGS_HEADER, _EARLIER_HOLDINGS_HEADERS)
        history = self._sheet(workbook, self.history_sheet, HISTORY_HEADER)
        if created:
            for name in [name for name in workbook.sheetnames if name not in (self.holdings_sheet, self.history_sheet)]:
                del workbook[name]

        written = self._write_holdings(holdings, valuation)
        # A history row is dated today, so it is only written when every value is today's.
        last_known = valuation.uses_last_known_prices
        history_action = "skipped" if last_known else self._write_history(history, valuation, today)
        _style(holdings, _HOLDINGS_FORMATS, bold_last_row=written > 0)
        _style(history, _HISTORY_FORMATS)

        notes: list[str] = []
        if first_write:
            backup = self._backup()
            notes.append(f'A backup of the spreadsheet as it was is in "{backup.name}".')
        if valuation.total_market_value is None:
            notes.append(
                f'Not every current value is available, so no row was written to "{self.history_sheet}" '
                "this time. Existing history was not changed."
            )
        elif last_known:
            notes.append(
                "Some values use a price from an earlier day because Yahoo could not be reached, so no row "
                f'was written to "{self.history_sheet}" this time. Existing history was not changed.'
            )
        self._save(workbook)
        return ExportResult(str(self.path), created, written, history_action, tuple(notes))

    # -- workbook handling -------------------------------------------------------

    def _open(self) -> tuple[Any, bool]:
        from openpyxl import Workbook, load_workbook
        from openpyxl.utils.exceptions import InvalidFileException

        if not self.path.exists():
            if not self.path.parent.exists():
                raise UserFacingError(
                    f'The folder "{self.path.parent}" does not exist.',
                    "Choose a folder that exists for the spreadsheet.",
                )
            return Workbook(), True
        try:
            return load_workbook(self.path), False
        except PermissionError as exc:
            raise self._locked(exc) from exc
        except (InvalidFileException, BadZipFile, KeyError, OSError, ValueError) as exc:
            raise UserFacingError(
                f'"{self.path.name}" could not be opened as an Excel workbook.',
                "Check that it is a real .xlsx file and not damaged, or choose another file.",
                details=repr(exc),
            ) from exc

    def _sheet(
        self,
        workbook: Any,
        name: str,
        header: tuple[str, ...],
        earlier_headers: tuple[tuple[str, ...], ...] = (),
    ) -> Any:
        """Return our sheet, creating it if missing. Refuse a sheet that is not ours."""
        if name not in workbook.sheetnames:
            sheet = workbook.create_sheet(name)
            sheet.append(header)
            return sheet
        sheet = workbook[name]
        found = tuple(cell.value for cell in sheet[1])
        while found and found[-1] is None:
            found = found[:-1]
        if sheet.max_row == 1 and not found:
            for column, title in enumerate(header, start=1):
                sheet.cell(row=1, column=column, value=title)
        elif found != header and found not in earlier_headers:
            raise UserFacingError(
                f'The spreadsheet already has a sheet called "{name}", but it was not made by this app.',
                "Rename that sheet in Excel, or choose another spreadsheet. Nothing was changed.",
            )
        return sheet

    def _backup(self) -> Path:
        backup = self.path.with_name(f"{self.path.stem}_backup_before_first_update{self.path.suffix}")
        if not backup.exists():
            shutil.copy2(self.path, backup)
        return backup

    def _locked(self, exc: Exception) -> UserFacingError:
        return UserFacingError(
            f'"{self.path.name}" could not be saved because it is open in another program.',
            "Close the spreadsheet in Excel and try again. Nothing was changed.",
            details=repr(exc),
        )

    def _save(self, workbook: Any) -> None:
        # Save beside the target and swap it in, so a failed save never leaves half a file.
        temporary = self.path.with_name(f"~{self.path.stem}.saving{self.path.suffix}")
        try:
            workbook.save(temporary)
            os.replace(temporary, self.path)
        except PermissionError as exc:
            raise self._locked(exc) from exc
        except OSError as exc:
            raise UserFacingError(
                f'"{self.path.name}" could not be saved.',
                "Check that the folder still exists and that there is free disk space, then try again.",
                details=repr(exc),
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    # -- sheet contents ----------------------------------------------------------

    def _write_holdings(self, sheet: Any, valuation: PortfolioValuation) -> int:
        """Rewrite the whole table. The sheet itself stays, so formulas pointing at it keep working."""
        if sheet.max_column > len(HOLDINGS_HEADER):
            sheet.delete_cols(len(HOLDINGS_HEADER) + 1, sheet.max_column - len(HOLDINGS_HEADER))
        sheet.delete_rows(1, sheet.max_row)
        rows: list[list[Any]] = [list(HOLDINGS_HEADER)]
        currency = valuation.portfolio.currency
        # "Current %" is a formula, as in the user's own sheet: the row's current value divided by
        # the Total row's. Without a total there is nothing to divide by, so it says unavailable.
        total_row = len(valuation.holdings) + 2
        has_total = valuation.total_market_value is not None and valuation.total_market_value > 0
        for row, holding in enumerate(valuation.holdings, start=2):
            position = holding.position
            name = self.index_names.get(position.ticker)
            rows.append(
                [
                    f"({position.ticker}) {name}" if name else position.ticker,
                    position.cost_basis,
                    _percent(holding.invested_percent),
                    _cell(holding.market_value),
                    f"=D{row}/D${total_row}" if has_total else UNAVAILABLE,
                    _percent(holding.percent_change),
                    position.dividends,
                    currency,
                ]
            )
        if valuation.holdings:
            invested = valuation.portfolio.total_cost_basis
            unrealized = valuation.unrealized_pnl
            rows.append(
                [
                    TOTAL_LABEL,
                    invested,
                    _percent(_HUNDRED if invested > 0 else None),
                    _cell(valuation.total_market_value),
                    f"=D{total_row}/D${total_row}" if has_total else UNAVAILABLE,
                    _cell(unrealized / invested if unrealized is not None and invested > 0 else None),
                    sum((holding.position.dividends for holding in valuation.holdings), Decimal(0)),
                    currency,
                ]
            )
        for row_number, values in enumerate(rows, start=1):
            for column, value in enumerate(values, start=1):
                sheet.cell(row=row_number, column=column, value=value)

        # A value at a price from an earlier run gets a comment (Excel shows a red corner) saying from when.
        for row, holding in enumerate(valuation.holdings, start=2):
            if holding.price is not None and holding.price.last_known:
                day = holding.price.as_of.date().isoformat() if holding.price.as_of else "an earlier day"
                sheet.cell(row=row, column=_VALUE_COLUMN).comment = _comment(
                    f"Last known price, from {day}. Yahoo could not be reached when this was written."
                )
        if valuation.uses_last_known_prices and valuation.total_market_value is not None:
            sheet.cell(row=total_row, column=_VALUE_COLUMN).comment = _comment(
                "Includes last known prices from an earlier day, so this total is not up to date."
            )
        return len(valuation.holdings)

    def _write_history(self, sheet: Any, valuation: PortfolioValuation, today: date) -> str:
        """Add today's row, or update it if today already has one. Other rows are never touched."""
        portfolio = valuation.portfolio
        if valuation.total_market_value is None or valuation.unrealized_pnl is None:
            return "skipped"
        cost_basis = portfolio.total_cost_basis
        values = [
            today,
            cost_basis,
            valuation.total_market_value,
            valuation.unrealized_pnl,
            portfolio.realized_pnl,
            _cell(valuation.unrealized_pnl / cost_basis if cost_basis > 0 else None),
            valuation.net_worth,
            portfolio.net_deposits,
            valuation.gain_vs_deposits,
        ]

        target = None
        for row in range(2, sheet.max_row + 1):
            existing = sheet.cell(row=row, column=1).value
            if isinstance(existing, datetime):
                existing = existing.date()
            if existing == today or existing == today.isoformat():
                target = row
                break
        action = "updated" if target else "added"
        target = target or sheet.max_row + 1
        for column, value in enumerate(values, start=1):
            sheet.cell(row=target, column=column, value=value)
        return action
