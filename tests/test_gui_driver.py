"""The test driver itself: the new window can be read and acted on as a user would, offscreen."""

from pathlib import Path

from fakes import FakeProvider
from quick_driver import app, click, close_windows_afterwards, drop, find, open_app, shows  # noqa: F401


def test_the_driver_reads_clicks_and_drops(app, tmp_path: Path) -> None:
    shell = open_app(tmp_path, FakeProvider())
    assert shows(shell.window, "Your portfolio")

    click(find(shell.window, "Try me"))
    assert shows(shell.window, "Clicked")

    drop(shell.window, tmp_path / "statement.csv")
    assert shows(shell.window, "statement.csv")


def test_the_smoke_test_opens_the_new_window_when_it_is_switched_on(app, tmp_path: Path, monkeypatch) -> None:
    # Spec J4, while both windows exist: STATEMENT_TRACKER_NEW_WINDOW=1 picks the Qt Quick one.
    import json

    from fakes import SAMPLE

    from statement_tracker.__main__ import main

    monkeypatch.setenv("STATEMENT_TRACKER_NEW_WINDOW", "1")
    out = tmp_path / "report.json"

    assert main(["--smoke-test", str(SAMPLE), "--smoke-out", str(out)]) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["window"] == "qt-quick"
    assert report["qml_warnings"] == []
