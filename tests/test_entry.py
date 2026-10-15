"""The app's start: what it tells the Windows installer while it is open."""

import sys

import pytest

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
