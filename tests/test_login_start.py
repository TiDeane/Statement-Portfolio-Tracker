"""The entry that opens the app when the user signs in, on each system. Rule numbers refer to tests/SPECIFICATION.md.

Never the real one: entries are written to pytest's folders, and the Windows registry is a dictionary.
"""

import plistlib
from pathlib import Path

from statement_tracker.login_start import (
    APPROVED_KEY,
    ENTRY_NAME,
    MAC_LABEL,
    MOVE_TO_APPLICATIONS,
    NOT_INSTALLED,
    RUN_KEY,
    LinuxAutostart,
    MacLaunchAgent,
    WindowsRun,
    login_start,
)

LINUX_APP = "/opt/Statement Tracker/StatementPortfolioTracker"
MAC_APP = "/Applications/Statement Portfolio Tracker.app/Contents/MacOS/StatementPortfolioTracker"
WINDOWS_APP = r"C:\Users\Ana\AppData\Local\Programs\Statement Portfolio Tracker\StatementPortfolioTracker.exe"


class FakeRegistry:
    """The current user's part of the Windows registry, as a dictionary."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str | bytes] = {}

    def get(self, key: str, name: str) -> str | bytes | None:
        return self.values.get((key, name))

    def set_text(self, key: str, name: str, value: str) -> None:
        self.values[(key, name)] = value

    def delete(self, key: str, name: str) -> None:
        self.values.pop((key, name), None)


def test_on_linux_an_autostart_entry_opens_the_app_minimized(tmp_path: Path) -> None:
    # Spec F12: the freedesktop autostart folder, created if missing; the path quoted, for its spaces.
    folder = tmp_path / "config" / "autostart"
    entry = LinuxAutostart([LINUX_APP, "--minimized"], folder)
    assert not entry.is_on()

    entry.turn_on()

    lines = (folder / "statement-portfolio-tracker.desktop").read_text(encoding="utf-8").splitlines()
    assert "[Desktop Entry]" in lines
    assert "Type=Application" in lines
    assert "Name=Statement Portfolio Tracker" in lines
    assert f'Exec="{LINUX_APP}" --minimized' in lines
    assert entry.is_on()

    entry.turn_off()

    assert not (folder / "statement-portfolio-tracker.desktop").exists()
    assert not entry.is_on()
    entry.turn_off()  # already off: nothing to do


def test_on_linux_an_entry_the_desktop_hid_is_off_until_turned_on_again(tmp_path: Path) -> None:
    # Spec F12: desktops turn an autostart entry off with Hidden=true.
    folder = tmp_path / "autostart"
    folder.mkdir()
    (folder / "statement-portfolio-tracker.desktop").write_text(
        f'[Desktop Entry]\nType=Application\nName=Statement Portfolio Tracker\nExec="{LINUX_APP}" --minimized\nHidden=true\n',
        encoding="utf-8",
    )
    entry = LinuxAutostart([LINUX_APP, "--minimized"], folder)
    assert not entry.is_on()

    entry.turn_on()

    assert entry.is_on()
    assert "Hidden=true" not in (folder / "statement-portfolio-tracker.desktop").read_text(encoding="utf-8")


def test_on_a_mac_a_launch_agent_opens_the_app_minimized(tmp_path: Path) -> None:
    # Spec F12.
    folder = tmp_path / "Library" / "LaunchAgents"
    entry = MacLaunchAgent([MAC_APP, "--minimized"], folder)
    assert not entry.is_on()

    entry.turn_on()

    with (folder / f"{MAC_LABEL}.plist").open("rb") as file:
        agent = plistlib.load(file)
    assert agent["Label"] == "io.github.tideane.statementportfoliotracker"
    assert agent["ProgramArguments"] == [MAC_APP, "--minimized"]
    assert agent["RunAtLoad"] is True
    assert entry.is_on()

    entry.turn_off()

    assert not (folder / f"{MAC_LABEL}.plist").exists()
    assert not entry.is_on()


def test_on_windows_a_run_value_opens_the_app_minimized() -> None:
    # Spec F12: the current user's Run key; the path quoted, for its spaces.
    registry = FakeRegistry()
    entry = WindowsRun([WINDOWS_APP, "--minimized"], registry)
    assert not entry.is_on()

    entry.turn_on()

    assert ENTRY_NAME == "StatementPortfolioTracker"
    assert RUN_KEY == r"Software\Microsoft\Windows\CurrentVersion\Run"
    assert registry.get(RUN_KEY, ENTRY_NAME) == f'"{WINDOWS_APP}" --minimized'
    assert entry.is_on()

    entry.turn_off()

    assert registry.values == {}
    assert not entry.is_on()


def test_on_windows_an_entry_turned_off_in_startup_apps_is_off_until_turned_on_again() -> None:
    # Spec F12: Task Manager and Settings > Apps > Startup turn it off beside the Run value.
    registry = FakeRegistry()
    entry = WindowsRun([WINDOWS_APP, "--minimized"], registry)
    entry.turn_on()
    registry.values[(APPROVED_KEY, ENTRY_NAME)] = bytes([3]) + bytes(11)
    assert APPROVED_KEY == r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
    assert not entry.is_on()

    entry.turn_on()

    assert entry.is_on()
    assert registry.get(APPROVED_KEY, ENTRY_NAME) is None

    registry.values[(APPROVED_KEY, ENTRY_NAME)] = bytes([2]) + bytes(11)  # turned on there
    assert entry.is_on()
    registry.values[(APPROVED_KEY, ENTRY_NAME)] = bytes([6]) + bytes(11)  # also on: an odd first byte is off
    assert entry.is_on()
    registry.values[(APPROVED_KEY, ENTRY_NAME)] = bytes([7]) + bytes(11)
    assert not entry.is_on()

    entry.turn_off()

    assert registry.values == {}


def test_run_from_the_source_the_app_cannot_open_by_itself(tmp_path: Path) -> None:
    # Spec G1, F12: only the installed app, so a copy run from the source code never starts by itself.
    for platform, system in [("win32", "windows"), ("darwin", "mac"), ("linux", "linux")]:
        entry = login_start(platform=platform, frozen=False, executable="/usr/bin/python3", home=tmp_path, environ={})

        assert entry.system == system
        assert entry.unavailable == NOT_INSTALLED == "Only the installed app can open by itself."
        assert not entry.is_on()


def test_a_mac_app_not_moved_to_applications_cannot_open_by_itself(tmp_path: Path) -> None:
    # Spec G1, F12: macOS runs an app left in Downloads from a random folder, and one in the disk image goes.
    for executable in [
        "/private/var/folders/x1/T/AppTranslocation/0A1B/d/Statement Portfolio Tracker.app/Contents/MacOS/StatementPortfolioTracker",
        "/Volumes/Statement Portfolio Tracker/Statement Portfolio Tracker.app/Contents/MacOS/StatementPortfolioTracker",
    ]:
        entry = login_start(platform="darwin", frozen=True, executable=executable, home=tmp_path, environ={})

        assert entry.unavailable == MOVE_TO_APPLICATIONS == "Move the app to Applications first."
        assert not entry.is_on()


def test_the_installed_app_writes_its_entry_where_each_system_looks(tmp_path: Path) -> None:
    # Spec F12.
    linux = login_start(platform="linux", frozen=True, executable=LINUX_APP, home=tmp_path, environ={})
    linux.turn_on()
    assert (tmp_path / ".config" / "autostart" / "statement-portfolio-tracker.desktop").exists()
    assert (linux.system, linux.unavailable) == ("linux", "")

    elsewhere = tmp_path / "xdg"
    login_start(platform="linux", frozen=True, executable=LINUX_APP, home=tmp_path, environ={"XDG_CONFIG_HOME": str(elsewhere)}).turn_on()
    assert (elsewhere / "autostart" / "statement-portfolio-tracker.desktop").exists()

    mac = login_start(platform="darwin", frozen=True, executable=MAC_APP, home=tmp_path, environ={})
    mac.turn_on()
    with (tmp_path / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist").open("rb") as file:
        assert plistlib.load(file)["ProgramArguments"] == [MAC_APP, "--minimized"]
    assert (mac.system, mac.unavailable) == ("mac", "")

    windows = login_start(platform="win32", frozen=True, executable=WINDOWS_APP, home=tmp_path, environ={}, registry=FakeRegistry())
    windows.turn_on()
    assert windows.is_on()
    assert (windows.system, windows.unavailable) == ("windows", "")
