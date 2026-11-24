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

- **F1.** Opening: with a statement kept from last time, the app opens on Home and fetches today's prices. With none, or one that can no longer be read, it opens on first launch, without an error message.
  - Once a fetch has read a statement to the end, a copy of it is kept in the app's own folder, replacing the one kept before, with where the file was read from. One that cannot be read, or a fetch that is stopped, keeps the one from before.
- **F2.** First launch, step 1: the statement.
  - A drop area ("Drop your Revolut statement here", with **Choose statement file…**) beside "Where do I get it?": the Revolut steps and "Always pick All time".
  - Dropping a statement anywhere on the window or choosing one reads it at once, without freezing the window: the drop area says "Reading your statement…" with a moving bar meanwhile. One that reads shows its file name, "<n> transactions, the latest on <date>" and "<n> investments you still hold", with **Choose another file…**. One that does not read is explained (F11) and the step stays as it was.
  - **Continue** stays disabled until a statement has been read.
  - The file chooser opens in the folder used last time.
  - A line says that everything stays on this computer and only fund codes and dates go to Yahoo Finance, with **About and privacy**.
  - Shown again (after the statement is forgotten in Settings), first launch starts afresh: step 1, nothing chosen.
- **F3.** First launch, step 2: keep a spreadsheet up to date?
  - Three options, one chosen at a time: **Use a spreadsheet I have** (opens the file chooser), **Create a new one** (asks where to save it, suggesting "investments_<today's date>.xlsx", e.g. investments_2026-11-24.xlsx, as on Home and in Settings; ".xlsx" is added when missing; Home creates it as soon as today's prices are in, without **Update my spreadsheet**) and **Not now**. A file chosen shows in its option with **Choose another…**; cancelling the chooser keeps the choice before. An .xlsx dropped on the window is a spreadsheet I have.
  - A line says a backup copy is saved beside the file before each day's first change, and names the app's two sheets.
  - **Back** returns to step 1 with the statement still chosen. **Show my investments**, enabled once an option is chosen, remembers the choice and opens Home.
  - When a spreadsheet is already remembered (someone upgrading from version 1.3 or earlier), step 2 is skipped.
- **F4.** Home, the totals: "Your portfolio", then **Worth now** in large type with the statement's currency, the gain or loss since buying (sign, arrow and colour, amount and %), **Invested** and the number of investments.
  - While prices are fetched, the amounts show placeholders, a progress bar moves forward and a line says what is being done (reading the statement, then the spreadsheet for values typed into it, then the listings and prices).
  - Then "Today's prices from Yahoo Finance, <time>" and **Refresh prices**, which fetches again.
  - Totals cover only what has a value (B8). When something is left out, a line says "<names> has (have) no price today, so these totals leave it (them) out."
- **F5.** Home, the investments list: one row per investment held, then a bold **Total**.
  - The investment's name comes first (the user's own, else Yahoo's, else its ticker), with "TICKER · exchange" under it. Many investments scroll with the page; the window keeps its size and long names are cut short.
  - Above the table: "Double-click a name to rename it. Click a heading to sort by it.", a search box ("Search by name or ticker"), **Show** and **Columns**.
  - Columns: Invested, Worth now, Share of total and Gain or loss unless the user chooses others. **Columns** lists, in the table's order, Investment (always shown), Shares, Average cost per share, Price per share, Invested, Worth now, Share of total, Share of invested, Gain or loss, Gain from sales and Dividends received, each with a tick box, and **Reset columns**. The Total adds up what adds up and leaves Shares and the per-share columns empty. Columns that do not fit scroll sideways inside the card.
  - Sorting: clicking a heading sorts by it, numbers largest first and names A to Z; a second click reverses, a third goes back to the usual order (by ticker). An arrow marks the column and direction. Investments without a value in that column come last both ways; the Total stays at the bottom. Hiding the sorted column goes back to the usual order.
  - **Show**: All investments, Gaining (a gain above zero) or Losing (a loss); the button says which ("Show: gaining") and stands out when it is not all. An investment without a price shows only under all. The search keeps the investments whose name or ticker contains what is typed, ignoring case, together with Show. While prices are on their way, every investment is listed.
  - While some are hidden, a line says which are shown ("Showing the 2 of your 3 investments that are gaining." "The Total below covers only these.") with **Show all**, which also empties the search. The Total reads "Total of the 2 shown"; its Share of total is their part of the whole ("82.7 % of all") while each row keeps its own share of the whole. When none are left, the line says "None of your 3 investments match." and there is no Total. "Worth now" at the top always covers the whole portfolio.
  - The columns, the sort and Show are remembered; the search is not. None of them is part of Ctrl+Z (F10). Renaming and entering a value act on the investment clicked, whatever the order or what is shown.
- **F6.** Home, the statement: a card "Your statement" with the statement's file name, "In <its folder>" (the whole path, wrapped if long), "Latest transaction <date>. Anything after it isn't included." and **Use a newer statement…**, "or drop it on this window". For the copy kept from last time, the file named is the one it was copied from; if that file has been moved or deleted since, the card says so and that the app's own copy is used. A copy kept before the app recorded where it came from names no file: its own copy, in the app's folder, would tell the user nothing.
  - A statement chosen or dropped anywhere on Home is read, prices are fetched for it, and it becomes the one kept (F1). One that does not read is explained and the one shown stays.
  - A new statement, **Refresh prices** or closing the window while prices are being fetched stops that fetch: nothing of it is saved or shown.
  - Side by side, the statement and spreadsheet cards share the row's width so that both need about the same height: neither has more than a line of empty space inside, whatever they say.
- **F7.** Home, the spreadsheet: a card with the file's name and one of "Last changed <date>", "Updated today at <time>", "Not updated today", "Ready once today's prices are in" or "It doesn't exist yet: updating creates it.", with **Open folder** and **Update my spreadsheet**.
  - **Update my spreadsheet** writes the values shown, without fetching again; it waits for the prices. Writing does not freeze the window: the card says "Updating your spreadsheet…" with a moving bar, and its buttons and Settings wait. The card then says "Your spreadsheet is up to date" (or "Your spreadsheet was created") in green, with what was written to Current Holdings, whether today's history row was added or updated (or why not, and what it leaves out) and the backup copy's name.
  - A spreadsheet that cannot be saved is said in red: "Your spreadsheet wasn't updated", what happened, what to do and **Copy details**; the values stay shown and the button reads **Try again**.
  - **Open folder** opens the folder the spreadsheet is in, with the file selected where the system allows it.
  - Without a spreadsheet, the card offers **Choose spreadsheet…** and **Create a new one…**. A new one is created as soon as today's prices are in, without pressing **Update my spreadsheet** (until then the card says "It will be created as soon as today's prices are in."); one asked for in Settings is created when Home shows again. An .xlsx dropped on Home becomes the spreadsheet.
  - When backup copies are turned off, the card says so in red.
- **F8.** Values that are not today's from Yahoo:
  - An investment without a value is greyed: its Worth now reads "No price today", its share "Not in the total", and its gain is a button **Enter its value…**. Double-clicking the row does the same.
  - Entering asks "What is <name> worth now?" for the whole investment, in the statement's currency, says how many shares that is and the last price found, and that the value is marked "your value" and kept until Yahoo Finance has a price again. Both 2,040.00 and 2.040,00 read as 2040; anything that is not an amount above zero is explained and asked again.
  - A value entered shows "your value" under it; a last known price shows "price from <date>". Either can be replaced by double-clicking its row.
  - When Yahoo Finance cannot be reached, the totals say so in amber: "Yahoo Finance can't be reached right now, so these values use the last prices found, from <date>.", with **Try again**. The spreadsheet card says updating then writes no history row.
- **F9.** Which listing is it? When the app cannot tell, a dialog "Which one is <ticker>?" says why and lists the listings found: name, exchange, currency and symbol, with "Matches your purchases" on those that fit; the first is chosen. A Yahoo Finance symbol can be typed instead. "From now on, take the first listing without asking" is offered whenever there is a listing. **Use this listing** uses the one chosen (or typed) and remembers it; **Skip this investment** leaves it without a value. While the dialog is open, Home says it is waiting for the user.
- **F10.** Renaming and undoing:
  - Double-clicking an investment's name, or pressing F2 (Return on a Mac) on it, opens it for typing. Enter saves the name, Esc cancels, and an empty name goes back to Yahoo's. The name is saved at once. Double-clicking elsewhere in a row without a price enters a value (F8).
  - Once the spreadsheet has been updated while the app is open, a new name or a value entered is written to it at once, and the card says so again. Before that, nothing is written: the change goes in with the next update.
  - Ctrl+Z and Ctrl+Y undo and redo changes to investments:
    - the history is shared by Home and Settings;
    - each step puts back only what it changed;
    - names and values stay undoable while the app is open;
    - Forget and "Choose the listing next time" stop being undoable once a fetch finishes;
    - the switch, forgetting the statement and backups are not part of it;
    - never during a fetch.
- **F11.** Errors are in plain words: what happened, and what to do.
  - Details can be copied with **Copy details**; no stack trace is shown.
  - **Help** on Home (and **About and privacy** on first launch) shows where the statement comes from (the Revolut steps and All time), the privacy text and the version.
  - Tab reaches every button, field and investment name, with a visible outline; Esc closes dialogs and Enter confirms them.
  - One dialog at a time: a question or a message wanted while another dialog is open waits for it to close, and is never lost.
  - Light and dark follow the system and switch while the app is open, unless Settings says otherwise (G1); the green buttons are #107C41 in light and #33C481 in dark. Everything in the window, tick boxes, menus and scroll bars included, takes the app's colours, never the computer's: the app can be light on a computer in dark mode. So do the window's title bar and frame (drawn by Qt on Linux, by the system on Windows).
  - The window shows the app's icon.
  - Numbers follow the computer's locale, and the currency is the statement's, never assumed. Dates are written in figures in the computer's order with a four-digit year (14/11/2026 in Portugal, 11/14/2026 in the United States), never with month or day names, which would be in the computer's language among English words.
  - The Windows program, its installer and the macOS app show the same icon as the window.

## G. Settings

- **G1.** Settings is a page, reached from Home's **Settings** and left with **← Your portfolio** (first launch when no statement is kept). A side menu of its chapters (Your investments, Your statement, Your spreadsheet, Appearance, About and privacy) stays in place while the page scrolls, marks the chapter being read, and scrolls to a chapter when it is clicked.
  - **Your investments:** every investment the app keeps something about, with its name, "TICKER · symbol, exchange, currency" and a status (Chosen by you, Matched automatically, Asks you next time, Not matched yet, and "value entered by you"). Its **⋯** menu opens under the button, in the app's own colours (light or dark), and offers **Rename**, **Choose the listing next time** and **Forget…** (in red, set apart by a line) (asks first; removes the listing, the name and the value entered). **Forget all investments…** asks first and keeps the spreadsheet, the statement and the last prices. The switch **Take the first listing without asking**. With nothing kept, the list says why. Ctrl+Z takes back the last change (F10).
  - **Your statement:** the file it was read from (as in F6), its latest transaction, **Use a newer one…** and **Forget it…** (asks first; then first launch asks for a statement again). With none kept, it says so.
  - **Your spreadsheet:** its name and folder, **Open folder**, **Choose another…** and **Stop using it**; without one, **Choose spreadsheet…** and **Create a new one…**. **Backup copies to keep**, from 0 to 99, with **−** and **+**.
  - **Appearance:** **Use device theme** (the default), **Light** or **Dark**, applied at once and remembered.
  - **About and privacy:** the version, where new versions are, the privacy text and the disclaimer.
  - Changes are saved at once and show on Home at once.
  - While prices are being fetched, Settings cannot be opened: a fetch reads and saves the same settings.

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
  - a row worked out from the statement kept from last time (F1) has a comment on its date saying so, with the date of the statement's latest transaction. It keeps it on later days. A later run that day with a new statement takes it away.
- **H5.** Backups:
  - before the first change each day to an existing file, a dated copy is saved beside it; later changes that day keep it;
  - no copy is made on the day the app created the file: before that there was nothing to keep;
  - the newest N are kept (default 1: each day's copy replaces the one before); other workbooks' copies and the old one-time copy are never deleted;
  - 0 makes no copy and deletes none;
  - a failed save leaves no new copy and deletes no old one;
  - when none will be made, the spreadsheet card says so in red (F7).
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
  - every statement read is kept as in F1, and without a statement the one kept from last time is used: stderr says so, with the date of its latest transaction. With none kept, it exits with code 2 and says to give one.
- **I4.** The terminal prompt accepts a number, a symbol, or nothing.

## J. Privacy, safety, packaging

- **J1.** Only ticker symbols and dates are sent to Yahoo. Amounts, quantities and the statement are never sent.
- **J2.** Only listings, names, prices per share, settings and a copy of the last statement read with where it was read from (F1) are kept, all in the app's own folder. No amount from the statement is kept anywhere else.
- **J3.** A damaged settings file is explained, not silently reset. Tests never touch the real settings or the network.
- **J4.** The packaged app's smoke test reads the sample offline and writes a spreadsheet.
- **J5.** On Windows, the installer can tell that the app is open.
- **J6.** Installing a newer version over an older one keeps everything: the settings, listings, names, entered values and last prices saved by any earlier version are read and used.
