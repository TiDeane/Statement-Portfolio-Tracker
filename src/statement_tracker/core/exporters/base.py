"""The interface every exporter implements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from statement_tracker.core.models import PortfolioValuation


@dataclass(frozen=True)
class ExportResult:
    """What an export did, in a form the user interfaces can report."""

    destination: str
    created: bool
    holdings_written: int
    history: str
    """``added``, ``updated`` or ``skipped`` (skipped when totals are unavailable)."""
    notes: tuple[str, ...] = ()
    backup: str | None = None
    """The file name of today's backup copy, the spreadsheet as it was before the day's first update; None
    when there is none (a new spreadsheet, or backups turned off)."""


class Exporter(Protocol):
    """Writes a valued portfolio to a destination. Raises UserFacingError when it cannot."""

    def export(self, valuation: PortfolioValuation, today: date) -> ExportResult:
        """Write the open holdings and the portfolio totals for ``today``."""
        ...
