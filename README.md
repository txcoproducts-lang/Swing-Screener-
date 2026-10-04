# Swing Screener

Nightly swing-trade screener for the S&P 500 + Nasdaq 100 with market and sector breadth.

- Runs automatically every weekday after the close (GitHub Actions, see `.github/workflows/nightly.yml`).
- Results page is published to GitHub Pages (the link is in the repo's About box / Settings → Pages).
- Each day's CSVs (all picks + sector breadth) are saved in `history/`.

**Run it now:** Actions tab → *Nightly screener* → *Run workflow*.

**Change the rules:** edit the `CFG` block at the top of `screener.py` (min volume, delta target, DTE, SMA vs EMA for the 150/200).

**Run on your own PC instead:** the files in `windows/` set up a local nightly run (put them next to `screener.py`).

Uptrend rule: price > EMA50 and EMA10 > EMA20, liquid stocks only (20-day avg volume ≥ 1M).
Not financial advice.
