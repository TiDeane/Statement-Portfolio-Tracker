"""Opening the app when the user signs in to the computer: the entry each system reads at sign-in.

The entry itself is the truth: nothing about it is kept in the settings, so turning it off in the system's
own list (Windows' Startup apps, say) shows as off in the app. The app opens minimized from it
(``--minimized``). Only the installed app makes one: a copy run from the source code would start Python.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from statement_tracker import APP_NAME, BUNDLE_ID

MINIMIZED = "--minimized"
"""On the app's command line: open minimized, as at sign-in."""
ENTRY_NAME = "StatementPortfolioTracker"
"""The Windows Run value's name. The uninstaller removes it: must match packaging/windows_installer.iss."""
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
"""Where Windows' Startup apps (Task Manager, Settings) mark a Run entry turned on or off."""
MAC_LABEL = BUNDLE_ID
"""The launch agent's label and file name."""
LINUX_FILE = "statement-portfolio-tracker.desktop"

NOT_INSTALLED = "Only the installed app can open by itself."
MOVE_TO_APPLICATIONS = "Move the app to Applications first."


class LoginStart:
    """The entry that opens the app at sign-in, on one system."""

    system = ""
    """"windows", "mac" or "linux"."""
    unavailable = ""
    """Why it cannot be turned on, or "" when it can."""

    def is_on(self) -> bool:
        """True if the app opens when the user signs in. Never raises: an entry that cannot be read is off."""
        raise NotImplementedError

    def turn_on(self) -> None:
        """Make the app open at sign-in, from where it is now: an entry that opens it from elsewhere (the app was
        moved) is written again; one already right is left as it is.

        Raises OSError if the entry cannot be written."""
        raise NotImplementedError

    def turn_off(self) -> None:
        """Stop the app from opening at sign-in. Raises OSError if the entry cannot be removed."""
        raise NotImplementedError


class Unavailable(LoginStart):
    """The app cannot open by itself here, for ``reason``."""

    def __init__(self, system: str, reason: str) -> None:
        self.system, self.unavailable = system, reason

    def is_on(self) -> bool:
        return False

    def turn_on(self) -> None:
        pass

    def turn_off(self) -> None:
        pass


class Registry(Protocol):
    """The current user's part of the Windows registry: string values, and the Startup apps' binary ones."""

    def get(self, key: str, name: str) -> str | bytes | None:
        """The value, or None if it is not there or cannot be read."""

    def set_text(self, key: str, name: str, value: str) -> None: ...

    def delete(self, key: str, name: str) -> None:
        """Remove the value; one that is not there is fine."""


class WinRegistry:
    """The real one, through Python's ``winreg`` (``HKEY_CURRENT_USER``)."""

    def get(self, key: str, name: str) -> str | bytes | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                value, _kind = winreg.QueryValueEx(handle, name)
        except OSError:  # not there, or not readable
            return None
        return value

    def set_text(self, key: str, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

    def delete(self, key: str, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            pass


class WindowsRun(LoginStart):
    """A value in the current user's Run key, which Windows' Startup apps can turn off beside it."""

    system = "windows"

    def __init__(self, command: list[str], registry: Registry) -> None:
        self._command, self._registry = command, registry

    def is_on(self) -> bool:
        return isinstance(self._registry.get(RUN_KEY, ENTRY_NAME), str) and not self._turned_off_in_startup_apps()

    def turn_on(self) -> None:
        command = subprocess.list2cmdline(self._command)
        if self._registry.get(RUN_KEY, ENTRY_NAME) != command:
            self._registry.set_text(RUN_KEY, ENTRY_NAME, command)
        if self._turned_off_in_startup_apps():
            self._registry.delete(APPROVED_KEY, ENTRY_NAME)  # on again there too

    def _turned_off_in_startup_apps(self) -> bool:
        # Windows writes an even first byte (02, 06) for an entry turned on there, an odd one (03, 07) and when
        # for one turned off.
        approved = self._registry.get(APPROVED_KEY, ENTRY_NAME)
        return isinstance(approved, bytes) and len(approved) > 0 and approved[0] % 2 == 1

    def turn_off(self) -> None:
        self._registry.delete(RUN_KEY, ENTRY_NAME)
        self._registry.delete(APPROVED_KEY, ENTRY_NAME)


class MacLaunchAgent(LoginStart):
    """A launch agent in the user's LaunchAgents folder, which macOS runs at log-in."""

    system = "mac"

    def __init__(self, command: list[str], folder: Path) -> None:
        self._command, self._file = command, folder / f"{MAC_LABEL}.plist"

    def is_on(self) -> bool:
        return os.path.exists(self._file)  # False, not an error, for a folder that cannot be read

    def turn_on(self) -> None:
        agent = {"Label": MAC_LABEL, "ProgramArguments": self._command, "RunAtLoad": True, "ProcessType": "Interactive"}
        _write_if_changed(self._file, plistlib.dumps(agent))

    def turn_off(self) -> None:
        self._file.unlink(missing_ok=True)


class LinuxAutostart(LoginStart):
    """A desktop entry in the freedesktop autostart folder, which desktops run at log-in."""

    system = "linux"

    def __init__(self, command: list[str], folder: Path) -> None:
        self._command, self._file = command, folder / LINUX_FILE

    def is_on(self) -> bool:
        try:
            lines = self._file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        return not any(line.replace(" ", "").lower() == "hidden=true" for line in lines)

    def turn_on(self) -> None:
        exec_line = " ".join(_desktop_argument(part) for part in self._command)
        entry = f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={exec_line}\nTerminal=false\n"
        _write_if_changed(self._file, entry.encode("utf-8"))

    def turn_off(self) -> None:
        self._file.unlink(missing_ok=True)


def _write_if_changed(file: Path, content: bytes) -> None:
    """Write ``content`` to ``file``, making its folder, unless the file holds it already."""
    try:
        if file.read_bytes() == content:
            return
    except OSError:
        pass  # not there yet, or not readable: written
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(content)


def _desktop_argument(argument: str) -> str:
    """One argument of a desktop entry's Exec line (freedesktop Desktop Entry Specification, "The Exec key")."""
    argument = argument.replace("%", "%%")
    if not any(character in argument for character in " \t\n\"'\\><~|&;$*?#()`"):
        return argument
    quoted = "".join("\\" + character if character in '"`$\\' else character for character in argument)
    return '"' + quoted.replace("\\", "\\\\") + '"'  # the value's own escaping, read before the Exec rules


_SYSTEMS = {"win32": "windows", "darwin": "mac"}


def login_start(
    *,
    platform: str | None = None,
    frozen: bool | None = None,
    executable: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    registry: Registry | None = None,
) -> LoginStart:
    """The entry for this computer and the app as it runs (each part can be given, for the tests)."""
    platform = sys.platform if platform is None else platform
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    executable = sys.executable if executable is None else executable
    home = Path.home() if home is None else home
    environ = os.environ if environ is None else environ
    system = _SYSTEMS.get(platform, "linux")
    if not frozen:
        return Unavailable(system, NOT_INSTALLED)
    command = [executable, MINIMIZED]
    if system == "windows":
        return WindowsRun(command, registry if registry is not None else WinRegistry())
    if system == "mac":
        if "/AppTranslocation/" in executable or executable.startswith("/Volumes/"):
            return Unavailable(system, MOVE_TO_APPLICATIONS)
        return MacLaunchAgent(command, home / "Library" / "LaunchAgents")
    config = Path(environ["XDG_CONFIG_HOME"]) if environ.get("XDG_CONFIG_HOME") else home / ".config"
    return LinuxAutostart(command, config / "autostart")
