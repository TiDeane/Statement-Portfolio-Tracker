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
        self._open: dict[str, Any] | None = None
        """The dialog shown and not answered yet: its own wait loop and, once answered, its answer."""

    def _is_open(self) -> bool:
        return self._open is not None

    isOpen = Property(bool, _is_open, notify=openChanged)

    def ask(self, kind: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Show the dialog ``kind`` and return its answer, or None if it was cancelled or the window closed.

        One dialog at a time: asked while another is open (a fetch's question while Help is shown, say),
        it waits for that one to close first, so nothing is lost."""
        while self._open is not None:
            waiting = QEventLoop()
            self.openChanged.connect(waiting.quit)
            waiting.exec()
            self.openChanged.disconnect(waiting.quit)
        shown: dict[str, Any] = {"loop": QEventLoop(), "answer": None}
        self._open = shown
        self.openChanged.emit()
        self.opened.emit(kind, data)
        if self._open is shown:  # not answered at once
            shown["loop"].exec()
        return shown["answer"]

    @Slot("QVariantMap")
    def answer(self, result: dict[str, Any]) -> None:
        """The dialog was answered. Once a question is settled, a later answer or cancel changes nothing
        (a dialog closing after being answered cancels, too late)."""
        self._finish(dict(result))

    @Slot()
    def cancel(self) -> None:
        """The dialog was cancelled or closed, or the window is closing."""
        self._finish(None)

    def _finish(self, answer: dict[str, Any] | None) -> None:
        shown = self._open
        if shown is None:
            return
        shown["answer"] = answer
        self._open = None
        shown["loop"].quit()
        self.openChanged.emit()
