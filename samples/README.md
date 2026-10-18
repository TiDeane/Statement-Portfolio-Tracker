# Sample statements

Made-up statements in the format of Revolut's account statement CSV, for trying the app by hand and for the tests. None of them is taken from a real statement. `tests/test_samples.py` checks that each one still does what is described here.

| File | What it is for |
|---|---|
| `revolut_sample.csv` | A short statement: one fund still held, and one bought several times, sold completely and paid a dividend. Used by the offline tests and the packaged app's smoke test. Never use it to check prices against Yahoo: its purchases do not fit any listing's real prices. |
| `long_history.csv` | Four years of monthly top-ups and buys of five funds, with sales of part or all of a holding, buying again after selling everything, and dividends, also on funds sold since. A big table, and a long history to read. |
| `unpriced_investment.csv` | Two investments, one of them (ZQXJ) a ticker Yahoo Finance does not know. Shows "unavailable", "not in total", and entering a value yourself. |
| `unknown_type.csv` | A row of a type the app does not handle (`STOCK SPLIT`, row 4). The app stops and names the row. |
| `incomplete_history.csv` | Not exported with "All time": it sells shares of IUSA that it never bought (row 4). The app stops and asks for the whole history. |

The funds in `long_history.csv` are real ticker codes, but their prices and dates are invented, so no listing fits the purchases: the app shows the listings it found and asks which one each fund is (or choose "Always choose the first option"). That also makes it a way to try the "Confirm your investment" window. Values after that come from Yahoo Finance's current prices, so they will not match the invented purchase prices.

`long_history.csv` was made with `random_statement` in `tests/fakes.py` (seed 2026, 48 months from January 2022).
