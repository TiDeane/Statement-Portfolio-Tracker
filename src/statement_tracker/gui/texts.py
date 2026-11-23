"""Fixed copy the window shows: privacy, where the statement comes from, where new versions are."""

RELEASES_URL = "https://github.com/TiDeane/Statement-Portfolio-Tracker/releases"

PRIVACY_TEXT = (
    "Everything happens on this computer. There are no accounts and nothing is recorded about how you "
    "use the app.\n\n"
    "The only information sent anywhere is the ticker symbols of your investments and dates, which go to "
    "Yahoo Finance to look up prices. Your amounts and your statement never leave this computer.\n\n"
    "The app keeps a copy of the last statement you used in its own folder, so that next time it can "
    "look up today's values without a new statement. It stays on this computer.\n\n"
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

REVOLUT_STEPS = (
    "In the Revolut app, open Invest, then More › Documents.",
    "Tap Brokerage account › Account statement.",
    "Choose CSV and the range All time.",
    "Get the file onto this computer, for example by emailing it to yourself.",
)
"""The short version of ``WHERE_IS_THE_FILE_TEXT``, beside the drop area on first launch."""

ALL_TIME_NOTE = "Always pick All time. The app needs your whole history to know what you still hold."
