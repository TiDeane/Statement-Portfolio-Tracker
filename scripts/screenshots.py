"""Take the screenshots of the app used on the website, with made-up investments and prices.

Nothing is fetched: prices come from the tests' FakeProvider, the statement is written here, and
settings and the spreadsheet live in a temporary folder. Run it from the repo root with the
Windows environment, so the pictures show Windows' own fonts:

    .venv-win\\Scripts\\python scripts\\screenshots.py OUT_FOLDER

It saves, for the dark and the light theme (`-dark.png`, `-light.png`):
  steps     first launch, with the statement chosen
  confirm   the "Which one is it?" dialog
  result    Home after prices came in, with the spreadsheet updated
  entered-value  the investments list's first columns, with one investment's value typed in by hand
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

from PySide6.QtCore import QPointF, QRect, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402  (loaded so the window's items can be measured)

from statement_tracker.settings import Settings  # noqa: E402
from statement_tracker.gui.app import AppWindow, make_application  # noqa: E402
from tests.fakes import HEADER, FakeProvider  # noqa: E402

TODAY = date.today()
STEPS_SIZE = (1120, 800)
RESULT_SIZE = (1120, 1320)
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


def wait(app: QGuiApplication, condition, seconds: float = 30) -> None:
    import time

    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    for _ in range(5):
        app.processEvents()


def save(window, path: Path) -> None:
    window.grabWindow().save(str(path))
    print("saved", path.name)


def find(window, wanted) -> QQuickItem:
    """The first item of ``window`` for which ``wanted(item)`` is true."""
    pending = [window.contentItem()]
    while pending:
        item = pending.pop(0)
        if wanted(item):
            return item
        pending.extend(item.childItems())
    raise LookupError("not in the window")


def take(app: QGuiApplication, out: Path, scheme: str, work: Path) -> None:
    folder = work
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    statement = folder / "account-statement.csv"
    statement.write_text("\n".join([HEADER, *statement_lines()]) + "\n", encoding="utf-8")
    spreadsheet = folder / "My investments.xlsx"
    earlier_weeks(folder, spreadsheet)
    fake = provider()

    shell = AppWindow(Settings.load(folder / "settings.json"), lambda: fake, lambda: TODAY)
    shell.theme.set_dark(scheme == "dark")
    session, window = shell.session, shell.window
    window.resize(*STEPS_SIZE)
    shell.show()
    wait(app, lambda: False, 0.5)

    welcome = session.welcome
    welcome.use_statement(statement)
    wait(app, lambda: not welcome.property("reading"))
    wait(app, lambda: False, 0.3)
    save(window, out / f"steps-{scheme}.png")

    def ask_listing(resolution):
        """The real dialog, pictured, then answered with the first listing."""

        def picture_and_answer() -> None:
            save(window, out / f"confirm-{scheme}.png")
            session.dialogs.answer({"symbol": resolution.candidates[0].info.symbol, "always": False})

        QTimer.singleShot(600, picture_and_answer)
        return session._ask_listing(resolution)

    session.ask_listing = ask_listing
    welcome.next()  # on to the spreadsheet
    welcome.use_spreadsheet(spreadsheet)
    window.resize(*RESULT_SIZE)
    welcome.next()  # "Show my investments": Home, fetching today's prices
    wait(app, lambda: not session.busy)
    session.home.updateSpreadsheet()
    wait(app, lambda: not session.home.property("writing"))
    wait(app, lambda: False, 0.3)
    save(window, out / f"result-{scheme}.png")
    if scheme == "dark":
        shutil.copy(spreadsheet, out / "spreadsheet.xlsx")

    # Yahoo has no price for one fund today: the value is typed in instead.
    fake.listings["EDIV.DE"] = fake.listings["EDIV.DE"].__class__(
        fake.listings["EDIV.DE"].info, None, fake.listings["EDIV.DE"].ranges, None
    )
    session.refresh()
    wait(app, lambda: not session.busy)
    session.ask_value = lambda choices, selected, currency: (selected, Decimal("627.50"))
    session.home.enterValue("EDIV")
    wait(app, lambda: False, 0.3)
    # Only the list's first columns, up to "Worth now", from its headings down (above them are the search box
    # and the buttons), so the marked value can be read when small.
    card = find(window, lambda item: item.objectName() == "investmentsCard")
    headings = find(window, lambda item: item.objectName() == "investmentHeader")
    share = find(window, lambda item: item.property("text") == "Share of total")
    left = card.mapToScene(QPointF(0, 0)).x()
    top = headings.mapToScene(QPointF(0, 0)).y()
    bottom = card.mapToScene(QPointF(0, card.height())).y()
    right = share.mapToScene(QPointF(0, 0)).x() - 8
    scale = window.devicePixelRatio()  # the picture is drawn at QT_SCALE_FACTOR, the items measured without it
    crop = QRect(int(left * scale), int(top * scale), int((right - left) * scale), int((bottom - top) * scale))
    window.grabWindow().copy(crop).save(str(out / f"entered-value-{scheme}.png"))
    print("saved", f"entered-value-{scheme}.png")

    shell.close()
    shell.deleteLater()
    wait(app, lambda: False, 0.2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="folder to save the pictures in")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    app = make_application(sys.argv[:1])
    try:
        for scheme in ("dark", "light"):
            take(app, args.out, scheme, WORK)
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    QTimer.singleShot(0, app.quit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
