"""Shared for every test: no test may reach the network (Spec J3), and none depends on the computer's own
language and region settings."""

import socket

import pytest

NO_NETWORK = "Tests must not use the network: blocked in tests/conftest.py."


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every attempt to look up or connect to an address fail, as if the computer were offline.
    A test that fakes the network itself (as the Yahoo provider's tests do) replaces these again."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(NO_NETWORK)

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


@pytest.fixture(autouse=True, scope="session")
def the_same_number_formats_on_every_computer():
    """Write numbers and dates the same way whatever the computer is set to ("1000.00", not "1000,00" on a
    Portuguese Windows): Qt's neutral C locale, as on Linux. Tests of a particular locale set their own."""
    try:
        from PySide6.QtCore import QLocale
    except ImportError:
        yield
        return
    before = QLocale()
    QLocale.setDefault(QLocale.c())
    yield
    QLocale.setDefault(before)
