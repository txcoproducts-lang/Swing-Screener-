# Swing Screener

Nightly swing-trade screener for the S&P 500 + Nasdaq 100 with market and sector breadth.

- Runs automatically every weekday after the close (GitHub Actions, see `.github/workflows/nightly.yml`).
- Results page is published to GitHub Pages (the link is in the repo's About box / Settings → Pages).
- Each day's CSVs (all picks + sector breadth) are saved in `history/`.

**Run it now:** Actions tab → *Nightly screener* → *Run workflow*.

**Change the rules:** edit the `CFG` block at the top of `screener.py` (min volume, delta target, DTE, the Top picks call rules `PK_DTE` / `PK_DELTA` / `PK_OI_OVER`, SMA vs EMA for the 150/200).

**Run on your own PC instead:** `setup_windows.bat` and `run_screener.bat` (in the repo root, next to `screener.py`) set up a local nightly run.

**Paper trading (Oct 6, 2026 to Apr 6, 2027):** two paper accounts start with $1,000 each. *Your system* trades the screener's setups with calls by your rules (15-30 days, delta 0.50-0.80, open interest over 500), or shares when no call fits the budget. *Claude's picks* holds the AI picks list as shares. `paper.py` runs every 30 minutes on market days (`.github/workflows/paper.yml`): it sells and buys at about 10:00 AM New York time, checks stops and targets until the close, and records the closing value. The accounts, with every trade and its reason, are saved on the `paper-trading` branch (`paper/A.json`, `paper/B.json`), and the page shows them as two tiles you can click into. Settings are in the `P` block at the top of `paper.py`. To test without saving: Actions tab → *Paper trading* → *Run workflow* (dry run is ticked by default).

Uptrend rule: EMA10 > EMA20, price > EMA50 and price > the 150-day MA (same rule as the chart shading), liquid stocks only (20-day avg volume ≥ 1M).
Not financial advice.
