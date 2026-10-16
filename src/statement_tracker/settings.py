"""Settings kept by the app in the per-user folder of the operating system.

Users never edit this file by hand; the user interfaces read and write it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.excel import (
    BACKUPS_KEPT,
    DEFAULT_HISTORY_SHEET,
    DEFAULT_HOLDINGS_SHEET,
    MAX_BACKUPS_KEPT,
)
from statement_tracker.core.ticker_resolver import DEFAULT_SUFFIXES

APP_FOLDER = "StatementPortfolioTracker"


@dataclass(frozen=True)
class TickerChoice:
    """The Yahoo listing used for a statement ticker."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    confirmed: bool = False
    """True once the user picked or accepted it; a confirmed choice is never replaced automatically."""


def default_settings_path() -> Path:
    """Return the settings file location for the current user and operating system."""
    import platformdirs

    return platformdirs.user_config_path(APP_FOLDER, appauthor=False) / "settings.json"


class Settings:
    """Ticker choices and resolver options, stored as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.ticker_choices: dict[str, TickerChoice] = {}
        self.ask_again: set[str] = set()
        """Tickers whose listing the user wants to choose again on the next run."""
        self.always_use_first_listing = False
        """When the app cannot tell a ticker's listing, take the first one instead of asking. Set by the user."""
        self.suffixes: tuple[str, ...] = DEFAULT_SUFFIXES
        self.index_names: dict[str, str] = {}
        """Names the user gave their investments, by statement ticker."""
        self.last_folder: Path | None = None
        """Where the user last picked a statement, so the file dialog opens there."""
        self.spreadsheet_path: Path | None = None
        self.holdings_sheet: str = DEFAULT_HOLDINGS_SHEET
        self.history_sheet: str = DEFAULT_HISTORY_SHEET
        self.backups_kept: int = BACKUPS_KEPT
        """Backup copies kept next to the spreadsheet, at most one a day; 0 turns backups off. Set by the user."""

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Load settings, or return defaults if nothing was saved yet."""
        settings = cls(path or default_settings_path())
        if not settings.path.exists():
            return settings
        try:
            raw = json.loads(settings.path.read_text(encoding="utf-8"))
            settings.ticker_choices = {
                ticker: TickerChoice(**choice) for ticker, choice in raw.get("ticker_choices", {}).items()
            }
            settings.ask_again = {str(ticker) for ticker in raw.get("ask_again", [])}
            settings.always_use_first_listing = bool(raw.get("always_use_first_listing", False))
            settings.suffixes = tuple(raw.get("suffixes", DEFAULT_SUFFIXES))
            settings.index_names = {str(k): str(v) for k, v in raw.get("index_names", {}).items()}
            last_folder = raw.get("last_folder")
            settings.last_folder = Path(last_folder) if last_folder else None
            spreadsheet = raw.get("spreadsheet_path")
            settings.spreadsheet_path = Path(spreadsheet) if spreadsheet else None
            settings.holdings_sheet = str(raw.get("holdings_sheet", DEFAULT_HOLDINGS_SHEET))
            settings.history_sheet = str(raw.get("history_sheet", DEFAULT_HISTORY_SHEET))
            settings.backups_kept = min(max(int(raw.get("backups_kept", BACKUPS_KEPT)), 0), MAX_BACKUPS_KEPT)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise UserFacingError(
                "The app's saved settings could not be read.",
                f'Delete the file "{settings.path}" and try again. Your investment choices will be asked again.',
                details=repr(exc),
            ) from exc
        return settings

    def save(self) -> None:
        """Write the settings, replacing the file in one step so it is never half written."""
        data = {
            "ticker_choices": {ticker: asdict(choice) for ticker, choice in sorted(self.ticker_choices.items())},
            "ask_again": sorted(self.ask_again),
            "always_use_first_listing": self.always_use_first_listing,
            "suffixes": list(self.suffixes),
            "index_names": dict(sorted(self.index_names.items())),
            "last_folder": str(self.last_folder) if self.last_folder else None,
            "spreadsheet_path": str(self.spreadsheet_path) if self.spreadsheet_path else None,
            "holdings_sheet": self.holdings_sheet,
            "history_sheet": self.history_sheet,
            "backups_kept": self.backups_kept,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def index_name(self, ticker: str) -> str | None:
        """Return the name to show for a ticker: the user's own, else the fund name from the price provider."""
        if ticker in self.index_names:
            return self.index_names[ticker]
        choice = self.ticker_choices.get(ticker)
        return choice.name if choice else None

    def known_tickers(self) -> list[str]:
        """Every ticker the app keeps something about (a listing or a name), sorted."""
        return sorted(set(self.ticker_choices) | set(self.index_names))

    def forget(self, ticker: str) -> None:
        """Drop the listing and the name kept for a ticker; the next run matches it again."""
        self.ticker_choices.pop(ticker, None)
        self.index_names.pop(ticker, None)
        self.ask_again.discard(ticker)

    def forget_all(self) -> None:
        """Drop every ticker's listing and name; the next run matches them all again."""
        self.ticker_choices.clear()
        self.index_names.clear()
        self.ask_again.clear()

    def remember(self, ticker: str, choice: TickerChoice) -> bool:
        """Store a ticker choice. A confirmed choice is only replaced by another confirmed one.

        Returns True if the choice was stored.
        """
        current = self.ticker_choices.get(ticker)
        if current is not None and current.confirmed and not choice.confirmed:
            return False
        self.ticker_choices[ticker] = choice
        return True
