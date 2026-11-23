"""Which listing an investment is, asked in the new window. Rule numbers refer to tests/SPECIFICATION.md."""

from pathlib import Path

from fakes import SAMPLE
from quick_driver import (  # noqa: F401
    EQQB_BUYS,
    app,
    click,
    close_windows_afterwards,
    find,
    open_app,
    opening_app,
    provider_with,
    rows,
    shows,
    type_text,
    wait_until,
    when_a_dialog_opens,
)

from statement_tracker.core.ticker_resolver import resolve_ticker
from statement_tracker.settings import Settings

TWO_LISTINGS = ("EQQB.DE", "EQQB.MI")


def ambiguous():
    return resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider_with(*TWO_LISTINGS))


def asked_in_the_dialog(app, tmp_path: Path, act):
    """Open the real dialog for an ambiguous EQQB, let ``act`` answer it, and return its answer."""
    shell = open_app(tmp_path, provider_with(), real_dialogs=True)
    seen = []
    when_a_dialog_opens(shell, lambda: seen.append(act(shell)))
    return shell.session.ask_listing(ambiguous()), seen


def test_the_dialog_lists_the_listings_and_returns_the_one_chosen(app, tmp_path: Path) -> None:
    # Spec F9.
    def choose_milan(shell) -> bool:
        ok = shows(shell.window, "Which one is EQQB?", "Matches your purchases", "XETRA · EUR · EQQB.DE")
        click(find(shell.window, "XETRA · EUR · EQQB.MI"))
        click(find(shell.window, "Use this listing"))
        return ok

    answer, seen = asked_in_the_dialog(app, tmp_path, choose_milan)

    assert answer == ("EQQB.MI", False) and seen == [True]


def test_a_typed_symbol_wins(app, tmp_path: Path) -> None:
    # Spec F9.
    def type_one(shell) -> None:
        click(find(shell.window, "Not in the list? Type its Yahoo Finance symbol"))
        type_text(shell.window, "EQQB.AS")
        click(find(shell.window, "Use this listing"))

    assert asked_in_the_dialog(app, tmp_path, type_one)[0] == ("EQQB.AS", False)


def test_skip_this_investment_answers_nothing(app, tmp_path: Path) -> None:
    # Spec F9.
    assert asked_in_the_dialog(app, tmp_path, lambda shell: click(find(shell.window, "Skip this investment")))[0] == (None, False)


def test_from_now_on_take_the_first_listing(app, tmp_path: Path) -> None:
    # Spec F9.
    def always_first(shell) -> None:
        click(find(shell.window, "From now on, take the first listing without asking. The best match always comes first."))
        click(find(shell.window, "Use this listing"))

    assert asked_in_the_dialog(app, tmp_path, always_first)[0] == ("EQQB.DE", True)


def test_an_unclear_investment_is_asked_once_and_remembered(app, tmp_path: Path) -> None:
    # Spec F9, C (a confirmed choice is kept).
    waiting = []

    def answer(resolution):
        waiting.append(shows(opening_app().window, "Waiting for you: which listing EQQB is."))
        return "EQQB.MI", False

    shell = open_app(tmp_path, provider_with(*TWO_LISTINGS), kept=SAMPLE, ask_listing=answer)
    wait_until(app, lambda: not shell.session.home.property("busy"))

    assert waiting == [True]
    choice = Settings.load(tmp_path / "settings.json").ticker_choices["EQQB"]
    assert choice.symbol == "EQQB.MI" and choice.confirmed

    again = open_app(tmp_path, provider_with(*TWO_LISTINGS), kept=SAMPLE)
    wait_until(app, lambda: not again.session.home.property("busy"))
    assert again.questions == []


def test_a_skipped_investment_has_no_value(app, tmp_path: Path) -> None:
    # Spec F9, F8.
    shell = open_app(tmp_path, provider_with(*TWO_LISTINGS), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))

    assert shell.questions == ["EQQB"]
    assert "No price today" in rows(shell.window)[0]


def test_take_the_first_from_now_on_is_saved_at_once(app, tmp_path: Path) -> None:
    # Spec F9.
    shell = open_app(tmp_path, provider_with(*TWO_LISTINGS), kept=SAMPLE,
                     ask_listing=lambda resolution: (resolution.candidates[0].info.symbol, True))
    wait_until(app, lambda: not shell.session.home.property("busy"))

    assert Settings.load(tmp_path / "settings.json").always_use_first_listing
