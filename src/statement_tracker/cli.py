"""Plain-text command line over the core, for testing and for people who prefer a terminal.

    python -m statement_tracker.cli STATEMENT.csv

prints one row per investment still held: index, amount invested, approximate
current value, and its share of the total current value.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TextIO

from statement_tracker import APP_NAME, __version__
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.market_data.provider import PriceProvider
from statement_tracker.core.ticker_resolver import Confidence, Resolution
from statement_tracker.settings import Settings
from statement_tracker.workflow import Chooser, Report, build_report, update_spreadsheet

UNAVAILABLE = "unavailable"
_CENT = Decimal("0.01")


def _money(value: Decimal | None) -> str:
    return UNAVAILABLE if value is None else str(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _number(value: Decimal | None, places: str) -> str:
    return UNAVAILABLE if value is None else str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def percent_is_by_value(report: Report) -> bool:
    """True if every holding has a current value, so "Current %" can be its share of the total value."""
    return all(holding.allocation_percent is not None for holding in report.valuation.holdings)


def report_rows(report: Report, details: bool = False) -> list[list[str]]:
    """Return the header row and one row per open holding, as text.

    "Current %" is each holding's share of the total current value. If any
    current value is missing, the column falls back to the share of the total
    amount invested, and its header says so.
    """
    currency = report.statement.currency
    by_value = percent_is_by_value(report)
    header = [
        "Index",
        f"Invested ({currency})",
        f"Current value ({currency} approx.)",
        "Current %" if by_value else "Current % (of invested)",
    ]
    if details:
        header += [
            "Shares",
            f"Average cost ({currency})",
            f"Price used ({currency})",
            "Yahoo symbol",
            "Price time",
            f"Realized gain ({currency})",
            f"Dividends ({currency})",
        ]
    rows = [header]
    for holding in report.valuation.holdings:
        position, price = holding.position, holding.price
        row = [
            position.ticker,
            _money(position.cost_basis),
            _money(holding.market_value),
            _money(holding.allocation_percent if by_value else holding.invested_percent),
        ]
        if details:
            row += [
                str(position.shares),
                _number(position.average_cost, "0.0001"),
                _number(price.price if price else None, "0.0001"),
                price.symbol if price else UNAVAILABLE,
                price.as_of.isoformat(timespec="minutes") if price and price.as_of else UNAVAILABLE,
                _money(position.realized_pnl),
                _money(position.dividends),
            ]
        rows.append(row)
    return rows


def write_report(report: Report, output: TextIO, table: bool = False, details: bool = False) -> None:
    """Write the rows as comma-separated values, or as an aligned table."""
    rows = report_rows(report, details)
    if not table:
        csv.writer(output, lineterminator="\n").writerows(rows)
        return
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [cell.rjust(width) for cell, width in zip(row[1:], widths[1:])]
        output.write("  ".join(cells).rstrip() + "\n")


def _prompting_chooser(errors: TextIO) -> Chooser:
    """Ask on the terminal which listing a ticker is."""

    def choose(resolution: Resolution) -> str | None:
        ticker = resolution.ticker
        if resolution.confidence is Confidence.AMBIGUOUS:
            print(f"\nMore than one listing fits {ticker}. Which one do you hold?", file=errors)
        else:
            print(f"\n{ticker} could not be matched to a listing automatically.", file=errors)
        for number, candidate in enumerate(resolution.candidates, start=1):
            info = candidate.info
            details = ", ".join(part for part in (info.name, info.exchange, info.currency) if part)
            if candidate.comparable:
                fit = f"{candidate.matched} of {candidate.checked} of your purchases fit its prices"
            else:
                fit = "other currency, purchases could not be compared"
            print(f"  {number}. {info.symbol}  {details}  [{fit}]", file=errors)
        print(
            "Type a number, or a Yahoo symbol, or just press Enter to skip this investment: ",
            end="",
            file=errors,
            flush=True,
        )
        answer = sys.stdin.readline().strip()
        if not answer:
            return None
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(resolution.candidates):
                return resolution.candidates[index - 1].info.symbol
            print("That number is not in the list; skipping this investment.", file=errors)
            return None
        return answer

    return choose


def _parse_pairs(pairs: Sequence[str], option: str, value_name: str) -> dict[str, str]:
    """Parse repeated ``TICKER=VALUE`` options."""
    parsed = {}
    for pair in pairs:
        ticker, separator, value = pair.partition("=")
        if not separator or not ticker.strip() or not value.strip():
            raise UserFacingError(
                f'"{pair}" is not a valid {option} value.',
                f"Write it as TICKER={value_name}, with the ticker exactly as in the statement.",
            )
        parsed[ticker.strip()] = value.strip()
    return parsed


def main(
    argv: Sequence[str] | None = None,
    provider: PriceProvider | None = None,
    output: TextIO | None = None,
    errors: TextIO | None = None,
    today: date | None = None,
) -> int:
    """Run the command line. Returns 0 on success, 2 when the statement could not be processed."""
    output = output or sys.stdout
    errors = errors or sys.stderr
    parser = argparse.ArgumentParser(
        prog="statement-tracker-cli",
        description="Print, for each investment in a Revolut stock statement: index, amount invested, "
        "approximate current value, and share of the total current value.",
    )
    parser.add_argument("statement", type=Path, help="the statement CSV file exported from Revolut")
    parser.add_argument("--table", action="store_true", help="print an aligned table instead of comma-separated rows")
    parser.add_argument(
        "--details",
        action="store_true",
        help="add columns for checking the numbers: shares, average cost, price used, Yahoo symbol, "
        "price time, realized gain and dividends",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        metavar="TICKER=YAHOOSYMBOL",
        help="use this Yahoo symbol for a ticker (remembered for next time); may be repeated",
    )
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        metavar="TICKER=NAME",
        help='name shown next to a ticker in the spreadsheet, e.g. --name "ABCD=World fund" '
        "(remembered; without it the fund name from Yahoo is used); may be repeated",
    )
    parser.add_argument(
        "--spreadsheet",
        type=Path,
        metavar="FILE.xlsx",
        help="update this Excel workbook (created if missing) and remember it; "
        "later runs update the remembered workbook without being asked",
    )
    parser.add_argument(
        "--no-spreadsheet",
        action="store_true",
        help="only print the rows this time; do not touch the remembered workbook",
    )
    parser.add_argument("--no-prompt", action="store_true", help="never ask questions; leave unclear tickers unavailable")
    parser.add_argument(
        "--ignore-unknown-types",
        action="store_true",
        help="skip rows of unknown transaction types instead of stopping (results may be wrong)",
    )
    parser.add_argument("--settings", type=Path, metavar="FILE", help="settings file to use instead of the per-user one")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args(argv)

    try:
        overrides = _parse_pairs(args.symbol, "--symbol", "YAHOOSYMBOL")
        names = _parse_pairs(args.name, "--name", "NAME")
        settings = Settings.load(args.settings)
        if names:
            settings.index_names.update(names)
            settings.save()
        if provider is None:
            from statement_tracker.core.market_data.yfinance_provider import YFinanceProvider

            provider = YFinanceProvider()
        interactive = not args.no_prompt and sys.stdin is not None and sys.stdin.isatty()
        report = build_report(
            args.statement,
            provider,
            settings,
            chooser=_prompting_chooser(errors) if interactive else None,
            symbol_overrides=overrides,
            ignore_unknown_types=args.ignore_unknown_types,
        )
    except UserFacingError as error:
        print(f"{error.what_happened}\n{error.what_to_do}", file=errors)
        return 2

    write_report(report, output, table=args.table, details=args.details)
    for note in report.notes:
        print(f"Note: {note}", file=errors)
    if not percent_is_by_value(report):
        print(
            "Note: not every current value is available, so this time the percentages are each "
            "index's share of the total amount invested instead of the total current value.",
            file=errors,
        )
    if not report.valuation.holdings:
        print("Note: the statement has no investments that are still held.", file=errors)

    if args.no_spreadsheet:
        return 0
    if args.spreadsheet is None and settings.spreadsheet_path is None:
        print(
            "Note: no spreadsheet was updated. Add --spreadsheet FILE.xlsx once and every later run "
            "updates that workbook.",
            file=errors,
        )
        return 0
    try:
        _update_spreadsheet(report, settings, args.spreadsheet, today or date.today(), errors)
    except UserFacingError as error:
        print(f"{error.what_happened}\n{error.what_to_do}", file=errors)
        return 2
    return 0


def _update_spreadsheet(
    report: Report, settings: Settings, chosen: Path | None, today: date, errors: TextIO
) -> None:
    """Write the report to the chosen or remembered workbook and say what was done."""
    path = chosen.expanduser().resolve() if chosen is not None else settings.spreadsheet_path
    if path is None:
        raise UserFacingError(
            "No spreadsheet has been chosen yet.",
            "Run once with --spreadsheet followed by the .xlsx file; it is remembered after that.",
        )
    result = update_spreadsheet(report, settings, path, today)

    history = {
        "added": f"a new row for {today.isoformat()} was added",
        "updated": f"the row for {today.isoformat()} was updated",
        "skipped": "no row was written",
    }[result.history]
    print(
        f'Spreadsheet {"created" if result.created else "updated"}: {result.destination}\n'
        f'  "{settings.holdings_sheet}": {result.holdings_written} row(s) written.\n'
        f'  "{settings.history_sheet}": {history}.',
        file=errors,
    )
    for note in result.notes:
        print(f"Note: {note}", file=errors)


if __name__ == "__main__":
    sys.exit(main())
