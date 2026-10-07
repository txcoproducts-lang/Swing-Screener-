# Swing Screener

Nightly swing-trade screener for the S&P 500 + Nasdaq 100 with market and sector breadth.

- Runs automatically every weekday after the close (GitHub Actions, see `.github/workflows/nightly.yml`).
- Results page is published to GitHub Pages (the link is in the repo's About box / Settings → Pages).
- Each day's CSVs (all picks + sector breadth) are saved in `history/`.

**Run it now:** Actions tab → *Nightly screener* → *Run workflow*.

**Change the rules:** edit the `CFG` block at the top of `screener.py` (min volume, delta target, DTE, the Top picks call rules `PK_DTE` / `PK_DELTA` / `PK_OI_OVER`, SMA vs EMA for the 150/200).

**Breadth over time:** the *Sector breadth* heatmap and the strip under each sector chart show Rising, the share of S&P 500 stocks with the 10 EMA above the 20 (for the S&P 500 and each sector, counting S&P 500 stocks only so each sector matches its SPDR ETF), with the share in the full uptrend as a slower line. An upswing is Rising above its own 10-day average. Under the heatmap, the *Breadth line* chart shows Rising day by day for the S&P 500 or any sector (pick it from the list or tap its heatmap row), with its 5-day and 10-day averages (both exponential), so you can see when it crosses above or below each. Built nightly by `breadth_history()` in `screener.py` from the 2 years of prices it already downloads.

**OVTLYR plan:** the page's *OVTLYR plan* section rebuilds OVTLYR's Plan M, Plan ETF and Plan #SICADFU checks from the screener's data each night, with stand-ins for OVTLYR's private heatmap and signals (listed on the page). Click *Plan M stocks* (or *Plan M is on / off* in its Market box) for every stock that passes Plan M that night. The list is rebuilt each night from the last saved plan: stocks that newly pass are marked New, and stocks that stop passing drop off with the rule they failed. Its settings are the `OV` block in `screener.py`.

**Run on your own PC instead:** `setup_windows.bat` and `run_screener.bat` (in the repo root, next to `screener.py`) set up a local nightly run.

**Paper trading (Oct 6, 2026 to Apr 6, 2027):** four paper accounts start with $1,000 each. *Your system* trades the screener's setups with calls by your rules (15-30 days, delta 0.50-0.80, open interest over 500), or shares when no call fits the budget. *Your system, after 2 PM* (from Oct 7) uses the same rules but only buys after 2:00 PM Central. *Claude's picks* holds the AI picks list as shares. *OVTLYR plan* (from Oct 7) trades OVTLYR's Plan M, Plan ETF and Plan #SICADFU from the page's *OVTLYR plan* section, as shares (`history/ovtlyr_<date>.json`, built by `screener.py` each night). `paper.py` runs every 30 minutes on market days (`.github/workflows/paper.yml`): it sells and buys at about 10:00 AM New York time, checks stops and targets until the close, and records the closing value. The accounts, with every trade and its reason, are saved on the `paper-trading` branch (`paper/A.json` to `D.json`), and the page shows them as tiles you can click into. Settings are in the `P` block at the top of `paper.py`. To test without saving: Actions tab → *Paper trading* → *Run workflow* (dry run is ticked by default).

Uptrend rule: EMA10 > EMA20, price > EMA50 and price > the 150-day MA (same rule as the chart shading), liquid stocks only (20-day avg volume ≥ 1M).

**Overbought rule (yours, from Oct 7, 2026):** nothing overbought gets a setup, a buy signal or a buy. A stock is overbought when its 14-day RSI is over 70, its 20-day CCI is over 100, or its sector's breadth (Rising on the breadth view) is over 75; the whole market is overbought when the S&P 500's breadth is over 75, and then nothing gets one. Such stocks show as *Overbought* in the stock table, with the reason, and are left off New uptrends and Breakout watch; the AI picks list passes them over for open spots; the OVTLYR plan fails the market, a sector or a stock on it; and all four paper accounts check it again on the live price when they buy. Under 30 on RSI or breadth, or under -100 on CCI, is shown as oversold, for information. The levels are `OB_RSI`, `OB_CCI`, `OB_BREADTH` (and the `OS_` ones) in `CFG`; tonight's breadth is saved as `history/breadth_<date>.csv` for the paper accounts.

Not financial advice.
