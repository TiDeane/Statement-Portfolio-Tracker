"""Shared for every test: no test may reach the network (Spec J3)."""

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
