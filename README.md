# Statement Portfolio Tracker

See how your Revolut investments are doing, and keep an Excel spreadsheet up to date, in three steps. No programming, no accounts, nothing to configure. Your statement, your amounts and your account details never leave your computer, and the app keeps no copy of them. The only thing sent anywhere are the codes of the funds you hold, to Yahoo Finance, to look up their prices.

The app reads the account statement CSV file you export from the Revolut app. It works out what you still hold, looks up current prices, and shows for each investment what you invested, what it is worth now, your gain or loss, and its share of the total. If you want, it also writes the same figures into an Excel spreadsheet.

> **Unofficial.** This app is not made by, affiliated with or endorsed by Revolut. It is not financial advice. Prices are read from Yahoo Finance's public web pages, which is unofficial; they may be delayed or wrong, and Yahoo's terms apply to them. Check important numbers against your Revolut app.

## Contents

- [Install](#install)
  - [Option 1: install with the `.exe` (Windows 10 and 11)](#option-1-install-with-the-exe-windows-10-and-11)
    - [macOS](#macos)
  - [Option 2: run from a zip of the project](#option-2-run-from-a-zip-of-the-project)
- [Get your statement from Revolut](#get-your-statement-from-revolut)
- [Use the app](#use-the-app)
  - [If the app asks you to confirm an investment](#if-the-app-asks-you-to-confirm-an-investment)
- [Read the result](#read-the-result)
  - [The columns](#the-columns)
  - [Renaming an investment](#renaming-an-investment)
- [When a price is missing](#when-a-price-is-missing)
  - [What you see](#what-you-see)
  - [Try again](#try-again)
  - [Enter its value yourself](#enter-its-value-yourself)
  - [How long your value is kept](#how-long-your-value-is-kept)
- [Your Excel spreadsheet](#your-excel-spreadsheet)
  - [New or existing spreadsheet](#new-or-existing-spreadsheet)
  - [The Current Holdings sheet](#the-current-holdings-sheet)
  - [The Portfolio History sheet](#the-portfolio-history-sheet)
  - [Backup copies](#backup-copies)
  - [Using Google Sheets](#using-google-sheets)
- [Settings](#settings)
  - [Your investments](#your-investments)
  - [Spreadsheet backups](#spreadsheet-backups)
- [Privacy](#privacy)
- [Known limitations](#known-limitations)
- [Report a problem](#report-a-problem)
- [For developers](#for-developers)
- [Licence](#licence)

## Install

There are two ways to get the app. Most people want the first.

|                  | Option 1: the installer       | Option 2: run from the source      |
|------------------|-------------------------------|------------------------------------|
| **For**          | Anyone                        | People comfortable with a terminal |
| **Needs Python** | No                            | Yes, 3.12 or newer                 |
| **Systems**      | Windows (macOS experimental)  | Windows, macOS, Linux              |

### Option 1: install with the `.exe` (Windows 10 and 11)

Nothing else needs to be installed first.

1. Open the [Releases page](https://github.com/TiDeane/Statement-Portfolio-Tracker/releases) and download the file ending in `-windows-x64-setup.exe` from the latest release.
2. Double-click it. Windows may show a blue box saying **"Windows protected your PC"**. If it does, this is because the app is not signed with a paid certificate, not because something was found in it. Click **More info**, then **Run anyway**.
3. Follow the installer. It installs only for you and does not ask for an administrator password.
4. Start **Statement Portfolio Tracker** from the Start menu or the desktop shortcut.

If the warning appears, it is only for the installer, not each time you start the app. Do not turn off Windows security features to install this, "Run anyway" applies to this one file only.

If Windows says the app was blocked by **Smart App Control** and offers no "Run anyway", the app cannot be installed on that computer for now. Smart App Control only allows signed apps, and this one is not signed yet. Option 2 still works there.

To remove the app, use **Settings > Apps > Installed apps** like any other program. This also deletes what the app remembers: your settings, the listings and names of your investments, and the values you entered. Your spreadsheets and their backup copies are kept. Installing a newer version over the old one keeps everything.

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
2. **Step 2 (optional): your Excel spreadsheet.** Choose **Don't use a spreadsheet** to only see the results in the window, or **Update my Excel spreadsheet** to also write them into Excel. With the second, two buttons appear: **Choose my spreadsheet...** to use an Excel file you already have, or **Create a new one...**. You can also drag an Excel file onto the window. The app remembers your choice for next time, and you can change it at any point. Before choosing an existing spreadsheet, read [New or existing spreadsheet](#new-or-existing-spreadsheet).
3. **Step 3.** Click the green button. The window turns to a page with your investments: a progress bar first shows how far the app is while it fetches prices, which takes a few seconds, then the table appears. With many investments, scroll the table to see them all.

**← Back to the steps** takes you back to choose other files. Pressed while the prices are still being fetched, it stops: nothing of that run is saved, and you can start again.

### If the app asks you to confirm an investment

Many funds are traded on several stock exchanges under the same code. When the app cannot tell which one is yours, it shows a short list. They are usually the same fund at almost the same price, so pick the one whose name and currency match what you see in Revolut. The app remembers your answer and does not ask again. If you are unsure, **Skip this investment** leaves it without a current value; nothing is guessed. If you picked the wrong one, see [Settings](#settings).

If you don't want to be asked at all, press **Always choose the first option**. The app uses the first listing for this investment, and from then on whenever it cannot tell by itself. When several listings fit your purchases, the first one fits best. When none fits (the app says it "could not tell for sure"), the first one is only the first found, so check in Settings, under "Listing used", that it is your fund. You can turn this off in Settings.

## Read the result

### The columns

| Column | Meaning |
|---|---|
| Investment | The fund or share, shown as its code and name. |
| Invested | What you paid for what you still hold, fees included. |
| % of invested | How much of all the money you invested went into this one. |
| Worth now | What it would be worth at the latest price. Approximate. |
| % of worth now | How much of all your investments this one is, by what they are worth now. |
| Gain or loss | Worth now minus invested. |

The last row is the total. Investments you have sold completely are not listed.

A value shown as "unavailable", in red, or marked with **\*** or **(your value)**, is explained in [When a price is missing](#when-a-price-is-missing).

### Renaming an investment

Double-click an investment's name in the table (or select it and press F2) and type the name you want. Enter saves it, Esc cancels. The name is remembered and also written to your spreadsheet, straight away. Leave it empty to go back to the fund's name from Yahoo Finance. You can also rename an investment in [Settings](#settings).

## When a price is missing

### What you see

**"unavailable"** means the app could not get a current price for that investment. Its row is shown in grey, with "not in total" in the percentage columns, and the Total and the percentages cover the other investments only. The app never guesses a value for it. Its **Worth now** cell is shown in red: you can [enter its value there yourself](#enter-its-value-yourself).

**A value marked with \*** uses the last price the app fetched on an earlier day, because Yahoo Finance could not be reached this time. Point at the value to see the date of that price. The Total is marked too, since it includes that value. An investment the app has never fetched a price for is shown as unavailable instead.

**A value marked (your value)** is one you entered yourself; see below. The Total is marked too.

When any of these is in the table, a line under it names the investments Yahoo Finance has no current price for, with two buttons: **Try again** and **Enter its value...**.

### Try again

**Try again** fetches the prices again, as the green button does. Use it for values marked with \* once you are back online.

### Enter its value yourself

**In the app:** press **Enter its value...**, or double-click the investment's row in the table, anywhere but its name (double-clicking the name renames it). Type what the investment is worth now, all your shares together, as the Revolut app shows it. The number you type is the number shown in **Worth now**. The app adds everything up again straight away and updates your spreadsheet, without fetching anything.

**In the spreadsheet:** type the investment's current value over "unavailable" in its red **Current Value** cell. The next time you press the green button, the app picks it up and keeps it, as if you had entered it in the app. See [The Current Holdings sheet](#the-current-holdings-sheet).

### How long your value is kept

The app keeps a value you entered for the next times, so you don't have to type it again (if you buy or sell shares, it follows them), and uses it whenever Yahoo Finance has no price for that investment. As soon as Yahoo Finance has one again, the app uses Yahoo's and forgets yours. To change a value you entered, double-click it in **Worth now**; to remove it, use **Forget** in [Settings](#settings).

## Your Excel spreadsheet

If you chose a spreadsheet in step 2, each run writes your results into two sheets of it, **Current Holdings** and **Portfolio History**, creating them the first time. Close the file in Excel before you press the green button: the app cannot save a file that Excel has open, and tells you if that happens.

### New or existing spreadsheet

**Create a new one...** makes an Excel file with only the app's two sheets. This is the safest choice.

**Choose my spreadsheet...** adds the two sheets to an Excel file you already have. Your own sheets in it are not changed, but to save the file the app has to write all of it again. Values, formulas, colours, colour rules and charts in your sheets are kept. **Pictures, shapes and text boxes are not**: they disappear from the saved file. If your spreadsheet has any of those, create a new one instead. If a sheet of yours is already called "Current Holdings" or "Portfolio History", the app stops without changing anything; rename that sheet in Excel first.

Before changing an existing file, the app saves a [backup copy](#backup-copies) of it. Step 2 says whether it will: in grey when it will, in red when backups are turned off.

### The Current Holdings sheet

One row per investment you still hold, and a **Total** row. The whole sheet is rewritten on every run, so keep your own notes in another sheet.

| Column | Meaning |
|---|---|
| Investment | The fund's code in brackets and its name, for example "(ABCD) World fund". To change the name, [rename it](#renaming-an-investment). |
| Invested | What you paid for what you still hold, fees included. |
| % of Invested | How much of all the money you invested went into this one. |
| Current Value | What it is worth now ("Worth now" in the app). |
| % of Current Value | How much of all your investments this one is, by what they are worth now. |
| % Up/Down | How much it has gone up or down since you bought it. |
| Dividends | The dividends it has paid you. |
| Currency | The currency of the amounts, the same as your statement's. |

The percentages and the Total row are Excel formulas worked out from **Current Value** and **Invested**, so they follow if you change a value.

Some cells say more:

- **"unavailable"**, in red, in **Current Value**: the app had no current price for it. Its row is grey with "not in total", and the Total covers the other investments. You can type its value over "unavailable": the row turns black and the percentages and the Total follow at once. The next time you press the green button, the app keeps the value you typed, as if you had [entered it in the app](#enter-its-value-yourself).
- **A comment** (a small red corner in Excel; point at it to read it) on a value that uses the last price from an earlier day says from when; on a value you entered, it says on which day. The Total has one too when it includes such a value.

### The Portfolio History sheet

One row per day you use the app, so you can follow your totals over time. Using it again on the same day updates that day's row. Rows from earlier days keep their numbers; the only exception is ROI %, which versions before 1.0 worked out differently: in their rows it switches to the meaning below.

Excel works out Unrealized PnL, ROI %, Net Worth and Gain vs Deposits from the other columns, so they follow if you change a number. Today's Total Cost Basis and Total Market Value come straight from the Total row of Current Holdings, so a value you type in there shows up in today's row at once. The next day you use the app, it keeps what the row showed by then.

| Column | Meaning |
|---|---|
| Date | The day of the run. |
| Total Cost Basis | What you paid for what you still hold, in total ("Invested" in the app). |
| Total Market Value | What it is all worth now ("Worth now" in the app). |
| Unrealized PnL | Your gain or loss on what you still hold: market value minus cost basis. |
| Realized PnL | Your gain or loss on what you have sold. |
| ROI % | Your return on the money you have put in: Gain vs Deposits as a percentage of Net Deposits. It counts what you have sold, dividends and the cash not yet invested (which brings it down). |
| Net Worth | Market value plus the cash left in your Revolut investment account, worked out from the statement. |
| Net Deposits | All the money you have put into the account. |
| Gain vs Deposits | Net worth minus net deposits: how much you are up or down overall. |

A row is dated today, so it is only written when its values are today's. No row is written, and existing rows are left unchanged, when:

- a value uses the last price from an earlier day (marked \*), because Yahoo Finance could not be reached;
- a value you entered was entered on an earlier day (one you entered today counts as today's);
- no investment has a price at all.

When only some investments have no price, the app still adds the day's row, and like the Total row in Current Holdings, all of it covers only the investments that have a value: the others count for nothing in Net Worth, Gain vs Deposits and ROI %, though the money you paid for them is still in Net Deposits. The history therefore dips on a day an investment is left out. Such a row is coloured light orange, and a comment on its date (a small red corner in Excel) says which investments it leaves out. Entering their value yourself, in the app, or by typing it into Current Holdings before you next use the app on another day, brings them in, and the colour goes.

### Backup copies

The first time each day that the app changes an existing spreadsheet, it first saves a copy of it as it was, in the same folder, named with the date, for example `My investments_backup_2026-10-15.xlsx`. Later changes that day (**Try again**, values you enter) keep that copy, so it is always the file as it was before you started that day.

The copies from the three most recent days you used the app are kept, and older ones are deleted. You can choose how many days, or turn backups off, in [Settings](#spreadsheet-backups).

To go back, open a copy and save it under your spreadsheet's name. If something of yours went missing (a picture, for example), get it back from a copy soon: once the app has been used on as many more days as copies are kept, the last copy that still had it is deleted.

### Using Google Sheets

Google Sheets can open and edit Excel files kept in Google Drive, so you can use the app with it:

1. Install [Google Drive for desktop](https://www.google.com/drive/download/) and sign in. Your Drive then appears on your computer like a folder or a drive (on Windows, usually `G:`).
2. In step 2, choose **Create a new one...** and save it inside your Drive, or choose an Excel file that is already there.
3. Open the file from [drive.google.com](https://drive.google.com). Google Sheets edits it as an Excel file and shows a small **.XLSX** label next to its name.

After each run, Drive uploads the updated file within a few moments; reload the page in your browser to see the new values. Close the file in Google Sheets before you press the green button, so that your edits and the app's don't overwrite each other.

The file stays an Excel file. **File > Save as Google Sheets** makes a separate copy, which the app does not update.

## Settings

### Your investments

The **Settings** button lists the investments the app remembers, including any you entered a value for even if the app never matched them to a listing. Select one to:

- **Rename** it: double-click its name (or press **Rename**) and type the name to show next to its code in the table and the spreadsheet. Enter saves it, Esc cancels. Leave it empty to go back to the fund's name from Yahoo Finance, which is shown in grey.
- **Choose the listing on the next run**: nothing changes right away. The next time you press the green button, the app shows you the list of listings for it again to pick from. Until then, the current one is kept.
- **Forget** it: the app matches it again on the next run, as on the first day. The name you gave it and any value you entered for it are removed too.

**Forget all...** does the same for every investment at once. Your spreadsheet choice and the last prices fetched from Yahoo Finance are kept.

The switch **When the app cannot tell which listing an investment is, use the first one without asking** is explained in [If the app asks you to confirm an investment](#if-the-app-asks-you-to-confirm-an-investment).

### Spreadsheet backups

**Days of backup copies to keep** sets how many days of [backup copies](#backup-copies) of your spreadsheet are kept; 3 unless you change it. When set to **0**, no copies are made, and step 2 says so in red; copies made earlier are left where they are.

## Privacy

Everything happens on your computer. There are no accounts, and the app does not record how you use it.

The only information that leaves your computer are the codes of your investments and dates, sent to Yahoo Finance to look up prices. Your amounts and your statement file are never sent anywhere.

The app keeps its settings (your confirmed investments and where your spreadsheet is), the last price it fetched for each fund, and any values you entered, in your user folder: `%LOCALAPPDATA%\StatementPortfolioTracker` on Windows, `~/Library/Application Support/StatementPortfolioTracker` on macOS and `~/.config/StatementPortfolioTracker` on Linux. Those are kept as prices per share; none of the amounts in your statement are kept. Together they take a few kilobytes. Uninstalling the app on Windows deletes that folder; otherwise (macOS, or running from the source), delete it yourself.

## Known limitations

- Only Revolut's stock statement in CSV format is supported, and only the "All time" range.
- The statement must be in a single currency. Statements with trades in more than one currency, or with a currency conversion, are not supported yet and are rejected with an explanation.
- Only these kinds of entries are understood: cash top-ups, market buys, market sells and dividends. Anything else (for example a stock split or a withdrawal) stops the app with a message naming the row, so that it never shows numbers built on a guess. Please report it if this happens to you.
- Prices need an internet connection. Without one, the app uses the last prices it fetched, marked with \*, or shows values as unavailable if it has never fetched them. You can then [enter values yourself](#enter-its-value-yourself).
- The figures are simple: what you paid against what it is worth now. There are no tax calculations and no time-weighted returns.
- The app is in English only. It does not update itself; new versions are on the Releases page.

## Report a problem

Open an issue at <https://github.com/TiDeane/Statement-Portfolio-Tracker/issues>. If the app showed an error box, click **Copy details** there and paste the text into the issue.

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
