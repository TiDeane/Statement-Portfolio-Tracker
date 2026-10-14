# Statement Portfolio Tracker

See how your Revolut investments are doing, and keep an Excel spreadsheet up to date, in three steps. No programming, no accounts, nothing to configure. Your statement, your amounts and your account details never leave your computer, and the app keeps no copy of them. The only thing sent anywhere are the codes of the funds you hold, to Yahoo Finance, to look up their prices.

The app reads the account statement CSV file you export from the Revolut app. It works out what you still hold, looks up current prices, and shows for each investment what you invested, what it is worth now, your gain or loss, and its share of the total. If you want, it also writes the same figures into an Excel spreadsheet.

> **Unofficial.** This app is not made by, affiliated with or endorsed by Revolut. It is not financial advice. Prices come from Yahoo Finance through an unofficial library; they may be delayed or wrong, and Yahoo's terms apply to them. Check important numbers against your Revolut app.

## Install

There are two ways to get the app. Most people want the first.

|                  | Option 1: the installer       | Option 2: run from the source      |
|------------------|-------------------------------|------------------------------------|
| **For**          | Anyone                        | People comfortable with a terminal |
| **Needs Python** | No                            | Yes, 3.12 or newer                 |
| **Systems**      | Windows (macOS experimental)  | Windows, macOS, Linux              |

### Option 1: install with the `.exe` (Windows 10 and 11)

Nothing else needs to be installed first.

1. Open the [Releases page](https://github.com/TiDeane/revolut-investment-tracker/releases) and download the file ending in `-windows-x64-setup.exe` from the latest release.
2. Double-click it. Windows may show a blue box saying **"Windows protected your PC"**. If it does, this is because the app is not signed with a paid certificate, not because something was found in it. Click **More info**, then **Run anyway**.
3. Follow the installer. It installs only for you and does not ask for an administrator password.
4. Start **Statement Portfolio Tracker** from the Start menu or the desktop shortcut.

If the warning appears, it is only for the installer, not each time you start the app. Do not turn off Windows security features to install this, "Run anyway" applies to this one file only.

If Windows says the app was blocked by **Smart App Control** and offers no "Run anyway", the app cannot be installed on that computer for now. Smart App Control only allows signed apps, and this one is not signed yet. Option 2 still works there.

To remove the app, use **Settings > Apps > Installed apps** like any other program.

#### macOS

Releases also include `.dmg` files for Apple Silicon and Intel Macs. They need **macOS 14.4 or newer**. They are built automatically and have not yet been tried on a real Mac, so treat them as experimental. Open the `.dmg` and drag the app to Applications. The first time you open it, macOS will refuse because the app is not signed. Open **System Settings > Privacy & Security**, scroll down, and click **Open Anyway** next to the app's name. This allows this one app only; do not turn Gatekeeper off.

### Option 2: run from a zip of the project

This runs the same app directly from its source code. You need [Python](https://www.python.org/downloads/) 3.12 or newer and an internet connection for the first setup, which downloads the libraries the app uses (a few hundred megabytes).

1. **Get the source**: on the project's GitHub page click **Code > Download ZIP**, or download **Source code (zip)** from a release.
2. Unzip it and open a terminal in the unzipped folder (the one that contains `pyproject.toml`).
3. Set it up once, then start the app.

   Windows (PowerShell):

   ```
   py -m venv .venv
   .venv\Scripts\python -m pip install .
   .venv\Scripts\python -m statement_tracker
   ```

   macOS and Linux:

   ```
   python3 -m venv .venv
   .venv/bin/python -m pip install .
   .venv/bin/python -m statement_tracker
   ```

From then on, only the last line is needed to start the app. To update, download the new zip and repeat the steps in the new folder. To remove it, delete the folder.

On Linux, if the window does not open, your system may be missing a library Qt needs; on Debian or Ubuntu, `sudo apt install libxcb-cursor0` usually fixes it.

## Get your statement from Revolut

In the Revolut app:

1. Open the **Invest** tab.
2. Tap **More**.
3. Tap **Documents**.
4. Tap **Brokerage account**.
5. Tap **Account statement**.
6. Choose **CSV** as the format.
7. Choose the date range **All time**.
8. Get the file onto your computer (for example, by emailing it to yourself).

> **Always choose All time.** The app needs your whole history, from your first trade until today, to know what you still hold. The other choices, a range of months or a tax year, list only the buys and sells inside that period, so the results would be wrong or the file would be rejected as incomplete.

Revolut may move these menus in newer versions of its app.

## Use the app

1. **Step 1: your Revolut statement.** Click **Choose statement file...** and pick the CSV file, or drag the file onto the window.
2. **Step 2 (optional): your Excel spreadsheet.** If you wish to write the app's output into an Excel sheet, click **Choose my spreadsheet...** to use an Excel file you already have, or **Create a new one...**. The app remembers your choice for next time, and you can change it at any point.
3. **Step 3.** Click the green button. A progress bar shows how far the app is while it fetches prices, which takes a few seconds. The window then grows to show your investments.

### If the app asks you to confirm an investment

Many funds are traded on several stock exchanges under the same code. When the app cannot tell which one is yours, it shows a short list. They are usually the same fund at almost the same price, so pick the one whose name and currency match what you see in Revolut. The app remembers your answer and does not ask again. If you are unsure, **Skip this investment** leaves it without a current value; nothing is guessed.

## Read the result

| Column | Meaning |
|---|---|
| Investment | The fund or share, shown as its code and name. |
| Invested | What you paid for what you still hold, fees included. |
| % of invested | How much of all the money you invested went into this one. |
| Worth now | What it would be worth at the latest price. Approximate. |
| % of worth now | How much of all your investments this one is, by what they are worth now. |
| Gain or loss | Worth now minus invested. |

The last row is the total. Investments you have sold completely are not listed.

**"unavailable"** means the app could not get a current price for that investment. When a value is unavailable, the calculated values that depend on it are unavailable too.

**A value marked with \*** uses the last price the app fetched on an earlier day, because Yahoo Finance could not be reached this time. Point at the value to see the date of that price. The Total is marked too, since it includes that value. Try again later for up-to-date values. An investment the app has never fetched a price for is shown as unavailable instead.

Notes under the table explain anything unusual, such as a price that is several days old.

## Your Excel spreadsheet

If you chose a spreadsheet, the app adds creates two sheets (or updates them if they already exist), writing:

- **Current Holdings**: one row per investment and a Total row, rewritten each time.
- **Portfolio History**: one row per day you run the app, so you can see your totals over time. Running twice on the same day updates that day's row; older rows are never changed.

A value that uses the last price from an earlier day has a comment (a small red corner in Excel) saying from when. On those runs no row is written to **Portfolio History**, because that row would be dated today.

Your own sheets in that file are left exactly as they are. Before the app changes an existing spreadsheet for the first time, it saves a copy next to it named `<your file>_backup_before_first_update.xlsx`.

### IMPORTANT NOTE

The app only changes its own two sheets, but to save them it has to write the whole file again. Values, formulas, colours, colour rules and charts in your own sheets are kept. **Pictures, shapes and text boxes are not**: they disappear from the saved file. If your spreadsheet has any of those, let the app create a separate new spreadsheet instead

The backup copy mentioned above is created in case something of yours does go missing.

## Privacy

Everything happens on your computer. There are no accounts, and the app does not record how you use it.

The only information that leaves your computer are the codes of your investments and dates, sent to Yahoo Finance to look up prices. Your amounts and your statement file are never sent anywhere.

The app keeps its settings (your confirmed investments and where your spreadsheet is) and the last price it fetched for each fund in your user folder: on Windows under `%LOCALAPPDATA%\StatementPortfolioTracker`. Those prices are prices per share from Yahoo Finance; none of your amounts are kept.

## Known limitations

- Only Revolut's stock statement in CSV format is supported, and only the "All time" range.
- The statement must be in a single currency. Statements with trades in more than one currency, or with a currency conversion, are not supported yet and are rejected with an explanation.
- Only these kinds of entries are understood: cash top-ups, market buys, market sells and dividends. Anything else (for example a stock split or a withdrawal) stops the app with a message naming the row, so that it never shows numbers built on a guess. Please report it if this happens to you.
- Prices need an internet connection. Without one, the app uses the last prices it fetched, marked with \*, or shows values as unavailable if it has never fetched them.
- The figures are simple: what you paid against what it is worth now. There are no tax calculations and no time-weighted returns.
- The app is in English only. It does not update itself; new versions are on the Releases page.

## Report a problem

Open an issue at <https://github.com/TiDeane/revolut-investment-tracker/issues>. If the app showed an error box, click **Copy details** there and paste the text into the issue.

Do not attach your real statement. It contains your trades and amounts. Describe the problem and the row the message mentions instead.

## For developers

The app is written in Python with PySide6. There is also a command-line version (`statement-tracker-cli`) with the same calculations.

To work on the code, install it in editable mode with the test and build tools, and run the tests:

```
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,build]"
.venv/bin/python -m pytest
```

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
