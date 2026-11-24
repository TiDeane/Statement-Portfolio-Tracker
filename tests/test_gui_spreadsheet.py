"""Home's spreadsheet card in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

import time
from pathlib import Path

import pytest
from fakes import SAMPLE
from openpyxl import Workbook, load_workbook
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    drop,
    find,
    open_app,
    provider_with,
    shows,
    wait_until,
)

from statement_tracker.gui.theme import LIGHT
from statement_tracker.settings import Settings

SHEETS = ["Current Holdings", "Portfolio History"]


def home_with_spreadsheet(app, tmp_path: Path, *, backups: int | None = None):
    if backups is not None:
        settings = Settings.load(tmp_path / "settings.json")
        settings.backups_kept = backups
        settings.save()
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, spreadsheet=tmp_path / "mine.xlsx")
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def update(shell) -> None:
    click(find(shell.window, "Update my spreadsheet"))


def test_update_writes_the_values_shown_and_says_what_it_did(app, tmp_path: Path) -> None:
    # Spec F7.
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path)
    assert shows(shell.window, "mine.xlsx", "Last changed", "Open folder")

    update(shell)

    assert load_workbook(tmp_path / "mine.xlsx").sheetnames[-2:] == SHEETS
    assert shows(shell.window, "Your spreadsheet is up to date", "Updated today at")
    assert shows(shell.window, "Current Holdings: 1 investment and the Total.", "Portfolio History: today's row was added.")
    assert shows(shell.window, "Backup copy of the file as it was before today's first update: mine_backup_2026-10-12.xlsx")


def test_a_spreadsheet_that_cannot_be_saved_offers_try_again(app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Spec F7, F11.
    shell = home_with_spreadsheet(app, tmp_path)

    def locked(source, target) -> None:
        raise PermissionError(13, "being used by another process")

    with monkeypatch.context() as patched:
        patched.setattr("os.replace", locked)
        update(shell)

    assert shows(shell.window, "Your spreadsheet wasn't updated", "open in another program", "Not updated today")
    assert shows(shell.window, "589.31")  # the values stay shown
    assert find(shell.window, "Copy details").isVisible()

    click(find(shell.window, "Try again"))

    assert shows(shell.window, "Your spreadsheet was created")
    assert (tmp_path / "mine.xlsx").exists()


def test_a_spreadsheet_moved_away_is_created_again(app, tmp_path: Path) -> None:
    # Spec F7 (Review Focus 3).
    shell = home_with_spreadsheet(app, tmp_path)
    assert shows(shell.window, "It doesn't exist yet: updating creates it.")

    update(shell)

    assert load_workbook(tmp_path / "mine.xlsx").sheetnames == SHEETS


def test_update_waits_for_the_prices(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, spreadsheet=tmp_path / "mine.xlsx")
    if shell.session.home.property("busy"):
        assert not find(shell.window, "Update my spreadsheet").isEnabled()
        assert shows(shell.window, "Ready once today's prices are in")
    wait_until(app, lambda: not shell.session.home.property("busy"))
    assert find(shell.window, "Update my spreadsheet").isEnabled()


def test_open_folder_shows_the_spreadsheet(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = home_with_spreadsheet(app, tmp_path)
    opened = []
    shell.session.show_in_folder = opened.append

    click(find(shell.window, "Open folder"))

    assert opened == [tmp_path / "mine.xlsx"]


def test_backups_turned_off_are_said_in_red(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = home_with_spreadsheet(app, tmp_path, backups=0)
    shell.theme.set_dark(False)

    line = find(shell.window, "No backup copy will be made before it is changed: backups are turned off in Settings.")

    assert line.property("color").name().upper() == LIGHT["errInk"]


def test_without_a_spreadsheet_the_card_offers_one(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    assert shows(shell.window, "Keep a spreadsheet up to date?", "Choose spreadsheet…")
    shell.session.ask_save_file = lambda title, start: tmp_path / "new"

    click(find(shell.window, "Create a new one…"))

    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "new.xlsx"
    assert shows(shell.window, "new.xlsx", "Update my spreadsheet")


def test_a_spreadsheet_dropped_on_home_is_the_one_updated(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))

    drop(shell.window, tmp_path / "dropped.xlsx")
    update(shell)

    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "dropped.xlsx"
    assert load_workbook(tmp_path / "dropped.xlsx").sheetnames == SHEETS


def test_another_spreadsheet_is_not_said_to_be_up_to_date(app, tmp_path: Path) -> None:
    # Spec F7: the card speaks of the spreadsheet it names.
    shell = home_with_spreadsheet(app, tmp_path)
    update(shell)
    assert shows(shell.window, "Updated today at")

    drop(shell.window, tmp_path / "other.xlsx")

    assert shows(shell.window, "other.xlsx", "It doesn't exist yet: updating creates it.")
    assert not shows(shell.window, "Updated today at")
    assert not shows(shell.window, "Your spreadsheet was created")


def held_back(monkeypatch, target: str):
    """Make ``target`` (a function the window calls) wait until the test lets it go, as a slow disk would."""
    import threading

    let_go = threading.Event()
    module, name = target.rsplit(".", 1)
    real = getattr(__import__(module, fromlist=[name]), name)

    def slow(*args, **kwargs):
        let_go.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(target, slow)
    return let_go


def test_updating_the_spreadsheet_does_not_freeze_the_window(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7: a moving bar while it writes; its buttons and Settings wait.
    shell = home_with_spreadsheet(app, tmp_path)
    let_go = held_back(monkeypatch, "statement_tracker.gui.home.update_spreadsheet")

    started = time.monotonic()
    click(find(shell.window, "Update my spreadsheet"), wait=False)

    assert time.monotonic() - started < 2  # the window answered at once
    assert shows(shell.window, "Updating your spreadsheet…")
    assert not find(shell.window, "Settings").isEnabled()
    let_go.set()
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))
    assert find(shell.window, "Settings").isEnabled()


def empty_space_in_the_cards(shell) -> list[float]:
    """How much empty height each of the two side-by-side cards shows, below what it has to say."""
    from quick_driver import _items

    cards = [item for item in _items(shell.window) if item.objectName() in ("statementCard", "spreadsheetCard")]
    assert len(cards) == 2
    return [card.height() - card.property("implicitHeight") for card in cards]


def test_the_statement_and_spreadsheet_cards_share_the_row_with_little_empty_space(app, tmp_path: Path) -> None:
    # Spec F6, F7.
    downloads = tmp_path / "Users" / "someone" / "Documents" / "Revolut statements" / "Downloads"
    downloads.mkdir(parents=True)
    statement = downloads / "trading-account-statement_2024-01-01_2026-11-20_en-gb.csv"
    statement.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    drop(shell.window, statement)  # a long name and folder; no spreadsheet yet
    wait_until(app, lambda: not shell.session.home.property("busy"))
    wait_until(app, lambda: max(empty_space_in_the_cards(shell)) <= 24, 3)

    shell.session.use_spreadsheet(tmp_path / "mine.xlsx")
    wait_until(app, lambda: max(empty_space_in_the_cards(shell)) <= 24, 3)

    update(shell)  # what was written, under the button
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))
    wait_until(app, lambda: max(empty_space_in_the_cards(shell)) <= 24, 3)
