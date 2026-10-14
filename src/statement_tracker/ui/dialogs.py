"""The small dialogs: errors, choosing a listing, help and about."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from statement_tracker import APP_NAME, __version__
from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.ticker_resolver import Confidence, Resolution

RELEASES_URL = "https://github.com/TiDeane/revolut-investment-tracker/releases"

PRIVACY_TEXT = (
    "Everything happens on this computer. There are no accounts and nothing is recorded about how you "
    "use the app.\n\n"
    "The only information sent anywhere is the ticker symbols of your investments and dates, which go to "
    "Yahoo Finance to look up prices. Your amounts and your statement never leave this computer.\n\n"
    "This app is unofficial and is not affiliated with Revolut. It is not financial advice. Prices come "
    "from Yahoo Finance through an unofficial library, may be delayed or wrong, and are subject to "
    "Yahoo's terms."
)

WHERE_IS_THE_FILE_TEXT = (
    "You need the statement of your stock and ETF trades from the Revolut app, saved as a CSV file.\n\n"
    "In the Revolut app:\n"
    "1. Open the Invest tab.\n"
    "2. Tap More.\n"
    "3. Tap Documents.\n"
    "4. Tap Brokerage account.\n"
    "5. Tap Account statement.\n"
    "6. Choose CSV as the format.\n"
    "7. Choose the date range All time.\n\n"
    "The date range matters: the app needs your whole history, from your first trade until today. "
    "The other choices, a range of months or a tax year, list only the buys and sells inside that "
    "period, so they give wrong results or are rejected as incomplete.\n\n"
    "Revolut may move these menus in a newer version of its app. Once you have the file on this "
    "computer, choose it in step 1 or drag it onto the window."
)


ALWAYS_FIRST_TEXT = "Always choose the first option"
ALWAYS_FIRST_TIP = (
    "Use the first listing now, and from now on whenever the app cannot tell by itself, without asking. "
    "When the first one could not be checked against your purchases, a note says so. "
    "You can turn this off in Settings."
)


def show_error(parent: QWidget | None, error: UserFacingError, can_retry: bool = False) -> bool:
    """Explain a problem in plain language, with the technical details one click away.

    With ``can_retry`` the box also offers "Try again"; returns True if the user chose it.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(APP_NAME)
    box.setText(error.what_happened)
    box.setInformativeText(error.what_to_do)
    retry = None
    if can_retry:
        retry = box.addButton("Try again", QMessageBox.ButtonRole.AcceptRole)
        retry.setObjectName("primary")  # the coloured main action, styled in ui/theme.py
        retry.style().unpolish(retry)
        retry.style().polish(retry)
        box.setDefaultButton(retry)
    copy = box.addButton("Copy details", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Not now" if can_retry else "OK", QMessageBox.ButtonRole.RejectRole)
    while True:
        box.exec()
        if box.clickedButton() is not copy:
            break
        details = f"{APP_NAME} {__version__}\n{error.what_happened}\n{error.what_to_do}\n\n{error.details}"
        QGuiApplication.clipboard().setText(details)
        if not can_retry:
            break  # copying is the last thing to do here; with "Try again" on offer, ask again
    return retry is not None and box.clickedButton() is retry


def show_text(parent: QWidget | None, title: str, text: str) -> None:
    """Show a page of plain text with an OK button."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.exec()


def show_about(parent: QWidget | None) -> None:
    """Show the version, the privacy statement and where new versions are published."""
    show_text(
        parent,
        "About and privacy",
        f"{APP_NAME}, version {__version__}\n\n{PRIVACY_TEXT}\n\nNew versions: {RELEASES_URL}",
    )


class ChooseListingDialog(QDialog):
    """Ask which stock exchange listing an investment is, when the app cannot tell by itself."""

    def __init__(self, resolution: Resolution, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm your investment")
        ticker = resolution.ticker
        layout = QVBoxLayout(self)

        if resolution.confidence is Confidence.AMBIGUOUS:
            intro = (
                f"Your investment {ticker} is traded in more than one place. They are usually the same "
                "fund at almost the same price. Choose the one that matches yours:"
            )
        elif resolution.confidence is Confidence.CONFIDENT:
            intro = (
                f"Choose which fund your investment {ticker} is. The one that fits your purchases is "
                "selected; you can also type a Yahoo Finance symbol:"
            )
        elif resolution.candidates:
            intro = (
                f"The app could not tell for sure which fund {ticker} is. "
                "Choose the one that matches yours, if it is in the list:"
            )
        else:
            intro = f"The app could not find {ticker} on Yahoo Finance by itself."
        label = QLabel(intro)
        label.setWordWrap(True)
        layout.addWidget(label)

        self._group = QButtonGroup(self)
        self._symbols: list[str] = []
        for index, candidate in enumerate(resolution.candidates):
            info = candidate.info
            parts = [part for part in (info.name, info.exchange, info.currency) if part]
            button = QRadioButton(f"{', '.join(parts) or info.symbol}  ({info.symbol})")
            if candidate.comparable:
                button.setToolTip(
                    f"{candidate.matched} of {candidate.checked} of your purchases fit this listing's prices."
                )
            else:
                button.setToolTip("Priced in another currency, so your purchases could not be compared.")
            button.setChecked(index == 0)
            self._group.addButton(button, index)
            self._symbols.append(info.symbol)
            layout.addWidget(button)

        self._typed = QLineEdit()
        self._typed.setPlaceholderText("Or type the Yahoo Finance symbol here (optional)")
        layout.addWidget(self._typed)

        self.setMinimumWidth(520)
        self._always_first = False
        # Laid out by hand, not with QDialogButtonBox, which reorders buttons per operating system:
        # the order here is part of the design.
        self.use_button = QPushButton("Use this one")
        self.use_button.setObjectName("primary")  # the coloured main action, styled in ui/theme.py
        self.use_button.setDefault(True)
        self.use_button.clicked.connect(self.accept)
        # Offered whenever there is a first listing to take. Where it does not fit the purchases,
        # the run says so in a note each time it is used.
        self.always_first_button = QPushButton(ALWAYS_FIRST_TEXT)
        self.always_first_button.setToolTip(ALWAYS_FIRST_TIP)
        self.always_first_button.setVisible(bool(resolution.candidates))
        self.always_first_button.clicked.connect(self._use_first_always)
        self.skip_button = QPushButton("Skip this investment")
        self.skip_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for button in (self.use_button, self.always_first_button, self.skip_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _use_first_always(self) -> None:
        self._always_first = True
        self.accept()

    def chosen_symbol(self) -> str | None:
        """Return the listing to use: the first one after "Always choose the first option", else the
        typed symbol if there is one, else the selected listing, else None."""
        if self._always_first:
            return self._symbols[0]
        typed = self._typed.text().strip()
        if typed:
            return typed
        index = self._group.checkedId()
        return self._symbols[index] if 0 <= index < len(self._symbols) else None

    def always_use_first(self) -> bool:
        """True if the user pressed "Always choose the first option" (only offered when there is a listing)."""
        return self._always_first


def ask_listing(parent: QWidget | None, resolution: Resolution) -> tuple[str | None, bool]:
    """Open the dialog. Returns the chosen Yahoo symbol (None if skipped) and whether the
    user asked to always use the first listing from now on (only when they did not skip)."""
    dialog = ChooseListingDialog(resolution, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen_symbol(), dialog.always_use_first()
    return None, False
