"""First launch in the new window, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

from pathlib import Path

from fakes import SAMPLE, SAMPLES, FakeProvider
from quick_driver import app, click, close_windows_afterwards, drop, find, open_app, shows  # noqa: F401


def continue_enabled(shell) -> bool:
    return find(shell.window, "Continue").isEnabled()


def test_step_1_waits_for_a_statement_that_reads(app, tmp_path: Path) -> None:
    # Spec K2.
    shell = open_app(tmp_path, FakeProvider())
    assert shows(shell.window, "Drop your Revolut statement here", "Choose statement file…", "Where do I get it?")
    assert shows(shell.window, "Always pick All time")
    assert not continue_enabled(shell)

    drop(shell.window, SAMPLE)

    assert shows(shell.window, "revolut_sample.csv", "18 transactions, the latest on", "1 investment you still hold")
    assert shows(shell.window, "Choose another file…")
    assert continue_enabled(shell)


def test_a_file_that_does_not_read_is_explained_and_the_step_stays(app, tmp_path: Path) -> None:
    # Spec K2, K12.
    shell = open_app(tmp_path, FakeProvider())

    drop(shell.window, SAMPLES / "unknown_type.csv")

    assert len(shell.errors) == 1 and "row" in shell.errors[0].what_happened.lower()
    assert shows(shell.window, "Drop your Revolut statement here")
    assert not continue_enabled(shell)


def test_a_bad_file_after_a_good_one_keeps_the_good_one(app, tmp_path: Path) -> None:
    # Spec K2: the step stays as it was.
    shell = open_app(tmp_path, FakeProvider())
    drop(shell.window, SAMPLE)

    drop(shell.window, SAMPLES / "unknown_type.csv")

    assert shows(shell.window, "revolut_sample.csv") and continue_enabled(shell)


def test_choose_statement_opens_in_the_folder_used_last_time(app, tmp_path: Path) -> None:
    # Spec K2 (F2's rule).
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
    # Spec K2.
    shell = open_app(tmp_path, FakeProvider())

    assert shows(shell.window, "Everything stays on this computer. Only fund codes and dates go to Yahoo Finance.")
    assert find(shell.window, "About and privacy").isEnabled()
