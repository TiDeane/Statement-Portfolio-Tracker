"""The main window, driven without a screen and with a mocked provider. No network."""

import gc
import os
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from fakes import SAMPLE, FakeProvider, ranges_around, write_statement  # noqa: E402
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from statement_tracker.core.calculator import buys_by_ticker  # noqa: E402
from statement_tracker.core.errors import UserFacingError  # noqa: E402
from statement_tracker.core.parser import load_statement  # noqa: E402
from statement_tracker.settings import Settings, TickerChoice  # noqa: E402
from statement_tracker.ui import theme  # noqa: E402
from statement_tracker.core.models import MarketPrice  # noqa: E402
from statement_tracker.ui.dialogs import (  # noqa: E402
    ChooseListingDialog,
    EnterValueDialog,
    ValueChoice,
    parse_amount,
)
from statement_tracker.ui.settings_dialog import ASK_AGAIN_STATUS, ENTERED_PRICE_STATUS, SettingsDialog  # noqa: E402
from statement_tracker.ui.main_window import (  # noqa: E402
    ENTERED_MARK,
    MIN_TABLE_HEIGHT,
    MIN_WINDOW_WIDTH,
    MainWindow,
    default_start_folder,
)

EQQB_BUYS = buys_by_ticker(load_statement(SAMPLE))["EQQB"]
TODAY = date(2026, 10, 12)


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(autouse=True)
def close_windows_afterwards(app):
    """Destroy each test's windows and dialogs when it ends.

    Left to Python's garbage collector, a window from one test can be destroyed at a random
    moment in the middle of a later test's event handling, which crashes Qt.
    """
    yield
    for widget in QtWidgets.QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    gc.collect()


def provider_with(*symbols: str) -> FakeProvider:
    provider = FakeProvider()
    for symbol in symbols:
        provider.add(symbol, "EUR", price="400", ranges=ranges_around(EQQB_BUYS), name="Nasdaq fund", exchange="XETRA")
    return provider


def make_window(tmp_path: Path, provider: FakeProvider) -> tuple[MainWindow, list[UserFacingError]]:
    window = MainWindow(Settings.load(tmp_path / "settings.json"), lambda: provider, lambda: TODAY)
    errors: list[UserFacingError] = []
    window.show_error = errors.append
    window.ask_retry = lambda error: bool(errors.append(error))  # record it and answer "not now"
    return window, errors


def run(app, window: MainWindow) -> None:
    window.start()
    deadline = time.monotonic() + 20
    while window._busy() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not window._busy()


def settle(app) -> None:
    """Let work queued for "once the current event is handled" run."""
    for _ in range(3):
        app.processEvents()


def shows(label, path: Path) -> bool:
    """True if the label shows the file's name and its folder, with the full path as tooltip."""
    return path.name in label.text() and str(path.parent) in label.text() and label.toolTip() == str(path)


def test_theme_styles_the_app_in_light_and_dark_and_marks_gains_with_arrow_and_colour(app, tmp_path: Path) -> None:
    try:
        assert theme.apply(app, dark=False) is theme.LIGHT
        assert theme.LIGHT.accent in app.styleSheet()
        assert theme.apply(app, dark=True) is theme.DARK
        assert theme.DARK.accent in app.styleSheet() and theme.LIGHT.background not in app.styleSheet()

        window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
        window.set_statement(SAMPLE)
        run(app, window)

        gain = window.table.item(0, 5)  # 589 now against 541 invested
        assert gain.text().startswith("▲ +")
        assert gain.foreground().color().name().upper() == theme.DARK.good.upper()
        assert window.status_label.property("state") == "ok"
        assert window.go_button.objectName() == "primary"
    finally:
        app.setStyleSheet("")


def cells(window: MainWindow) -> list[list[str]]:
    table = window.table
    return [[table.item(row, column).text() for column in range(6)] for row in range(table.rowCount())]


def test_button_is_disabled_until_a_statement_is_chosen(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    assert not window.go_button.isEnabled()
    assert window.no_spreadsheet_option.isChecked()
    assert window.go_button.text() == "Step 3: show my investments"

    window.set_statement(SAMPLE)

    assert window.go_button.isEnabled()
    assert shows(window.statement_label, SAMPLE)


def test_step_2_shows_the_choice_as_options_and_the_files_as_actions(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)

    def state() -> tuple[bool, bool, bool]:
        """(no spreadsheet chosen, spreadsheet chosen, step 3 possible)"""
        return window.no_spreadsheet_option.isChecked(), window.spreadsheet_option.isChecked(), window.go_button.isEnabled()

    def files_shown() -> bool:
        return window.existing_spreadsheet_button.isVisibleTo(window) and window.spreadsheet_label.isVisibleTo(window)

    # The file buttons are actions: never checkable, so never highlighted as if they were the choice.
    assert not window.existing_spreadsheet_button.isCheckable() and not window.new_spreadsheet_button.isCheckable()
    # Without a spreadsheet they mean nothing, so they are not shown.
    assert state() == (True, False, True) and not files_shown()

    # Choosing "Update my Excel spreadsheet" shows them, and asks for a file before step 3 can run.
    window.spreadsheet_option.click()
    assert state() == (False, True, False) and files_shown()
    assert window.spreadsheet_badge.text().startswith("To do")

    # A cancelled file dialog changes nothing.
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))
    window.existing_spreadsheet_button.click()
    assert state() == (False, True, False)

    new_file = tmp_path / "new.xlsx"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(new_file), ""))
    window.new_spreadsheet_button.click()
    assert state() == (False, True, True) and "will be created" in window.spreadsheet_label.text()

    # Back to no spreadsheet and then to the spreadsheet again: the file is still there.
    window.no_spreadsheet_option.click()
    assert state() == (True, False, True) and not files_shown()
    window.spreadsheet_option.click()
    assert state() == (False, True, True) and new_file.name in window.spreadsheet_label.text()

    # Dropping an Excel file on the window switches to the spreadsheet too.
    window.no_spreadsheet_option.click()
    window.drop_file(new_file)
    assert state() == (False, True, True) and files_shown()


def test_a_smaller_window_shrinks_the_table_instead_of_covering_it(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, FakeProvider(offline=True))  # no price: the line with buttons shows
    window.show()
    window.set_statement(SAMPLE)
    run(app, window)
    settle(app)
    table = window.table
    rows_height = table.horizontalHeader().height() + sum(table.rowHeight(row) for row in range(table.rowCount()))
    assert table.viewport().height() + table.horizontalHeader().height() >= rows_height  # every row shows

    def top(widget) -> int:
        return widget.mapTo(window, widget.rect().topLeft()).y()

    def bottom(widget) -> int:
        return widget.mapTo(window, widget.rect().bottomLeft()).y()

    window.resize(window.width(), 100)  # far smaller than everything needs
    settle(app)

    assert window.height() == window.minimumHeight()
    assert bottom(window.table) < top(window.price_bar) < top(window.settings_button)  # nothing covers the table
    assert window.table.height() >= MIN_TABLE_HEIGHT

    # Narrow as well: wrapped text takes more lines, and the window still keeps room for everything.
    window.resize(300, 100)
    settle(app)

    assert window.width() == MIN_WINDOW_WIDTH
    assert bottom(window.status_label) < top(window.table)
    assert bottom(window.table) < top(window.price_bar) < top(window.settings_button)
    assert bottom(window.settings_button) <= window.height()
    assert window.table.height() >= MIN_TABLE_HEIGHT

    # Some window managers ignore the minimum size (Weston's, as under WSL). The window then grows back to it.
    minimum = window.minimumSize()
    window.setMinimumSize(0, 0)  # what Qt enforces: nothing, as such a window manager...
    window.minimumSize = lambda: minimum  # ...while the window still knows its own minimum
    window.resize(300, 200)
    settle(app)

    assert window.size() == minimum
    del window.minimumSize

    # And if it cannot grow back either, the contents scroll rather than being drawn over each other.
    window.resize(300, 200)
    settle(app)

    assert window.height() == 200
    assert window.centralWidget().verticalScrollBar().isVisible()
    assert bottom(window.status_label) < top(window.table)
    assert bottom(window.table) < top(window.price_bar) < top(window.settings_button)
    assert window.table.height() >= MIN_TABLE_HEIGHT


def test_the_window_fits_the_steps_until_there_is_a_result(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.show()
    settle(app)
    without_files = window.height()

    window.spreadsheet_option.click()
    settle(app)
    with_files = window.height()
    window.no_spreadsheet_option.click()
    settle(app)

    assert with_files > without_files  # grown for the file buttons...
    assert window.height() == without_files  # ...and back, with no empty band left at the bottom

    window.set_statement(SAMPLE)
    run(app, window)
    with_result = window.height()
    window.spreadsheet_option.click()
    window.no_spreadsheet_option.click()
    settle(app)
    assert window.height() >= with_result  # with a result shown, the window is never shrunk


def test_a_remembered_spreadsheet_is_shown_as_the_choice_with_nothing_to_press(app, tmp_path: Path) -> None:
    first, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    first.set_spreadsheet(tmp_path / "mine.xlsx")

    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    assert window.spreadsheet_option.isChecked() and not window.no_spreadsheet_option.isChecked()
    assert window.spreadsheet_badge.text() == "✓ Already done: remembered from last time."


def test_each_step_says_whether_it_is_done_optional_or_remembered(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    assert window.statement_badge.text().startswith("To do")
    assert window.spreadsheet_badge.text() == "Optional. You can skip this step."
    assert window.spreadsheet_badge.property("state") == "optional"

    window.set_statement(SAMPLE)
    window.set_spreadsheet(tmp_path / "mine.xlsx")
    assert window.statement_badge.text() == "✓ Done"
    assert (window.spreadsheet_badge.text(), window.spreadsheet_badge.property("state")) == ("✓ Done", "ok")

    # Next time the app starts, step 2 is already taken care of and says so.
    reopened, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    assert reopened.spreadsheet_badge.text() == "✓ Already done: remembered from last time."
    assert reopened.spreadsheet_badge.property("state") == "ok"

    reopened.set_spreadsheet(None)
    assert reopened.spreadsheet_badge.text() == "Optional. You can skip this step."


def test_buttons_are_only_highlighted_when_reached_with_the_keyboard(app, tmp_path: Path) -> None:
    from PySide6.QtCore import Qt

    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.show()
    app.processEvents()

    buttons = window.findChildren(QtWidgets.QPushButton)
    assert buttons and all(button.focusPolicy() == Qt.FocusPolicy.TabFocus for button in buttons)
    assert not any(button.hasFocus() for button in buttons)
    window.close()


def test_the_result_has_its_own_page_in_the_same_window(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.show()
    settle(app)
    assert window.height() < 600  # just the three steps, no reserved empty space
    assert window.pages.currentWidget() is window.steps_page
    window.set_statement(SAMPLE)
    settle(app)
    start_height = window.height()

    run(app, window)
    settle(app)

    assert window.pages.currentWidget() is window.result_page
    assert window.result_page.isVisible() and not window.steps_page.isVisible()
    assert window.table.isVisible() and window.table.rowCount() == 2
    assert window.height() == start_height  # the same window, not a longer one

    window.back_button.click()
    assert window.pages.currentWidget() is window.steps_page
    window.go_button.click()  # step 3 again: back to the result page
    assert window.pages.currentWidget() is window.result_page
    assert not window.back_button.isEnabled()  # not while the prices are being fetched
    run(app, window)
    assert window.back_button.isEnabled()

    # A file dropped on the result page is taken by the steps, which are shown again.
    window.drop_file(tmp_path / "mine.xlsx")
    assert window.pages.currentWidget() is window.steps_page
    window.close()


def test_many_investments_scroll_in_the_table_without_lengthening_the_window(app, tmp_path: Path) -> None:
    tickers = [f"T{number:02d}" for number in range(20)]
    provider = FakeProvider()
    for ticker in tickers:
        provider.add(f"{ticker}.DE", "EUR", price="12")
    lines = ["2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 5000,EUR,1"] + [
        f"2025-01-06T10:00:{number:02d}.000Z,{ticker},BUY - MARKET,1,EUR 10.00,EUR 10,EUR,1"
        for number, ticker in enumerate(tickers)
    ]
    window, _ = make_window(tmp_path, provider)
    window.ask_listing = lambda resolution: f"{resolution.ticker}.DE"
    window.show()
    window.set_statement(write_statement(tmp_path, *lines))
    settle(app)
    start_height = window.height()

    run(app, window)
    settle(app)

    table = window.table
    assert table.rowCount() == 21  # twenty investments and the total
    row, header = table.rowHeight(0), table.horizontalHeader().height()
    assert window.height() == start_height
    assert table.height() < header + table.rowCount() * row  # the rest is reached by scrolling
    assert table.verticalScrollBar().maximum() > 0
    window.close()


def test_statement_alone_shows_the_investments(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)

    run(app, window)

    assert errors == []
    rows = cells(window)
    assert rows[0][0] == "(EQQB) Nasdaq fund"
    assert "541" in rows[0][1] and "EUR" in rows[0][1]
    assert "589" in rows[0][3]
    assert rows[0][5].startswith("▲ +47") and "(+8" in rows[0][5]  # 589.31 against 541.49
    assert rows[0][3][0].isdigit()  # the value itself carries no arrow
    assert rows[0][2].startswith("100") and rows[0][4].startswith("100")  # both shares: the only holding
    assert rows[1][0] == "Total"
    assert window.status_label.text() == "Done. Your investments are shown below."
    assert list(tmp_path.glob("*.xlsx")) == []


def test_with_a_spreadsheet_it_is_created_and_remembered(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    spreadsheet = tmp_path / "mine.xlsx"
    window.set_statement(SAMPLE)
    window.set_spreadsheet(spreadsheet)
    assert window.go_button.text() == "Step 3: show my investments and update my spreadsheet"
    assert "will be created" in window.spreadsheet_label.text()

    run(app, window)

    assert errors == []
    assert "Your spreadsheet was created" in window.status_label.text()
    assert load_workbook(spreadsheet).sheetnames == ["Current Holdings", "Portfolio History"]
    assert load_workbook(spreadsheet)["Current Holdings"]["A2"].value == "(EQQB) Nasdaq fund"

    reopened, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    assert shows(reopened.spreadsheet_label, spreadsheet)
    reopened.set_spreadsheet(None)
    assert Settings.load(tmp_path / "settings.json").spreadsheet_path is None


def test_dropped_files_go_to_the_right_step(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    window.drop_file(tmp_path / "book.xlsx")
    window.drop_file(SAMPLE)

    assert shows(window.spreadsheet_label, tmp_path / "book.xlsx")
    assert shows(window.statement_label, SAMPLE)
    assert Settings.load(tmp_path / "settings.json").last_folder == SAMPLE.parent


def test_file_dialogs_open_in_the_start_folder_until_a_folder_is_remembered(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    assert window._start_folder() == str(project)  # run from source: where the app was started

    window.set_statement(SAMPLE)
    assert window._start_folder() == str(SAMPLE.parent)  # afterwards: the last folder used

    monkeypatch.setattr("sys.frozen", True, raising=False)  # the installed app
    assert default_start_folder() != project
    assert default_start_folder().exists()


def test_wrong_file_is_explained_in_plain_words(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(write_statement(tmp_path, "2025-01-06,ABCD,1", header="Date,Symbol,Amount"))

    run(app, window)

    assert len(errors) == 1
    assert "does not look like a Revolut stock statement" in errors[0].what_happened
    assert window.status_label.text() == "That did not work. Nothing was changed."
    assert window.go_button.isEnabled()


def test_unexpected_failure_becomes_a_reportable_error_not_a_crash(app, tmp_path: Path) -> None:
    def broken_provider():
        raise RuntimeError("boom")

    window = MainWindow(Settings.load(tmp_path / "settings.json"), broken_provider, lambda: TODAY)
    errors: list[UserFacingError] = []
    window.show_error = errors.append
    window.set_statement(SAMPLE)

    run(app, window)

    assert errors[0].what_happened == "Something unexpected went wrong."
    assert "RuntimeError: boom" in errors[0].details
    assert "Traceback" not in errors[0].what_happened + errors[0].what_to_do


def test_ambiguous_investment_asks_the_user_and_remembers_the_answer(app, tmp_path: Path) -> None:
    provider = provider_with("EQQB.DE", "EQQB.MI")
    window, errors = make_window(tmp_path, provider)
    asked = []

    def choose(resolution):
        asked.append(resolution)
        return "EQQB.MI"

    window.ask_listing = choose
    window.set_statement(SAMPLE)

    run(app, window)

    assert errors == []
    assert [resolution.ticker for resolution in asked] == ["EQQB"]
    saved = Settings.load(tmp_path / "settings.json").ticker_choices["EQQB"]
    assert (saved.symbol, saved.confirmed) == ("EQQB.MI", True)

    run(app, window)
    assert len(asked) == 1  # not asked again


def test_skipped_investment_shows_as_unavailable(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE", "EQQB.MI"))
    window.ask_listing = lambda resolution: None
    window.set_statement(SAMPLE)

    run(app, window)

    assert cells(window)[0][3] == "unavailable"
    assert cells(window)[0][4] == "unavailable"  # no share of worth without a worth


def test_locked_spreadsheet_still_shows_the_investments(app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)  # first run settles the ticker choice, so only the spreadsheet is saved below
    window.set_spreadsheet(tmp_path / "mine.xlsx")

    def locked(source, target) -> None:
        raise PermissionError(13, "being used by another process")

    monkeypatch.setattr("os.replace", locked)
    run(app, window)

    assert "open in another program" in errors[0].what_happened
    assert cells(window)[0][0] == "(EQQB) Nasdaq fund"
    assert "spreadsheet was not updated" in window.status_label.text()


def test_an_investment_is_renamed_by_typing_in_its_cell(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    spreadsheet = tmp_path / "mine.xlsx"
    window.show()
    window.set_statement(SAMPLE)
    window.set_spreadsheet(spreadsheet)
    run(app, window)
    asked = []
    window.ask_value = lambda *question: asked.append(question)
    table = window.table
    assert table.item(0, 0).text() == "(EQQB) Nasdaq fund"
    editable = Qt.ItemFlag.ItemIsEditable
    assert table.item(0, 0).flags() & editable  # the name...
    assert not table.item(0, 3).flags() & editable and not table.item(1, 0).flags() & editable  # ...and nothing else

    def type_name(shown: str, typed: str) -> None:
        table.editItem(table.item(0, 0))  # what double-clicking does
        editor = table.findChild(QtWidgets.QLineEdit)
        assert editor.text() == shown  # the name alone, without the ticker
        editor.setText(typed)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        settle(app)

    type_name("Nasdaq fund", " Tech fund ")

    assert table.item(0, 0).text() == "(EQQB) Tech fund"
    assert Settings.load(tmp_path / "settings.json").index_names == {"EQQB": "Tech fund"}
    assert load_workbook(spreadsheet)["Current Holdings"]["A2"].value == "(EQQB) Tech fund"
    assert asked == [] and errors == []  # no price was asked for, nothing went wrong

    type_name("Tech fund", "")  # empty: back to the name from Yahoo
    assert table.item(0, 0).text() == "(EQQB) Nasdaq fund"
    assert Settings.load(tmp_path / "settings.json").index_names == {}


def test_a_value_typed_into_the_spreadsheet_is_used_on_the_next_run(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, FakeProvider(offline=True))
    spreadsheet = tmp_path / "mine.xlsx"
    window.set_statement(SAMPLE)
    window.set_spreadsheet(spreadsheet)
    run(app, window)
    assert window.table.item(0, 3).text() == "unavailable"
    workbook = load_workbook(spreadsheet)
    workbook["Current Holdings"]["D2"] = 600  # typed by the user over "unavailable"
    workbook.save(spreadsheet)

    run(app, window)

    assert errors == []
    assert window.table.item(0, 3).text().endswith(ENTERED_MARK)
    assert "600" in window.table.item(0, 3).text()


def test_packaging_smoke_test_reads_the_sample_and_writes_a_spreadsheet(app, tmp_path: Path) -> None:
    import json

    from statement_tracker.__main__ import _run_smoke_test

    out = tmp_path / "report.json"

    assert _run_smoke_test(SAMPLE, out, None) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] and report["spreadsheet_written"]
    assert report["sample_rows"] == 18
    assert report["imports"]["openpyxl"]["version"]


def test_help_page_gives_the_revolut_steps_and_asks_for_the_whole_history() -> None:
    from statement_tracker.ui.dialogs import WHERE_IS_THE_FILE_TEXT

    for step in ("Invest", "More", "Documents", "Brokerage account", "Account statement", "CSV", "All time"):
        assert step in WHERE_IS_THE_FILE_TEXT
    assert "whole history" in WHERE_IS_THE_FILE_TEXT
    assert "PLACEHOLDER" not in WHERE_IS_THE_FILE_TEXT


def test_try_again_saves_the_spreadsheet_without_fetching_prices_again(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    provider = provider_with("EQQB.DE")
    window, _ = make_window(tmp_path, provider)
    window.set_statement(SAMPLE)
    run(app, window)  # settles the ticker choice
    spreadsheet = tmp_path / "mine.xlsx"
    window.set_spreadsheet(spreadsheet)

    real_replace, attempts, asked = os.replace, [], []

    def locked_twice(source, target) -> None:
        if Path(target) == spreadsheet:  # other files (settings, last prices) are saved normally
            attempts.append(target)
        if Path(target) == spreadsheet and len(attempts) <= 2:
            raise PermissionError(13, "being used by another process")
        real_replace(source, target)

    def try_again(error: UserFacingError) -> bool:
        asked.append(error.what_happened)
        return True

    monkeypatch.setattr("os.replace", locked_twice)
    window.ask_retry = try_again
    provider.calls.clear()
    run(app, window)

    assert len(asked) == 2 and all("open in another program" in text for text in asked)
    assert provider.calls == [("quote", "EQQB.DE")]  # prices fetched once, not once per attempt
    assert spreadsheet.exists()
    assert "Your spreadsheet was created" in window.status_label.text()
    assert window.status_label.property("state") == "ok"


def test_last_known_price_is_marked_in_the_table_and_explained(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    assert "*" not in cells(window)[0][3]

    offline, _ = make_window(tmp_path, FakeProvider(offline=True))
    offline.set_statement(SAMPLE)
    run(app, offline)

    worth, total = offline.table.item(0, 3), offline.table.item(1, 3)
    assert worth.text().endswith(" *") and "Last known price, from" in worth.toolTip()
    assert total.text().endswith(" *") and "not up to date" in total.toolTip()


def test_prices_line_appears_only_when_a_price_is_missing(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    assert window.price_bar.isHidden()
    asked = []
    window.ask_value = lambda *question: asked.append(question)
    window.table.cellDoubleClicked.emit(0, 3)
    settle(app)
    assert asked == []  # a current price from Yahoo: nothing to enter
    assert window.table.item(0, 3).background().style() == Qt.BrushStyle.NoBrush

    (tmp_path / "other").mkdir()  # no last known price there
    offline, _ = make_window(tmp_path / "other", FakeProvider(offline=True))
    offline.set_statement(SAMPLE)
    run(app, offline)
    assert not offline.price_bar.isHidden()
    worth = offline.table.item(0, 3)
    assert worth.text() == "unavailable"
    assert "Double-click to enter its value" in worth.toolTip()
    # In red, as in the spreadsheet: missing, and a price can be entered there. Only that cell.
    assert worth.background().color().name().upper() == theme.current().missing.upper()
    assert offline.table.item(0, 1).background().style() == Qt.BrushStyle.NoBrush
    assert offline.table.item(1, 3).background().style() == Qt.BrushStyle.NoBrush  # nor the Total


def test_entered_value_fills_in_the_table_and_the_spreadsheet_as_typed(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, FakeProvider(offline=True))
    window._now = lambda: datetime(TODAY.year, TODAY.month, TODAY.day, 12).astimezone()
    spreadsheet = tmp_path / "mine.xlsx"
    window.set_statement(SAMPLE)
    window.set_spreadsheet(spreadsheet)
    run(app, window)
    asked = []

    def answer(choices, selected, currency):
        asked.append(([(choice.label, choice.shares) for choice in choices], selected, currency))
        return "EQQB", Decimal("600")  # what all 1.47 shares are worth, not one share's price

    window.ask_value = answer
    window.table.cellDoubleClicked.emit(1, 3)  # the Total row: nothing to enter there
    settle(app)
    assert asked == []
    window.table.cellDoubleClicked.emit(0, 3)
    settle(app)

    assert asked == [([("EQQB", Decimal("1.47328346"))], "EQQB", "EUR")]
    assert errors == []
    worth, total = window.table.item(0, 3), window.table.item(1, 3)
    assert worth.text().startswith(("600.00", "600,00"))  # the number typed is the number shown
    assert worth.text().endswith(f" {ENTERED_MARK}") and "Value you entered on" in worth.toolTip()
    assert total.text().endswith(f" {ENTERED_MARK}") and "entered yourself" in total.toolTip()
    assert not window.price_bar.isHidden()  # the value can still be changed, or fetched again
    sheet = load_workbook(spreadsheet)["Current Holdings"]
    assert sheet["D2"].value == pytest.approx(600)
    history = load_workbook(spreadsheet)["Portfolio History"]
    assert history.max_row == 2  # typed in today, so today's row is written

    window.ask_value = lambda choices, selected, currency: ("EQQB", Decimal("123"))  # changed again
    window.enter_value(0)
    assert window.table.item(0, 3).text().startswith(("123.00", "123,00"))


def test_investments_without_a_price_are_left_out_of_the_totals(app, tmp_path: Path) -> None:
    statement = write_statement(
        tmp_path,
        "2025-01-06T09:00:00.000Z,,CASH TOP-UP,,,EUR 2000,EUR,1",
        "2025-01-06T10:00:00.000Z,EQQB,BUY - MARKET,1,EUR 380.00,EUR 381,EUR,1",
        "2025-01-20T10:00:00.000Z,ZQXJ,BUY - MARKET,2,EUR 50.00,EUR 100,EUR,1",  # not on Yahoo
    )
    settings = Settings.load(tmp_path / "settings.json")
    settings.remember("EQQB", TickerChoice("EQQB.DE", "Nasdaq fund", confirmed=True))
    settings.save()

    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.ask_listing = lambda resolution: None  # "Skip this investment"
    window.set_statement(statement)
    run(app, window)

    eqqb, zqxj, total = cells(window)
    assert zqxj[0] == "ZQXJ" and zqxj[2] == zqxj[4] == "not in total" and zqxj[3] == "unavailable"
    assert window.price_bar_label.text() == "Yahoo Finance has no current price for ZQXJ."
    assert "left out of the totals" in window.table.item(1, 3).toolTip()
    assert eqqb[2] == eqqb[4] == total[2] == total[4]  # 100 %: EQQB is all the totals cover
    assert total[1] == eqqb[1] and total[3] == eqqb[3]


def test_enter_value_dialog_starts_from_the_value_known_and_returns_the_one_typed(app) -> None:
    last_known = MarketPrice(
        Decimal("100"), "BBBB.DE", "EUR", as_of=datetime(2026, 10, 3, 17, 30, tzinfo=UTC), last_known=True
    )
    choices = [
        ValueChoice("AAAA", "(AAAA) First fund", Decimal("3"), None),
        ValueChoice("BBBB", "(BBBB) Second fund", Decimal("2.5"), last_known),
    ]
    dialog = EnterValueDialog(choices, "BBBB", "EUR")

    assert dialog.investment.isVisibleTo(dialog) and dialog.investment.currentData() == "BBBB"
    assert parse_amount(dialog.value.text()) == Decimal("250")  # 2.5 shares at 100: the whole value
    assert dialog.use_button.isEnabled()

    dialog.investment.setCurrentIndex(0)
    assert dialog.value.text() == "" and not dialog.use_button.isEnabled()
    dialog.value.setText("abc")
    assert not dialog.use_button.isEnabled() and dialog.entered() is None
    dialog.value.setText("512,34")
    assert dialog.use_button.isEnabled()
    assert dialog.entered() == ("AAAA", Decimal("512.34"))


def test_investments_without_a_price_are_named_as_a_sentence() -> None:
    from statement_tracker.ui.main_window import _listed

    assert [_listed(["A"]), _listed(["A", "B"]), _listed(["A", "B", "C"])] == ["A", "A and B", "A, B and C"]


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("512.34", "512.34"), ("512,34", "512.34"), (" 500 ", "500"), ("1,234.56", "1234.56"),
        ("1.234,56", "1234.56"), ("1 234,5", "1234.5"), ("0", None), ("-5", None), ("", None),
        ("abc", None), ("1.2.3", None), ("12 EUR", None), ("NaN", None),
    ],
)  # fmt: skip
def test_typed_amounts_are_read_with_a_comma_or_a_full_stop(text: str, price: str | None) -> None:
    assert parse_amount(text) == (Decimal(price) if price else None)


def test_settings_rename_choose_again_and_forget_an_investment(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    dialog = SettingsDialog(Settings.load(tmp_path / "settings.json"))

    def row() -> list[str]:
        return [dialog.table.item(0, column).text() for column in range(4)]

    assert row() == ["EQQB", "Nasdaq fund", "EQQB.DE (XETRA, EUR)", "Matched automatically"]
    assert "from Yahoo Finance" in dialog.table.item(0, 1).toolTip()  # Yahoo's name, not the user's
    assert not dialog.rename_button.isEnabled()  # nothing selected yet

    dialog.table.selectRow(0)
    dialog.table.item(0, 1).setText(" Tech fund ")  # what pressing Enter in the cell's editor does
    settle(app)  # the table is redrawn once the edit is over
    assert row()[1] == "Tech fund"
    assert "from Yahoo Finance" not in dialog.table.item(0, 1).toolTip()
    assert Settings.load(tmp_path / "settings.json").index_names == {"EQQB": "Tech fund"}

    dialog.choose_again_selected()
    assert row()[3] == ASK_AGAIN_STATUS
    assert not dialog.choose_again_button.isEnabled()
    assert Settings.load(tmp_path / "settings.json").ask_again == {"EQQB"}

    dialog.confirm = lambda question: False
    dialog.forget_selected()
    assert dialog.table.rowCount() == 1  # cancelled
    dialog.confirm = lambda question: True
    dialog.table.selectRow(0)
    dialog.forget_selected()
    assert dialog.table.isHidden() and not dialog.empty_label.isHidden()
    assert Settings.load(tmp_path / "settings.json").known_tickers() == []


def test_settings_forget_all_keeps_the_rest(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    window.set_spreadsheet(tmp_path / "mine.xlsx")
    run(app, window)
    settings_path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings.load(settings_path))
    asked: list[str] = []

    dialog.confirm = lambda question: bool(asked.append(question))  # cancelled
    dialog.forget_all()
    assert dialog.table.rowCount() == 1 and asked[0].startswith("Forget your one investment?")

    dialog.confirm = lambda question: True
    dialog.forget_all()
    saved = Settings.load(settings_path)
    assert saved.known_tickers() == [] and not dialog.forget_all_button.isEnabled()
    assert saved.spreadsheet_path == tmp_path / "mine.xlsx"
    assert (tmp_path / "last_prices.json").exists()


def test_settings_forget_the_prices_entered_too_but_not_the_ones_fetched(app, tmp_path: Path) -> None:
    from statement_tracker.price_cache import PriceCache

    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)  # EQQB matched, and its price fetched
    settings_path = tmp_path / "settings.json"
    prices = PriceCache.beside(settings_path)
    entered_at = datetime(2026, 10, 12, 12, tzinfo=UTC)
    prices.enter("EQQB", Decimal("410"), "EUR", entered_at)
    prices.enter("ZQXJ", Decimal("55"), "EUR", entered_at)  # never matched to a listing: only its price is kept
    prices.save()
    dialog = SettingsDialog(Settings.load(settings_path))
    dialog.confirm = lambda question: True

    def row(ticker: str) -> list[str]:
        (found,) = [r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).text() == ticker]
        return [dialog.table.item(found, column).text() for column in range(4)]

    assert row("ZQXJ") == ["ZQXJ", "", "", f"Not matched yet; {ENTERED_PRICE_STATUS}"]
    assert row("EQQB")[3] == f"Matched automatically; {ENTERED_PRICE_STATUS}"

    dialog.table.selectRow(1)  # ZQXJ, after EQQB
    dialog.forget_selected()
    assert PriceCache.beside(settings_path).entered_tickers() == {"EQQB"}
    assert dialog.table.rowCount() == 1

    dialog.forget_all()
    kept = PriceCache.beside(settings_path)
    assert kept.entered_tickers() == set()
    assert kept.last_known("EQQB.DE", "EUR") is not None  # the price fetched from Yahoo stays
    assert dialog.table.rowCount() == 0


def test_forgetting_in_settings_shows_at_once_in_the_result(app, tmp_path: Path) -> None:
    provider = provider_with("EQQB.DE")
    window, errors = make_window(tmp_path, provider)
    window.set_statement(SAMPLE)
    run(app, window)
    provider.offline = True
    run(app, window)  # Yahoo unreachable: the last price fetched
    window.ask_value = lambda choices, selected, currency: ("EQQB", Decimal("450"))
    window.enter_value(0)
    assert window.table.item(0, 3).text().endswith(ENTERED_MARK)

    def forget_everything(dialog: SettingsDialog) -> None:
        dialog.confirm = lambda question: True
        dialog.forget_all()

    window.show_settings = forget_everything
    window.open_settings()

    assert errors == []
    assert window.table.item(0, 3).text().endswith(" *")  # back to the last price fetched, not the one entered
    assert Settings.load(tmp_path / "settings.json").known_tickers() == []  # and the listing stays forgotten


def test_settings_only_the_name_is_edited_in_the_table(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    settings_path = tmp_path / "settings.json"
    dialog = SettingsDialog(Settings.load(settings_path))

    editable = [bool(dialog.table.item(0, column).flags() & Qt.ItemFlag.ItemIsEditable) for column in range(4)]
    assert editable == [False, True, False, False]

    def type_name(text: str | None) -> None:
        """Press Rename, then type ``text`` and Enter, or Esc when ``text`` is None."""
        dialog.table.selectRow(0)
        dialog.rename_button.click()  # opens the same in-cell editor as a double click
        editors = dialog.table.viewport().findChildren(QtWidgets.QLineEdit)
        editor = next(editor for editor in editors if editor.isVisible())
        if text is None:
            QTest.keyClick(editor, Qt.Key.Key_Escape)
        else:
            editor.setText(text)
            QTest.keyClick(editor, Qt.Key.Key_Return)
        settle(app)

    dialog.show()
    type_name("Nasdaq fund")  # Yahoo's name, unchanged: stays Yahoo's
    assert Settings.load(settings_path).index_names == {}
    type_name("Mine")
    assert Settings.load(settings_path).index_names == {"EQQB": "Mine"}
    type_name(None)  # Esc cancels
    assert Settings.load(settings_path).index_names == {"EQQB": "Mine"}
    type_name("  ")  # empty: back to Yahoo's name
    assert Settings.load(settings_path).index_names == {}
    assert dialog.table.item(0, 1).text() == "Nasdaq fund"
    dialog.close()


def test_settings_highlight_the_whole_row_under_the_mouse(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    dialog = SettingsDialog(Settings.load(tmp_path / "settings.json"))
    delegate = dialog.table.itemDelegate()

    def hovered(column: int) -> bool:
        option = QtWidgets.QStyleOptionViewItem()
        delegate.initStyleOption(option, dialog.table.model().index(0, column))
        return bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)

    dialog.table.entered.emit(dialog.table.model().index(0, 1))  # the mouse is over the name
    assert [hovered(column) for column in range(4)] == [True, True, True, True]
    dialog.table.viewportEvent(QEvent(QEvent.Type.Leave))  # the mouse leaves the table
    assert not any(hovered(column) for column in range(4))


def test_settings_open_from_the_window_on_its_own_settings(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    run(app, window)
    shown: list[list[str]] = []
    window.show_settings = lambda dialog: shown.append(dialog._settings.known_tickers())

    window.open_settings()

    assert shown == [["EQQB"]]


def test_settings_button_is_disabled_while_running(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)
    window.start()
    assert not window.settings_button.isEnabled()
    run(app, window)
    assert window.settings_button.isEnabled()


def test_progress_bar_counts_each_investment_and_the_spreadsheet(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    seen: list[tuple[int, int, str]] = []
    window.progressed.connect(lambda done, total, text: seen.append((done, total, text)))
    window.set_statement(SAMPLE)
    window.set_spreadsheet(tmp_path / "mine.xlsx")
    assert window.progress_bar.isHidden()

    run(app, window)

    assert seen[0] == (0, 0, "Reading your statement...")  # total not known yet: a moving bar
    # Getting ready, finding EQQB's listing (a first run), its price and the spreadsheet: four steps.
    assert (0, 4, "Getting ready to look up prices...") in seen
    assert (1, 4, "Finding the stock exchange listing of EQQB...") in seen
    assert (2, 4, "Getting the current prices (0 of 1)...") in seen
    assert (3, 4, "Getting the current prices (1 of 1)...") in seen
    assert seen[-1] == (3, 4, "Updating your spreadsheet...")
    assert [done for done, total, _ in seen if total] == sorted(done for done, total, _ in seen if total)
    assert window.progress_bar.isHidden()  # hidden again once finished
    assert window.progress_bar.format() == "%p%"


def test_listing_dialog_returns_the_selection_or_the_typed_symbol(app) -> None:
    from statement_tracker.core.ticker_resolver import resolve_ticker

    resolution = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider_with("EQQB.DE", "EQQB.MI"))
    dialog = ChooseListingDialog(resolution)

    assert dialog.chosen_symbol() == "EQQB.DE"
    dialog._group.button(1).setChecked(True)
    assert dialog.chosen_symbol() == "EQQB.MI"
    dialog._typed.setText(" EQQB.SW ")
    assert dialog.chosen_symbol() == "EQQB.SW"


def test_always_use_the_first_listing_is_offered_whenever_there_is_a_listing(app, tmp_path: Path) -> None:
    from statement_tracker.core.ticker_resolver import Confidence, resolve_ticker

    several = ChooseListingDialog(resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider_with("EQQB.DE", "EQQB.MI")))
    # The buttons, in this order: use the selection, always use the first, skip.
    row = [several.use_button, several.always_first_button, several.skip_button]
    layout = several.layout().itemAt(several.layout().count() - 1).layout()
    shown = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
    assert shown == row
    assert several.always_first_button.isVisibleTo(several)

    # "Always choose the first option" uses the first listing now, even with another one selected.
    several._group.button(1).setChecked(True)
    several.always_first_button.click()
    assert several.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert (several.chosen_symbol(), several.always_use_first()) == ("EQQB.DE", True)

    used = ChooseListingDialog(resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider_with("EQQB.DE", "EQQB.MI")))
    used._group.button(1).setChecked(True)
    used.use_button.click()
    assert (used.chosen_symbol(), used.always_use_first()) == ("EQQB.MI", False)

    # Choosing a matched listing again from Settings: the first one fits, so it is offered too.
    matched = resolve_ticker("EQQB", EQQB_BUYS, "EUR", provider_with("EQQB.DE"))
    assert matched.confidence is Confidence.CONFIDENT
    again = ChooseListingDialog(matched)
    assert again.always_first_button.isVisibleTo(again)

    # "The app could not tell for sure": listings found, none fitting the purchases. Offered as well.
    far_off = {day: (low + 100, high + 100) for day, (low, high) in ranges_around(EQQB_BUYS).items()}
    unmatched = FakeProvider()
    unmatched.add("EQQB.DE", "EUR", price="400", ranges=far_off)  # exists, but no purchase fits its prices
    guess = resolve_ticker("EQQB", EQQB_BUYS, "EUR", unmatched)
    assert guess.confidence is Confidence.UNRESOLVED and guess.candidates
    none_fit = ChooseListingDialog(guess)
    assert none_fit.always_first_button.isVisibleTo(none_fit)

    # Nothing found at all: there is no first listing to take.
    nothing_found = ChooseListingDialog(resolve_ticker("EQQB", EQQB_BUYS, "EUR", FakeProvider()))
    assert not nothing_found.always_first_button.isVisibleTo(nothing_found)


def test_nothing_found_asks_for_a_symbol_or_to_skip(app) -> None:
    from statement_tracker.core.ticker_resolver import resolve_ticker

    dialog = ChooseListingDialog(resolve_ticker("EQQB", EQQB_BUYS, "EUR", FakeProvider()))

    # Only typing a symbol gives something to use; until then, skipping is the way on.
    assert dialog.use_button.text() == "Use this symbol" and not dialog.use_button.isEnabled()
    dialog._typed.setText("  ")
    assert not dialog.use_button.isEnabled()
    dialog._typed.setText("EQQB.SW")
    assert dialog.use_button.isEnabled() and dialog.chosen_symbol() == "EQQB.SW"


def test_always_using_the_first_listing_is_remembered_and_shown_in_settings(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from statement_tracker.ui import dialogs

    monkeypatch.setattr(dialogs, "ask_listing", lambda parent, resolution: ("EQQB.DE", True))
    window, _ = make_window(tmp_path, provider_with("EQQB.DE", "EQQB.MI"))
    window.set_statement(SAMPLE)
    run(app, window)

    assert window.table.item(0, 0).text() == "(EQQB) Nasdaq fund"
    settings_path = tmp_path / "settings.json"
    assert Settings.load(settings_path).always_use_first_listing
    assert Settings.load(settings_path).ticker_choices["EQQB"].symbol == "EQQB.DE"

    dialog = SettingsDialog(Settings.load(settings_path))
    assert dialog.always_first.isChecked()
    dialog.always_first.setChecked(False)
    assert not Settings.load(settings_path).always_use_first_listing
