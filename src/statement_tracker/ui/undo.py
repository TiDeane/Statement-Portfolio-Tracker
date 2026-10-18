"""Undo and redo for what is kept about each investment: its listing, its name and the value typed in.

One history is shared by the result table and the settings window, so a name changed in the
table can be undone in Settings and the other way round. Each step keeps only what it changed
(a rename only the name, an entered value only the value) of the investments it changed, so
undoing it leaves alone everything else, including what a later run learned.

Renames and entered values can be undone as long as the app is open. Forgetting an investment
and choosing its listing again can only be undone until the next run finishes: that run
matches the listing again or asks for it, and undoing would then replace the user's new pick
with the old one. The other settings (backups, the tick box) are not part of it. Nothing here
uses Qt.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from statement_tracker.price_cache import PriceCache
from statement_tracker.settings import Settings

LISTING, NAME, ASK_AGAIN, ENTERED = "listing", "name", "ask again", "entered"
"""What a step can change about an investment: its listing, the name the user gave it, whether
the next run asks for its listing again, and the value typed in for it."""
EVERYTHING = frozenset({LISTING, NAME, ASK_AGAIN, ENTERED})


@dataclass(frozen=True)
class _Step:
    what: str
    """What the change was, as the message after undoing it names it: "the new name of ABCD"."""
    before: Mapping[str, Mapping[str, Any]]
    """By ticker, the fields the change made to it, as they were before (None for not kept)."""
    clears_on_run: bool
    """Dropped once a run has finished, as it would undo what the run chose."""


class ChangeHistory:
    """The changes made to investments while the app is open, newest last."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._undo: list[_Step] = []
        self._redo: list[_Step] = []

    def record(self, what: str, tickers: Iterable[str], fields: Iterable[str], clears_on_run: bool = False) -> None:
        """Remember ``fields`` of ``tickers`` as they are now, just before a change to them called ``what``."""
        fields = frozenset(fields)
        prices = PriceCache.beside(self._settings.path)
        self._undo.append(_Step(what, {ticker: self._kept(ticker, fields, prices) for ticker in tickers}, clears_on_run))
        self._redo.clear()

    def run_finished(self) -> None:
        """Forget the steps that a run makes wrong to undo: forgetting an investment, choosing its listing again."""
        self._undo = [step for step in self._undo if not step.clears_on_run]
        self._redo = [step for step in self._redo if not step.clears_on_run]

    def undo(self) -> str | None:
        """Put back what the last change changed, and say what it was (None if there is nothing).
        The values typed in are saved here; the caller saves the settings."""
        return self._swap(self._undo, self._redo)

    def redo(self) -> str | None:
        """Make the last change undone again, as ``undo`` does."""
        return self._swap(self._redo, self._undo)

    def _swap(self, take: list[_Step], keep: list[_Step]) -> str | None:
        if not take:
            return None
        step = take.pop()
        prices = PriceCache.beside(self._settings.path)
        now = {ticker: self._kept(ticker, frozenset(kept), prices) for ticker, kept in step.before.items()}
        keep.append(_Step(step.what, now, step.clears_on_run))
        for ticker, kept in step.before.items():
            self._put(ticker, kept, prices)
        prices.save()
        return step.what

    def _kept(self, ticker: str, fields: frozenset[str], prices: PriceCache) -> dict[str, Any]:
        settings = self._settings
        now = {
            LISTING: lambda: settings.ticker_choices.get(ticker),
            NAME: lambda: settings.index_names.get(ticker),
            ASK_AGAIN: lambda: ticker in settings.ask_again,
            ENTERED: lambda: prices.entered_entry(ticker),
        }
        return {field: now[field]() for field in fields}

    def _put(self, ticker: str, kept: Mapping[str, Any], prices: PriceCache) -> None:
        settings = self._settings
        if LISTING in kept:
            if kept[LISTING] is None:
                settings.ticker_choices.pop(ticker, None)
            else:
                settings.ticker_choices[ticker] = kept[LISTING]
        if NAME in kept:
            if kept[NAME] is None:
                settings.index_names.pop(ticker, None)
            else:
                settings.index_names[ticker] = kept[NAME]
        if ASK_AGAIN in kept:
            if kept[ASK_AGAIN]:
                settings.ask_again.add(ticker)
            else:
                settings.ask_again.discard(ticker)
        if ENTERED in kept:
            prices.put_entered(ticker, kept[ENTERED])
