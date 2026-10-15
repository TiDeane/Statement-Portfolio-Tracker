"""The small dialogs: errors, choosing a listing, entering a price, help and about."""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, QLocale
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
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
from statement_tracker.core.models import MarketPrice
from statement_tracker.core.ticker_resolver import Confidence, Resolution

RELEASES_URL = "https://github.com/TiDeane/Statement-Portfolio-Tracker/releases"

PRIVACY_TEXT = (
    "Everything happens on this computer. There are no accounts and nothing is recorded about how you "
    "use the app.\n\n"
    "The only information sent anywhere is the ticker symbols of your investments and dates, which go to "
    "Yahoo Finance to look up prices. Your amounts and your statement never leave this computer.\n\n"
    "This app is unofficial and is not affiliated with Revolut. It is not financial advice. Prices are "
    "read from Yahoo Finance's public web pages, which is unofficial; they may be delayed or wrong, and "
    "are subject to Yahoo's terms."
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
    "Settings shows which listing each investment uses, and you can turn this off there."
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
            intro = (
                f"The app could not find your investment {ticker} on Yahoo Finance, so it cannot look up "
                "its price.\n\n"
                "If you know its Yahoo Finance symbol (for example ABCD.DE), type it below and press "
                '"Use this symbol". Otherwise press "Skip this investment": its value is then shown as '
                "unavailable, and you can enter its price yourself afterwards."
            )
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
        if resolution.candidates:
            self._typed.setPlaceholderText("Not in the list? Type its Yahoo Finance symbol here instead")
        else:
            self._typed.setPlaceholderText("Yahoo Finance symbol, for example ABCD.DE")
        layout.addWidget(self._typed)

        self.setMinimumWidth(520)
        self._always_first = False
        # Laid out by hand, not with QDialogButtonBox, which reorders buttons per operating system:
        # the order here is part of the design.
        self.use_button = QPushButton("Use this one" if resolution.candidates else "Use this symbol")
        self.use_button.setObjectName("primary")  # the coloured main action, styled in ui/theme.py
        self.use_button.setDefault(True)
        self.use_button.clicked.connect(self.accept)
        if not resolution.candidates:
            # Nothing to choose from: there is only something to use once a symbol is typed.
            self._typed.textChanged.connect(lambda text: self.use_button.setEnabled(bool(text.strip())))
            self.use_button.setEnabled(False)
        # Offered whenever there is a first listing to take.
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


def parse_amount(text: str) -> Decimal | None:
    """Read an amount typed in as people write it: 512.34, 512,34, 1,234.56 or 1.234,56.

    Of a comma and a full stop, the last one is the decimal point and the other separates
    thousands; either one alone is the decimal point. Returns None unless it is above zero.
    """
    text = text.strip().replace(" ", "").replace(" ", "")
    if "," in text and "." in text:
        decimal_point = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal_point == "," else ",", "")
    text = text.replace(",", ".")
    if not text or not all(character.isdigit() or character == "." for character in text):
        return None
    try:
        price = Decimal(text)
    except InvalidOperation:
        return None
    return price if price > 0 else None


@dataclass(frozen=True)
class ValueChoice:
    """An investment the user may type its current value in for."""

    ticker: str
    label: str
    """How the investment is shown, e.g. "(ABCD) World fund"."""
    shares: Decimal
    price: MarketPrice | None
    """The price per share used now (last known or typed in before), or None if there is none."""


class EnterValueDialog(QDialog):
    """Ask what an investment that Yahoo has no current price for is worth now: the whole holding,
    as the Revolut app shows it and as the table shows it, not the price of one share."""

    def __init__(
        self, choices: Sequence[ValueChoice], selected: str, currency: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Enter its value")
        self.setMinimumWidth(460)
        self._choices = list(choices)
        self._currency = currency
        self._locale = QLocale()
        layout = QVBoxLayout(self)

        intro = QLabel(
            f"Type what this investment is worth now, all your shares together, in {currency}. "
            "The Revolut app shows it on the investment's page."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # One investment is named; several are offered in a list, starting with the one asked about.
        self.investment = QComboBox()
        for choice in self._choices:
            self.investment.addItem(choice.label, choice.ticker)
        self.investment.setCurrentIndex(max(0, self.investment.findData(selected)))
        self.investment.setVisible(len(self._choices) > 1)
        self._name = QLabel()
        self._name.setVisible(len(self._choices) == 1)
        layout.addWidget(self.investment)
        layout.addWidget(self._name)

        self.value = QLineEdit()
        self.value.setPlaceholderText("What it is worth now, e.g. 1234.56")
        self.value.textChanged.connect(self._update_button)
        value_row = QHBoxLayout()
        value_row.addWidget(self.value, stretch=1)
        value_row.addWidget(QLabel(currency))
        layout.addLayout(value_row)

        self._current = QLabel()
        self._current.setObjectName("notes")
        self._current.setWordWrap(True)
        layout.addWidget(self._current)
        kept = QLabel(
            "The app keeps it for the next times too, following any shares you buy or sell, and uses it "
            "until Yahoo Finance has a price for this investment again."
        )
        kept.setObjectName("notes")
        kept.setWordWrap(True)
        layout.addWidget(kept)

        self.use_button = QPushButton("Use this value")
        self.use_button.setObjectName("primary")  # the coloured main action, styled in ui/theme.py
        self.use_button.setDefault(True)
        self.use_button.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.use_button)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        self.investment.currentIndexChanged.connect(self._show_choice)
        self._show_choice()

    def _choice(self) -> ValueChoice:
        return self._choices[max(0, self.investment.currentIndex())]

    def _show_choice(self) -> None:
        """Show what is known about the chosen investment's value, and start from it."""
        choice = self._choice()
        self._name.setText(f"<b>{html.escape(choice.label)}</b>")
        price = choice.price
        value = price.price * choice.shares if price is not None else None
        self.value.setText(self._number(value) if value is not None else "")
        if price is None or value is None:
            self._current.setText("There is no value for it at the moment.")
        else:
            shown = f"{self._number(value)} {self._currency}"
            when = self._day(price)
            if price.entered:
                self._current.setText(f"You entered {shown} on {when}.")
            else:
                self._current.setText(
                    f"At the last price fetched from Yahoo Finance, from {when}, it is worth {shown}."
                )
        self.value.selectAll()
        self.value.setFocus()
        self._update_button()

    def _day(self, price: MarketPrice) -> str:
        if price.as_of is None:
            return "an earlier day"
        day = price.as_of.astimezone().date() if price.entered else price.as_of.date()
        return self._locale.toString(QDate(day.year, day.month, day.day), QLocale.FormatType.LongFormat)

    def _number(self, value: Decimal) -> str:
        """An amount as this computer writes numbers, with 2 decimals and no thousands separator."""
        shown = self._locale.toString(float(value), "f", 2)
        return shown.replace(self._locale.groupSeparator(), "")

    def _update_button(self) -> None:
        self.use_button.setEnabled(parse_amount(self.value.text()) is not None)

    def entered(self) -> tuple[str, Decimal] | None:
        """The chosen investment's ticker and the value typed in, or None if it is not an amount."""
        value = parse_amount(self.value.text())
        return (self._choice().ticker, value) if value is not None else None


def ask_value(
    parent: QWidget | None, choices: Sequence[ValueChoice], selected: str, currency: str
) -> tuple[str, Decimal] | None:
    """Open the dialog. Returns the investment's ticker and the value typed in, or None if cancelled."""
    dialog = EnterValueDialog(choices, selected, currency, parent)
    try:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.entered()
        return None
    finally:
        dialog.deleteLater()
