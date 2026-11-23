"""The packaged app's smoke test, run here from source. (Clicks, typing and drops are exercised by every
window test from test_gui_session.py on.)"""

from pathlib import Path

from quick_driver import app, close_windows_afterwards  # noqa: F401


def test_the_smoke_test_opens_the_window_reads_the_sample_and_writes_a_spreadsheet(app, tmp_path: Path) -> None:
    # Spec J4.
    import json

    from fakes import SAMPLE

    from statement_tracker.__main__ import main

    out = tmp_path / "report.json"

    assert main(["--smoke-test", str(SAMPLE), "--smoke-out", str(out)]) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["window"] == "qt-quick"
    assert report["qml_warnings"] == []
