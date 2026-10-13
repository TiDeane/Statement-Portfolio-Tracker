# Statement Portfolio Tracker

See how your Revolut investments are doing, and keep an Excel spreadsheet up to
date, in three steps. No programming, no accounts, nothing to configure.

You give the app the statement file you export from the Revolut app. It works
out what you still hold, looks up current prices, and shows for each
investment what you invested, what it is worth now, your gain or loss, and its
share of the total. If you want, it also writes the same figures into an Excel
spreadsheet.

> **Unofficial.** This app is not made by, affiliated with or endorsed by
> Revolut. It is not financial advice. Prices come from Yahoo Finance through
> an unofficial library; they may be delayed or wrong, and Yahoo's terms apply
> to them. Check important numbers against your Revolut app.

## Install

Downloads are on the [Releases page](https://github.com/TiDeane/revolut-investment-tracker/releases).
You do not need to install Python or anything else.

### Windows 10 and 11

1. Download the file ending in `-windows-x64-setup.exe` from the latest release.
2. Double-click it. Windows will probably show a blue box saying
   **"Windows protected your PC"**. This appears because the app is not
   signed with a paid certificate, not because something was found in it.
   Click **More info**, then **Run anyway**.
3. Follow the installer. It installs only for you and does not ask for an
   administrator password.
4. Start **Statement Portfolio Tracker** from the Start menu or the desktop
   shortcut.

You only see the warning for the installer, not each time you start the app.
Do not turn off Windows security features to install this; "Run anyway"
applies to this one file only.

If Windows says the app was blocked by **Smart App Control** and offers no
"Run anyway", the app cannot be installed on that computer for now. Smart App
Control only allows signed apps, and this one is not signed yet.

### macOS

Releases include `.dmg` files for Apple Silicon and Intel Macs. They are built
automatically and have not yet been tried on a real Mac by the maintainer, so
treat them as experimental. Open the `.dmg` and drag the app to Applications.
The first time you open it, macOS will refuse because the app is not signed.
Open **System Settings > Privacy & Security**, scroll down, and click
**Open Anyway** next to the app's name. This allows this one app only; do not
turn Gatekeeper off.

## Get your statement from Revolut

In the Revolut app:

1. Open the **Invest** tab.
2. Tap **More**.
3. Tap **Documents**.
4. Tap **Brokerage account**.
5. Tap **Account statement**.
6. Choose **CSV** as the format.
7. Choose the date range **All time**.

Always choose **All time**. The app needs your whole history, from your first
trade until today, to know what you still hold. A statement for one month or
one tax year lists only that period's trades, so the results would be wrong
or the file would be rejected as incomplete.

Then get the file onto your computer (for example by emailing it to yourself)
and remember where you saved it. Revolut may move these menus in newer
versions of its app.

## Use the app

1. **Step 1: your Revolut statement.** Click **Choose statement file...** and
   pick the CSV file, or drag the file onto the window.
2. **Step 2 (optional): your Excel spreadsheet.** Skip this if you only want
   to see the figures. Otherwise click **Choose my spreadsheet...** to use an
   Excel file you already have, or **Create a new one...**. The app remembers
   your choice, so next time this step is already done.
3. **Step 3.** Click the green button and wait a few seconds while prices are
   fetched.

### If the app asks you to confirm an investment

Many funds are traded on several stock exchanges under the same code. When
the app cannot tell which one is yours, it shows a short list. They are
usually the same fund at almost the same price, so pick the one whose name
and currency match what you see in Revolut. The app remembers your answer and
does not ask again. If you are unsure, **Skip this investment** leaves it
without a current value; nothing is guessed.

## Read the result

| Column | Meaning |
|---|---|
| Investment | The fund or share, shown as its code and name. |
| Invested | What you paid for what you still hold, fees included. |
| Worth now | What it would be worth at the latest price. Approximate. |
| Gain or loss | Worth now minus invested, with ▲ for a gain and ▼ for a loss, and the same as a percentage. |
| Share of total | How much of all your investments this one is, by what they are worth now. |

The last row is the total. Investments you have sold completely are not
listed.

**"unavailable"** means the app could not get a current price for that
investment. It never fills in a guess. When one value is unavailable, the
totals that depend on it are unavailable too, and the last column switches to
"Share of total invested" (based on what you paid) and says so.

Notes under the table explain anything unusual, such as a price that is
several days old.

## Your Excel spreadsheet

If you chose a spreadsheet, the app adds two sheets to it and updates them on
every run:

- **Current Holdings**: one row per investment and a Total row, rewritten
  each time.
- **Portfolio History**: one row per day you run the app, so you can see your
  totals over time. Running twice on the same day updates that day's row;
  older rows are never changed.

Your own sheets in that file are left exactly as they are. Before the app
changes an existing spreadsheet for the first time, it saves a copy next to
it named `<your file> (backup before first update).xlsx`.

**Close the spreadsheet in Excel before pressing the button.** If it is open,
the app shows your results but cannot save, and tells you so.

The app only changes its own two sheets, but to save them it has to write
the whole file again. Values, formulas, colours, colour rules and charts in
your own sheets are kept. Pictures, shapes and text boxes are not: they
disappear from the saved file. If your spreadsheet has any of those, let the
app create a separate new spreadsheet instead. The backup copy mentioned
above is there in case something of yours does go missing.

## Privacy

Everything happens on your computer. There are no accounts, and the app does
not record how you use it.

The only information that leaves your computer is the codes of your
investments and dates, sent to Yahoo Finance to look up prices. Your amounts
and your statement file are never sent anywhere.

The app keeps its settings (your confirmed investments and where your
spreadsheet is) in your user folder: on Windows under
`%LOCALAPPDATA%\StatementPortfolioTracker`.

## Known limitations

- Only Revolut's stock statement in CSV format is supported, and only the
  "All time" range.
- The statement must be in a single currency. Statements with trades in more
  than one currency, or with a currency conversion, are not supported yet and
  are rejected with an explanation.
- Only these kinds of entries are understood: cash top-ups, market buys,
  market sells and dividends. Anything else (for example a stock split or a
  withdrawal) stops the app with a message naming the row, so that it never
  shows numbers built on a guess. Please report it if this happens to you.
- Prices need an internet connection. Without one, current values are shown
  as unavailable.
- The figures are simple: what you paid against what it is worth now. There
  are no tax calculations and no time-weighted returns.
- The app is in English only. It does not update itself; new versions are on
  the Releases page.

## Report a problem

Open an issue at
<https://github.com/TiDeane/revolut-investment-tracker/issues>. If the app
showed an error box, click **Copy details** there and paste the text into the
issue.

Do not attach your real statement. It contains your trades and amounts.
Describe the problem and the row the message mentions instead.

## For developers

The app is written in Python with PySide6. There is also a command-line
version (`statement-tracker-cli`) with the same calculations.

```
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,build]"
.venv/bin/python -m pytest
.venv/bin/python -m statement_tracker
```

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
