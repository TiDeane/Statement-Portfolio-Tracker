"""Entry point for ``python -m statement_tracker`` and for the packaged app."""

from __future__ import annotations

import time

_STARTED = time.perf_counter()  # before the heavy imports, to measure startup

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

from statement_tracker import APP_NAME, __version__, spike  # noqa: E402


def _run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from statement_tracker.core.errors import UserFacingError
    from statement_tracker.settings import Settings, default_settings_path
    from statement_tracker.ui import dialogs, theme
    from statement_tracker.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.follow_system(app)
    try:
        settings = Settings.load()
    except UserFacingError as error:
        # Damaged settings must not keep the app from starting: explain, then start fresh.
        dialogs.show_error(None, error)
        settings = Settings(default_settings_path())
    window = MainWindow(settings)
    window.show()
    return app.exec()


def _run_smoke_test(sample: Path, out: Path | None, quote_symbol: str | None) -> int:
    """Open the window, load ``sample``, import the heavy libraries, write a JSON report.

    Used by CI against the packaged app. The optional price fetch is reported
    but never decides the result, because it depends on the network.
    """
    report: dict[str, object] = {
        "ok": False,
        "version": __version__,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    try:
        from PySide6.QtWidgets import QApplication

        from statement_tracker.settings import Settings
        from statement_tracker.ui.main_window import MainWindow

        app = QApplication(sys.argv[:1])
        # A throwaway settings file: the smoke test must never touch the user's own settings.
        window = MainWindow(Settings(Path(tempfile.mkdtemp()) / "settings.json"))
        window.show()
        app.processEvents()
        report["window_shown_s"] = round(time.perf_counter() - _STARTED, 3)
        report["qt_platform"] = app.platformName()
        report["bundled_sample_rows"] = spike.count_statement_rows(spike.bundled_sample_path())
        report["sample_rows"] = spike.count_statement_rows(sample)
        window.set_statement(sample)
        imports = (spike.import_yfinance(), spike.import_openpyxl())
        report["imports"] = {
            item.name: {"version": item.version, "seconds": round(item.seconds, 3)} for item in imports
        }
        report["openpyxl_roundtrip"] = spike.openpyxl_roundtrip()
        if quote_symbol:
            try:
                _, currency = spike.fetch_last_price(quote_symbol)
                report["quote"] = {"ok": True, "currency": currency}
            except Exception as exc:
                report["quote"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        app.processEvents()
        window.close()
        report["ok"] = bool(report["openpyxl_roundtrip"]) and report["sample_rows"] == report["bundled_sample_rows"]
    except Exception:
        report["error"] = traceback.format_exc()

    text = json.dumps(report, indent=2)
    if out is not None:
        out.write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    """Start the app, or run the packaging smoke test when asked to."""
    parser = argparse.ArgumentParser(prog="statement-tracker", description=APP_NAME)
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument("--smoke-test", metavar="CSV", type=Path, help="load CSV, write a report and exit")
    parser.add_argument("--smoke-out", metavar="JSON", type=Path, help="where the smoke test writes its report")
    parser.add_argument("--smoke-quote", metavar="SYMBOL", help="also try one price fetch (uses the network)")
    args, _unknown = parser.parse_known_args(argv)

    if args.smoke_test is not None:
        return _run_smoke_test(args.smoke_test, args.smoke_out, args.smoke_quote)
    return _run_gui()


if __name__ == "__main__":
    sys.exit(main())
