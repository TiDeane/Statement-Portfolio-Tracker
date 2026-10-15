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

from statement_tracker import APP_NAME, __version__  # noqa: E402

RUNNING_MUTEX = "StatementPortfolioTracker"
"""Named while the window is open on Windows. The installer and uninstaller look for it (AppMutex in
packaging/windows_installer.iss) and ask for the app to be closed first: an app left open while it is
uninstalled would write its settings back after they were deleted."""


def mark_running() -> int | None:
    """On Windows, create the named mutex that says the app is open. Windows removes it when the app exits."""
    if sys.platform != "win32":
        return None
    import ctypes

    return ctypes.windll.kernel32.CreateMutexW(None, False, RUNNING_MUTEX) or None


def _run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from statement_tracker.core.errors import UserFacingError
    from statement_tracker.settings import Settings, default_settings_path
    from statement_tracker.ui import dialogs, theme
    from statement_tracker.ui.main_window import MainWindow

    mark_running()
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
    """Open the window, read ``sample`` and write it to a spreadsheet, offline; write a JSON report.

    Used by CI against the packaged app, so the real parser and exporter are what gets
    checked. The optional price fetch is reported but never decides the result, because
    it depends on the network.
    """
    report: dict[str, object] = {
        "ok": False,
        "version": __version__,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    try:
        from datetime import date

        from PySide6.QtWidgets import QApplication

        from statement_tracker.core.calculator import compute_portfolio, value_portfolio
        from statement_tracker.core.exporters.excel import ExcelExporter
        from statement_tracker.core.parser import load_statement
        from statement_tracker.settings import Settings
        from statement_tracker.ui.main_window import MainWindow

        app = QApplication.instance() or QApplication(sys.argv[:1])
        # A throwaway folder: the smoke test must never touch the user's own settings or files.
        scratch = Path(tempfile.mkdtemp())
        window = MainWindow(Settings(scratch / "settings.json"))
        window.show()
        app.processEvents()
        report["window_shown_s"] = round(time.perf_counter() - _STARTED, 3)
        report["qt_platform"] = app.platformName()
        window.set_statement(sample)

        started = time.perf_counter()
        import openpyxl

        report["imports"] = {
            "openpyxl": {"version": openpyxl.__version__, "seconds": round(time.perf_counter() - started, 3)}
        }
        statement = load_statement(sample)
        report["sample_rows"] = len(statement.transactions)
        valuation = value_portfolio(compute_portfolio(statement), {})  # offline: no prices
        written = ExcelExporter(scratch / "smoke.xlsx").export(valuation, date.today()).holdings_written
        report["spreadsheet_written"] = written == len(valuation.holdings) > 0
        if quote_symbol:
            try:
                from statement_tracker.core.market_data.yahoo_provider import YahooProvider

                report["quote"] = {"ok": True, "currency": YahooProvider().quote(quote_symbol).currency}
            except Exception as exc:
                report["quote"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        app.processEvents()
        window.close()
        report["ok"] = bool(report["spreadsheet_written"])
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
