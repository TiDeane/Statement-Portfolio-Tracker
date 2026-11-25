"""Home's spreadsheet card in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

import time
import zipfile
from pathlib import Path

import pytest
from fakes import SAMPLE
from openpyxl import Workbook, load_workbook
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    drag_away,
    drag_over,
    drop,
    find,
    find_starting,
    item_named,
    leave_and_come_back,
    open_app,
    provider_with,
    shows,
    wait_until,
    when_a_dialog_opens,
)

from statement_tracker.gui.theme import LIGHT
from statement_tracker.settings import Settings

SHEETS = ["Current Holdings", "Portfolio History"]
SHEET_GONE = (
    "This file has been moved or deleted since. If you moved it, choose it where it is now from Use another… below. "
    "Updating creates a new one here."
)


def home_with_spreadsheet(app, tmp_path: Path, *, backups: int | None = None, auto: bool = False):
    """Home on the sample with "mine.xlsx" as the spreadsheet, once the prices are in. ``auto``: the Settings
    switch "Update it by itself" was turned on before."""
    if backups is not None or auto:
        settings = Settings.load(tmp_path / "settings.json")
        if backups is not None:
            settings.backups_kept = backups
        settings.auto_update = auto
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


def test_the_card_names_the_spreadsheet_and_its_folder(app, tmp_path: Path) -> None:
    # Spec F7: like the statement card, its folder and when it changed on one line; the way to another
    # spreadsheet beside the buttons, and in its menu, that one can be dropped.
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path)

    assert shows(shell.window, "Your spreadsheet", "mine.xlsx")
    assert find_starting(shell.window, f"In {tmp_path} · Last changed")
    assert not shows(shell.window, "or drop one on this window")

    click(find(shell.window, "Use another…"))

    assert shows(shell.window, "Use an existing spreadsheet…", "Create a new one…", "Or drop an Excel file on this window.")


def test_after_an_update_the_folder_and_the_time_share_a_line(app, tmp_path: Path) -> None:
    # Spec F7: no line of its own for when it was updated, so the card is no taller than it needs to be.
    shell = home_with_spreadsheet(app, tmp_path)

    update(shell)

    assert find_starting(shell.window, f"In {tmp_path} · Updated today at")


def test_another_spreadsheet_can_be_chosen_from_home(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = home_with_spreadsheet(app, tmp_path)
    Workbook().save(tmp_path / "other.xlsx")
    shell.session.ask_open_file = lambda title, filters, start: tmp_path / "other.xlsx"

    click(find(shell.window, "Use another…"))
    click(find(shell.window, "Use an existing spreadsheet…"))

    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "other.xlsx"
    assert shows(shell.window, "other.xlsx", "Last changed")
    assert not shows(shell.window, "mine.xlsx")


def test_the_menu_closes_before_the_file_chooser_opens(app, tmp_path: Path) -> None:
    # Spec F7: the menu does not stay open behind the file chooser.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, spreadsheet=tmp_path / "mine.xlsx", real_dialogs=True)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    menu_shown = []

    def look_and_cancel() -> None:
        menu_shown.append(shows(shell.window, "Create a new one…"))
        shell.session.dialogs.cancel()

    click(find(shell.window, "Use another…"))
    when_a_dialog_opens(shell, look_and_cancel)
    click(find(shell.window, "Use an existing spreadsheet…"))

    assert menu_shown == [False]


def test_a_new_spreadsheet_can_be_created_from_home(app, tmp_path: Path) -> None:
    # Spec F7: created as soon as today's prices are in, here at once.
    shell = home_with_spreadsheet(app, tmp_path)
    shell.session.ask_save_file = lambda title, start: tmp_path / "fresh"

    click(find(shell.window, "Use another…"))
    click(find(shell.window, "Create a new one…"))

    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))
    assert load_workbook(tmp_path / "fresh.xlsx").sheetnames == SHEETS
    assert shows(shell.window, "fresh.xlsx")
    assert not shows(shell.window, "mine.xlsx")


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
    assert not shows(shell.window, SHEET_GONE)  # the app never wrote it

    update(shell)

    assert load_workbook(tmp_path / "mine.xlsx").sheetnames == SHEETS


def test_a_spreadsheet_moved_away_since_is_said_to_be(app, tmp_path: Path) -> None:
    # Spec F7: seen as soon as the window is active again.
    shell = home_with_spreadsheet(app, tmp_path)
    update(shell)
    (tmp_path / "mine.xlsx").rename(tmp_path / "elsewhere.xlsx")

    leave_and_come_back(shell)

    assert shows(shell.window, SHEET_GONE)
    assert not shows(shell.window, "It doesn't exist yet: updating creates it.")
    assert not shows(shell.window, "Your spreadsheet was created")  # what the update said is of a file not there now
    assert not shows(shell.window, "Updated today at")
    (tmp_path / "elsewhere.xlsx").rename(tmp_path / "mine.xlsx")  # put back
    leave_and_come_back(shell)
    assert not shows(shell.window, SHEET_GONE)


def test_an_update_that_failed_is_still_said_when_the_window_comes_back(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7: the user went to look at the folder; what went wrong is still said when they come back.
    shell = home_with_spreadsheet(app, tmp_path)
    update(shell)
    (tmp_path / "mine.xlsx").unlink()

    def locked(source, target) -> None:
        raise PermissionError(13, "being used by another process")

    with monkeypatch.context() as patched:
        patched.setattr("os.replace", locked)
        update(shell)
    assert shows(shell.window, "Your spreadsheet wasn't updated")

    leave_and_come_back(shell)

    assert shows(shell.window, "Your spreadsheet wasn't updated", "Try again", SHEET_GONE)


def test_a_spreadsheet_deleted_while_the_app_was_closed_is_said_to_be(app, tmp_path: Path) -> None:
    # Spec F7: the app remembers which spreadsheets it has written.
    shell = home_with_spreadsheet(app, tmp_path)
    update(shell)
    (tmp_path / "mine.xlsx").unlink()

    again = home_with_spreadsheet(app, tmp_path)

    assert shows(again.window, "mine.xlsx", SHEET_GONE)
    assert not shows(again.window, "It doesn't exist yet: updating creates it.")


def test_one_created_again_where_one_was_deleted_waits_for_the_prices(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7: asked for again at the same place, it is not said to be gone while it waits to be created.
    shell = home_with_spreadsheet(app, tmp_path)
    update(shell)
    (tmp_path / "mine.xlsx").unlink()
    let_go = held_back(monkeypatch, "statement_tracker.gui.session.build_report")
    click(find(shell.window, "Refresh prices"), wait=False)
    wait_until(app, lambda: shell.session.home.property("busy"))
    shell.session.ask_save_file = lambda title, start: tmp_path / "mine.xlsx"

    click(find(shell.window, "Use another…"), wait=False)
    click(find(shell.window, "Create a new one…"), wait=False)

    assert shows(shell.window, "It will be created as soon as today's prices are in.")
    assert not shows(shell.window, SHEET_GONE)
    let_go.set()
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))


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


def test_a_new_spreadsheet_is_created_without_pressing_update(app, tmp_path: Path) -> None:
    # Spec F7, H5: created at once, and updating it again the same day makes no backup copy of it.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    suggested = []
    shell.session.ask_save_file = lambda title, start: (suggested.append(start.name), tmp_path / "new")[1]

    click(find(shell.window, "Create a new one…"))
    assert suggested == ["investments_2026-10-12.xlsx"]  # today's date

    assert load_workbook(tmp_path / "new.xlsx").sheetnames == SHEETS
    assert shows(shell.window, "Your spreadsheet was created")
    update(shell)
    assert not list(tmp_path.glob("new_backup_*.xlsx"))


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


def test_a_fetch_says_when_it_reads_the_spreadsheet(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F4: the line under the totals says what is being done, reading the spreadsheet included
    # (values typed into it are looked for before prices are fetched), not "Reading your statement".
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path)
    let_go = held_back(monkeypatch, "statement_tracker.gui.session.values_typed_in")

    click(find(shell.window, "Refresh prices"), wait=False)

    wait_until(app, lambda: shows(shell.window, "Reading your spreadsheet"))
    assert not shows(shell.window, "Reading your statement")
    let_go.set()
    wait_until(app, lambda: not shell.session.home.property("busy"))
    assert shows(shell.window, "589.31")  # 1.47328346 shares at 400


def test_updating_the_spreadsheet_does_not_freeze_the_window(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7: a moving bar while it writes; its buttons and Settings wait.
    shell = home_with_spreadsheet(app, tmp_path)
    let_go = held_back(monkeypatch, "statement_tracker.gui.home.update_spreadsheet")

    started = time.monotonic()
    click(find(shell.window, "Update my spreadsheet"), wait=False)

    assert time.monotonic() - started < 2  # the window answered at once
    assert shows(shell.window, "Updating your spreadsheet…")
    assert not find(shell.window, "Settings").isEnabled()
    assert not find(shell.window, "Use another…").isEnabled()
    let_go.set()
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))
    assert find(shell.window, "Settings").isEnabled()
    assert find(shell.window, "Use another…").isEnabled()


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


def test_a_spreadsheet_dragged_over_home_lights_up_its_card(app, tmp_path: Path) -> None:
    # Spec F7: where a file will go is shown before it is dropped.
    shell = home_with_spreadsheet(app, tmp_path)

    drag_over(shell.window, tmp_path / "other.xlsx")

    assert shows(shell.window, "Drop it to use this spreadsheet", "mine.xlsx stays as it is. The next update goes to the new one.")
    assert item_named(shell.window, "statementCard").opacity() < 1
    drag_away(shell.window)
    assert not shows(shell.window, "Drop it to use this spreadsheet")
    assert item_named(shell.window, "statementCard").opacity() == 1
    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "mine.xlsx"


def test_a_spreadsheet_dragged_over_home_without_one(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE)
    wait_until(app, lambda: not shell.session.home.property("busy"))

    drag_over(shell.window, tmp_path / "mine.xlsx")

    assert shows(shell.window, "Drop it to use this spreadsheet", "The next update goes to it.")
    drag_away(shell.window)
    assert not shows(shell.window, "Drop it to use this spreadsheet")


def test_a_statement_dragged_over_home_lights_up_its_card(app, tmp_path: Path) -> None:
    # Spec F7: also while the prices are still on their way; dropping it ends the highlight.
    newer = tmp_path / "newer.csv"
    newer.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, spreadsheet=tmp_path / "mine.xlsx")

    drag_over(shell.window, newer)

    assert shows(shell.window, "Drop it to use this statement", "Today's values are worked out again from it.")
    assert item_named(shell.window, "spreadsheetCard").opacity() < 1
    drop(shell.window, newer)
    assert not shows(shell.window, "Drop it to use this statement")
    assert item_named(shell.window, "spreadsheetCard").opacity() == 1


def test_a_statement_and_a_spreadsheet_dragged_together_light_up_both_cards(app, tmp_path: Path) -> None:
    # Spec F7.
    shell = home_with_spreadsheet(app, tmp_path)

    drag_over(shell.window, tmp_path / "newer.csv", tmp_path / "other.xlsx")

    assert shows(shell.window, "Drop it to use this statement", "Drop it to use this spreadsheet")
    assert item_named(shell.window, "statementCard").opacity() == 1
    assert item_named(shell.window, "spreadsheetCard").opacity() == 1
    drag_away(shell.window)
    assert not shows(shell.window, "Drop it to use this statement")


def invested_written(path: Path):
    """What Current Holdings says was invested in EQQB, or None while the app has not written it."""
    try:
        sheet = load_workbook(path)["Current Holdings"]
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    for row in sheet.iter_rows(values_only=True):
        if row and isinstance(row[0], str) and "EQQB" in row[0]:
            return row[1]
    return None


def test_the_spreadsheet_is_updated_by_itself_when_the_app_opens(app, tmp_path: Path) -> None:
    # Spec F7: with "Update it by itself" turned on in Settings.
    Workbook().save(tmp_path / "mine.xlsx")

    shell = home_with_spreadsheet(app, tmp_path, auto=True)

    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))
    assert load_workbook(tmp_path / "mine.xlsx").sheetnames[-2:] == SHEETS


def test_refresh_and_a_new_statement_update_it_by_itself(app, tmp_path: Path) -> None:
    # Spec F7: each time the values are worked out.
    from test_gui_home import newer_statement

    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path, auto=True)
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))

    click(find(shell.window, "Refresh prices"))
    wait_until(app, lambda: shows(shell.window, "Portfolio History: today's row was updated."))

    drop(shell.window, newer_statement(tmp_path))  # one more buy: 38.00 more invested
    wait_until(app, lambda: invested_written(tmp_path / "mine.xlsx") == pytest.approx(579.49))


def test_without_the_switch_nothing_is_written_by_itself(app, tmp_path: Path) -> None:
    # Spec F7: off unless turned on.
    Workbook().save(tmp_path / "mine.xlsx")

    shell = home_with_spreadsheet(app, tmp_path)
    settle_a_while(app)

    assert load_workbook(tmp_path / "mine.xlsx").sheetnames == ["Sheet"]
    assert not shows(shell.window, "Your spreadsheet is up to date")


def test_while_prices_come_in_the_card_says_it_will_be_updated(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7.
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path, auto=True)
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))
    let_go = held_back(monkeypatch, "statement_tracker.gui.session.build_report")

    click(find(shell.window, "Refresh prices"), wait=False)

    wait_until(app, lambda: shows(shell.window, "It will be updated as soon as today's prices are in."))
    let_go.set()
    wait_until(app, lambda: shows(shell.window, "Portfolio History: today's row was updated."))


def test_a_spreadsheet_open_in_excel_at_launch_says_so(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7, F11: written by itself, it fails as the button would, with Try again.
    Workbook().save(tmp_path / "mine.xlsx")

    def locked(source, target) -> None:
        raise PermissionError(13, "being used by another process")

    with monkeypatch.context() as patched:
        patched.setattr("statement_tracker.core.exporters.excel.replace_file", locked)  # only the spreadsheet is held
        shell = home_with_spreadsheet(app, tmp_path, auto=True)
        wait_until(app, lambda: shows(shell.window, "Your spreadsheet wasn't updated"))

    assert shows(shell.window, "Try again", "589.31")  # the values stay shown


def test_a_spreadsheet_not_written_by_itself_asks_for_the_user(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F12: opened minimized at sign-in, its taskbar button flashes.
    Workbook().save(tmp_path / "mine.xlsx")

    def locked(source, target) -> None:
        raise PermissionError(13, "being used by another process")

    with monkeypatch.context() as patched:
        patched.setattr("statement_tracker.core.exporters.excel.replace_file", locked)
        shell = home_with_spreadsheet(app, tmp_path, auto=True)
        wait_until(app, lambda: shows(shell.window, "Your spreadsheet wasn't updated"))

    assert len(shell.attentions) == 1


def test_a_spreadsheet_written_by_itself_does_not_disturb_the_user(app, tmp_path: Path) -> None:
    # Spec F12: nothing flashes when all went well.
    Workbook().save(tmp_path / "mine.xlsx")

    shell = home_with_spreadsheet(app, tmp_path, auto=True)
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))

    assert shell.attentions == []


def test_a_moved_spreadsheet_is_not_created_again_by_itself(app, tmp_path: Path) -> None:
    # Spec F7: only a spreadsheet that is there is written by itself.
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path, auto=True)
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))
    (tmp_path / "mine.xlsx").rename(tmp_path / "elsewhere.xlsx")

    again = home_with_spreadsheet(app, tmp_path, auto=True)
    settle_a_while(app)

    assert not (tmp_path / "mine.xlsx").exists()
    assert shows(again.window, SHEET_GONE)


def test_a_new_spreadsheet_and_the_switch_write_once(app, tmp_path: Path, monkeypatch) -> None:
    # Spec F7, H5: a new one asked for during a fetch is created once, with no backup copy.
    Workbook().save(tmp_path / "mine.xlsx")
    shell = home_with_spreadsheet(app, tmp_path, auto=True)
    wait_until(app, lambda: shows(shell.window, "Your spreadsheet is up to date"))
    let_go = held_back(monkeypatch, "statement_tracker.gui.session.build_report")
    click(find(shell.window, "Refresh prices"), wait=False)
    wait_until(app, lambda: shell.session.home.property("busy"))
    shell.session.ask_save_file = lambda title, start: tmp_path / "fresh"

    click(find(shell.window, "Use another…"), wait=False)
    click(find(shell.window, "Create a new one…"), wait=False)
    let_go.set()

    wait_until(app, lambda: shows(shell.window, "Your spreadsheet was created"))
    settle_a_while(app)
    assert shows(shell.window, "Your spreadsheet was created")  # not written a second time ("is up to date")
    assert not list(tmp_path.glob("fresh_backup_*.xlsx"))


def settle_a_while(app) -> None:
    """Let a second go by, for anything that would be written by itself to be written."""
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
