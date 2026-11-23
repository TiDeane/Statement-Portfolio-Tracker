"""First launch in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

from pathlib import Path

from fakes import SAMPLE, SAMPLES, FakeProvider
from quick_driver import app, click, close_windows_afterwards, drop, find, open_app, shows  # noqa: F401

from statement_tracker.settings import Settings


def continue_enabled(shell) -> bool:
    return find(shell.window, "Continue").isEnabled()


def test_step_1_waits_for_a_statement_that_reads(app, tmp_path: Path) -> None:
    # Spec F2.
    shell = open_app(tmp_path, FakeProvider())
    assert shows(shell.window, "Drop your Revolut statement here", "Choose statement file…", "Where do I get it?")
    assert shows(shell.window, "Always pick All time")
    assert not continue_enabled(shell)

    drop(shell.window, SAMPLE)

    assert shows(shell.window, "revolut_sample.csv", "18 transactions, the latest on", "1 investment you still hold")
    assert shows(shell.window, "Choose another file…")
    assert continue_enabled(shell)


def test_a_file_that_does_not_read_is_explained_and_the_step_stays(app, tmp_path: Path) -> None:
    # Spec F2, F11.
    shell = open_app(tmp_path, FakeProvider())

    drop(shell.window, SAMPLES / "unknown_type.csv")

    assert len(shell.errors) == 1 and "row" in shell.errors[0].what_happened.lower()
    assert shows(shell.window, "Drop your Revolut statement here")
    assert not continue_enabled(shell)


def test_a_bad_file_after_a_good_one_keeps_the_good_one(app, tmp_path: Path) -> None:
    # Spec F2: the step stays as it was.
    shell = open_app(tmp_path, FakeProvider())
    drop(shell.window, SAMPLE)

    drop(shell.window, SAMPLES / "unknown_type.csv")

    assert shows(shell.window, "revolut_sample.csv") and continue_enabled(shell)


def test_choose_statement_opens_in_the_folder_used_last_time(app, tmp_path: Path) -> None:
    # Spec F2.
    starts = []
    shell = open_app(tmp_path, FakeProvider())
    shell.session.ask_open_file = lambda title, kinds, start: starts.append(start) or SAMPLE
    click(find(shell.window, "Choose statement file…"))
    assert shows(shell.window, "revolut_sample.csv")

    again = open_app(tmp_path, FakeProvider())
    again.session.ask_open_file = lambda title, kinds, start: starts.append(start) or None
    click(find(again.window, "Choose statement file…"))

    assert starts[-1] == SAMPLE.parent
    assert not continue_enabled(again)  # nothing chosen this time


def test_first_launch_says_what_leaves_the_computer(app, tmp_path: Path) -> None:
    # Spec F2.
    shell = open_app(tmp_path, FakeProvider())

    assert shows(shell.window, "Everything stays on this computer. Only fund codes and dates go to Yahoo Finance.")
    assert find(shell.window, "About and privacy").isEnabled()


def to_step_2(shell) -> None:
    drop(shell.window, SAMPLE)
    click(find(shell.window, "Continue"))


def test_step_2_remembers_a_spreadsheet_i_have(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider())
    to_step_2(shell)
    assert shows(shell.window, "Keep a spreadsheet up to date?", "Step 2 of 2", "backup copy")
    assert not find(shell.window, "Show my investments").isEnabled()
    shell.session.ask_open_file = lambda title, kinds, start: tmp_path / "mine.xlsx"

    click(find(shell.window, "Use a spreadsheet I have"))

    assert shows(shell.window, "mine.xlsx", "Choose another…")
    click(find(shell.window, "Show my investments"))
    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "mine.xlsx"
    assert shows(shell.window, "Your portfolio")


def test_create_a_new_one_adds_the_xlsx_ending(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider())
    to_step_2(shell)
    shell.session.ask_save_file = lambda title, start: tmp_path / "Investments"

    click(find(shell.window, "Create a new one"))
    click(find(shell.window, "Show my investments"))

    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "Investments.xlsx"


def test_cancelling_the_file_chooser_keeps_the_choice_before(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider())
    to_step_2(shell)
    click(find(shell.window, "Not now"))
    shell.session.ask_open_file = lambda title, kinds, start: None

    click(find(shell.window, "Use a spreadsheet I have"))
    click(find(shell.window, "Show my investments"))

    assert Settings.load(tmp_path / "settings.json").spreadsheet_path is None


def test_not_now_leaves_no_spreadsheet_and_back_keeps_the_statement(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider())
    to_step_2(shell)

    click(find(shell.window, "Back"))
    assert shows(shell.window, "revolut_sample.csv", "Step 1 of 2")

    click(find(shell.window, "Continue"))
    click(find(shell.window, "Not now"))
    click(find(shell.window, "Show my investments"))
    assert Settings.load(tmp_path / "settings.json").spreadsheet_path is None
    assert shows(shell.window, "Your portfolio")


def test_a_spreadsheet_dropped_on_step_2_is_one_i_have(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider())
    to_step_2(shell)

    drop(shell.window, tmp_path / "dropped.xlsx")

    assert shows(shell.window, "dropped.xlsx")
    assert find(shell.window, "Show my investments").isEnabled()


def test_someone_with_a_remembered_spreadsheet_skips_step_2(app, tmp_path: Path) -> None:
    # Spec F3.
    shell = open_app(tmp_path, FakeProvider(), spreadsheet=tmp_path / "mine.xlsx")

    to_step_2(shell)

    assert shows(shell.window, "Your portfolio")
    assert Settings.load(tmp_path / "settings.json").spreadsheet_path == tmp_path / "mine.xlsx"
