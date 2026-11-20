"""Take the screenshots of the app used on the website, with made-up investments and prices.

Nothing is fetched: prices come from the tests' FakeProvider, the statement is written here, and
settings and the spreadsheet live in a temporary folder. Run it from the repo root with the
Windows environment, so the pictures show the real Windows 11 look:

    .venv-win\\Scripts\\python scripts\\screenshots.py OUT_FOLDER

It saves, for the dark and the light theme (`-dark.png`, `-light.png`):
  steps     the three steps, with a statement and a spreadsheet chosen
  confirm   the "which listing is yours?" dialog
  result    the result page after a run, with the spreadsheet updated
  entered-value  the table's first columns, with one investment's value typed in by hand
and the spreadsheet the run wrote, `spreadsheet.xlsx`, for pictures of its sheets.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("QT_SCALE_FACTOR", "2")  # sharp on high-density screens

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from statement_tracker.settings import Settings  # noqa: E402
from statement_tracker.ui import dialogs, theme  # noqa: E402
from statement_tracker.ui.main_window import MainWindow  # noqa: E402
from tests.fakes import HEADER, FakeProvider  # noqa: E402

TODAY = date.today()
STEPS_SIZE = (1120, 700)
RESULT_SIZE = (1120, 560)
# Shown in the pictures ("in C:\\Users\\Public\\Documents\\Investments"), so it names nobody.
WORK = Path(os.environ.get("PUBLIC", tempfile.gettempdir())) / "Documents" / "Investments"

# Made-up funds: (ticker, name, listings, price per share now, buys as (days ago, shares, price)).
FUNDS = [
    ("WRLD", "Global equity fund", ["WRLD.DE"], "112.40", [(700, "4", "86.10"), (400, "3", "94.25"), (90, "2", "108.30")]),
    ("NSDQ", "US technology fund", ["NSDQ.DE"], "418.75", [(650, "1.5", "301.20"), (300, "0.8", "362.90")]),
    ("EMKT", "Emerging markets fund", ["EMKT.DE", "EMKT.AS"], "31.85", [(500, "20", "33.40"), (200, "10", "30.15")]),
    ("EDIV", "Europe dividend fund", ["EDIV.DE"], "27.10", [(450, "15", "24.60"), (120, "8", "26.05")]),
    ("GBND", "Global bond fund", ["GBND.DE"], "48.92", [(600, "10", "47.80"), (250, "6", "48.10")]),
    ("CLEN", "Clean energy fund", ["CLEN.DE"], "6.84", [(550, "60", "8.12")]),
    ("JPEQ", "Japan equity fund", ["JPEQ.DE"], "19.37", [(350, "25", "16.90")]),
]


def statement_lines(until: date = TODAY) -> list[str]:
    """A full-history statement in EUR up to ``until``: a top-up before each buy, and one dividend."""
    lines = []
    for ticker, _, _, _, buys in FUNDS:
        for days_ago, shares, price in buys:
            if TODAY - timedelta(days=days_ago) > until:
                continue
            when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=10)
            total = (Decimal(shares) * Decimal(price) + Decimal("1")).quantize(Decimal("0.01"))
            stamp = when.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            lines.append(f"{stamp},,CASH TOP-UP,,,EUR {total + 50},EUR,1.0000")
            lines.append(f"{stamp.replace('10:00', '10:05')},{ticker},BUY - MARKET,{shares},EUR {price},EUR {total},EUR,1.0000")
    if TODAY - timedelta(days=60) <= until:
        stamp = (TODAY - timedelta(days=60)).strftime("%Y-%m-%dT09:00:00.000Z")
        lines.append(f"{stamp},EDIV,DIVIDEND,,,EUR 6.42,EUR,1.0000")
    return sorted(lines)


def provider(scale: Decimal = Decimal(1)) -> FakeProvider:
    """Today's made-up prices, or, with ``scale``, the prices of an earlier day."""
    fake = FakeProvider()
    for ticker, name, listings, price, buys in FUNDS:
        price = str((Decimal(price) * scale).quantize(Decimal("0.01")))
        ranges = {}
        for days_ago, _, buy_price in buys:
            p = Decimal(buy_price)
            ranges[TODAY - timedelta(days=days_ago)] = (p - Decimal("0.5"), p + Decimal("0.5"))
        for symbol in listings:
            exchange = "Amsterdam" if symbol.endswith(".AS") else "XETRA"
            fake.add(symbol, "EUR", price=price, ranges=ranges, name=name, exchange=exchange)
    return fake


# How the whole portfolio moved over the weeks before today, oldest first (1 = today's prices).
WEEKS = ["0.93", "0.95", "0.94", "0.97", "0.96", "0.99", "0.98", "1.01"]


def earlier_weeks(folder: Path, spreadsheet: Path) -> None:
    """Fill Portfolio History with a row a week for the last weeks, as if the app had been used then.
    Uses its own settings, so the window still asks which listing EMKT is."""
    from statement_tracker.workflow import build_report, update_spreadsheet

    own = folder / "earlier"
    own.mkdir()
    settings = Settings.load(own / "settings.json")
    settings.backups_kept = 0
    for weeks_ago, scale in zip(range(len(WEEKS), 0, -1), WEEKS):
        day = TODAY - timedelta(weeks=weeks_ago)
        statement = own / f"statement-{day}.csv"
        statement.write_text("\n".join([HEADER, *statement_lines(day)]) + "\n", encoding="utf-8")
        report = build_report(
            statement,
            provider(Decimal(scale)),
            settings,
            chooser=lambda resolution: resolution.candidates[0].info.symbol,
            now=datetime.combine(day, datetime.min.time()).replace(hour=18, tzinfo=UTC),
        )
        update_spreadsheet(report, settings, spreadsheet, day)
    shutil.rmtree(own)


def wait(app: QApplication, condition, seconds: float = 30) -> None:
    import time

    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    for _ in range(5):
        app.processEvents()


def save(widget, path: Path) -> None:
    widget.grab().save(str(path))
    print("saved", path.name)


def take(app: QApplication, out: Path, scheme: str, work: Path) -> None:
    theme.apply(app, dark=scheme == "dark")
    folder = work
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    statement = folder / "account-statement.csv"
    statement.write_text("\n".join([HEADER, *statement_lines()]) + "\n", encoding="utf-8")
    spreadsheet = folder / "My investments.xlsx"
    earlier_weeks(folder, spreadsheet)
    fake = provider()

    window = MainWindow(Settings.load(folder / "settings.json"), lambda: fake, lambda: TODAY)
    window.resize(*STEPS_SIZE)
    window.show()
    wait(app, lambda: False, 0.5)

    window.set_statement(statement)
    window.set_spreadsheet(spreadsheet)
    wait(app, lambda: False, 0.3)
    save(window, out / f"steps-{scheme}.png")

    def ask_listing(resolution):
        dialog = dialogs.ChooseListingDialog(resolution, window)
        dialog.show()
        wait(app, lambda: False, 0.5)
        save(dialog, out / f"confirm-{scheme}.png")
        symbol = dialog.chosen_symbol()
        dialog.reject()
        return symbol

    window.ask_listing = ask_listing
    window.resize(*RESULT_SIZE)
    window.start()
    wait(app, lambda: not window._busy())
    wait(app, lambda: False, 0.3)
    save(window, out / f"result-{scheme}.png")
    if scheme == "dark":
        shutil.copy(spreadsheet, out / "spreadsheet.xlsx")

    # Yahoo has no price for one fund today: the value is typed in instead.
    fake.listings["EDIV.DE"] = fake.listings["EDIV.DE"].__class__(
        fake.listings["EDIV.DE"].info, None, fake.listings["EDIV.DE"].ranges, None
    )
    window.start()
    wait(app, lambda: not window._busy())
    window.ask_value = lambda choices, selected, currency: (selected, Decimal("627.50"))
    window.enter_value()
    wait(app, lambda: False, 0.3)
    # Only the table's first columns, up to "Worth now", so the marked value can be read when small.
    table = window.table
    right = table.columnViewportPosition(4) + table.viewport().x() + 1
    bottom = table.viewport().y() + sum(table.rowHeight(row) for row in range(table.rowCount())) + 2
    table.grab(QRect(0, 0, right, bottom)).save(str(out / f"entered-value-{scheme}.png"))
    print("saved", f"entered-value-{scheme}.png")

    window.close()
    window.deleteLater()
    wait(app, lambda: False, 0.2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="folder to save the pictures in")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    try:
        for scheme in ("dark", "light"):
            take(app, args.out, scheme, WORK)
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    QTimer.singleShot(0, app.quit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
