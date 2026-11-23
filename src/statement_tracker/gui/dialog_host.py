"""Asking the user something in a QML dialog and waiting for the answer, as a modal dialog does."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QEventLoop, QObject, Signal, Slot


class DialogHost(QObject):
    """Opens one QML dialog at a time and waits for it to be answered.

    ``ask`` emits ``opened`` (the window shows the dialog named by ``kind``, filled from ``data``),
    then runs an event loop until QML calls ``answer`` or ``cancel``, as ``QDialog.exec`` would.
    Exposed to QML as ``dialogs``.
    """

    opened = Signal(str, "QVariantMap")
    openChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop: QEventLoop | None = None
        self._result: dict[str, Any] | None = None
        self._waiting = False
        """A dialog is shown and not answered yet."""

    def _is_open(self) -> bool:
        return self._waiting

    isOpen = Property(bool, _is_open, notify=openChanged)

    def ask(self, kind: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Show the dialog ``kind`` and return its answer, or None if it was cancelled or the window closed."""
        if self._loop is not None:
            raise RuntimeError("A dialog is already open.")
        self._result = None
        self._loop = QEventLoop()
        self._waiting = True
        self.openChanged.emit()
        self.opened.emit(kind, data)
        self._loop.exec()
        self._loop = None
        return self._result

    @Slot("QVariantMap")
    def answer(self, result: dict[str, Any]) -> None:
        """The dialog was answered (called from QML)."""
        self._result = dict(result)
        self._finish()

    @Slot()
    def cancel(self) -> None:
        """The dialog was cancelled or closed, or the window is closing."""
        self._result = None
        self._finish()

    def _finish(self) -> None:
        if self._waiting:
            self._waiting = False
            self.openChanged.emit()
        if self._loop is not None:
            self._loop.quit()
