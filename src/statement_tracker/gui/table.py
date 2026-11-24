"""Home's investments table: its headings, and which investments it shows in which order.

Pure functions over the list's rows; ``Home`` keeps the user's choices and calls them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from statement_tracker.gui.holdings_model import HoldingRow

HEADINGS = {
    "name": "Investment",
    "shares": "Shares",
    "average_cost": "Average cost per share",
    "price": "Price per share",
    "invested": "Invested",
    "worth": "Worth now",
    "share": "Share of total",
    "invested_share": "Share of invested",
    "gain": "Gain or loss",
    "realized": "Gain from sales",
    "dividends": "Dividends received",
}
"""Each column's heading, by its key (``settings.TABLE_COLUMNS``, and "name", always shown)."""


def next_sort(current: tuple[str, bool] | None, column: str) -> tuple[str, bool] | None:
    """The sort after clicking ``column``'s heading: a new column sorts largest first (names A to Z), the
    same column reverses once, and then the table goes back to its usual order (None)."""
    first = column != "name"  # descending first, except names
    if current is None or current[0] != column:
        return column, first
    if current[1] == first:
        return column, not first
    return None


def _kept(row: HoldingRow, show: str, needle: str, priced: bool) -> bool:
    if needle and needle not in row.name.casefold() and needle not in row.ticker.casefold():
        return False
    if show == "all" or not priced:  # while prices come in, nothing is gaining or losing yet: all are listed
        return True
    gained = row.sort_values.get("gain")
    return gained is not None and (gained > 0 if show == "gaining" else gained < 0)


def arrange(rows: list[HoldingRow], sort: tuple[str, bool] | None, show: str, search: str, priced: bool) -> list[HoldingRow]:
    """The rows the table shows, in its order.

    Kept: those ``show`` asks for ("gaining": a gain above zero, "losing": below; one without a price is
    neither, and while prices are not ``priced`` yet every row is kept), whose name or ticker contains
    ``search``, ignoring case. Sorted by ``sort`` (column, descending), the usual order kept among equals;
    rows without a value in that column last, both ways.
    """
    needle = search.strip().casefold()
    shown = [row for row in rows if _kept(row, show, needle, priced)]
    if sort is None:
        return shown
    column, descending = sort
    valued = [row for row in shown if row.sort_values.get(column) is not None]
    valued.sort(key=lambda row: row.sort_values[column], reverse=descending)
    return valued + [row for row in shown if row.sort_values.get(column) is None]


def filter_line(shown: int, held: int, show: str, search: str) -> str:
    """What the line above the table says while some investments are hidden: which ones are shown. ""
    when none are hidden."""
    if shown == held:
        return ""
    if shown == 0:
        return f"None of your {held} investments match."
    one = shown == 1
    reasons = []
    if show != "all":
        reasons.append(f"{'is' if one else 'are'} {show}")
    if search.strip():
        reasons.append(f"{'matches' if one else 'match'} \u201c{search.strip()}\u201d")
    return (f"Showing the {shown} of your {held} investments that {' and '.join(reasons)}. "
            "The Total below covers only these.")
