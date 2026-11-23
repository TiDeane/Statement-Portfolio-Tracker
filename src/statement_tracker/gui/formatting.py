"""How the window writes amounts, percentages, gains and dates.

Numbers follow the computer's locale. Dates are figures only (see ``day_text``). The currency
is always the statement's, passed in, never assumed.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, QLocale


def _locale(locale: QLocale | None) -> QLocale:
    return locale or QLocale()


def money(amount: Decimal, locale: QLocale | None = None) -> str:
    """An amount with two decimals and the locale's separators: "12,727.80"."""
    return _locale(locale).toString(float(amount), "f", 2)


def money_with_currency(amount: Decimal, currency: str, locale: QLocale | None = None) -> str:
    """An amount followed by its currency code: "541.49 EUR"."""
    return f"{money(amount, locale)} {currency}"


def shares_text(shares: Decimal, locale: QLocale | None = None) -> str:
    """A number of shares, with as many decimals as it has (up to Revolut's 8): "1.47328346", "4"."""
    text = _locale(locale).toString(float(shares), "f", 8)
    point = _locale(locale).decimalPoint()
    return text.rstrip("0").rstrip(point) if point in text else text


def percent(value: Decimal, locale: QLocale | None = None) -> str:
    """A percentage with two decimals: "12.87 %"."""
    return f"{_locale(locale).toString(float(value), 'f', 2)} %"


def share(value: Decimal, locale: QLocale | None = None) -> str:
    """A share of a total, with one decimal: "56.0 %"."""
    return f"{_locale(locale).toString(float(value), 'f', 1)} %"


def gain(amount: Decimal, change: Decimal | None, locale: QLocale | None = None) -> str:
    """A gain or loss with an arrow and a sign, and its percentage when known: "▲ +1,451.70 (+12.87 %)".
    Nothing gained or lost has no arrow."""
    if amount == 0:
        return money(amount, locale)
    arrow, sign = ("▲", "+") if amount > 0 else ("▼", "-")
    text = f"{arrow} {sign}{money(abs(amount), locale)}"
    if change is not None:
        text += f" ({sign}{percent(abs(change), locale)})"
    return text


def day_text(day: date, locale: QLocale | None = None) -> str:
    """A date in figures, in the order and with the separators the computer uses: 14/11/2026 in
    Portugal, 11/14/2026 in the United States.

    Never with month or day names: the app's words are English, and names would be in the
    computer's own language in the middle of an English sentence.
    """
    locale = _locale(locale)
    pattern = locale.dateFormat(QLocale.FormatType.ShortFormat)
    if "MMM" in pattern or "ddd" in pattern:  # a name after all: the date as Revolut's statement writes it
        pattern = "yyyy-MM-dd"
    elif "yyyy" not in pattern:
        pattern = pattern.replace("yy", "yyyy")  # 14/11/26 could be read as 2014 or 2026
    return locale.toString(QDate(day.year, day.month, day.day), pattern)


def time_text(moment: datetime, locale: QLocale | None = None) -> str:
    """The local time of ``moment``, short, as the computer writes it: "14:32"."""
    return _locale(locale).toString(moment.astimezone().time(), QLocale.FormatType.ShortFormat)


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
