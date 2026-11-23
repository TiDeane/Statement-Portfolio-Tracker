# Behaviour specification

What the app must do, as the tests should check it. It is written from the README and the approved decisions, not from the code. Each rule can be checked from the outside: give the app what a user would give it, then look at what the user would see. That means the window, the spreadsheet as Excel shows it, the command line's output, and the files on disk.

A test names the rule it checks, for example `# Spec H3`. When a behaviour changes, change the rule here first, then the tests.

## A. Reading the statement

- **A1.** A Revolut stock statement (CSV, the exact header `Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate`) is read in full. So is one saved again by Excel without its data changing: an invisible mark at the start ("CSV UTF-8"), Windows line endings, or Windows' own text encoding.
- **A2.** Amounts such as `EUR 355.45`, `EUR 123` and `EUR 1,234.56` are read exactly, with no rounding.
- **A3.** Times are ISO 8601 UTC with 3 or 6 fractional digits and a `Z`.
- **A4.** Rows are used in time order, whatever their order in the file.
- **A5.** Blank lines are ignored.
- **A6.** These stop the run with a plain-language message, before anything is shown or saved:
  - a different header: the message shows the expected and the found columns;
  - an empty file, a missing file, or a file that is not text;
  - an amount, date or row that cannot be read: the message names the row;
  - more than one currency, an amount in another currency than its row, or an FX Rate other than 1: the message names the row;
  - a transaction type other than the four known ones: the message names the row and the type;
  - a row that does not fit its type (a buy without a ticker or quantity, a dividend with a quantity, and so on);
  - a statement with no rows;
  - a sell of more shares than are held: the message says the full history is needed;
  - a file whose layout another program changed when saving it (columns separated by `;` or tabs, dates or numbers rewritten): the message says what is wrong, what a statement from Revolut looks like (commas between columns, dates like `2025-01-06T10:00:00.000Z`, amounts like `EUR 1,234.56`, quantities like `1.47328346`), and to export it from Revolut again. It does not guess which program changed it.
- **A7.** "Ignore unknown types" skips unknown rows and shows a prominent "results may be wrong" warning that names the type and the rows.

## B. Calculations

- **B1.** Cost basis is the Total Amount, fees included, never quantity × price.
- **B2.** Average cost: a sell realizes Total Amount − average cost × shares sold, and leaves the average cost unchanged.
- **B3.** A sell down to (almost) zero shares closes the position. Buying again starts a fresh average.
- **B4.** Closed positions are not listed. Their realized gain and dividends stay in the totals.
- **B5.** Dividends are counted per ticker, including after the position is closed.
- **B6.** Cash = top-ups − buys + sells + dividends. If it is negative, a warning is shown.
- **B7.** The portfolio totals:
  - net deposits are the sum of the top-ups;
  - net worth is the value of what has a value, plus the cash;
  - gain vs deposits is net worth − net deposits;
  - ROI % is gain vs deposits ÷ net deposits.
- **B8.** An investment without a value is left out of every total and share, and nothing is estimated for it. If no investment has a value, the totals are unavailable rather than zero.
- **B9.** Self-check: when the figures do not reconcile, a warning is shown.
- **B10.** For the sample statement, the hand-computed figures are reproduced: deposits 996.56, IUSA realized +45.83, dividends 3.86, cash 504.76, EQQB 1.47328346 shares, cost basis 541.49.

## C. Finding each investment's listing

- **C1.** A listing fits when most of the purchases' prices fall within its daily low–high range.
  - The trade date is taken in the exchange's own time zone; on a non-trading day, the nearest trading day is used.
  - A small tolerance is allowed.
  - Prices in pence are compared in pounds.
- **C2.** Exactly one fitting listing is used without asking.
- **C3.** Several fitting listings, no fitting listing, or no listing at all: the user is asked.
  - The question shows name, exchange, currency and how many purchases fit.
  - The user can pick one, type a symbol, skip, or choose "always the first option".
- **C4.** Answers are remembered.
  - A listing the user chose is never replaced automatically.
  - A listing the app chose is not matched again on the next run.
- **C5.** "Always use the first listing" takes the first listing whenever there is one, says so, and still asks when nothing was found.
- **C6.** "Choose the listing next time" asks on the next run that can ask, even if matching is sure, and only once.
  - Skipping keeps the old listing.
  - A run that cannot ask (command line, no prompt) keeps the request for later.
- **C7.** When Yahoo cannot be reached, the run says so. It never decides that no listing exists.
- **C8.** Listings found by Yahoo's search stay as options even without prices near the purchases.

## D. Prices

- **D1.** The current price is the latest one Yahoo has. A price much older than expected is pointed out.
- **D2.** A price in another currency is converted at the current rate and labelled as converted. Pence are turned into pounds. Without an exchange rate, the value is unavailable.
- **D3.** When Yahoo cannot be reached:
  - the last price found on an earlier day is used, marked with its date, and the totals are marked too;
  - an investment never priced is shown as unavailable;
  - a last price in another statement currency is never used;
  - when Yahoo answers for some investments only, each one is marked for what it got.
- **D4.** A fresh price replaces the kept one. A damaged file of kept prices is ignored and rebuilt.
- **D5.** A run with several investments looks up their prices at the same time, and each exchange rate is fetched once.
- **D6.** Notes and results are in statement order, whatever order the prices arrive in.

## E. Values the user enters

- **E1.** A value can be entered for an investment that has no current price, or only a last known one.
  - In the window, the value is for the whole holding, and the number typed is the number shown.
  - In the spreadsheet, the value is typed over "unavailable".
  - On the command line (`--price`), the price is per share.
- **E2.** The totals, the window and the spreadsheet update at once, without looking up prices again.
- **E3.** The value is marked "(your value)", with its date, and so is the Total.
- **E4.** How long it lasts:
  - it is kept for later runs, and follows a change in the number of shares;
  - it is used whenever Yahoo has no price;
  - it is dropped as soon as Yahoo has a price, after which the last price from Yahoo applies, not the old value.
- **E5.** A value entered today counts for today's history row. One entered on an earlier day blocks the row.
- **E6.** Which value wins:
  - a value the app itself wrote in the spreadsheet is never taken for one the user typed;
  - a newer value entered in the app wins over an older one left in the sheet;
  - a value forgotten in Settings does not come back from the sheet.
- **E7.** Amounts are accepted with a comma or a full stop, and with thousands separators. Zero, negative and non-numbers are refused.

## F. The window

- **F1.** The three steps:
  - step 3 is disabled until a statement is chosen;
  - step 2 is optional: no spreadsheet, an existing one, or a new one;
  - each step says whether it is done, optional, or remembered from last time; a step still to do says only what to do.
- **F2.** Files are chosen with a dialog or dropped on the window. A CSV goes to step 1 and an .xlsx to step 2. The last folder used is remembered. Step 1 is a drop area (a dashed outline saying "Drag your statement file here", with the button to choose one inside it), and it turns green while a statement is dragged over the window.
- **F3.** Step 3 turns to the result page in the same window.
  - Its progress bar only moves forward, and counts each listing to find, each price and the spreadsheet.
  - While the app waits for the user's answer, the status says so.
- **F4.** The table:
  - one row per held investment, and a Total;
  - investments the user named show their own name;
  - columns: Investment, Invested, % of invested, Worth now, % of worth now, Gain or loss;
  - a gain shows a sign and an arrow as well as a colour;
  - numbers follow the computer's locale, and the currency is the statement's, never assumed;
  - dates, here and in every window, are written in figures in the computer's order and with a four-digit year (14/11/2026 in Portugal, 11/14/2026 in the United States). They never use month or day names, which would be in the computer's language among English words.
- **F5.** Values that are not today's from Yahoo:
  - an unavailable value is grey, marked "not in total", and its Worth now cell is red;
  - a last known value is marked `*`, with a dated tooltip;
  - an entered value is marked "(your value)";
  - in all three cases, a line under the table names them, with **Try again** and **Enter its value...**.
- **F6.** Double-clicking a name, or pressing F2 (Return on a Mac, as in Finder), renames the investment.
  - Enter saves the name, Esc cancels, and an empty name goes back to Yahoo's.
  - The new name is saved and written to the spreadsheet at once.
  - Double-clicking elsewhere in a row without a price enters a value.
- **F7.** Ctrl+Z / Ctrl+Y undo and redo changes to investments:
  - the history is shared by the result table and Settings;
  - each step puts back only what it changed;
  - names and values stay undoable across runs;
  - Forget and "Choose the listing next time" stop being undoable once a run finishes;
  - the tick box, forgetting the statement (G7) and backups are not part of it;
  - it works only on the result page, never during a run.
- **F8.** "Back to the steps" during a run stops it, and nothing of it is saved or shown.
- **F9.** Errors are in plain words: what happened, and what to do.
  - Unexpected failures can be reported with **Copy details**, and no stack trace is shown.
  - If the spreadsheet cannot be saved, the investments are still shown.
  - Try again saves the spreadsheet without looking up prices again.
- **F10.** Layout:
  - many investments scroll inside the table;
  - a small window shrinks the table instead of covering it, and scrolls when the system ignores the minimum size;
  - there are light and dark themes;
  - buttons are only highlighted when reached with the keyboard.
- **F11.** "Where do I get this file?" gives the Revolut steps and asks for All time. "About and privacy" shows the version and the releases link.
- **F12.** The window and its dialogs show the app's icon, and the Windows program, its installer and the macOS app show the same one.
- **F13.** When a spreadsheet is used, the result page says on its own, apart from the table, what became of it.
  - Updated or created: in green, with the time, the file and its folder, what was written to Current Holdings, whether today's history row was added or updated (or why not, and what it leaves out), and the backup copy's name.
  - Not updated: in red, with what happened and what to do.
  - It says so again after each later change that rewrites the spreadsheet (a rename, a value entered).
  - Either way, "Open its folder" opens the folder the spreadsheet is in, with the file selected where the system allows it.
- **F14.** The statement is kept for next time, so that today's values need no new statement.
  - Once a run has read a statement, a copy of it is kept in the app's own folder, replacing the one kept before. A statement that cannot be read, or a run stopped with "Back to the steps", keeps the one from before.
  - When the app opens with a statement kept, step 1 is a choice, like step 2: "Use my statement from last time" or "Use a new statement".
    - The first is chosen and remembered from last time. Under it are the date of its latest transaction and a note that anything bought, sold or added since then is not included. Step 3 can be pressed at once.
    - The drop area shows only while "Use a new statement" is chosen, and step 3 then waits for a statement.
    - A statement chosen or dropped chooses "Use a new statement". Going back and forth keeps it.
  - When the app opens with no statement kept, step 1 is only the drop area. It stays that way until the app is opened again.
  - The result of a run on the statement from last time says so, with the date of its latest transaction.

## G. Settings

- **G1.** Settings lists every investment the app keeps something about, including one with only an entered value, with its name, listing and status. Yahoo's name is shown in grey.
- **G2.** For the selected investment:
  - Rename follows the same rules as F6;
  - "Choose the listing next time" applies on the next run;
  - Forget asks first, then removes the listing, the name and the entered value.
- **G3.** Forget all asks first, and keeps the spreadsheet choice, the statement from last time and the last prices from Yahoo.
- **G4.** The other settings:
  - the "always the first listing" switch;
  - "Backup copies to keep", from 0 to 99, saved and kept within that range.
- **G5.** Changes are saved at once, and the result page shows them at once.
- **G6.** With nothing remembered, the empty table still shows, with the reason inside it.
- **G7.** The statement from last time (F14):
  - Settings says whether one is kept, with the date of its latest transaction;
  - "Forget the statement..." asks first, then deletes the copy, and step 1 goes back to asking for a statement;
  - it is only enabled while a statement is kept, it leaves the investments alone, and Ctrl+Z does not bring the statement back.

## H. The spreadsheet

- **H1.** Only the app's two sheets are written: created if missing, rewritten if they are the app's.
  - Every other sheet keeps its values, formulas, formatting, colour rules, tables, charts and defined names.
  - A new workbook has only the app's two sheets.
- **H2.** Refusing:
  - a sheet with the app's name that is not the app's (by its heading) makes the app stop without changing anything;
  - a file that is not an .xlsx, or not a workbook, is explained and left untouched;
  - a file open in Excel gives a friendly message, and the file and its backups are untouched.
- **H3.** Current Holdings:
  - one row per held investment and a bold Total, in the documented columns;
  - Current Value holds numbers, or "unavailable" in red;
  - shares, % Up/Down and the Total are formulas, so typing a value updates them;
  - an unpriced row is grey with "not in total", and returns to normal once a value is typed;
  - comments explain last known and entered values;
  - the Investment cell reads "(TICKER) Name";
  - sheets written by earlier versions are recognised and rewritten in the current layout.
- **H4.** Portfolio History:
  - one row per day, updated if the app runs again that day; earlier days are kept;
  - no row is added when a value is a last known price, a value was entered on an earlier day, or no investment has a price;
  - Unrealized PnL, ROI %, Net Worth and Gain vs Deposits follow when a figure is changed;
  - today's row follows a value typed into Current Holdings, and keeps it on later days;
  - a row that leaves an investment out is light orange with a "Leaves out ..." comment until the value is in, and stays marked if it never comes;
  - rows from versions before 1.0 switch ROI % to the new meaning, and nothing else in them changes;
  - a row worked out from the statement kept from last time (F14) has a comment on its date saying so, with the date of the statement's latest transaction. It keeps it on later days. A later run that day with a new statement takes it away.
- **H5.** Backups:
  - before the first change each day to an existing file, a dated copy is saved beside it; later changes that day keep it;
  - the newest N are kept (default 3); other workbooks' copies and the old one-time copy are never deleted;
  - 0 makes no copy and deletes none;
  - a failed save leaves no new copy and deletes no old one;
  - step 2 says whether a copy will be made, in grey, or in red when none will.
- **H6.** Presentation:
  - percentages are real Excel percentages;
  - the header has its own colour;
  - every cell has a thin outline;
  - columns are wide enough for their text;
  - rows are taller than Excel's default.

## I. Command line

- **I1.** Output and its options:
  - one comma-separated row per held investment and a Total, with the documented columns;
  - `--table` aligns them;
  - `--details` adds the checking columns.
- **I2.** Notes and questions go to stderr. A bad file or a bad option exits with code 2 and a message, with no stack trace.
- **I3.** The options:
  - `--symbol` and `--name` are remembered;
  - `--symbol` replaces a saved choice, as one chosen by the user;
  - a symbol Yahoo does not know is not saved;
  - `--price` is per share, is used only when Yahoo has none, and is refused unless it is a positive number;
  - `--spreadsheet` is remembered, and later runs update it by default;
  - `--no-spreadsheet` skips it for one run;
  - without a spreadsheet, the output says how to choose one;
  - `--no-prompt` never asks;
  - `--ignore-unknown-types` behaves as in A7;
  - every statement read is kept as in F14, and without a statement the one kept from last time is used: stderr says so, with the date of its latest transaction. With none kept, it exits with code 2 and says to give one.
- **I4.** The terminal prompt accepts a number, a symbol, or nothing.

## J. Privacy, safety, packaging

- **J1.** Only ticker symbols and dates are sent to Yahoo. Amounts, quantities and the statement are never sent.
- **J2.** Only listings, names, prices per share, settings and a copy of the last statement read (F14) are kept, all in the app's own folder. No amount from the statement is kept anywhere else.
- **J3.** A damaged settings file is explained, not silently reset. Tests never touch the real settings or the network.
- **J4.** The packaged app's smoke test reads the sample offline and writes a spreadsheet.
- **J5.** On Windows, the installer can tell that the app is open.
- **J6.** Installing a newer version over an older one keeps everything: the settings, listings, names, entered values and last prices saved by any earlier version are read and used.

## K. The new window (Qt Quick)

The window being built to replace F and G (design: `docs/superpowers/specs/2026-11-23-qt-quick-redesign-design.md`). While both exist, F and G describe the Widgets window and K the new one; K then becomes the new F and G.

- **K1.** Opening: with a statement kept from last time, the app opens on Home and fetches today's prices. With none, or one that can no longer be read, it opens on first launch, without an error message.
- **K2.** First launch, step 1: the statement.
  - A drop area ("Drop your Revolut statement here", with **Choose statement file…**) beside "Where do I get it?": the Revolut steps and "Always pick All time".
  - Dropping a statement anywhere on the window or choosing one reads it at once. One that reads shows its file name, "<n> transactions, the latest on <date>" and "<n> investments you still hold", with **Choose another file…**. One that does not read is explained (K12) and the step stays as it was.
  - **Continue** stays disabled until a statement has been read.
  - The file chooser opens in the folder used last time (F2's rule).
  - A line says that everything stays on this computer and only fund codes and dates go to Yahoo Finance, with **About and privacy**.
- **K3.** First launch, step 2: keep a spreadsheet up to date?
  - Three options, one chosen at a time: **Use a spreadsheet I have** (opens the file chooser), **Create a new one** (asks where to save it; ".xlsx" is added when missing) and **Not now**. A file chosen shows in its option with **Choose another…**; cancelling the chooser keeps the choice before. An .xlsx dropped on the window is a spreadsheet I have.
  - A line says a backup copy is saved beside the file before each day's first change, and names the app's two sheets.
  - **Back** returns to step 1 with the statement still chosen. **Show my investments**, enabled once an option is chosen, remembers the choice and opens Home.
  - When a spreadsheet is already remembered (someone upgrading from the Widgets window), step 2 is skipped.
- **K4.** Home, the totals: "Your portfolio", then **Worth now** in large type with the statement's currency, the gain or loss since buying (sign, arrow and colour, amount and %), **Invested** and the number of investments.
  - While prices are fetched, the amounts show placeholders, a progress bar moves forward and a line says what is being done.
  - Then "Today's prices from Yahoo Finance, <time>" and **Refresh prices**, which fetches again.
  - Totals cover only what has a value (B8). When something is left out, a line says "<names> has (have) no price today, so these totals leave it (them) out."
- **K5.** Home, the investments list: one row per investment held, then a bold **Total**.
  - Columns: Investment, Invested, Worth now, Share of total, Gain or loss. The investment's name comes first (the user's own, else Yahoo's, else its ticker), with "TICKER · exchange" under it.
  - Many investments scroll with the page; the window keeps its size and long names are cut short.
- **K12.** Errors are in plain words: what happened, and what to do.
  - Details can be copied with **Copy details**; no stack trace is shown.
