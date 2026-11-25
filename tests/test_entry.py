"""The app's start: what it tells the Windows installer while it is open."""

import sys

import pytest
from quick_driver import app  # noqa: F401

from statement_tracker import __main__ as entry
from statement_tracker.__main__ import RUNNING_MUTEX, mark_running


@pytest.mark.skipif(sys.platform != "win32", reason="the installer and its mutex are Windows only")
def test_the_installer_can_tell_the_app_is_open() -> None:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    synchronize = 0x00100000
    handle = mark_running()
    try:
        assert handle
        # What Inno Setup's AppMutex does: open the mutex by name.
        found = kernel32.OpenMutexW(synchronize, False, RUNNING_MUTEX)
        assert found
        kernel32.CloseHandle(found)
    finally:
        kernel32.CloseHandle(handle)


@pytest.mark.skipif(sys.platform == "win32", reason="checks the other systems")
def test_nothing_is_marked_on_other_systems() -> None:
    assert mark_running() is None


def test_the_entry_written_for_sign_in_opens_the_window_minimized(monkeypatch: pytest.MonkeyPatch) -> None:
    # Spec F12: the startup entries run the app with --minimized.
    started = []
    monkeypatch.setattr(entry, "_run_gui", lambda minimized=False: started.append(minimized) or 0)

    assert entry.main(["--minimized"]) == 0
    assert entry.main([]) == 0

    assert started == [True, False]


def test_a_second_copy_shows_the_first_and_closes(app, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Spec F12: opening the app while it is open shows the window that is open; no second window.
    from quick_driver import wait_until

    from statement_tracker.gui.one_window import OneWindow, window_name

    monkeypatch.setattr("statement_tracker.settings.default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr("statement_tracker.gui.app.AppWindow", None)  # a second window would fail here
    first = OneWindow(window_name(tmp_path / "settings.json"))
    assert first.claim()
    wanted = []
    first.showWanted.connect(lambda: wanted.append(True))
    try:
        assert entry._run_gui() == 0

        wait_until(app, lambda: wanted == [True])
    finally:
        first.release()
