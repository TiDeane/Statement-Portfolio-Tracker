"""Running slow work (file reading, price fetching) off the window's thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, Signal


class TaskSignals(QObject):
    """Results of a background task, delivered on the window's thread."""

    finished = Signal(object)
    failed = Signal(object)


class Task(QRunnable):
    """Run a callable on the thread pool; report its result or its exception."""

    def __init__(self, work: Callable[[], object]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self._work = work
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self._work()
        except Exception as exc:  # handed to the window, which explains it to the user
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


class QuestionBridge(QObject):
    """Lets background work ask the user a question and wait for the answer.

    ``ask`` runs on the window's thread (it may open a dialog); ``__call__`` is
    what the background work calls.
    """

    # Both as plain objects: a signal declared with ``list`` would hand the slot a copy,
    # and the answer written into it would be lost.
    _asked = Signal(object, object)

    def __init__(self, ask: Callable[[object], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ask = ask
        self._asked.connect(self._answer, Qt.ConnectionType.BlockingQueuedConnection)

    def _answer(self, question: object, holder: list) -> None:
        holder.append(self._ask(question))

    def __call__(self, question: object) -> object:
        holder: list = []
        self._asked.emit(question, holder)
        return holder[0] if holder else None
