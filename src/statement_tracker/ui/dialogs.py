"""The small dialogs: errors, choosing a listing, help and about."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
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
    "A statement for only a month or a tax year will give wrong results or be rejected as incomplete.\n\n"
    "Revolut may move these menus in a newer version of its app. Once you have the file on this "
    "computer, choose it in step 1 or drag it onto the window."
)


def show_error(parent: QWidget | None, error: UserFacingError) -> None:
    """Explain a problem in plain language, with the technical details one click away."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(APP_NAME)
    box.setText(error.what_happened)
    box.setInformativeText(error.what_to_do)
    copy = box.addButton("Copy details", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()
    if box.clickedButton() is copy:
        details = f"{APP_NAME} {__version__}\n{error.what_happened}\n{error.what_to_do}\n\n{error.details}"
        QGuiApplication.clipboard().setText(details)


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
        buttons = QDialogButtonBox()
        use = buttons.addButton("Use this one", QDialogButtonBox.ButtonRole.AcceptRole)
        use.setObjectName("primary")  # the coloured main action, styled in ui/theme.py
        buttons.addButton("Skip this investment", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen_symbol(self) -> str | None:
        """Return the typed symbol if there is one, else the selected listing, else None."""
        typed = self._typed.text().strip()
        if typed:
            return typed
        index = self._group.checkedId()
        return self._symbols[index] if 0 <= index < len(self._symbols) else None


def ask_listing(parent: QWidget | None, resolution: Resolution) -> str | None:
    """Open the dialog and return the chosen Yahoo symbol, or None if the user skipped."""
    dialog = ChooseListingDialog(resolution, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen_symbol()
    return None
