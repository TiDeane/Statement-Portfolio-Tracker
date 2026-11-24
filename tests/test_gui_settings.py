"""The Settings page, Help, the keyboard and the themes of the new window. Rule numbers refer to
tests/SPECIFICATION.md."""

from decimal import Decimal
from pathlib import Path

from fakes import SAMPLE
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from quick_driver import (  # noqa: F401
    app,
    click,
    close_windows_afterwards,
    find,
    open_app,
    press,
    provider_with,
    rows,
    settle,
    shows,
    texts,
    type_text,
    wait_until,
    when_a_dialog_opens,
)
from test_gui_values import bond_without_a_price

from statement_tracker import __version__
from statement_tracker.gui.theme import DARK, LIGHT
from statement_tracker.kept_statement import find_kept_statement
from statement_tracker.price_cache import PriceCache
from statement_tracker.settings import Settings


def home(app, tmp_path: Path, **options):
    shell = open_app(tmp_path, provider_with("EQQB.DE"), kept=SAMPLE, **options)
    wait_until(app, lambda: not shell.session.home.property("busy"))
    return shell


def to_settings(shell) -> None:
    click(find(shell.window, "Settings"))


def saved(tmp_path: Path) -> Settings:
    return Settings.load(tmp_path / "settings.json")


def from_menu(shell, investment: str, item: str) -> None:
    click(find(shell.window, f"More for {investment}"))
    click(find(shell.window, item))


def test_settings_lists_each_investment_with_its_listing_and_status(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path)
    to_settings(shell)

    assert shows(shell.window, "Settings", "Your investments", "Nasdaq fund", "EQQB · EQQB.DE, XETRA, EUR")
    assert shows(shell.window, "Matched automatically", "Take the first listing without asking")
    assert shows(shell.window, "Your statement", "Your spreadsheet", "About and privacy", f"Version {__version__}")


def test_with_nothing_kept_the_list_says_why(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = open_app(tmp_path, provider_with())
    shell.session.goTo("settings")
    settle(app)

    assert shows(shell.window, "No investments are remembered yet. They appear here after your first run.")
    assert shows(shell.window, "No statement is kept.")


def test_rename_choose_again_and_forget_from_the_menu(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path)
    to_settings(shell)

    from_menu(shell, "Nasdaq fund", "Rename")
    type_text(shell.window, "Tech fund")
    press(shell.window, Qt.Key.Key_Return)
    assert saved(tmp_path).index_names == {"EQQB": "Tech fund"} and shows(shell.window, "Tech fund")

    from_menu(shell, "Tech fund", "Choose the listing next time")
    assert saved(tmp_path).ask_again == {"EQQB"} and shows(shell.window, "Asks you next time")

    questions = []
    shell.session.confirm = lambda question, label: (questions.append(question), False)[1]
    from_menu(shell, "Tech fund", "Forget…")
    assert questions[0].startswith("Forget EQQB?") and "EQQB" in saved(tmp_path).ticker_choices

    shell.session.confirm = lambda question, label: True
    from_menu(shell, "Tech fund", "Forget…")
    assert saved(tmp_path).known_tickers() == []
    assert shows(shell.window, "No investments are remembered yet.")


def test_forget_all_keeps_the_spreadsheet_the_statement_and_the_prices(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    to_settings(shell)
    shell.session.confirm = lambda question, label: question.startswith("Forget your one investment?")

    click(find(shell.window, "Forget all investments…"))

    assert saved(tmp_path).known_tickers() == []
    assert saved(tmp_path).spreadsheet_path == tmp_path / "mine.xlsx"
    assert find_kept_statement(tmp_path / "settings.json") is not None
    assert PriceCache.beside(tmp_path / "settings.json").last_known("EQQB.DE", "EUR") is not None


def test_values_entered_are_listed_and_forgotten_too(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = bond_without_a_price(app, tmp_path)
    shell.session.ask_value = lambda choices, selected, currency: ("WXYZ", Decimal("204"))
    click(find(shell.window, "Enter its value…"))
    to_settings(shell)
    assert shows(shell.window, "value entered by you")

    shell.session.confirm = lambda question, label: True
    from_menu(shell, "Bond fund", "Forget…")

    assert PriceCache.beside(tmp_path / "settings.json").entered("WXYZ", "EUR") is None


def test_the_switch_and_the_backup_copies_are_saved_at_once(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    to_settings(shell)

    click(find(shell.window, "Take the first listing without asking"))
    assert saved(tmp_path).always_use_first_listing

    click(find(shell.window, "One more"))
    assert saved(tmp_path).backups_kept == 2  # one more than the default, 1
    for _ in range(6):
        click(find(shell.window, "One fewer"))
    assert saved(tmp_path).backups_kept == 0


def test_the_spreadsheet_can_be_changed_or_given_up(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    to_settings(shell)
    assert shows(shell.window, "mine.xlsx")
    opened = []
    shell.session.show_in_folder = opened.append
    click(find(shell.window, "Open folder"))
    assert opened == [tmp_path / "mine.xlsx"]

    shell.session.ask_open_file = lambda title, kinds, start: tmp_path / "other.xlsx"
    click(find(shell.window, "Choose another…"))
    assert saved(tmp_path).spreadsheet_path == tmp_path / "other.xlsx"

    click(find(shell.window, "Stop using it"))
    assert saved(tmp_path).spreadsheet_path is None
    assert shows(shell.window, "Choose spreadsheet…")


def test_forgetting_the_statement_goes_back_to_first_launch(app, tmp_path: Path) -> None:
    # Spec G1.
    shell = home(app, tmp_path)
    to_settings(shell)
    assert shows(shell.window, "Latest transaction")
    shell.session.confirm = lambda question, label: question.startswith("Forget your statement from last time?")

    click(find(shell.window, "Forget it…"))
    assert shows(shell.window, "No statement is kept.")
    assert find_kept_statement(tmp_path / "settings.json") is None

    click(find(shell.window, "Your portfolio"))
    assert shows(shell.window, "Let's see how your investments are doing")


def test_changes_in_settings_show_on_home_at_once_and_can_be_undone(app, tmp_path: Path) -> None:
    # Spec G1, F10.
    shell = home(app, tmp_path)
    to_settings(shell)
    from_menu(shell, "Nasdaq fund", "Rename")
    type_text(shell.window, "Tech fund")
    press(shell.window, Qt.Key.Key_Return)

    click(find(shell.window, "Your portfolio"))
    assert rows(shell.window)[0][0] == "Tech fund"

    press(shell.window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert rows(shell.window)[0][0] == "Nasdaq fund"


def test_help_gives_the_revolut_steps_the_privacy_and_the_version(app, tmp_path: Path) -> None:
    # Spec F11.
    shell = home(app, tmp_path, real_dialogs=True)
    seen = []

    def read() -> None:
        seen.append(shows(shell.window, "Where do I get my statement?", "All time", "Yahoo Finance", __version__))
        press(shell.window, Qt.Key.Key_Escape)

    when_a_dialog_opens(shell, read)
    click(find(shell.window, "Help"))

    assert seen == [True]


def test_tab_reaches_every_button(app, tmp_path: Path) -> None:
    # Spec F11: keyboard navigable.
    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    for page in ("home", "settings"):
        shell.session.goTo(page)
        settle(app)
        buttons = {item for item in buttons_shown(shell.window)}
        reached = set()
        for _ in range(80):
            press(shell.window, Qt.Key.Key_Tab)
            reached.add(shell.window.activeFocusItem())
        missed = [item.property("text") for item in buttons if item not in reached]
        assert missed == [], f"on {page}, Tab never reaches {missed}"


def buttons_shown(window):
    from quick_driver import _items, _shown

    return [item for item in _items(window) if _shown(item) and item.property("enabled") and item.inherits("QQuickAbstractButton")]


def test_the_theme_follows_the_system_while_the_app_is_open(app, tmp_path: Path) -> None:
    # Spec F11.
    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    update = find(shell.window, "Update my spreadsheet")

    shell.theme.set_dark(False)
    settle(app)
    assert update.property("background").property("color").name().upper() == LIGHT["accent"]
    shell.theme.set_dark(True)
    settle(app)
    assert update.property("background").property("color").name().upper() == DARK["accent"]


def test_the_window_shows_the_apps_icon(app, tmp_path: Path) -> None:
    # Spec F11.
    shell = open_app(tmp_path, provider_with())

    assert not shell.window.icon().isNull()
    assert not QGuiApplication.windowIcon().isNull() or not shell.window.icon().isNull()


def test_the_program_the_installer_and_the_mac_app_use_the_same_icon_as_the_window() -> None:
    # Spec F11: made together by packaging/make_icon.py, and named where the app is built.
    from PySide6.QtGui import QImageReader

    root = Path(__file__).resolve().parents[1]
    icons = root / "packaging" / "icon"
    assert (icons / "app.png").read_bytes() == (root / "src" / "statement_tracker" / "gui" / "icon.png").read_bytes()
    reader = QImageReader(str(icons / "app.ico"))
    sizes = set()
    for number in range(reader.imageCount()):
        reader.jumpToImage(number)
        sizes.add(reader.read().width())
    assert {16, 32, 48, 256} <= sizes  # small enough for a title bar, big enough for Explorer
    assert (icons / "app.icns").read_bytes()[:4] == b"icns"
    spec = (root / "packaging" / "statement_tracker.spec").read_text(encoding="utf-8")
    assert '"app.icns"' in spec and '"app.ico"' in spec and "WINDOW_ICON" in spec
    assert "SetupIconFile=icon\\app.ico" in (root / "packaging" / "windows_installer.iss").read_text(encoding="utf-8")


def test_settings_cannot_be_opened_while_prices_are_fetched(app, tmp_path: Path) -> None:
    # Spec G1: a fetch reads and saves the same settings.
    from test_gui_home import slow_eqqb

    provider = slow_eqqb()
    shell = open_app(tmp_path, provider, kept=SAMPLE)
    wait_until(app, lambda: shows(shell.window, "current prices"))

    assert not find(shell.window, "Settings").isEnabled()

    provider.let_go.set()
    wait_until(app, lambda: not shell.session.home.property("busy"))
    assert find(shell.window, "Settings").isEnabled()


def test_forgetting_the_statement_starts_first_launch_afresh(app, tmp_path: Path) -> None:
    # Spec F2.
    shell = open_app(tmp_path, provider_with("EQQB.DE"))
    from quick_driver import drop

    drop(shell.window, SAMPLE)
    click(find(shell.window, "Continue"))
    click(find(shell.window, "Not now"))
    click(find(shell.window, "Show my investments"))
    wait_until(app, lambda: not shell.session.home.property("busy"))
    to_settings(shell)
    shell.session.confirm = lambda question, label: True

    click(find(shell.window, "Forget it…"))
    click(find(shell.window, "Your portfolio"))

    assert shows(shell.window, "Step 1 of 2", "Drop your Revolut statement here")
    assert not find(shell.window, "Continue").isEnabled()


def chapters(window) -> dict:
    """The side menu's chapters, by name, from top to bottom."""
    from PySide6.QtCore import QPointF

    from quick_driver import _items, _shown

    shown = [item for item in _items(window) if item.objectName() == "chapter" and _shown(item)]
    shown.sort(key=lambda item: item.mapToScene(QPointF(0, 0)).y())
    return {item.property("text"): item for item in shown}


def current_chapter(window) -> str:
    return next(name for name, item in chapters(window).items() if item.property("current"))


def test_the_chapters_stay_in_place_mark_the_one_being_read_and_scroll_to_theirs(app, tmp_path: Path) -> None:
    # Spec G1.
    from PySide6.QtCore import QPointF

    from quick_driver import scroll_to

    shell = home(app, tmp_path, spreadsheet=tmp_path / "mine.xlsx")
    to_settings(shell)
    shown = chapters(shell.window)
    assert list(shown) == ["Your investments", "Your statement", "Your spreadsheet", "Appearance", "About and privacy"]
    assert current_chapter(shell.window) == "Your investments"
    where = shown["Your investments"].mapToScene(QPointF(0, 0))

    scroll_to(find(shell.window, "New versions"))  # read down to the end of the page
    wait_until(app, lambda: current_chapter(shell.window) == "About and privacy")
    assert chapters(shell.window)["Your investments"].mapToScene(QPointF(0, 0)) == where  # it stayed in place

    click(chapters(shell.window)["Your spreadsheet"])
    wait_until(app, lambda: current_chapter(shell.window) == "Your spreadsheet")
    assert shows(shell.window, "Backup copies to keep")


def test_appearance_can_be_light_or_dark_and_is_remembered(app, tmp_path: Path) -> None:
    # Spec G1, F11.
    shell = home(app, tmp_path)
    to_settings(shell)
    assert find(shell.window, "Use device theme").property("checked")

    click(find(shell.window, "Dark"))
    assert shell.window.property("color").name().upper() == DARK["bg"]
    assert saved(tmp_path).appearance == "dark"

    click(find(shell.window, "Light"))
    assert shell.window.property("color").name().upper() == LIGHT["bg"]

    again = open_app(tmp_path, provider_with())
    assert again.window.property("color").name().upper() == LIGHT["bg"] and saved(tmp_path).appearance == "light"


def test_a_new_spreadsheet_made_in_settings_is_created_back_on_home(app, tmp_path: Path) -> None:
    # Spec G1, F7: Settings waits for no writing; the spreadsheet is created once Home shows again.
    shell = home(app, tmp_path)
    to_settings(shell)
    suggested = []
    shell.session.ask_save_file = lambda title, start: (suggested.append(start.name), tmp_path / "new")[1]

    click(find(shell.window, "Create a new one…"))
    assert suggested == ["investments_2026-10-12.xlsx"]  # today's date
    assert not (tmp_path / "new.xlsx").exists()
    click(find(shell.window, "Your portfolio"))

    wait_until(app, lambda: (tmp_path / "new.xlsx").exists() and not shell.session.home.property("writing"))
    assert shows(shell.window, "Your spreadsheet was created")


def test_the_frame_qt_draws_around_the_window_takes_the_apps_colours(app, tmp_path: Path) -> None:
    # Spec F11: on Linux, Qt draws the window's title bar and frame itself, in the application's colours.
    from PySide6.QtGui import QColor, QPalette

    def frame() -> tuple[str, str]:
        palette = QGuiApplication.palette()
        return (palette.color(QPalette.ColorRole.Window).name().upper(),
                palette.color(QPalette.ColorRole.WindowText).name().upper())

    original = QGuiApplication.palette()
    try:
        shell = home(app, tmp_path)
        to_settings(shell)
        for look, colours in (("Dark", DARK), ("Light", LIGHT), ("Dark", DARK)):
            click(find(shell.window, look))
            assert frame() == (colours["bg"], colours["text"])

        QGuiApplication.setPalette(QPalette(QColor("#EFEFEF")))  # a light computer
        again = open_app(tmp_path, provider_with())
        assert again.window.property("color").name().upper() == DARK["bg"]
        assert frame() == (DARK["bg"], DARK["text"])  # from the start, not only after a change
    finally:
        QGuiApplication.setPalette(original)


def test_the_investment_menu_is_drawn_in_the_apps_colours_under_its_button(app, tmp_path: Path) -> None:
    # Spec G1.
    from PySide6.QtCore import QPointF

    shell = home(app, tmp_path)
    to_settings(shell)
    for look, colours in (("Dark", DARK), ("Light", LIGHT)):
        click(find(shell.window, look))
        button = find(shell.window, "More for Nasdaq fund")
        click(button)
        rename = find(shell.window, "Rename")
        inside = rename.mapToScene(QPointF(3, rename.height() / 2))
        ratio = shell.window.devicePixelRatio()

        def colour_inside() -> str:
            picture = shell.window.grabWindow()
            return picture.pixelColor(int(inside.x() * ratio), int(inside.y() * ratio)).name().upper()

        wait_until(app, lambda: colour_inside() == colours["surface"], 2)  # once it has faded in
        menu_right = rename.mapToScene(QPointF(rename.width(), 0)).x()
        assert menu_right <= button.mapToScene(QPointF(button.width(), 0)).x() + 8  # not past its button
        press(shell.window, Qt.Key.Key_Escape)
        assert not shows(shell.window, "Rename")


def test_settings_names_the_statement_file(app, tmp_path: Path) -> None:
    # Spec G1, F6.
    from test_gui_home import newer_statement

    from quick_driver import drop

    shell = home(app, tmp_path)
    newer = newer_statement(tmp_path)
    drop(shell.window, newer)
    wait_until(app, lambda: not shell.session.busy)
    to_settings(shell)

    assert shows(shell.window, "newer.csv", f"In {newer.parent.resolve()}")
