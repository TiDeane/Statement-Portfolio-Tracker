"""The new window's start and its messages, driven as a user would. Rule numbers refer to tests/SPECIFICATION.md."""

from pathlib import Path

from fakes import SAMPLE, FakeProvider
from PySide6.QtGui import QGuiApplication
from quick_driver import app, click, close_windows_afterwards, find, open_app, shows, when_a_dialog_opens  # noqa: F401

from statement_tracker.core.errors import UserFacingError

FIRST_LAUNCH = "Let's see how your investments are doing"


def test_without_a_kept_statement_the_app_opens_on_first_launch(app, tmp_path: Path) -> None:
    # Spec F1.
    shell = open_app(tmp_path, FakeProvider())

    assert shows(shell.window, FIRST_LAUNCH)
    assert not shows(shell.window, "Your portfolio")


def test_with_a_kept_statement_the_app_opens_on_home(app, tmp_path: Path) -> None:
    # Spec F1.
    shell = open_app(tmp_path, FakeProvider(), kept=SAMPLE)

    assert shows(shell.window, "Your portfolio")
    assert not shows(shell.window, FIRST_LAUNCH)


def test_a_kept_statement_that_cannot_be_read_opens_first_launch_quietly(app, tmp_path: Path) -> None:
    # Spec F1: deleted or damaged since the last run.
    (tmp_path / "last_statement.csv").write_text("not a statement", encoding="utf-8")

    shell = open_app(tmp_path, FakeProvider())

    assert shows(shell.window, FIRST_LAUNCH)
    assert shell.errors == []


def test_errors_say_what_happened_and_what_to_do_and_copy_their_details(app, tmp_path: Path) -> None:
    # Spec F11.
    shell = open_app(tmp_path, FakeProvider(), real_dialogs=True)
    seen = []

    def read_and_copy() -> None:
        seen.append(shows(shell.window, "It broke.", "Do this."))
        seen.append(shows(shell.window, "Traceback"))  # the details themselves are not shown
        click(find(shell.window, "Copy details"))
        click(find(shell.window, "OK"))

    when_a_dialog_opens(shell, read_and_copy)
    shell.session.show_error(UserFacingError("It broke.", "Do this.", details="Traceback: line 1"))

    assert seen == [True, False]
    assert QGuiApplication.clipboard().text() == "Traceback: line 1"
    assert not shows(shell.window, "It broke.")
