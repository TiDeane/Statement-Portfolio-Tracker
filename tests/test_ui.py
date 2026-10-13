"""The main window, driven without a screen and with a mocked provider. No network."""

import os
import time
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from fakes import SAMPLE, FakeProvider, ranges_around, write_statement  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from statement_tracker.core.calculator import buys_by_ticker  # noqa: E402
from statement_tracker.core.errors import UserFacingError  # noqa: E402
from statement_tracker.core.parser import load_statement  # noqa: E402
from statement_tracker.settings import Settings  # noqa: E402
from statement_tracker.ui import theme  # noqa: E402
from statement_tracker.ui.dialogs import ChooseListingDialog  # noqa: E402
from statement_tracker.ui.main_window import (  # noqa: E402
    MAX_SCREEN_SHARE,
    NO_SPREADSHEET,
    MainWindow,
    default_start_folder,
)

EQQB_BUYS = buys_by_ticker(load_statement(SAMPLE))["EQQB"]
TODAY = date(2026, 10, 12)


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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

        gain = window.table.item(0, 3)  # 589 now against 541 invested
        assert gain.text().startswith("▲ +")
        assert gain.foreground().color().name().upper() == theme.DARK.good.upper()
        assert window.status_label.property("state") == "ok"
        assert window.go_button.objectName() == "primary"
    finally:
        app.setStyleSheet("")


def cells(window: MainWindow) -> list[list[str]]:
    table = window.table
    return [[table.item(row, column).text() for column in range(5)] for row in range(table.rowCount())]


def test_button_is_disabled_until_a_statement_is_chosen(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))

    assert not window.go_button.isEnabled()
    assert window.spreadsheet_label.text() == NO_SPREADSHEET
    assert window.go_button.text() == "Step 3: show my investments"

    window.set_statement(SAMPLE)

    assert window.go_button.isEnabled()
    assert shows(window.statement_label, SAMPLE)


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


def test_window_starts_compact_and_grows_to_show_the_result(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    window.show()
    app.processEvents()
    start_height = window.height()
    assert start_height < 600  # just the three steps, no reserved empty space
    assert window.table.isHidden()

    window.set_statement(SAMPLE)
    run(app, window)

    assert window.height() > start_height
    assert not window.table.isHidden()

    # A size the user chose by hand is never reduced by a later run.
    window.resize(window.width(), window.height() + 150)
    chosen = window.height()
    run(app, window)
    assert window.height() == chosen
    window.close()


def test_window_stops_growing_at_a_share_of_the_screen_and_the_table_scrolls(app, tmp_path: Path) -> None:
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
    app.processEvents()

    window.set_statement(write_statement(tmp_path, *lines))
    run(app, window)

    table = window.table
    assert table.rowCount() == 21  # twenty investments and the total
    row, header = table.rowHeight(0), table.horizontalHeader().height()
    limit = int(window.screen().availableGeometry().height() * MAX_SCREEN_SHARE)
    assert MAX_SCREEN_SHARE == 0.8
    # Never taller than 80% of the screen, unless the screen is too small for even two rows.
    assert window.height() <= max(limit, window.minimumSizeHint().height())
    assert table.height() < header + table.rowCount() * row  # the rest is reached by scrolling
    window.close()


def test_statement_alone_shows_the_investments(app, tmp_path: Path) -> None:
    window, errors = make_window(tmp_path, provider_with("EQQB.DE"))
    window.set_statement(SAMPLE)

    run(app, window)

    assert errors == []
    rows = cells(window)
    assert rows[0][0] == "(EQQB) Nasdaq fund"
    assert "541" in rows[0][1] and "EUR" in rows[0][1]
    assert "589" in rows[0][2]
    assert rows[0][3].startswith("▲ +47") and "(+8" in rows[0][3]  # 589.31 against 541.49
    assert rows[0][2][0].isdigit()  # the value itself carries no arrow
    assert rows[0][4].startswith("100")
    assert rows[1][0] == "Total"
    assert window.status_label.text() == "Done. Your investments are shown below."
    assert "EQQB was matched to EQQB.DE" in window.notes_label.text()
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

    assert cells(window)[0][2] == "unavailable"
    assert window.table.horizontalHeaderItem(4).text() == "Share of total invested"


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
        attempts.append(target)
        if len(attempts) <= 2:
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


def test_progress_bar_counts_each_investment_and_the_spreadsheet(app, tmp_path: Path) -> None:
    window, _ = make_window(tmp_path, provider_with("EQQB.DE"))
    seen: list[tuple[int, int, str]] = []
    window.progressed.connect(lambda done, total, text: seen.append((done, total, text)))
    window.set_statement(SAMPLE)
    window.set_spreadsheet(tmp_path / "mine.xlsx")
    assert window.progress_bar.isHidden()

    run(app, window)

    assert seen[0] == (0, 0, "Reading your statement...")  # total not known yet: a moving bar
    # One investment plus the spreadsheet: two steps in total.
    assert (0, 2, "Getting the current price of EQQB (1 of 1)...") in seen
    assert seen[-1] == (1, 2, "Updating your spreadsheet...")
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
