"""The settings window: the investments the app remembers, how it matches them, and spreadsheet backups.

Every change is saved at once. The only thing changed inside the table is the
name, typed into its cell; everything else is read-only and changed with buttons.
Nothing here contacts Yahoo: choosing a listing again happens on the next run,
when the statement is there to compare against.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from statement_tracker.core.errors import UserFacingError
from statement_tracker.core.exporters.excel import MAX_BACKUPS_KEPT
from statement_tracker.price_cache import PriceCache
from statement_tracker.settings import Settings
from statement_tracker.ui import dialogs, theme

HEADERS = ["Investment", "Name shown", "Listing used", "Status"]
NAME_COLUMN = 1
NAME_TIP = "Double-click a name to change it. Leave it empty to use the fund's name from Yahoo Finance."
YAHOO_NAME_TIP = "The fund's name from Yahoo Finance. Double-click to use your own name instead."
ASK_AGAIN_STATUS = "Asks you next time"
ENTERED_PRICE_STATUS = "value entered by you"
ALWAYS_FIRST_SETTING = "When the app cannot tell which listing an investment is, use the first one without asking"
NOTHING_REMEMBERED = "No investments are remembered yet. They appear here after your first run."
BACKUPS_HELP = (
    "The first time each day that the app changes your spreadsheet, it first saves a copy of it as it was, "
    'in the same folder, named with the date (for example "My investments_backup_2026-10-15.xlsx"). '
    "Once there are more copies than the number above, the oldest is deleted. When set to 0, no copies are "
    "made, and copies made earlier are left as they are."
)


class InvestmentsTable(QTableWidget):
    """A table that highlights the whole row under the mouse, not one cell: it is a list of investments."""

    def __init__(self, columns: int) -> None:
        super().__init__(0, columns)
        self.hovered_row = -1
        self.setMouseTracking(True)
        self.entered.connect(lambda index: self.hover(index.row()))
        self.setItemDelegate(_RowHoverDelegate(self))

    def hover(self, row: int) -> None:
        """Highlight ``row`` (-1 for none)."""
        if row != self.hovered_row:
            self.hovered_row = row
            self.viewport().update()

    def viewportEvent(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Leave:
            self.hover(-1)
        return super().viewportEvent(event)


class _RowHoverDelegate(QStyledItemDelegate):
    """Draws every cell of the hovered row as hovered."""

    def __init__(self, table: InvestmentsTable) -> None:
        super().__init__(table)
        self._table = table

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        super().initStyleOption(option, index)
        if index.row() == self._table.hovered_row:
            option.state |= QStyle.StateFlag.State_MouseOver
        else:
            option.state &= ~QStyle.StateFlag.State_MouseOver


class SettingsDialog(QDialog):
    """Rename investments, choose a listing again on the next run, or forget one or all of them."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._prices = PriceCache.beside(settings.path)
        """The values typed in (kept as prices per share), which forgetting an investment removes too."""
        self.changed = False
        """True once anything was changed here, so that the window shows its result again."""
        self._filling = False
        self._select_after_edit: str | None = None
        # Replaceable in tests, like the main window's questions.
        self.confirm: Callable[[str], bool] = self._confirm

        self.setWindowTitle("Settings")
        self.setMinimumWidth(760)

        intro = QLabel(
            "The app remembers which stock exchange listing each of your investments is, and the name "
            "shown for it in the table and the spreadsheet. Double-click a name to change it, or select "
            "an investment and use the buttons below."
        )
        intro.setWordWrap(True)
        self.table = InvestmentsTable(len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.horizontalHeaderItem(NAME_COLUMN).setToolTip(NAME_TIP)
        # Only the name can be changed in the table, by typing in its cell. Everything else is read-only
        # and changed with the buttons.
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.itemChanged.connect(self._name_edited)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(NAME_COLUMN, QHeaderView.ResizeMode.Stretch)  # the name takes what is left
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.empty_label = QLabel(NOTHING_REMEMBERED)

        self.rename_button = QPushButton("&Rename")
        self.rename_button.setToolTip("Type a new name in the table. Enter saves it, Esc cancels.")
        self.rename_button.clicked.connect(self.rename_selected)
        self.choose_again_button = QPushButton("Choose the &listing next time")
        self.choose_again_button.setToolTip(
            "Nothing changes now. The next time you press step 3, the app shows the listings for this investment "
            "so you can pick again."
        )
        self.choose_again_button.clicked.connect(self.choose_again_selected)
        self.forget_button = QPushButton("&Forget")
        self.forget_button.setToolTip("Forget the listing and the name; the app looks for its listing again next time.")
        self.forget_button.clicked.connect(self.forget_selected)
        self.forget_all_button = QPushButton("Forget &all...")
        self.forget_all_button.setToolTip(
            "Forget the listings and names of every investment; the app looks for their listings again next time."
        )
        self.forget_all_button.clicked.connect(self.forget_all)
        row_buttons = QHBoxLayout()
        for button in (self.rename_button, self.choose_again_button, self.forget_button):
            row_buttons.addWidget(button)
        row_buttons.addStretch(1)
        row_buttons.addWidget(self.forget_all_button)  # apart: it is not about the selected investment
        self.always_first = QCheckBox(ALWAYS_FIRST_SETTING)
        self.always_first.setToolTip(
            "Usually the same fund is traded on more than one exchange, and the first listing fits your "
            "purchases best. When no listing fits your purchases, the first one found is used: check it in "
            'the "Listing used" column above.'
        )
        self.always_first.toggled.connect(self._always_first_toggled)
        self.message_label = QLabel("")
        self.message_label.setObjectName("status")
        self.message_label.setWordWrap(True)

        investments_box = QGroupBox("Your investments")
        investments_layout = QVBoxLayout(investments_box)
        investments_layout.addWidget(intro)
        investments_layout.addWidget(self.table)
        investments_layout.addWidget(self.empty_label)
        investments_layout.addLayout(row_buttons)
        investments_layout.addWidget(self.always_first)
        investments_layout.addWidget(self.message_label)

        self.backups = QSpinBox()
        self.backups.setRange(0, MAX_BACKUPS_KEPT)
        self.backups.setValue(settings.backups_kept)
        self.backups.valueChanged.connect(self._backups_changed)
        backups_label = QLabel("&Backup copies to keep:")
        backups_label.setBuddy(self.backups)
        backups_row = QHBoxLayout()
        backups_row.addWidget(backups_label)
        backups_row.addWidget(self.backups)
        backups_row.addStretch(1)
        backups_help = QLabel(BACKUPS_HELP)
        backups_help.setWordWrap(True)
        backups_box = QGroupBox("Spreadsheet backups")
        backups_layout = QVBoxLayout(backups_box)
        backups_layout.addLayout(backups_row)
        backups_layout.addWidget(backups_help)

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(investments_box, stretch=1)
        layout.addWidget(backups_box)
        layout.addWidget(close)
        self._refresh()

    # -- showing -----------------------------------------------------------------

    def _tickers(self) -> list[str]:
        """Every investment the app keeps something about: a listing, a name or a price typed in."""
        return sorted(set(self._settings.known_tickers()) | self._prices.entered_tickers())

    def _status(self, ticker: str) -> str:
        choice = self._settings.ticker_choices.get(ticker)
        if ticker in self._settings.ask_again:
            status = ASK_AGAIN_STATUS
        elif choice is None:
            status = "Not matched yet"
        else:
            status = "Chosen by you" if choice.confirmed else "Matched automatically"
        return f"{status}; {ENTERED_PRICE_STATUS}" if ticker in self._prices.entered_tickers() else status

    def _row(self, ticker: str) -> tuple[list[str], bool]:
        """The four texts for a ticker, and whether the name is Yahoo's rather than the user's own."""
        choice = self._settings.ticker_choices.get(ticker)
        own = self._settings.index_names.get(ticker)
        yahoo_name = choice.name if choice is not None and choice.name else ""
        if choice is None:
            listing = ""
        else:
            details = ", ".join(part for part in (choice.exchange, choice.currency) if part)
            listing = f"{choice.symbol} ({details})" if details else choice.symbol
        return [ticker, own or yahoo_name, listing, self._status(ticker)], not own and bool(yahoo_name)

    def _refresh(self, select: str | None = None) -> None:
        tickers = self._tickers()
        muted = QBrush(QColor(theme.current().muted))
        self._filling = True  # filling the table is not the user editing a name
        self.table.setRowCount(len(tickers))
        for row, ticker in enumerate(tickers):
            texts, from_yahoo = self._row(ticker)
            for column, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if column == NAME_COLUMN:
                    if from_yahoo:
                        item.setForeground(muted)
                        item.setToolTip(YAHOO_NAME_TIP)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
        self._filling = False
        self.table.setVisible(bool(tickers))
        self.empty_label.setVisible(not tickers)
        self.forget_all_button.setEnabled(bool(tickers))
        if select in tickers:
            self.table.selectRow(tickers.index(select))
        self._update_buttons()

        self.always_first.blockSignals(True)  # showing the setting is not changing it
        self.always_first.setChecked(self._settings.always_use_first_listing)
        self.always_first.blockSignals(False)

    def selected_ticker(self) -> str | None:
        """The investment selected in the table, if any."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.text() if item else None

    def _update_buttons(self) -> None:
        ticker = self.selected_ticker()
        self.rename_button.setEnabled(ticker is not None)
        self.forget_button.setEnabled(ticker is not None)
        self.choose_again_button.setEnabled(
            ticker is not None
            and ticker in self._settings.ticker_choices
            and ticker not in self._settings.ask_again
        )

    # -- changing ----------------------------------------------------------------

    def _save(self) -> bool:
        self.changed = True
        self._prices.save()  # only if a price was forgotten
        try:
            self._settings.save()
        except OSError as exc:
            dialogs.show_error(
                self,
                UserFacingError(
                    "The change could not be saved.",
                    "Check that there is free disk space, then try again.",
                    details=repr(exc),
                ),
            )
            return False
        return True

    def _always_first_toggled(self, checked: bool) -> None:
        self._settings.always_use_first_listing = checked
        self._save()

    def _backups_changed(self, days: int) -> None:
        # Saved without marking the result as changed: the next update of the spreadsheet uses it.
        self._settings.backups_kept = days
        try:
            self._settings.save()
        except OSError as exc:
            dialogs.show_error(
                self,
                UserFacingError(
                    "The change could not be saved.",
                    "Check that there is free disk space, then try again.",
                    details=repr(exc),
                ),
            )

    def rename_selected(self) -> None:
        """Start typing a new name in the selected investment's name cell, as a double click does."""
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.table.editItem(self.table.item(rows[0].row(), NAME_COLUMN))

    def _name_edited(self, item: QTableWidgetItem) -> None:
        """Keep the name typed in a cell. An empty name goes back to the fund's name from Yahoo."""
        if self._filling or item.column() != NAME_COLUMN:
            return
        ticker = self.table.item(item.row(), 0).text()
        name = item.text().strip()
        own = self._settings.index_names.get(ticker)
        choice = self._settings.ticker_choices.get(ticker)
        shown_before = own or (choice.name if choice is not None else None) or ""
        if name != shown_before:  # Enter on an unchanged name (Yahoo's included) changes nothing
            if name:
                self._settings.index_names[ticker] = name
            else:
                self._settings.index_names.pop(ticker, None)
            if self._save():
                self.message_label.setText("The new name is used the next time you run the app, also in the spreadsheet.")
        # Redrawn once the edit is over: the cell being edited must not be replaced while Qt still uses it.
        # Tied to this dialog, so it is dropped if the dialog is closed first.
        self._select_after_edit = ticker
        QTimer.singleShot(0, self, self._refresh_after_edit)

    def _refresh_after_edit(self) -> None:
        self._refresh(select=self._select_after_edit)

    def choose_again_selected(self) -> None:
        """Have the next run ask which listing the selected investment is."""
        ticker = self.selected_ticker()
        if ticker is None or ticker not in self._settings.ticker_choices:
            return
        self._settings.ask_again.add(ticker)
        if self._save():
            self.message_label.setText(
                f"The next time you run the app, it will show you the listings for {ticker} to choose from. "
                "Until then, the current one is kept."
            )
        self._refresh(select=ticker)

    def forget_selected(self) -> None:
        """Forget the listing and name of the selected investment, after asking."""
        ticker = self.selected_ticker()
        if ticker is None:
            return
        if not self.confirm(
            f"Forget {ticker}?\n\nThe next time you run the app, it looks for its listing "
            "again, asking you if it cannot tell. The name you gave it and the value you entered for it are removed."
        ):
            return
        self._settings.forget(ticker)
        self._prices.forget_entered(ticker)
        if self._save():
            self.message_label.setText(f"{ticker} was forgotten.")
        self._refresh()

    def forget_all(self) -> None:
        """Forget the listing, name and price typed in of every investment, after asking."""
        count = len(self._tickers())
        if not count or not self.confirm(
            f"Forget {'your one investment' if count == 1 else f'all {count} investments'}?\n\n"
            "Their listings, the names you gave them and the values you entered are removed. The next time you "
            "run the app, it looks for their listings again, asking you when it cannot tell.\n\n"
            "Your spreadsheet choice and the last prices found on Yahoo Finance are kept."
        ):
            return
        self._settings.forget_all()
        self._prices.forget_all_entered()
        if self._save():
            self.message_label.setText("All investments were forgotten.")
        self._refresh()

    # -- questions -----------------------------------------------------------------

    def _confirm(self, question: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Settings")
        box.setText(question)
        yes = box.addButton("Yes", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is yes
