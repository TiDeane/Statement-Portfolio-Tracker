"""Home's spreadsheet card in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

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
