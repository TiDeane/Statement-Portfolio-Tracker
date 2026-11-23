"""The new window's start: the smoke test opens it when switched on. (Clicks, typing and drops are
exercised by every window test from test_gui_session.py on.)"""

from pathlib import Path

from quick_driver import app, close_windows_afterwards  # noqa: F401


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
