#!/usr/bin/env python3
"""
Swing-trade screener + market breadth (S&P 500 + Nasdaq 100)

Windows setup (once): put this file, setup_windows.bat and run_screener.bat in one
folder, then double-click setup_windows.bat. It installs the packages, runs the
screener once and schedules it for 4:30 PM Central every weekday.

Manual use:
    python screener.py              -> writes output/latest.html (+ dated copy + CSV)
    python screener.py --demo       -> fake data, just to preview the layout
    python screener.py --no-options -> skip the options-chain step (faster)

Tune your rules in the CFG block below (delta target, DTE, min volume, SMA vs EMA).
"""
import argparse, datetime as dt, io, json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

# ----------------------------------------------------------------- settings
CFG = dict(
    MIN_PRICE=10.0,          # ignore cheap stocks
    MIN_AVG_VOL=1_000_000,   # 20-day avg shares, liquidity for options
    LONG_MA_TYPE="SMA",      # "SMA" or "EMA" for the 150 / 200
    CROSS_DAYS=10,           # "50 recently crossed above 150" window
    # options helper
    OPT_TOP_N=25,            # only look up options for the best N picks
    TARGET_DTE=40,           # days to expiry you like to buy
    DTE_MIN=25, DTE_MAX=60,
    TARGET_DELTA=0.65,       # calls
    MIN_OI=100,
    MAX_SPREAD_PCT=12.0,     # bid/ask spread as % of mid
    RISK_FREE=0.045,
    # options on the Top picks lists (your rules): calls 15-30 days out, delta 0.50-0.80, open interest over 500;
    # each stock shows the one nearest the middle of the delta range
    PK_DTE=(15, 30),
    PK_DELTA=(0.50, 0.80),
    PK_OI_OVER=500,
    # order blocks on the charts; research/ob_backtest.py tested all of these on 1,000 stocks over 10 years
    OB_TYPE="strong",        # classic, strong (best in the test), bos, fvg, volume or lux
    OB_ENTRY="top",          # box runs from the candle's far side to: "top" (whole candle, best), "body" or "mid" (50%)
    # top picks lists: research/picks_backtest.py chose these on 2014-2021 S&P 500 data and checked them on 2022-2026
    NEW_UP="all",            # every stock that turned into an uptrend (no ordering did better), strongest RS first
    NEW_UP_N=50,
    BREAKOUT="tight",        # uptrend within 5% of a 50-day high, tightest first ("squeeze" tied on return, broke out less often)
    BREAKOUT_N=10,
    AI_SCORE="rs",           # AI picks: IBD-style relative strength (see ai_scores for the other versions tested)
    AI_N=10, AI_KEEP=20, AI_CAP=3,   # hold 10, at most 3 per sector; a pick stays while it ranks in the top 20
    AI_TREND_EXIT=False,     # True = also drop a pick on a close below its EMA50 (tested worse)
    AI_MARKET_FILTER=False,  # True = no new picks while SPY is below its 200-day average (tested no better)
    # overbought / oversold, the user's rule (2026-10-07): nothing overbought gets a setup, a buy signal or a buy,
    # anywhere (the setups, the Top picks lists, the OVTLYR plan and all four paper accounts)
    OB_RSI=70, OS_RSI=30,    # 14-day RSI
    CCI_N=20,                # 20-day CCI; it swings around 0 (most days between -100 and +100), so its levels are +-100
    OB_CCI=100, OS_CCI=-100,
    OB_BREADTH=75, OS_BREADTH=30,   # breadth (Rising: the share of stocks with the 10 EMA over the 20 and price over the 50 EMA), market or sector
)

# ----------------------------------------------------------------- universe
ICB_TO_GICS = {"Technology": "Information Technology", "Telecommunications": "Communication Services",
               "Basic Materials": "Materials"}

def get_universe():
    import requests
    hdr = {"User-Agent": "Mozilla/5.0"}

    def tables(url):
        html = requests.get(url, headers=hdr, timeout=30).text
        return pd.read_html(io.StringIO(html))

    sp = tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    tk = sp["Symbol"].str.replace(".", "-", regex=False)
    sectors = dict(zip(tk, sp["GICS Sector"]))
    subs = dict(zip(tk, sp["GICS Sub-Industry"])) if "GICS Sub-Industry" in sp.columns else {}   # for industry strength
    syms = set(sectors)
    sp500 = set(sectors)                 # the breadth view counts S&P 500 stocks only
    for t in tables("https://en.wikipedia.org/wiki/Nasdaq-100"):
        col = next((c for c in ("Ticker", "Symbol") if c in t.columns), None)
        if col and len(t) > 50:
            t[col] = t[col].astype(str).str.replace(".", "-", regex=False)
            syms |= set(t[col])
            scol = next((c for c in t.columns if "Sector" in str(c) or "Industry" in str(c)), None)
            if scol:
                for tk, sec in zip(t[col], t[scol].astype(str)):
                    sectors.setdefault(tk, ICB_TO_GICS.get(sec, sec))
            ucol = next((c for c in t.columns if "Sub" in str(c)), None)
            if ucol:
                for tk, sub in zip(t[col], t[ucol].astype(str)):
                    subs.setdefault(tk, sub)
            break
    return sorted(syms), sectors, subs, sp500


def download(tickers, size=100):
    import time
    import yfinance as yf
    frames = {}
    for i in range(0, len(tickers), size):
        chunk = tickers[i:i + size]
        print(f"  downloading {i + 1}-{i + len(chunk)} of {len(tickers)}", flush=True)
        try:
            df = yf.download(chunk, period="2y", interval="1d", auto_adjust=True,
                             group_by="ticker", threads=True, progress=False)
        except Exception as e:
            print("  batch failed:", e)
            continue
        if df.empty:
            continue
        top = set(df.columns.get_level_values(0))
        for t in chunk:
            if t not in top:
                continue
            d = df[t].dropna(subset=["Close"])
            if len(d) >= 210:
                frames[t] = d[["Open", "High", "Low", "Close", "Volume"]]
        time.sleep(1)
    return frames


def download_with_retry(tickers):
    import time
    frames = download(tickers)
    missing = [t for t in tickers if t not in frames]
    if len(missing) > 20:                 # likely rate-limited; wait and retry in smaller batches
        print(f"  retrying {len(missing)} missing tickers in 60s...")
        time.sleep(60)
        frames.update(download(missing, size=25))
    return frames


def demo_frames(n=80, days=600):
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    frames = {}
    for i in range(n):
        drift = rng.normal(0.0004, 0.0004)
        r = rng.normal(drift, 0.017, days)
        c = 50 * np.exp(np.cumsum(r)) * rng.uniform(0.6, 4)
        o = np.concatenate([[c[0]], c[:-1]]) * (1 + rng.normal(0, 0.004, days))
        hi = np.maximum(o, c) * (1 + rng.uniform(0, 0.012, days)); lo = np.minimum(o, c) * (1 - rng.uniform(0, 0.012, days))
        v = rng.uniform(1.5e6, 9e6, days) * (1 + 0.5 * (rng.random(days) > 0.93))
        frames[f"DEMO{i:02d}"] = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": c, "Volume": v}, index=idx)
    return frames

# ------------------------------------------------------------ sector charts
SECTOR_ETF = {
    "S&P 500": "SPY", "Information Technology": "XLK", "Health Care": "XLV", "Financials": "XLF",
    "Consumer Discretionary": "XLY", "Communication Services": "XLC", "Industrials": "XLI",
    "Consumer Staples": "XLP", "Energy": "XLE", "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB",
}
CHART_BARS = {"D": 130, "W": 104, "M": 120}   # ~6 months daily, 2 years weekly, 10 years monthly


def download_etfs():
    import yfinance as yf
    etfs = list(SECTOR_ETF.values())
    df = yf.download(etfs, period="10y", interval="1d", auto_adjust=True,
                     group_by="ticker", threads=True, progress=False)
    top = set(df.columns.get_level_values(0)) if not df.empty else set()
    return {t: df[t].dropna(subset=["Close"])[["Open", "High", "Low", "Close", "Volume"]] for t in etfs if t in top}


def download_vix():
    """The VIX (Cboe volatility index, ^VIX): daily closes, last 2 years. An extra for the Market tab."""
    import yfinance as yf
    c = yf.Ticker("^VIX").history(period="2y", interval="1d", auto_adjust=False)["Close"].dropna()
    c.index = pd.DatetimeIndex(c.index).tz_localize(None).normalize()
    return c


def demo_vix(days=520):
    rng = np.random.default_rng(7); x = [16.0]
    for _ in range(days - 1):
        x.append(max(9.0, x[-1] + 0.08 * (16 - x[-1]) + rng.normal(0, 1.1) + (8 if rng.random() > 0.995 else 0)))
    return pd.Series(x, index=pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days))


def chart_data(etf_frames):
    """Daily / weekly / monthly OHLC + EMA10/20/50 per sector ETF, as compact lists for the page."""
    out = {}
    for name, etf in SECTOR_ETF.items():
        d = etf_frames.get(etf)
        if d is None or len(d) < 60:
            continue
        tfs = {}
        for tf in ("D", "W", "M"):
            if tf == "D":
                b = d
            else:
                g = d.groupby(d.index.to_period(tf))
                b = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(),
                                  "Close": g.Close.last(), "Volume": g.Volume.sum()})
                b.index = [g_.index[0] for _, g_ in g]          # first trading day of the week / month
            e = {n: ema(b.Close, n) for n in (10, 20, 50)}
            b = b.iloc[-CHART_BARS[tf]:]
            day = [i.strftime("%Y-%m-%d") for i in b.index]
            r2 = lambda s: [round(float(x), 2) for x in s]
            tfs[tf] = dict(t=day, o=r2(b.Open), h=r2(b.High), l=r2(b.Low), c=r2(b.Close),
                           v=[int(x) for x in b.Volume], **{f"e{n}": r2(e[n].iloc[-len(b):]) for n in e})
        out[name] = dict(etf=etf, **tfs)
    return out



# ------------------------------------------------------- per-stock trend charts
STOCK_BARS = {"4H": 300, "D": 1260, "W": 156, "M": 180}  # ~5 months, 5 years (opens on the last year), 3 years, 15 years


def yf_batch(tickers, size=100, **kw):
    import yfinance as yf
    frames = {}
    for i in range(0, len(tickers), size):
        chunk = tickers[i:i + size]
        try:
            df = yf.download(chunk, auto_adjust=True, group_by="ticker", threads=True, progress=False, **kw)
        except Exception as e:
            print("  batch failed:", e)
            continue
        if df.empty:
            continue
        top = set(df.columns.get_level_values(0))
        for t in chunk:
            if t in top:
                d = df[t].dropna(subset=["Close"])
                if len(d):
                    frames[t] = d[["Open", "High", "Low", "Close", "Volume"]]
    return frames


def to_4h(h):
    """Hourly regular-session bars -> two bars per day (09:30-13:30 and 13:30-16:00 New York)."""
    if h.index.tz is not None:
        h = h.tz_convert("America/New_York").tz_localize(None)
    half = (h.index.hour * 60 + h.index.minute >= 13 * 60 + 30).astype(int)
    key = h.index.normalize() + pd.to_timedelta(half * 4, unit="h")
    g = h.groupby(key)
    b = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(),
                      "Close": g.Close.last(), "Volume": g.Volume.sum()})
    b.index = [grp.index[0] for _, grp in g]
    return b


def to_period(d, rule):
    g = d.groupby(d.index.to_period(rule))
    b = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(),
                      "Close": g.Close.last(), "Volume": g.Volume.sum()})
    b.index = [grp.index[0] for _, grp in g]
    return b


def trend_series(b, n_show, intraday=False, blocks=False):
    """OHLC + EMA10/20/50 + 150 MA + trend state (1 up, -1 down, 0 neither) for the last n_show bars.
    Uptrend = EMA10 > EMA20, close > EMA50 and close > 150 MA; downtrend is the mirror image."""
    c = b.Close
    e10, e20, e50 = ema(c, 10), ema(c, 20), ema(c, 50)
    m150 = ema(c, 150) if CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()
    up = (e10 > e20) & (c > e50) & (c > m150)
    dn = (e10 < e20) & (c < e50) & (c < m150)
    tr = up.astype(int) - dn.astype(int)
    k = slice(-n_show, None)
    r2 = lambda s: [None if x != x else round(float(x), 2) for x in s.iloc[k]]
    t = ([int(i.timestamp()) for i in b.index[k]] if intraday else [i.strftime("%Y-%m-%d") for i in b.index[k]])
    return dict(t=t, o=r2(b.Open), h=r2(b.High), l=r2(b.Low), c=r2(c), v=[int(x) for x in b.Volume.iloc[k]],
                e10=r2(e10), e20=r2(e20), e50=r2(e50), m150=r2(m150), tr=[int(x) for x in tr.iloc[k]],
                **({"ob": order_blocks(b, n_show, t)} if blocks else {}))


# ------------------------------------------------------------ order blocks
def _ahead(a, k):
    """a[i + k] lined up with bar i (NaN past the end)."""
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[:len(a) - k] = a[k:]
    return out


def _lux_pivots(h, l, v, p=5):
    """LuxAlgo-style candidates: highest volume of 2p+1 bars, at a swing low (bullish) or high (bearish)."""
    n = len(v)
    pad = np.concatenate([np.full(p, -np.inf), v, np.full(p, -np.inf)])
    piv = (v >= np.lib.stride_tricks.sliding_window_view(pad, 2 * p + 1).max(axis=1)) & (v > 0)
    piv[max(0, n - p):] = False
    hn = np.fmax.reduce(np.vstack([_ahead(h, k) for k in range(1, p + 1)]), axis=0)
    ln = np.fmin.reduce(np.vstack([_ahead(l, k) for k in range(1, p + 1)]), axis=0)
    state, st = np.zeros(n, int), 0
    for i in range(n):
        st = 0 if h[i] > hn[i] else 1 if l[i] < ln[i] else st
        state[i] = st
    return piv & (state == 1), piv & (state == 0)


def _bull_blocks(o, h, l, c, v, a, avgv, kind, lux):
    """Bullish order blocks as (candle, bar where it is confirmed): the last down candle before a
    move that closes 1 ATR (2 for "strong") above its high within 3 bars, plus the extra test of
    each type. Bearish blocks come from the same code run on mirrored prices."""
    if kind == "lux":
        i = np.flatnonzero(lux)
        return i, i + 5
    n = len(c)
    best = np.fmax.accumulate(np.vstack([_ahead(c, k) for k in (1, 2, 3)]), axis=0)   # best close 1, 2, 3 bars on
    cond = best >= h + (2.0 if kind == "strong" else 1.0) * a
    if kind in ("bos", "fvg"):                      # also closes above the last confirmed swing high
        p = 3
        pad = np.concatenate([np.full(p, -np.inf), h, np.full(p, -np.inf)])
        piv = np.flatnonzero(h >= np.lib.stride_tricks.sliding_window_view(pad, 2 * p + 1).max(axis=1))
        piv = piv[piv + p < n]
        sh = np.full(n, np.nan)
        sh[piv + p] = h[piv]
        cond &= best > pd.Series(sh).ffill().to_numpy()
    if kind == "fvg":                               # and leaves a gap between candles 1 and 3 of the move
        g1 = _ahead(l, 2) > h
        cond &= np.vstack([np.zeros(n, bool), g1, g1 | (_ahead(l, 3) > _ahead(h, 1))])
    if kind == "volume":                            # on 1.5x the 20-day average volume
        cond &= np.fmax.accumulate(np.vstack([_ahead(v, k) for k in (1, 2, 3)]), axis=0) >= 1.5 * avgv
    cond &= (c < o) & (_ahead(c, 1) > _ahead(o, 1))
    first = np.where(cond.any(axis=0), cond.argmax(axis=0), -1)
    i = np.flatnonzero(first >= 0)
    return i, i + first[i] + 1


def order_blocks(b, n_show, times):
    """Zones that start inside the shown window: [start, end, top, bottom, side, fresh].
    side 1 = bullish (support), -1 = bearish (resistance). A zone ends where price first comes
    back into it; fresh = 1 if price hasn't come back yet (drawn to the right edge)."""
    kind, entry = CFG["OB_TYPE"], CFG["OB_ENTRY"]
    O, H, L, C, V = (b[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    n = len(C)
    pc = np.concatenate([[np.nan], C[:-1]])
    A = pd.Series(np.fmax(H - L, np.fmax(np.abs(H - pc), np.abs(L - pc)))).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    avgv = pd.Series(V).rolling(20).mean().to_numpy()
    lux = _lux_pivots(H, L, V) if kind == "lux" else (None, None)
    first = max(0, n - n_show)
    zones = []
    for sgn, lx in ((1, lux[0]), (-1, lux[1])):
        o, h, l, c = (O, H, L, C) if sgn > 0 else (-O, -L, -H, -C)
        for i, a in zip(*_bull_blocks(o, h, l, c, V, A, avgv, kind, lx)):
            if i < first or a >= n:
                continue
            p = h[i] if entry == "top" else max(o[i], c[i]) if entry == "body" else (h[i] + l[i]) / 2
            if not c[a] > p:
                continue
            hit = np.flatnonzero(l[a + 1:] <= p)
            end = a + 1 + hit[0] if hit.size else n - 1
            top, bot = (p, l[i]) if sgn > 0 else (-l[i], -p)
            zones.append([times[i - first], times[end - first], round(float(top), 2), round(float(bot), 2),
                          sgn, int(not hit.size)])
    return zones


# ----------------------------------------------------------- 10-year backtest
BT = dict(YEARS=10, STOP=0.08)   # each stock's last 10 years on the user's rules, against holding it and holding SPY


def backtest(d, spy, years=None, br=None, group=None):
    """The user's rules on one stock's daily bars, against buy-and-hold of the stock and of SPY over the same days.
    Buy at the next open after a close with one of the page's setups (Momentum or Pullback, as analyze() finds them)
    that is on the strongest sector, strongest stock list that night, as Your system buys: a Super or Regular setup (EMA10 > EMA20 and price > EMA50; the 150 line not needed since 2026-10-28), its
    sector (br[group]) in an upswing (Rising over its 10-day average) and not over the 75 line, and the market not over
    75 (RSI and CCI aren't checked: the user dropped that part of the overbought rule on 2026-10-15). Sell at the next open after a close with EMA10 under EMA20
    and the price under EMA50 (the user's 4-hour exit, on daily bars: Yahoo keeps only ~2 years of intraday bars), or
    on an 8% drop from the entry (the paper accounts' share stop). Cash earns nothing while out; no costs.
    br: {group: daily Rising / avg} (bt_breadth); days without breadth skip those checks, and a ticker with no group
    (the funds) checks the market only."""
    years = years or BT["YEARS"]
    o, h, l, c = (d[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    if len(c) < 260:
        return None
    C = d["Close"]
    e10, e20, e50 = ema(C, 10), ema(C, 20), ema(C, 50)
    lm = (lambda n: ema(C, n)) if CFG["LONG_MA_TYPE"] == "EMA" else (lambda n: C.rolling(n).mean())
    m150 = lm(150)
    r, a = rsi(C), atr(d)
    hi252 = C.rolling(252, min_periods=200).max()
    prior20 = C.shift().rolling(20).max()
    up = (e10 > e20) & (C > e50)                       # your uptrend without the 150 line: Super over it, Regular under
    ext = (C - e20) / a
    mom = up & r.between(55, 80) & (ext <= 3) & ((C > prior20) | (C >= 0.97 * hi252))
    depth = (C.rolling(15).max() - C) / C.rolling(15).max() * 100
    pull = (C > e50) & (e20 > e50) & (r <= 50) & ((C - e20) / e20 <= 0.02) & (depth >= 3)
    buy = (mom | pull) & up                           # Super and Regular setups (the user, 2026-10-28)
    lim, checked = CFG["OB_BREADTH"], 0
    for g, own in (("S&P 500", False), (group, True)):
        b = (br or {}).get(g) if g else None
        if b is None:
            continue
        b = b.reindex(d.index)
        known = b.rise.notna()
        on = (b.rise.round(1) > b.avg.round(1)) if own else True      # the sector in an upswing, as on the list
        buy &= ~known | (on & ~(b.rise > lim))
        checked = max(checked, int(known.sum()))
    buy = buy.to_numpy()
    sell = ((e10 < e20) & (C < e50)).to_numpy()
    ok = hi252.notna().to_numpy() & m150.notna().to_numpy()
    first = d.index[-1] - pd.DateOffset(years=years)
    s = max(int(np.searchsorted(d.index, first)), int(np.argmax(ok)) if ok.any() else len(c))
    if s >= len(c) - 20:
        return None
    eq, pos, trades, days_in, last = 1.0, None, [], 0, len(c) - 1
    for i in range(s, last + 1):
        if pos is None:
            if buy[i] and i < last:
                pos = (i + 1, o[i + 1])
            continue
        days_in += 1                            # bar i is held: its stop first, then its close for the exit
        stop = pos[1] * (1 - BT["STOP"])
        if l[i] <= stop:
            px, j, why = min(o[i], stop), i, "stop"     # a gap under the stop sells at the open
        elif sell[i] and i < last:
            px, j, why = o[i + 1], i + 1, "exit"
        else:
            continue
        trades.append((pos[0], j, pos[1], px, why))
        eq *= px / pos[1]
        pos = None
    if pos is not None:                         # still holding: marked at the last close
        trades.append((pos[0], last, pos[1], c[-1], "open"))
        eq *= c[-1] / pos[1]
    t0, t1 = d.index[s], d.index[-1]
    sp = spy.loc[(spy.index >= t0) & (spy.index <= t1)] if spy is not None else None
    ds = lambda i: d.index[i].strftime("%Y-%m-%d")
    wins = sum(1 for t in trades if t[3] > t[2])
    return dict(
        start=t0.strftime("%Y-%m-%d"), end=t1.strftime("%Y-%m-%d"), years=round((t1 - t0).days / 365.25, 1),
        rules=round((eq - 1) * 100, 1), hold=round((c[-1] / c[s] - 1) * 100, 1),
        spy=round((float(sp.iloc[-1]) / float(sp.iloc[0]) - 1) * 100, 1) if sp is not None and len(sp) > 1 else None,
        n=len(trades), win=round(wins / len(trades) * 100) if trades else None,
        inmkt=round(days_in / max(1, last + 1 - s) * 100), holding=pos is not None,
        breadth=round(min(1.0, checked / max(1, last + 1 - s)) * 100),       # % of the days with breadth checked
        trades=[[ds(t[0]), ds(t[1]), round(t[2], 2), round(t[3], 2), t[4]] for t in trades])


def bt_breadth(bh):
    """Breadth for the backtests, {group: daily rise / avg}: the 10 years research/plan_backtest.py saves on Saturdays
    (history/breadth_10y.json), with tonight's breadth history (bh, about 2 years) on top for the latest days."""
    out = {}
    f = Path(__file__).resolve().parent / "history" / "breadth_10y.json"
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
        idx = pd.DatetimeIndex(j["dates"])
        out = {g: pd.DataFrame(dict(rise=v["rise"], avg=v["avg"]), index=idx, dtype=float) for g, v in j["groups"].items()}
    except FileNotFoundError:
        pass
    except Exception as e:                  # extras; never lose the backtests over it
        print("  10-year breadth unreadable:", e)
    for g, b in (bh or {}).items():
        new = b[["rise", "avg"]]
        out[g] = new if g not in out else pd.concat([out[g][out[g].index < new.index[0]], new])
    return out


def write_stock_charts(tickers, out, demo=False, known=None, br=None, groups=None):
    """One JSON per ticker (4H / D / W / M), loaded by the chart pop-up on click."""
    if demo:
        fr = demo_frames(n=len(tickers), days=2600)
        daily = {t: (known or {}).get(t, d) for t, d in zip(tickers, fr.values())}   # same prices as the demo table
        monthly = {t: to_period(d, "M") for t, d in daily.items()}
        hourly = {}
        for t, d in daily.items():
            last = d.iloc[-200:]
            idx = [ts + pd.Timedelta(hours=9.5 + i) for ts in last.index for i in range(7)]
            px = np.repeat(last.Close.values, 7) * (1 + np.random.default_rng(1).normal(0, .003, len(idx)))
            op = np.concatenate([[px[0]], px[:-1]])
            hourly[t] = pd.DataFrame({"Open": op, "High": np.maximum(op, px) * 1.002, "Low": np.minimum(op, px) * .998,
                                      "Close": px, "Volume": np.repeat(last.Volume.values / 7, 7)}, index=idx)
    else:
        def fetch(**kw):                    # one retry in small batches for anything Yahoo dropped
            f = yf_batch(tickers, **kw)
            miss = [t for t in tickers if t not in f]
            if miss:
                f.update(yf_batch(miss, size=10, **kw))
            return f
        # 10 years for the backtest plus a year and a half to warm up its averages (the 150-day and the 52-week high)
        daily = fetch(start=(dt.date.today() - dt.timedelta(days=round(365.25 * (BT["YEARS"] + 1.5)))).isoformat(), interval="1d")
        monthly = fetch(period="max", interval="1mo")
        # explicit dates: with period= yfinance starts at the listing date for some recent IPOs (GEV) and Yahoo rejects it
        hourly = fetch(start=(dt.date.today() - dt.timedelta(days=700)).isoformat(), interval="60m")
    dd = out / "data"; dd.mkdir(parents=True, exist_ok=True)
    n, bts = 0, {}
    spy = daily["SPY"]["Close"] if "SPY" in daily else None
    for t in tickers:
        d = daily.get(t)
        if d is None or len(d) < 60:
            continue
        rec = {"D": trend_series(d, STOCK_BARS["D"], blocks=True), "W": trend_series(to_period(d, "W"), STOCK_BARS["W"])}
        try:
            bt = backtest(d, spy, br=br, group=(groups or {}).get(t))
        except Exception as e:              # extras; never lose the chart over it
            print("  backtest failed", t, e)
            bt = None
        if bt:
            rec["bt"] = bts[t] = bt
        if t in monthly and len(monthly[t]) > 20:
            rec["M"] = trend_series(monthly[t], STOCK_BARS["M"])
        if t in hourly and len(hourly[t]) > 60:
            rec["4H"] = trend_series(to_4h(hourly[t]), STOCK_BARS["4H"], intraday=True)
        (dd / f"{t}.json").write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
        n += 1
    return n, bts

# --------------------------------------------------------------- indicators
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def atr(d, n=14):
    pc = d["Close"].shift()
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def cci(d, n=None):
    """Commodity Channel Index: how far the typical price ((high + low + close) / 3) is from its n-day average, in
    units of 0.015 x its mean deviation, so most days land between -100 and +100."""
    n = n or CFG["CCI_N"]
    tp = (d["High"] + d["Low"] + d["Close"]) / 3
    dev = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - tp.rolling(n).mean()) / (0.015 * dev)

def lvl(v, lim):
    """A reading next to its line: whole, or with one decimal when it would round to the line (70.4 -> "70.4")."""
    return f"{v:.1f}" if round(v) == lim else f"{v:.0f}"

def hot(r, c):
    """Why a stock is overbought by RSI or CCI: never, since 2026-10-15. The user dropped the RSI over 70 / CCI over 100
    part of the overbought rule everywhere; only breadth over the 75 line (breadth_hot) blocks now. RSI and CCI stay on
    the page as information (OB / OS tags)."""
    return []

def breadth_hot(sector, br):
    """Overbought breadth, over the 75 line: the market's (sector=None) or one sector's. br: {group: Rising %}, the
    breadth view's numbers (S&P 500 stocks only). Returns the reason, or "" when it isn't."""
    v, lim = br.get(sector or "S&P 500"), CFG["OB_BREADTH"]
    if v is None or v != v or v <= lim:
        return ""
    name = "market" if not sector else SHORT_SECTOR.get(sector, sector)
    return f"{name} breadth {lvl(v, lim)}% is over {lim}"

def overbought(frames, sectors, br):
    """Tonight's overbought stocks by the user's rule: {ticker: (own, sec)}, where own lists the reasons from its RSI /
    CCI and sec is its sector's breadth over the 75 line ("" when it isn't). Stocks with neither are left out."""
    out = {}
    for t, d in frames.items():
        if len(d) <= 3 * CFG["CCI_N"]:
            continue
        own = hot(float(rsi(d["Close"]).iloc[-1]), float(cci(d.tail(3 * CFG["CCI_N"])).iloc[-1]))
        sec = breadth_hot(sectors.get(t), br) if sectors.get(t) else ""
        if own or sec:
            out[t] = (own, sec)
    return out


def analyze(t, d):
    c = d["Close"]
    e10, e20, e50 = ema(c, 10), ema(c, 20), ema(c, 50)
    lm = (lambda s, n: ema(s, n)) if CFG["LONG_MA_TYPE"] == "EMA" else (lambda s, n: s.rolling(n).mean())
    m150, m200 = lm(c, 150), lm(c, 200)
    r, a = rsi(c), atr(d)
    px = c.iloc[-1]
    avgv = d["Volume"].rolling(20).mean().iloc[-1]
    if px < CFG["MIN_PRICE"] or avgv < CFG["MIN_AVG_VOL"] or np.isnan(m200.iloc[-1]):
        return None
    relv = d["Volume"].iloc[-1] / avgv
    hi252 = c.rolling(252, min_periods=200).max().iloc[-1]
    prior20hi = c.shift().rolling(20).max().iloc[-1]
    above = (e50 > m150)
    n = CFG["CROSS_DAYS"]
    crossed = bool(above.iloc[-1] and (~above.iloc[-n - 1:]).any())
    days_since_cross = None
    if above.iloc[-1]:
        flips = (~above)[::-1].values
        days_since_cross = int(np.argmax(flips)) if flips.any() else 999
    atr_pct = a.iloc[-1] / px * 100
    ext = (px - e20.iloc[-1]) / a.iloc[-1]           # extension above 20 EMA in ATRs

    p_e50 = px > e50.iloc[-1]; x1020 = e10.iloc[-1] > e20.iloc[-1]; x2050 = e20.iloc[-1] > e50.iloc[-1]
    p150 = px > m150.iloc[-1]; p200 = px > m200.iloc[-1]; x50150 = e50.iloc[-1] > m150.iloc[-1]
    core = bool(p_e50 and x1020 and p150)             # your uptrend rule (same as the chart shading)

    trend = (20 * p_e50 + 20 * x1020 + 10 * x2050 + 10 * p150 + 10 * p200 + 5 * x50150 + 5 * crossed)

    # ---- momentum breakout. The user's tiers (2026-10-15): a setup with the price over the 150 line is a Super setup, one
    # without it a Regular setup. Since 2026-10-28 both are bought, Super first (the user's call):
    # a Super setup in your full uptrend, or a Regular one with EMA10 > EMA20 and price > EMA50.
    setup, pts = None, 0
    if p_e50 and x1020 and 55 <= r.iloc[-1] <= 80 and ext <= 3.0:
        near_hi = px >= 0.97 * hi252
        brk = px > prior20hi
        if brk or near_hi:
            setup = "Momentum"
            pts = 12 * brk + 6 * near_hi + (8 if relv >= 1.5 else 4 if relv >= 1.2 else 0) \
                + (5 if r.iloc[-1] <= 75 else 0) + (5 if ext <= 2 else 0)
    # ---- oversold pullback inside an uptrend (10>20 may dip, so not required)
    if setup is None and p_e50 and x2050:
        dist20 = (px - e20.iloc[-1]) / e20.iloc[-1]
        dist50 = (px - e50.iloc[-1]) / e50.iloc[-1]
        recent_hi = c.iloc[-15:].max()
        depth = (recent_hi - px) / recent_hi * 100      # % off the 15-day high
        if r.iloc[-1] <= 50 and dist20 <= 0.02 and depth >= 3:
            setup = "Pullback"
            pts = (10 if r.iloc[-1] <= 40 else 6 if r.iloc[-1] <= 45 else 3) \
                + (10 if dist50 <= 0.02 else 6 if dist20 <= 0.005 else 3) \
                + (5 if relv < 0.9 else 0) + (5 if depth <= 10 else 0)
    score = trend * 0.7 + min(pts, 30) if setup else trend * 0.7

    return dict(
        ticker=t, setup=setup, tier=("Super" if p150 else "Regular") if setup else "", score=round(score, 1), close=px,
        open=d["Open"].iloc[-1], chg1d=(px / c.iloc[-2] - 1) * 100,
        chg5d=(px / c.iloc[-6] - 1) * 100, chg1m=(px / c.iloc[-22] - 1) * 100, rsi=r.iloc[-1],
        cci=float(cci(d.tail(3 * CFG["CCI_N"])).iloc[-1]), atr_pct=atr_pct, relvol=relv,
        from_hi=(px / hi252 - 1) * 100,
        vs10=(px / e10.iloc[-1] - 1) * 100, vs20=(px / e20.iloc[-1] - 1) * 100, vs50=(px / e50.iloc[-1] - 1) * 100,
        p150=bool(p150), p200=bool(p200), x1020=bool(x1020), core=core, reg_up=bool(p_e50 and x1020 and not p150),
        cross=crossed, days_since_cross=days_since_cross, brk20=bool(px > prior20hi),
        stack=bool(e10.iloc[-1] > e20.iloc[-1] > e50.iloc[-1] > m150.iloc[-1] > m200.iloc[-1]),
    )

# ------------------------------------------------------------------ breadth
def build_breadth(frames):
    close = pd.DataFrame({t: d["Close"] for t, d in frames.items()}).sort_index()
    vol = pd.DataFrame({t: d["Volume"] for t, d in frames.items()}).reindex(close.index)
    out = {}
    for n in (20, 50, 200):
        sma = close.rolling(n).mean()
        out[f"pct{n}"] = (close > sma).where(sma.notna()).mean(axis=1) * 100
    chg = close.diff()
    adv, dec = (chg > 0).sum(axis=1), (chg < 0).sum(axis=1)
    out["adv"], out["dec"], out["ad_line"] = adv, dec, (adv - dec).cumsum()
    hi, lo = close.rolling(252, min_periods=200).max(), close.rolling(252, min_periods=200).min()
    out["nh"] = ((close >= hi) & hi.notna()).sum(axis=1)
    out["nl"] = ((close <= lo) & lo.notna()).sum(axis=1)
    out["udvol"] = vol.where(chg > 0).sum(axis=1) / vol.where(chg < 0).sum(axis=1).replace(0, np.nan)
    b = pd.DataFrame(out).iloc[-60:].copy()
    b["ad_line"] -= b["ad_line"].iloc[0]
    return b


def sector_breadth(frames, df, sectors):
    close = pd.DataFrame({t: d["Close"] for t, d in frames.items()}).sort_index()
    chg = close.diff().iloc[-1]
    above = {n: (close > close.rolling(n).mean()) for n in (20, 50, 200)}
    hi = close.rolling(252, min_periods=200).max().iloc[-1]
    lo = close.rolling(252, min_periods=200).min().iloc[-1]
    last = close.iloc[-1]
    sec = pd.Series({t: sectors.get(t) or "Other" for t in close.columns})
    rows = []
    for name, tks in sec.groupby(sec).groups.items():
        tks = list(tks)
        liq = df[df.sector == name]
        r = dict(sector=name, stocks=len(tks), liquid=len(liq),
                 uptrend=int(liq.core.sum()),
                 momentum=int((liq.setup == "Momentum").sum()), pullback=int((liq.setup == "Pullback").sum()),
                 adv=int((chg[tks] > 0).sum()), dec=int((chg[tks] < 0).sum()),
                 nh=int((last[tks] >= hi[tks]).sum()), nl=int((last[tks] <= lo[tks]).sum()))
        for n, a in above.items():
            r[f"pct{n}"] = a[tks].iloc[-1].mean() * 100
            r[f"pct{n}_5d"] = a[tks].iloc[-6].mean() * 100
        r["up_pct"] = r["uptrend"] / r["liquid"] * 100 if r["liquid"] else 0
        rows.append(r)
    return pd.DataFrame(rows).sort_values("up_pct", ascending=False).reset_index(drop=True)


def regime(b):
    x = b.iloc[-1]
    votes = [x.pct20 > 50, x.pct50 > 50, x.pct200 > 50, x.nh > x.nl, x.udvol > 1, x.adv > x.dec]
    s = sum(bool(v) for v in votes)
    return ("Strong / risk-on", "good") if s >= 5 else ("Mixed", "mid") if s >= 3 else ("Weak / risk-off", "bad")


# Breadth over time for the S&P 500 and each sector, on S&P 500 stocks only so each sector matches its SPDR ETF.
# Rising = the share of stocks with the 10 EMA above the 20 and the close above the 50 EMA (your rule); uptrend = the share
# passing the full rule; an upswing = Rising above its own 10-day EMA (the same test as the OVTLYR section's breadth).
def breadth_history(frames, sectors, members):
    tks = [t for t in frames if t in members]
    per = lambda f: pd.DataFrame({t: f(frames[t]["Close"]) for t in tks}).sort_index()   # each on its own dates
    C = per(lambda c: c)
    e10, e20, e50 = (per(lambda c, n=n: ema(c, n)) for n in (10, 20, 50))
    m150 = per(lambda c: ema(c, 150) if CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean())
    rise = ((e10 > e20) & (C > e50)).astype(float).where(C.notna())     # your rule (2026-10-15): 10 EMA over the 20, price over the 50 EMA
    up = ((e10 > e20) & (C > e50) & (C > m150)).astype(float).where(C.notna() & m150.notna())
    groups = {"S&P 500": tks}
    for t in tks:
        groups.setdefault(sectors.get(t) or "Other", []).append(t)
    out = {}
    for name, cols in groups.items():
        if name not in SECTOR_ETF or len(cols) < 5:
            continue
        r = rise[cols].mean(axis=1) * 100
        b = pd.DataFrame(dict(rise=r, avg=r.ewm(span=10, adjust=False).mean(), a5=r.ewm(span=5, adjust=False).mean(),
                              up=up[cols].mean(axis=1) * 100))
        r1 = b.rise.round(1)                         # the numbers the page shows; a tie keeps the day before's state
        above = lambda a1: pd.Series(np.where(r1 > a1, 1.0, np.where(r1 < a1, 0.0, np.nan)), index=b.index).ffill().fillna(0.0)
        b["on"], b["on5"] = above(b.avg.round(1)), above(b.a5.round(1))     # Rising above its 10-day / 5-day average
        b.index = pd.DatetimeIndex([pd.Timestamp(i.strftime("%Y-%m-%d")) for i in b.index])
        out[name] = b.iloc[30:]                      # skip the EMA warm-up at the start of the 2 years
    return out


def bzone(v):
    """The user's breadth lines: 2 = overbought (over 75), -1 = oversold (under 30), 0 = in between. Over 75 there is no
    upswing, only overbought (the user's rule)."""
    return 2 if v > CFG["OB_BREADTH"] else -1 if v < CFG["OS_BREADTH"] else 0


def swing_state(b):
    """Tonight's state for one group: Rising, its 10-day average, Uptrend, whether it's an upswing (Rising above the
    average), the day that state began and how many trading days it has lasted; z = its zone (bzone) and zsince the day
    it entered it."""
    on = b.on > 0
    k = int(np.flatnonzero(on.ne(on.shift()).to_numpy())[-1])
    z = b.rise.round(1).map(bzone)
    kz = int(np.flatnonzero(z.ne(z.shift()).to_numpy())[-1])
    x = b.iloc[-1]
    return dict(rise=round(float(x.rise), 1), avg=round(float(x.avg), 1), up=None if x.up != x.up else round(float(x.up), 1),
                on=bool(on.iloc[-1]), since=b.index[k].date().isoformat(), days=len(b) - k, z=int(z.iloc[-1]),
                zsince=b.index[kz].date().isoformat())


def chart_breadth(charts, bh):
    """Adds the breadth strip to each sector chart, lined up on the chart's own bars: daily as is, weekly from each
    week's last day. The monthly charts go back 10 years, past the 2 years of stock prices, so they have none."""
    for name, c in charts.items():
        b = bh.get(name)
        if b is None:
            continue
        wk = b.groupby(b.index.to_period("W")).last()
        for tf in ("D", "W"):
            s = c.get(tf)
            if not s:
                continue
            days = pd.DatetimeIndex(pd.to_datetime(s["t"]))
            src = b.reindex(days) if tf == "D" else wk.reindex(days.to_period("W"))
            for key, col in (("br", "rise"), ("ba", "avg"), ("bu", "up")):
                s[key] = [None if v != v else round(float(v), 1) for v in src[col]]
            s["bs"] = [None if v != v else int(v) for v in src["on"]]          # 1 = upswing, 0 = fading
        c["sw"] = swing_state(b)

# ------------------------------------------------- strongest sector, strongest stock
# The user's rule (2026-10-14): find the strongest sector, then the strongest stock inside it, and only buy when the
# sector is turning around and rising; a move is 40% the market, 40% the sector and 20% the stock. Each part is 0-100:
#   market = the S&P 500's Rising (the breadth view: the share of its stocks with the 10 EMA over the 20 and price over the 50 EMA)
#   sector = the stock's sector's Rising
#   stock  = its relative strength (IBD-style, as the AI picks use) ranked among the liquid stocks in its sector, 100 = strongest
# On the list: a stock in the user's uptrend, in a sector in an upswing (Rising above its 10-day average) that isn't over
# the 75 line, and not overbought itself. Your system and Your system, after 2 PM buy the highest-scoring setup on it.
SS = dict(W_MKT=0.4, W_SEC=0.4, W_STK=0.2, N=25, PER_SECTOR=3)


def ibd_rs(c):
    """IBD-style relative strength from a close series: 40% on the last 3 months, 20% each on 6, 9 and 12."""
    r = lambda n: c.iloc[-1] / c.iloc[-1 - n] - 1 if len(c) > n else np.nan
    return 0.4 * r(63) + 0.2 * r(126) + 0.2 * r(189) + 0.2 * r(252)


def strength(df, frames, bh):
    """Adds the strength score and its parts to df (the liquid stocks): rs, rs_n / rs_of (its rank in its sector),
    ss_mkt / ss_sec / ss_stk (each part's points), strength (the total, 0-100), sec_on (its sector is in an upswing and
    not over the 75 line) and ss_ok (on the list). Also returns the market's and each sector's state for the page."""
    sw = {g: swing_state(b) for g, b in bh.items()}
    m = sw.get("S&P 500")
    df["rs"] = df.ticker.map(lambda t: ibd_rs(frames[t]["Close"]))
    g = df.groupby("sector").rs
    df["rs_n"] = g.rank(ascending=False, method="min")
    df["rs_of"] = g.transform("count")
    pct = g.rank(pct=True, method="max") * 100            # 100 = the strongest in its sector
    rise = df.sector.map(lambda s: sw[s]["rise"] if s in sw else np.nan)
    df["ss_mkt"] = round(SS["W_MKT"] * m["rise"], 1) if m else np.nan
    df["ss_sec"] = (SS["W_SEC"] * rise).round(1)
    df["ss_stk"] = (SS["W_STK"] * pct).round(1)
    df["strength"] = (df.ss_mkt + df.ss_sec + df.ss_stk).round(1)
    df["sec_on"] = df.sector.map(lambda s: bool(s in sw and sw[s]["on"] and sw[s]["z"] != 2))
    reg = df.reg_up & (df.tier == "Regular")                  # a Regular setup (or one left out as overbought)
    df["ss_ok"] = (df.core | reg) & df.sec_on & (df.ob == "") & df.strength.notna() & df.rs.notna()
    return sw


def ss_order(scr):
    """Setups in buying order: on the strongest sector, strongest stock list, highest score first. Screener files from
    before 2026-10-14 have no score, so they keep the stock table's order."""
    s = scr[scr.has_setup.astype(bool)]
    if "ss_ok" not in s:
        return s.reset_index(drop=True), False
    s = s[s.ss_ok.astype(bool)].assign(_sup=s.tier.eq("Super") if "tier" in s else True)      # Super setups first (2026-10-28)
    return s.sort_values(["_sup", "strength"], ascending=False, kind="stable").drop(columns="_sup").reset_index(drop=True), True

# --------------------------------------------------------------- pick lists
# Signals for the three lists at the top of the page (New uptrends, Breakout watch, AI picks).
# research/picks_backtest.py runs this same code on 12 years of S&P 500 data to choose the rules.
def wide(frames, key, idx=None):
    w = pd.DataFrame({t: d[key] for t, d in frames.items()})
    return (w.reindex(idx) if idx is not None else w.sort_index()).astype(float)


def days_since(mask):
    """Trading days since the mask was last True (NaN if never)."""
    i = np.arange(len(mask), dtype=float)[:, None]
    last = pd.DataFrame(np.where(mask.to_numpy(bool), i, np.nan)).ffill().to_numpy()
    return pd.DataFrame(i - last, index=mask.index, columns=mask.columns)


def group_mean(X, ok, labels, min_n=3):
    """Average of X over the liquid stocks in each group (sector, industry), given back per stock."""
    lab = pd.Series(labels, dtype=object).reindex(X.columns).to_numpy()
    g = X.where(ok).T.groupby(lab)
    m = g.mean().T.where(g.count().T >= min_n)
    out = m.reindex(columns=lab)
    out.columns = X.columns
    return out


def zs(X, ok):
    """Cross-sectional z-score among the liquid stocks each day, capped at +-3; missing = 0 (neutral)."""
    x = X.where(ok)
    return x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0).clip(-3, 3).fillna(0).where(ok)


def pick_features(P, sector=None, sub=None):
    """Everything the lists use, as dates x tickers tables. P: wide Open/High/Low/Close/Volume tables;
    sector / sub: ticker -> GICS sector / sub-industry (for industry strength)."""
    O, H, L, C, V = (P[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    pc = C.shift()
    ret = C / pc - 1
    e10, e20, e50 = (C.ewm(span=n, adjust=False).mean() for n in (10, 20, 50))
    m50, m150, m200 = (C.rolling(n).mean() for n in (50, 150, 200))
    tr = np.fmax(H - L, np.fmax((H - pc).abs(), (L - pc).abs()))
    atr_ = tr.ewm(alpha=1 / 14, adjust=False).mean()
    av20 = V.rolling(20).mean()
    up = (e10 > e20) & (C > e50) & (C > m150)                      # your uptrend rule
    F = dict(close=C, up=up, e50=e50, atr=atr_,
             liquid=(C >= CFG["MIN_PRICE"]) & (av20 >= CFG["MIN_AVG_VOL"]) & m200.notna())
    F["new_up"] = up & ~up.shift(fill_value=False)                  # turned into an uptrend today
    F["days_out"] = days_since(up).shift()                          # days it was out of an uptrend before that
    r = lambda n: C / C.shift(n) - 1
    lr = np.log(C).diff()
    F["mom"] = C.shift(21) / C.shift(252) - 1                       # 12-month return, skipping the last month
    F["mom_va"] = F["mom"] / (lr.rolling(252, min_periods=200).std() * np.sqrt(252))
    F["mom6"] = C.shift(21) / C.shift(126) - 1
    F["rs"] = 0.4 * r(63) + 0.2 * r(126) + 0.2 * r(189) + 0.2 * r(252)   # IBD-style relative strength
    F["r5"], F["r21"], F["r63"], F["r126"], F["r252"] = r(5), r(21), r(63), r(126), r(252)
    F["vol"] = lr.rolling(63).std() * np.sqrt(252)
    F["hi52"] = C / C.rolling(252, min_periods=200).max()
    F["lo52"] = C / C.rolling(252, min_periods=200).min()
    share = lambda b: b.astype(float).where(ret.notna()).shift(21).rolling(231, min_periods=200).mean()
    F["smooth"] = np.sign(F["mom"]) * (share(ret > 0) - share(ret < 0))    # steady climbs beat jumpy ones
    if sector is not None:
        sec = group_mean(F["r126"], F["liquid"], sector)
        F["ind"] = (group_mean(F["r126"], F["liquid"], sub) if sub is not None else sec).fillna(sec)
        F["sec_up"] = group_mean(up.astype(float), F["liquid"], sector)
    pg = (O / pc - 1 >= 0.04) & (V >= 2.5 * av20.shift()) & (C >= O)   # gap up 4%+ on 2.5x volume that held
    F["pgap"] = (C > L.where(pg).ffill(limit=39)).astype(float)         # ...in the last 40 days, still above that day's low
    upv, dnv = V.where(ret > 0, 0).rolling(50).sum(), V.where(ret < 0, 0).rolling(50).sum()
    F["accum"] = np.log((upv + 1) / (dnv + 1))                          # up-day vs down-day volume, 50 days
    piv = H.rolling(50).max()                                           # breakout level: the 50-day high
    F["piv"] = piv
    F["base_days"] = days_since(H >= piv)                              # days since that high was set
    F["dist"] = (piv - C) / C                                           # how far below it
    F["depth"] = (piv - L.rolling(50).min()) / piv
    F["tight"] = (H.rolling(10).max() - L.rolling(10).min()) / C        # 10-day range
    F["vcp"] = tr.rolling(10).mean() / tr.rolling(50).mean()           # daily ranges shrinking
    F["dry"] = V.rolling(10).mean() / V.rolling(50).mean()             # volume drying up
    F["hl"] = L.rolling(10).min() / L.shift(10).rolling(20).min() - 1   # higher lows
    F["clv"] = ((C - L) / (H - L).where(H > L)).fillna(0.5).rolling(5).mean()   # closing near the highs
    bbw = C.rolling(20).std() / C.rolling(20).mean()
    F["squeeze"] = bbw / bbw.rolling(126).min()                         # 1 = tightest Bollinger width in 6 months
    F["template"] = ((C > m50) & (m50 > m150) & (m150 > m200) & (m200 > m200.shift(21))
                     & (F["lo52"] >= 1.3) & (F["hi52"] >= 0.75))        # Minervini's trend template
    F["ext"] = (C - e20) / atr_
    F["relvol"] = V / av20
    return F


def ai_scores(F, ok):
    """AI score versions (higher = better), each as (description, dates x tickers score). CFG AI_SCORE picks one.
    Single signals rank by their percentile among liquid stocks: a capped z-score would tie the strongest stocks."""
    z = lambda k: zs(F[k], ok)
    pct = lambda k: F[k].where(ok).rank(axis=1, pct=True)
    core = z("mom_va") + z("hi52") + z("ind")
    return {
        "mom": ("12-month momentum (skip the last month)", pct("mom")),
        "mom_va": ("Momentum per unit of volatility", pct("mom_va")),
        "hi52": ("Closeness to the 52-week high", pct("hi52")),
        "rs": ("IBD-style relative strength", pct("rs")),
        "core": ("Momentum/vol + 52w high + industry strength", core),
        "core_smooth": ("Core + steady climb", core + z("smooth")),
        "core_smooth_gap": ("Core + steady climb + recent power gap", core + z("smooth") + z("pgap")),
    }


def new_up_lists(F, ok, ai):
    """New uptrend list versions: (description, candidates, ranking or None for all). CFG NEW_UP picks one."""
    cand = F["new_up"] & ok
    return {
        "all": ("Every new uptrend", cand, None),
        "rs": ("Strongest relative strength first", cand, F["rs"]),
        "hi52": ("Closest to the 52-week high first", cand, F["hi52"]),
        "relvol": ("Highest volume on the day it turned", cand, F["relvol"]),
        "ai": ("Best AI score first", cand, ai),
        "fresh": ("Out of an uptrend for 20+ days, then relative strength", cand & (F["days_out"] >= 20), F["rs"]),
        "sector": ("Strongest sector first", cand, F["sec_up"] + 0.001 * zs(F["rs"], ok)),
    }


def breakout_lists(F, ok):
    """Breakout watch versions: (description, candidates, ranking). CFG BREAKOUT picks one."""
    z = lambda k: zs(F[k], ok)
    near = ok & (F["dist"] <= 0.05) & (F["base_days"] >= 5)          # within 5% of a 50-day high set 5+ days ago
    tight = -z("tight") - z("vcp") - z("dry") - z("dist")
    return {
        "all": ("Every stock within 5% of its 50-day high", near, None),
        "near": ("Closest to the breakout level", near, -F["dist"]),
        "tight": ("Uptrend + tightest range, shrinking ranges, drying volume, closest", near & F["up"], tight),
        "tight_rs": ("Same + relative strength", near & F["up"], tight + z("rs")),
        "template": ("Minervini trend template, strongest RS first", near & F["template"], F["rs"]),
        "squeeze": ("Uptrend + Bollinger squeeze, strongest RS first", near & F["up"] & (F["squeeze"] <= 1.15), F["rs"]),
    }


def ai_step(held, score, sector, n=10, keep=30, cap=3, allow_new=True, sell=(), skip=()):
    """One night of the AI picks list. held: the current picks; score: today's AI score for every liquid
    stock (Series). A pick stays while it ranks in the top `keep` and isn't in `sell`; open slots go to
    the best-ranked stocks not in `skip` (overbought tonight), at most `cap` per sector. Returns (kept, added, dropped)."""
    order = score.dropna().sort_values(ascending=False, kind="stable").index[:keep]
    top = set(order)
    kept = [t for t in held if t in top and t not in sell]
    dropped = [t for t in held if t not in kept]
    grp = lambda t: sector.get(t) if isinstance(sector.get(t), str) and sector.get(t) else t
    added = []
    if allow_new:
        cnt = Counter(grp(t) for t in kept)
        for t in order:
            if len(kept) + len(added) >= n:
                break
            if t not in kept and t not in dropped and t not in sell and t not in skip and cnt[grp(t)] < cap:
                added.append(t)
                cnt[grp(t)] += 1
    return kept, added, dropped


def ai_update(prev, score, sector, close, spy_now, asof, present, sell=(), allow_new=True, skip=()):
    """Step the saved AI picks list once per trading day. State: {as_of, picks, closed}; each pick keeps
    the day it was added and that day's close (and SPY's) so the page can show how it has done."""
    st = prev if prev and prev.get("picks") is not None else dict(as_of=None, picks=[], closed=[])
    if st.get("as_of") == asof:                       # already stepped for this day (a re-run)
        return st
    old = {p["ticker"]: p for p in st["picks"]}
    gone = [t for t in old if t not in present]       # no prices tonight: hold, don't guess
    kept, added, dropped = ai_step([t for t in old if t in present], score, sector, n=CFG["AI_N"] - len(gone),
                                   keep=CFG["AI_KEEP"], cap=CFG["AI_CAP"], allow_new=allow_new, sell=sell, skip=skip)
    px = lambda t: round(float(close[t]), 2)
    spy = round(float(spy_now), 2) if spy_now == spy_now and spy_now is not None else None
    closed = list(st.get("closed", []))
    for t in dropped:
        why = (f"closed below its 50-day EMA" if t in sell else f"fell out of the top {CFG['AI_KEEP']}"
               if t in score.index else "no longer passes the liquidity filter")
        closed.append(dict(old[t], dropped=asof, out=px(t), spy_out=spy, why=why))
    picks = [old[t] for t in kept + gone] + [dict(ticker=t, added=asof, price=px(t), spy=spy) for t in added]
    return dict(as_of=asof, picks=picks, closed=closed)


def pick_lists(frames, sectors, subs, spy, prev, demo=False, step=True, ob=None, mkt_hot=""):
    """The three lists for tonight. Returns (lists for the page, new AI picks state).
    step=False (a run before the close) shows the saved AI picks without changing them.
    The user's overbought rule: ob = {ticker: why} for stocks overbought tonight, left off New uptrends and Breakout
    watch and never added to the AI picks; mkt_hot = why the whole market is overbought (then all three add nothing)."""
    ob = ob or {}
    idx = pd.DatetimeIndex(sorted(set().union(*(d.index for d in frames.values()))))
    P = {k: wide(frames, k, idx) for k in ("Open", "High", "Low", "Close", "Volume")}
    F = pick_features(P, sectors, subs)
    ok = F["liquid"]
    asof = idx[-1].date().isoformat()
    last = {k: v.iloc[-1] for k, v in F.items()}
    pr = lambda k: F[k].where(ok).rank(axis=1, pct=True).iloc[-1]       # percentile among liquid stocks today
    rs, c, c1 = pr("rs"), last["close"], F["close"].iloc[-2]

    v1, v5 = P["Volume"].iloc[-1], P["Volume"].iloc[-5:].sum(min_count=5)    # shares: last day, last 5 days

    def row(t, **kw):
        return dict(ticker=t, sector=sectors.get(t) or "", close=float(c[t]), chg1d=float(c[t] / c1[t] - 1) * 100,
                    rs=int(round(float(rs[t]) * 99)) if rs[t] == rs[t] else None,
                    from_hi=float(last["hi52"][t] - 1) * 100 if last["hi52"][t] == last["hi52"][t] else None,
                    vol1=float(v1[t]), vol5=float(v5[t]), **kw)

    ranked = lambda score, cand: score.iloc[-1].where(cand.iloc[-1]).dropna().sort_values(ascending=False, kind="stable")
    A = ai_scores(F, ok)
    ai = A[CFG["AI_SCORE"]][1]

    desc, cand, rank = new_up_lists(F, ok, ai)[CFG["NEW_UP"]]
    tks = list(ranked(rank if rank is not None else F["rs"], cand).index)       # the whole list is shown strongest RS first
    cool = lambda ts: [] if mkt_hot else [t for t in ts if t not in ob]
    hot_out = lambda ts: [] if mkt_hot else [dict(ticker=t, why=ob[t]) for t in ts if t in ob]
    nu = dict(desc=desc, total=int((F["new_up"].iloc[-1] & ok.iloc[-1]).sum()), hot=hot_out(tks), rows=[
        row(t, days_out=None if last["days_out"][t] != last["days_out"][t] else int(last["days_out"][t]),
            relvol=float(last["relvol"][t])) for t in cool(tks)[:CFG["NEW_UP_N"]]])

    desc, cand, rank = breakout_lists(F, ok)[CFG["BREAKOUT"]]
    s = ranked(rank, cand)
    bo = dict(desc=desc, total=int(cand.iloc[-1].sum()), hot=hot_out(s.index[:CFG["BREAKOUT_N"]]), rows=[
        row(t, piv=float(last["piv"][t]), dist=float(last["dist"][t]) * 100, base_days=int(last["base_days"][t]),
            tight=float(last["tight"][t]) * 100, dry=float(last["dry"][t])) for t in cool(s.index)[:CFG["BREAKOUT_N"]]])

    score = ai.iloc[-1].dropna()
    present = set(c.dropna().index)
    sell = set(c.index[(c < last["e50"]).to_numpy(bool)]) if CFG["AI_TREND_EXIT"] else set()
    spy_now = float(spy.iloc[-1]) if spy is not None and len(spy) else float("nan")
    market_ok = True
    if CFG["AI_MARKET_FILTER"] and spy is not None and len(spy) > 200:
        market_ok = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
    st = (ai_update(prev, score, sectors, c, spy_now, asof, present, sell, market_ok and not mkt_hot, set(ob)) if step else
          prev if prev and prev.get("picks") is not None else dict(as_of=None, picks=[], closed=[]))
    rank_now = score.rank(ascending=False, method="first")
    ind = pr("ind") if "ind" in F else None
    ai_rows = []
    for p in st["picks"]:
        t = p["ticker"]
        why = []
        if t in rank_now.index:
            ok3, ok12 = last["r63"][t] == last["r63"][t], last["r252"][t] == last["r252"][t]
            if ok3 or ok12:
                why.append(" and ".join(([f"{last['r63'][t] * 100:+.0f}% in 3 months"] if ok3 else [])
                                        + ([f"{last['r252'][t] * 100:+.0f}% in 12"] if ok12 else [])))
            h = last["hi52"][t]
            if h == h:
                why.append("at its 52-week high" if h >= 0.995 else f"{(1 - h) * 100:.0f}% below its 52-week high")
            if ind is not None and ind[t] == ind[t] and ind[t] >= 0.8:
                why.append(f"strong industry ({subs.get(t) or sectors.get(t) or 'its group'})")
        now = float(c[t]) if t in c.index and c[t] == c[t] else None
        old_pick = p["added"] < asof                         # picked today: nothing to measure yet
        ai_rows.append(row(t, added=p["added"], price=p["price"], now=now, ob=ob.get(t, ""),
                           ret=(now / p["price"] - 1) * 100 if now and old_pick else None,
                           spy_ret=(spy_now / p["spy"] - 1) * 100 if p.get("spy") and spy_now == spy_now and old_pick else None,
                           rank=int(rank_now[t]) if t in rank_now.index else None, why=why) if t in c.index else
                       dict(ticker=t, sector=sectors.get(t) or "", added=p["added"], price=p["price"], why=["no prices tonight"]))
    ai_rows.sort(key=lambda r: r.get("rank") or 999)
    track = []
    for p in st["closed"]:
        track.append(((p["out"] / p["price"] - 1) * 100, (p["spy_out"] / p["spy"] - 1) * 100 if p.get("spy") and p.get("spy_out") else None))
    for r in ai_rows:
        if r.get("ret") is not None:
            track.append((r["ret"], r.get("spy_ret")))
    ai_list = dict(desc=A[CFG["AI_SCORE"]][0], rows=ai_rows, market_ok=market_ok, as_of=st["as_of"], step=step,
                   dropped=[p for p in st["closed"] if p["dropped"] == asof], since=min(
                       [p["added"] for p in st["picks"]] + [p["added"] for p in st["closed"]], default=asof), track=track)
    return dict(asof=asof, nu=nu, bo=bo, ai=ai_list, mkt_hot=mkt_hot), st

# -------------------------------------------------------------- OVTLYR plan
# OVTLYR's Plan M (stocks), Plan ETF (TQQQ / SPXL) and Plan #SICADFU (SGOV), from the trading-plan deck the user shared
# on 2026-10-07, rebuilt from data this screener already has. OVTLYR's fear & greed heatmap and its buy / sell signals
# are private, so these stand in for them: heatmap = 14-day RSI (0-100, high = greedy); buy signal = the 10 EMA
# crossing above the 20 EMA, good for 5 trading days as in the deck; sell signal = the 10 EMA under the 20 EMA;
# breadth ("bull list %") = the share of stocks with the 10 EMA above the 20 EMA, against its own 10-day EMA.
# Left out: OVTLYR channels, the deck's per-stock backtest check and option rolls. paper.py's account D trades it.
OV = dict(
    SIGNAL_DAYS=5,             # a stock's buy signal counts for this many trading days
    HEAT_MAX=70,               # SPY and sector heatmaps must be under this, and rising
    OB_GAP=0.02,               # stay more than 2% away from any untouched order block
    PRICE=(10.0, 350.0),       # stock price range (in the deck: for option availability and pricing)
    EXCLUDE=("Health Care",),  # permanently excluded in the deck
    EARN_DAYS=4,               # buy only with at least this many days to earnings
    ETF={"TQQQ": "QQQ", "SPXL": "SPY"},   # Plan ETF buys the 3x fund on its index's signals
    ZONE_ATR=2.0,              # Plan ETF value zone: from the 20 EMA to 2 ATR above it
    ETF_OB_AGE=30,             # Plan ETF only minds order blocks at least 30 calendar days old
    HOT_ATR=3.0,               # Plan ETF exit: a close more than 3 ATR above the 20 EMA
)


_HK = None
def hk(k):
    """The collapsed "How to read this" key under a section's heading (page_keys.py, shared with the crypto page)."""
    global _HK
    if _HK is None:
        import page_keys
        _HK = page_keys.page_keys("stock", CFG, OV)
    return _HK.get(k, "")


def hk_css():
    import page_keys
    return page_keys.CSS


def ov_blocks(d):
    """Order blocks in one daily frame (the chart's definition): bot, top, side (1 bullish, -1 bearish),
    start / end dates and fresh (price hasn't come back to it yet)."""
    days = [i.date() for i in d.index]
    return [dict(bot=z[3], top=z[2], side=z[4], start=z[0], end=z[1], fresh=bool(z[5]))
            for z in order_blocks(d, len(d), days)]


def ob_near(blocks, px, asof, gap=None, min_age=0):
    """The nearest untouched block (at least min_age days old) within `gap` of the price, or containing it:
    (distance, block), or None when every block is farther away."""
    gap = OV["OB_GAP"] if gap is None else gap
    best = None
    for b in blocks:
        if not b["fresh"] or (asof - b["start"]).days < min_age:
            continue
        dist = 0.0 if b["bot"] <= px <= b["top"] else b["bot"] / px - 1 if px < b["bot"] else 1 - b["top"] / px
        if dist <= gap and (best is None or dist < best[0]):
            best = (dist, b)
    return best


def ob_above(blocks, px):
    """The bottom of the nearest untouched block above the price, where a rise runs into old sellers."""
    lv = [b["bot"] for b in blocks if b["fresh"] and b["bot"] > px]
    return min(lv) if lv else None


def ob_hit(blocks, last, min_age=0):
    """A bearish block that price came back to for the first time on the last bar (`last`, a date)."""
    for b in blocks:
        if b["side"] < 0 and not b["fresh"] and b["end"] == last and (last - b["start"]).days >= min_age:
            return b
    return None


def idx_state(d):
    """SPY or QQQ tonight: close, high, 10 / 20 / 50-day EMAs, RSI today and the day before, CCI, ATR."""
    c = d["Close"]
    e = {n: ema(c, n).iloc[-1] for n in (10, 20, 50)}
    r = rsi(c)
    return dict(date=d.index[-1].date().isoformat(), close=round(float(c.iloc[-1]), 2), high=round(float(d["High"].iloc[-1]), 2),
                e10=round(float(e[10]), 2), e20=round(float(e[20]), 2), e50=round(float(e[50]), 2),
                rsi=round(float(r.iloc[-1]), 1), rsi_prev=round(float(r.iloc[-2]), 1), atr=round(float(atr(d).iloc[-1]), 2),
                cci=round(float(cci(d.tail(3 * CFG["CCI_N"])).iloc[-1]), 1))


def ovtlyr_plan(frames, sectors, spy, qqq, earn=None, prev=None, br=None, hot_own=None):
    """Tonight's OVTLYR plan: the market and sector checks, Plan ETF's checks and sell signals, and the Plan M setups
    (stocks passing every stock and sector rule, freshest signal first). frames: the universe's daily bars; spy / qqq:
    daily bars; earn: a function giving next earnings dates for a list of tickers (None skips that check); prev: the
    last saved plan, so the Plan M list shows which stocks are new and why any of the last list's stocks left.
    The user's overbought rule on top of the plan: br = tonight's breadth view numbers ({group: Rising %}); the market or
    a sector over the 75 line fails its check; hot_own = {ticker: why} for stocks with RSI over 70 or CCI over 100."""
    br, hot_own = br or {}, hot_own or {}
    mkt_hot = breadth_hot(None, br)
    idx = pd.DatetimeIndex(sorted(set().union(*(d.index for d in frames.values()))))
    C, H, L, V = (wide(frames, k, idx) for k in ("Close", "High", "Low", "Volume"))
    e10, e20, e50 = (ema(C, n) for n in (10, 20, 50))
    R = rsi(C)
    pc = C.shift()
    A = np.fmax(H - L, np.fmax((H - pc).abs(), (L - pc).abs())).ewm(alpha=1 / 14, adjust=False).mean()
    bull = (e10 > e20).where(C.notna() & e20.notna())               # the "bull list": 10 EMA above the 20 EMA
    asof = idx[-1].date()

    def f0(v, *vs):
        """A value for the page: whole, or with one decimal when it would read the same as one it's compared with."""
        return f"{v:.1f}" if any(round(v) == round(x) for x in vs) else f"{v:.0f}"

    def breadth(cols):
        """Tonight's share of these stocks on the bull list, and its 10-day EMA."""
        p_ = bull[cols].mean(axis=1) * 100
        return float(p_.iloc[-1]), float(p_.ewm(span=10, adjust=False).mean().iloc[-1])

    # market: all four must hold for new Plan M trades
    s = idx_state(spy)
    bp, be = breadth(list(C.columns))
    heat_ok = s["rsi"] < OV["HEAT_MAX"] and s["rsi"] > s["rsi_prev"]
    checks = [
        dict(k="heat", ok=heat_ok, text=f"SPY heatmap (RSI) {f0(s['rsi'], s['rsi_prev'], OV['HEAT_MAX'])}, "
                                        f"{'up' if s['rsi'] > s['rsi_prev'] else 'down'} from {f0(s['rsi_prev'], s['rsi'])} "
                                        f"(needs under {OV['HEAT_MAX']} and rising)"),
        dict(k="signal", ok=s["e10"] > s["e20"], text=f"SPY buy signal: 10 EMA {s['e10']:.2f} {'above' if s['e10'] > s['e20'] else 'below'} "
                                                     f"the 20 EMA {s['e20']:.2f}"),
        dict(k="trend", ok=s["e10"] > s["e20"] and s["close"] > s["e50"],
             text=f"SPY 10/20/50 uptrend: close {s['close']:.2f} {'above' if s['close'] > s['e50'] else 'below'} the 50 EMA {s['e50']:.2f}"
                  + ("" if s["e10"] > s["e20"] else ", 10 EMA under the 20")),
        dict(k="breadth", ok=bp > be, text=f"Market breadth: {f0(bp, be)}% of stocks have the 10 EMA above the 20, "
                                           f"{'above' if bp > be else 'below'} its 10-day average of {f0(be, bp)}%"),
    ]
    hot_check = None
    if "S&P 500" in br:
        v, lim = br["S&P 500"], CFG["OB_BREADTH"]
        hot_check = dict(k="hot", ok=not mkt_hot, text=f"Your overbought rule: {lvl(v, lim)}% of S&P 500 stocks rising, "
                                                       + (f"over the {lim} line" if mkt_hot else f"not over the {lim} line"))
        checks.append(hot_check)
    market = dict(ok=all(c["ok"] for c in checks), checks=checks, spy=s, breadth=dict(pct=round(bp, 1), ema=round(be, 1)))

    # sectors: breadth above its 10-day average, average RSI above SPY's, under 70 and rising; Health Care is out
    groups = {}
    for t in C.columns:
        groups.setdefault(sectors.get(t) or "Other", []).append(t)
    secs = {}
    for name, cols in sorted(groups.items()):
        if len(cols) < 5:
            continue
        p_, e_ = breadth(cols)
        r_, rp = float(R[cols].iloc[-1].mean()), float(R[cols].iloc[-2].mean())
        miss = []
        if name in OV["EXCLUDE"]:
            miss.append("excluded in the plan")
        if breadth_hot(name, br):
            miss.append(f"overbought by your rule: {lvl(br[name], CFG['OB_BREADTH'])}% of its S&P 500 stocks rising, over "
                        f"the {CFG['OB_BREADTH']} line")
        if p_ <= e_:
            miss.append(f"breadth {f0(p_, e_)}% not above its 10-day average {f0(e_, p_)}%")
        if r_ <= s["rsi"]:
            miss.append(f"RSI {f0(r_, s['rsi'])} not above SPY's {f0(s['rsi'], r_)}")
        if r_ >= OV["HEAT_MAX"]:
            miss.append(f"RSI {f0(r_, OV['HEAT_MAX'])} not under {OV['HEAT_MAX']}")
        if r_ <= rp:
            miss.append(f"RSI {f0(r_, rp)} not rising (was {f0(rp, r_)})")
        secs[name] = dict(ok=not miss, n=len(cols), bull=round(p_, 1), bull_ema=round(e_, 1), rsi=round(r_, 1),
                          rsi_prev=round(rp, 1), miss=miss)

    # Plan M stocks: buy signal in the last 5 trading days, 10/20/50 uptrend, price over the 10 EMA, RSI rising,
    # $10-$350, 1M+ shares a day, in a passing sector, more than 2% from any order block, 4+ days before earnings
    cross = (e10 > e20) & ~(e10.shift() > e20.shift())
    age = days_since(cross).iloc[-1]
    c_ = C.iloc[-1]
    av = V.rolling(20).mean().iloc[-1]
    lo, hi = OV["PRICE"]
    liquid = c_.notna() & (av >= CFG["MIN_AVG_VOL"]) & (c_ >= CFG["MIN_PRICE"])
    sig = liquid & c_.between(lo, hi) & (age <= OV["SIGNAL_DAYS"] - 1)
    rules = (sig & (e10.iloc[-1] > e20.iloc[-1]) & (c_ > e50.iloc[-1]) & (c_ > e10.iloc[-1]) & (R.iloc[-1] > R.iloc[-2]))
    in_sec = [t for t in rules.index[rules.to_numpy(bool)] if secs.get(sectors.get(t) or "Other", {}).get("ok")]
    cool = [t for t in in_sec if t not in hot_own]                   # the user's overbought rule
    n_back = lambda n: C.iloc[-1] / C.iloc[-1 - n] - 1 if len(C) > n else np.nan
    rs = (0.4 * n_back(63) + 0.2 * n_back(126) + 0.2 * n_back(189) + 0.2 * n_back(252)).where(liquid).rank(pct=True)
    clear, near_n = [], 0
    for t in cool:
        blocks = ov_blocks(frames[t])
        if ob_near(blocks, float(c_[t]), asof):
            near_n += 1
            continue
        clear.append((t, ob_above(blocks, float(c_[t]))))
    dates = earn([t for t, _ in clear]) if earn and clear else {}
    entry = (pd.Timestamp(asof) + pd.offsets.BDay(1)).date()       # the account buys the next market day
    setups, earn_n = [], 0
    for t, up in clear:
        e = dates.get(t)
        if e and (dt.date.fromisoformat(e) - entry).days < OV["EARN_DAYS"]:
            earn_n += 1
            continue
        k = int(age[t])
        setups.append(dict(ticker=t, sector=sectors.get(t) or "", close=round(float(c_[t]), 2),
                           e10=round(float(e10[t].iloc[-1]), 2), e20=round(float(e20[t].iloc[-1]), 2), e50=round(float(e50[t].iloc[-1]), 2),
                           rsi=round(float(R[t].iloc[-1]), 1), rsi_prev=round(float(R[t].iloc[-2]), 1),
                           atr=round(float(A[t].iloc[-1]), 2), age=k, cross=idx[-1 - k].date().isoformat(),
                           ob_up=round(up, 2) if up else None, earn=e, rs=int(round(rs[t] * 99)) if rs[t] == rs[t] else None,
                           vol=int(av[t])))
    setups.sort(key=lambda x: (x["age"], -(x["rs"] or 0)))

    def why_out(t):
        """The first Plan M rule that a stock from the last list fails tonight, in the funnel's order."""
        if t not in C.columns or c_[t] != c_[t]:
            return "no price tonight (it may have left the S&P 500 / Nasdaq 100)"
        px = float(c_[t])
        if not av[t] >= CFG["MIN_AVG_VOL"]:
            return "volume fell under 1M shares a day (20-day average)"
        if not lo <= px <= hi:
            return f"price {px:.2f} is outside ${lo:.0f}-${hi:.0f}"
        x10, x20, x50 = (float(x[t].iloc[-1]) for x in (e10, e20, e50))
        if x10 <= x20:
            return "sell signal: the 10 EMA fell under the 20"
        if age[t] != age[t]:
            return "no recent buy signal"
        if age[t] > OV["SIGNAL_DAYS"] - 1:
            return f"its buy signal from {md(idx[-1 - int(age[t])].date())} has used up its {OV['SIGNAL_DAYS']} trading days"
        if px <= x50:
            return f"closed {px:.2f}, under the 50 EMA ({x50:.2f})"
        if px <= x10:
            return f"closed {px:.2f}, under the 10 EMA ({x10:.2f})"
        r0, r1 = float(R[t].iloc[-1]), float(R[t].iloc[-2])
        if not r0 > r1:
            return f"RSI stopped rising ({f0(r0, r1)}, from {f0(r1, r0)})"
        sec = sectors.get(t) or "Other"
        v = secs.get(sec)
        if not v or not v["ok"]:
            return f"its sector, {sec}, stopped passing" + (f": {v['miss'][0]}" if v and v["miss"] else "")
        if t in hot_own:
            return f"overbought by your rule: {hot_own[t]}"
        near = ob_near(ov_blocks(frames[t]), px, asof)
        if near:
            return f"within {OV['OB_GAP']:.0%} of an order block ({near[1]['bot']:.2f}-{near[1]['top']:.2f})"
        e = dates.get(t)
        if e and (dt.date.fromisoformat(e) - entry).days < OV["EARN_DAYS"]:
            return f"earnings on {md(e)}, too close to buy"
        return "no longer passes every rule"

    # the Plan M list from one night to the next: when each stock joined, and why any of the last list's stocks left
    before = {x["ticker"]: x for x in (prev or {}).get("setups", [])}
    for x in setups:
        p_ = before.get(x["ticker"])
        x["since"] = (p_.get("since") or prev["asof"]) if p_ else asof.isoformat()
        x["new"] = p_ is None
    now = {x["ticker"] for x in setups}
    dropped = [dict(ticker=t, sector=p_.get("sector") or sectors.get(t) or "", since=p_.get("since") or prev["asof"],
                    why=why_out(t)) for t, p_ in before.items() if t not in now]

    # Plan ETF: 3x funds on their index's signals, in the value zone, clear of order blocks 30+ days old
    etf = {}
    for fund, und in OV["ETF"].items():
        d = spy if und == "SPY" else qqq
        if d is None or len(d) < 60:
            etf[fund] = dict(under=und, ok=False, checks=[dict(k="data", ok=False, text=f"no {und} prices tonight")], sell=[])
            continue
        x = idx_state(d)
        blocks, day = ov_blocks(d.iloc[-504:]), d.index[-1].date()     # 2 years, like the stocks' blocks
        near = ob_near(blocks, x["close"], day, min_age=OV["ETF_OB_AGE"])
        zone = round(x["e20"] + OV["ZONE_ATR"] * x["atr"], 2)
        ch = [dict(k="heat", ok=x["rsi"] < OV["HEAT_MAX"], text=f"{und} heatmap (RSI) {f0(x['rsi'], OV['HEAT_MAX'])} (needs under {OV['HEAT_MAX']})"),
              dict(k="signal", ok=x["e10"] > x["e20"], text=f"{und} buy signal: 10 EMA {'above' if x['e10'] > x['e20'] else 'below'} the 20 EMA"),
              dict(k="trend", ok=x["e10"] > x["e20"] and x["close"] > x["e50"],
                   text=f"{und} uptrend: close {x['close']:.2f} {'above' if x['close'] > x['e50'] else 'below'} the 50 EMA {x['e50']:.2f}"),
              dict(k="zone", ok=x["e20"] <= x["close"] <= zone, text=f"{und} value zone: close {x['close']:.2f}, zone {x['e20']:.2f}-{zone:.2f} "
                                                                    "(20 EMA to 2 ATR above it)"),
              dict(k="ob", ok=near is None, text=f"{und} order blocks 30+ days old: " + (
                  "none within 2%" if near is None else f"{near[1]['bot']:.2f}-{near[1]['top']:.2f} is {near[0] * 100:.1f}% away"))]
        if hot_check:
            ch.append(hot_check)
        sell = (([f"{und}'s 10 EMA is under its 20 EMA (a 10/20 bearish cross, the sell signal here)"] if x["e10"] < x["e20"] else [])
                + ([f"{und} closed more than {OV['HOT_ATR']:g} ATR above its 20 EMA"] if x["close"] > x["e20"] + OV["HOT_ATR"] * x["atr"] else []))
        hit = ob_hit(blocks, day, OV["ETF_OB_AGE"])
        if hit:
            sell.append(f"{und} reached an order block from {hit['start']:%b} {hit['start'].day} ({hit['bot']:.2f}-{hit['top']:.2f})")
        etf[fund] = dict(under=und, ok=all(c["ok"] for c in ch), checks=ch, sell=sell, **x)

    funnel = dict(signal=int(sig.sum()), rules=int(rules.sum()), sector=len(in_sec), hot=len(in_sec) - len(cool), near_ob=near_n,
                  earnings=earn_n, setups=len(setups), earn_checked=bool(earn))
    return dict(asof=asof.isoformat(), market=market, sectors=secs, etf=etf, setups=setups, funnel=funnel, dropped=dropped,
                prev_asof=(prev or {}).get("asof"), screen=ov_screen(locals()), hist=ov_hist(locals()))


OV_RULES = ("sig", "trend", "e10", "rsi", "px", "sec", "hot", "ob", "earn")   # the screener's 9 Plan M rules, in order


def ov_screen(v):
    """The OVTLYR screener: every liquid stock against Plan M's 9 rules (OV_RULES), so the page can show the stocks closest
    to a setup. v: ovtlyr_plan()'s locals. Each row: ticker, sector, close, RSI, days since the buy signal (None when the
    10 EMA is under the 20) and one character per rule: 1 pass, 0 fail, - not checked. Earnings are only looked up for
    stocks that miss at most one of the other rules, to keep the nightly run short."""
    C, R, e10, e20, e50, age, c_ = (v[k] for k in ("C", "R", "e10", "e20", "e50", "age", "c_"))
    lo, hi, secs, sectors, hot_own, frames, asof = (v[k] for k in ("lo", "hi", "secs", "sectors", "hot_own", "frames", "asof"))
    x10, x20, x50, r0, r1 = e10.iloc[-1], e20.iloc[-1], e50.iloc[-1], R.iloc[-1], R.iloc[-2]
    rows = {}
    for t in c_.index[v["liquid"].to_numpy(bool)]:
        px = float(c_[t])
        rows[t] = dict(sig=bool(age[t] <= OV["SIGNAL_DAYS"] - 1), trend=bool(x10[t] > x20[t] and px > x50[t]),
                       e10=bool(px > x10[t]), rsi=bool(r0[t] > r1[t]), px=bool(lo <= px <= hi),
                       sec=bool(secs.get(sectors.get(t) or "Other", {}).get("ok")), hot=t not in hot_own,
                       ob=not ob_near(ov_blocks(frames[t]), px, asof), earn=None)
    dates = dict(v["dates"])
    if v["earn"]:
        near = [t for t, ok in rows.items() if sum(not x for k, x in ok.items() if k != "earn") <= 1]
        dates.update(v["earn"]([t for t in near if t not in dates][:80]) if near else {})
        for t in near:
            e = dates.get(t)
            rows[t]["earn"] = not (e and (dt.date.fromisoformat(e) - v["entry"]).days < OV["EARN_DAYS"])
    out, A = [], v["A"].iloc[-1]
    for t, ok in rows.items():
        k, a = age[t], A[t]
        out.append([t, sectors.get(t) or "", round(float(c_[t]), 2), round(float(r0[t]), 1),
                    int(k) if k == k and x10[t] > x20[t] else None,
                    "".join("-" if ok[r] is None else "1" if ok[r] else "0" for r in OV_RULES),
                    round(float(a), 2) if a == a else None, dates.get(t) if v["earn"] else None])
    rs = v["rs"]
    out.sort(key=lambda r: (r[5].count("0"), -(rs[r[0]] if rs[r[0]] == rs[r[0]] else 0)))
    return out


def ov_hist(v, n=63):
    """The last 3 months for the OVTLYR page's charts: the market's and each sector's breadth (share of stocks with the
    10 EMA over the 20) with its 5-day and 10-day EMAs, each sector's average heat (RSI), and SPY's heat."""
    bull, R, C, idx, spy = (v[k] for k in ("bull", "R", "C", "idx", "spy"))
    r1 = lambda x: [None if y != y else round(float(y), 1) for y in x.iloc[-n:]]
    tri = lambda p_: [r1(p_), r1(p_.ewm(span=5, adjust=False).mean()), r1(p_.ewm(span=10, adjust=False).mean())]
    secs = {name: dict(b=tri(bull[cols].mean(axis=1) * 100), heat=r1(R[cols].mean(axis=1)))
            for name, cols in v["groups"].items() if name in v["secs"]}
    sr = rsi(spy["Close"])
    return dict(t=[d.strftime("%Y-%m-%d") for d in idx[-n:]], mkt=tri(bull[list(C.columns)].mean(axis=1) * 100),
                spy=r1(sr.reindex(idx).ffill()), secs=secs)

# ------------------------------------------------------------------ options
def norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs_call(S, K, T, r, sig):
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / sq
    d2 = d1 - sq
    pdf = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    return dict(
        delta=norm_cdf(d1), gamma=pdf / (S * sq),
        theta=(-S * pdf * sig / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365,
        vega=S * pdf * math.sqrt(T) / 100)


def bs_price(S, K, T, r, sig):
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / sq
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d1 - sq)


def implied_vol(price, S, K, T, r):
    """Bisection IV from an option price; None if the price is outside the model's range."""
    lo, hi = 0.01, 5.0
    if not (bs_price(S, K, T, r, lo) <= price <= bs_price(S, K, T, r, hi)):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bs_price(S, K, T, r, mid) < price else (lo, mid)
    return (lo + hi) / 2


def pick_call(t, S):
    """Call nearest TARGET_DELTA at ~TARGET_DTE. Returns (contract or None, reason).
    After the close Yahoo often reports bid/ask 0 and a junk IV, so when there are no live quotes it
    falls back to the last trade price and solves IV from it (marked quote="last")."""
    import yfinance as yf
    tk = yf.Ticker(t)
    today = dt.date.today()
    exps = [(abs((dt.date.fromisoformat(e) - today).days - CFG["TARGET_DTE"]), e, (dt.date.fromisoformat(e) - today).days)
            for e in tk.options]
    exps = [x for x in exps if CFG["DTE_MIN"] <= x[2] <= CFG["DTE_MAX"]]
    if not exps:
        return None, "no expiry in DTE window"
    why = ""
    for _, exp, dte in sorted(exps)[:3]:          # nearest-to-target first; weeklies can be thin, so try the next
        rows, why = chain_rows(tk.option_chain(exp).calls, S, exp, dte, CFG["MIN_OI"])
        if rows:
            return min(rows, key=lambda r: abs(r["delta"] - CFG["TARGET_DELTA"])), why
    return None, why


def chain_rows(ch, S, exp, dte, min_oi):
    """Usable calls from one Yahoo option chain, with Greeks. Returns (rows, "live" / "last"), or ([], reason)."""
    T = dte / 365
    oi_known = ch.openInterest.fillna(0).gt(0).any()   # Yahoo often zeroes OI on weekends
    if oi_known:
        ch = ch[ch.openInterest.fillna(0) >= min_oi].copy()
    if ch.empty:
        return [], f"{exp}: no strikes with OI >= {min_oi}"
    live = ch[(ch.bid > 0) & (ch.ask > 0)].copy()
    if len(live):
        live["px"] = (live.bid + live.ask) / 2
        live["spr"] = (live.ask - live.bid) / live.px * 100
        ch, quote = live[live.spr <= CFG["MAX_SPREAD_PCT"]], "live"
    else:
        ch = ch[ch.lastPrice > 0].copy()
        ch["px"], ch["spr"], quote = ch.lastPrice, np.nan, "last"
    rows = []
    for _, o in ch.iterrows():
        iv = o.impliedVolatility if quote == "live" and o.impliedVolatility > 0.05 else implied_vol(o.px, S, o.strike, T, CFG["RISK_FREE"])
        if not iv:
            continue
        g = bs_call(S, o.strike, T, CFG["RISK_FREE"], iv)
        rows.append({**g, "strike": o.strike, "iv": iv * 100, "bid": o.bid, "ask": o.ask, "last": o.lastPrice,
                     "spr": o.spr, "oi": int(o.openInterest) if oi_known else None, "exp": exp, "dte": dte, "quote": quote,
                     "symbol": o.get("contractSymbol")})
    if not rows:
        return [], f"{exp}: {quote} quotes but none usable"
    return rows, quote


def pick_list_call(S, chains, today):
    """Top picks lists: among calls PK_DTE days out (chains: {expiry: Yahoo calls table}) with open interest
    over PK_OI_OVER and delta in PK_DELTA, the one nearest the middle of the range (more open interest wins a tie).
    When none fits, the closest miss: with expiries in the window, the call in the delta range with the most open
    interest; with none, the next expiry after the window. Returns (contract or None, reason); the contract has
    fits = how many calls fit and miss = the rules it misses ("dte", "oi")."""
    lo, hi = CFG["PK_DTE"]
    dlo, dhi = CFG["PK_DELTA"]
    mid, need = (dlo + dhi) / 2, CFG["PK_OI_OVER"]
    dte = {e: (dt.date.fromisoformat(e) - today).days for e in chains}
    calls = lambda e, min_oi: [r for r in chain_rows(chains[e], S, e, dte[e], min_oi)[0] if dlo <= r["delta"] <= dhi]
    low_oi = lambda e: [r for r in calls(e, 1) if r["oi"] is not None and r["oi"] <= need]
    nearest = lambda rows: min(rows, key=lambda r: (abs(r["delta"] - mid), -(r["oi"] or 0)))
    most_oi = lambda rows: max(rows, key=lambda r: (r["oi"], -abs(r["delta"] - mid)))
    win = [e for e in chains if lo <= dte[e] <= hi]
    fit = [r for e in win for r in calls(e, need + 1)]
    if fit:
        best = nearest(fit)
        return dict(best, fits=len(fit), miss=[]), best["quote"]
    if win:
        why = f"no call {dlo:.2f}-{dhi:.2f} delta with OI over {need}"
        rows = [r for e in win for r in low_oi(e)]
        return (dict(most_oi(rows), fits=0, miss=["oi"]) if rows else None), why
    why = f"no expiry {lo}-{hi} days out"
    later = sorted(e for e in chains if dte[e] > hi)
    if later:
        ok = calls(later[0], need + 1)
        if ok:
            return dict(nearest(ok), fits=0, miss=["dte"]), why
        rows = low_oi(later[0])
        if rows:
            return dict(most_oi(rows), fits=0, miss=["dte", "oi"]), why
    return None, why


def list_calls(prices, demo=False):
    """Option contracts for the Top picks lists: {ticker: contract dict, or the reason there is none}."""
    lo, hi = CFG["PK_DTE"]
    today, out = dt.date.today(), {}
    for t, S in prices.items():
        try:
            if demo:
                chains = demo_chains(t, S, today)
            else:
                import yfinance as yf
                tk = yf.Ticker(t)
                days = {e: (dt.date.fromisoformat(e) - today).days for e in tk.options}
                want = [e for e in days if lo <= days[e] <= hi] or sorted(e for e in days if days[e] > hi)[:1]  # else the next one
                chains = {e: tk.option_chain(e).calls for e in want}
            o, why = pick_list_call(S, chains, today)
            out[t] = o or why
        except Exception as e:
            out[t] = "lookup failed"
            print("  options failed", t, e)
    return out


def demo_chains(t, S, today):
    """Made-up after-hours call chains (last trades only) for the demo page."""
    rng = np.random.default_rng(sum(map(ord, t)))
    fri = [today + dt.timedelta(days=d) for d in range(1, 50) if (today + dt.timedelta(days=d)).weekday() == 4]
    step = 1 if S < 50 else 2.5 if S < 150 else 5 if S < 400 else 10
    ks = np.arange(round(S * 0.8 / step) * step, S * 1.2, step)
    out = {}
    for f in fri:
        T = (f - today).days / 365
        iv = rng.uniform(0.25, 0.6)
        px = [round(bs_price(S, k, T, CFG["RISK_FREE"], iv), 2) for k in ks]
        oi = (rng.lognormal(6.3, 1.1, len(ks)) * (1 if rng.random() > 0.15 else 0.1)).astype(int)
        out[f.isoformat()] = pd.DataFrame(dict(strike=ks, lastPrice=px, bid=0.0, ask=0.0, impliedVolatility=1e-5, openInterest=oi))
    return out

# --------------------------------------------------------------------- html
def spark(vals, w=150, h=34, color="currentColor"):
    v = [x for x in vals if x == x]
    if len(v) < 2: return ""
    lo, hi = min(v), max(v); rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(v) - 1):.1f},{h - 3 - (x - lo) / rng * (h - 6):.1f}" for i, x in enumerate(v))
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="{color}" stroke-width="1.6" points="{pts}"/></svg>'


def card(label, value, sub, series, good=None):
    cls = good if isinstance(good, str) else "" if good is None else ("up" if good else "dn")
    return f'<div class="card"><div class="lbl">{label}</div><div class="val {cls}">{value}</div><div class="sub">{sub}</div>{spark(series)}</div>'


# The VIX's usual reading: under 15 calm, 15-20 normal, 20-30 nervous, over 30 fear (common rules of thumb).
VIX_ZONES = [(0, 15, "Calm", "var(--up)"), (15, 20, "Normal", "var(--mut)"), (20, 30, "Nervous", "var(--warn)"),
             (30, 1e9, "Fear", "var(--dn)")]


def vix_html(vix):
    """Market tab: the VIX now, its zone, where it sits in the last year, and a 1-year line over the zone bands."""
    if vix is None or len(vix) < 30:
        return ""
    v = vix.iloc[-252:]
    now, prev, wk = float(v.iloc[-1]), float(v.iloc[-2]), float(v.iloc[-6])
    zone = next(z for z in VIX_ZONES if z[0] <= now < z[1])
    rank = (v < now).mean() * 100                 # share of the last year's days it closed lower
    hi, lo, avg = float(v.max()), float(v.min()), float(v.mean())
    # the 1-year line, with the zone bands behind it
    W, H, top = 640, 160, max(40.0, hi * 1.08)
    y = lambda x: H - 4 - min(x, top) / top * (H - 8)
    X = lambda i: i * W / (len(v) - 1)
    bands = "".join(f'<rect x="0" y="{y(min(b, top)):.1f}" width="{W}" height="{y(a) - y(min(b, top)):.1f}" fill="{c}" opacity=".09"/>'
                    for a, b, _, c in VIX_ZONES if a < top)
    pc = lambda x: f"{y(x) / H * 100:.1f}%"      # chart text and the dot are HTML, so they keep their size on a phone
    lines = "".join(f'<line x1="0" x2="{W}" y1="{y(k):.1f}" y2="{y(k):.1f}" stroke="var(--line)" stroke-dasharray="4 4" '
                    f'vector-effect="non-scaling-stroke"/>' for k in (15, 20, 30))
    labels = "".join(f'<span class="vy" style="top:{pc(k)}">{k}</span>' for k in (15, 20, 30))
    pts = " ".join(f"{X(i):.1f},{y(x):.1f}" for i, x in enumerate(v))
    months, last = [], None
    for i, d in enumerate(v.index):
        if d.month != last and 5 < i < len(v) - 8:
            months.append(f'<span style="left:{X(i) / W * 100:.1f}%">{d.strftime("%b")}</span>')
        last = d.month
    svg = (f'<div class="vxw"><svg class="vxc" viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" '
           f'aria-label="VIX over the last year">' + bands + lines
           + f'<polyline fill="none" stroke="var(--fg)" stroke-width="1.6" vector-effect="non-scaling-stroke" points="{pts}"/></svg>'
           + labels + f'<i class="vxd" style="top:{pc(now)};background:{zone[3]}"></i></div>'
           + f'<div class="vxm">{"".join(months)}</div>')
    chg = now - prev
    tell = {"Calm": "Traders expect small moves. Calm markets usually suit trends, and calls are cheaper.",
            "Normal": "An ordinary amount of expected movement.",
            "Nervous": "Traders are paying up for protection. Swings get bigger and calls cost more.",
            "Fear": "Fear: expect big daily swings. Uptrends often break down here, and calls are expensive."}[zone[2]]
    keys = "".join(f'<span><i style="background:{c}"></i>{n} {a:g}{"+" if b > 1e8 else f"-{b:g}"}</span>' for a, b, n, c in VIX_ZONES)
    return ('<h2>VIX (fear gauge)</h2>' + hk("vix") + '<div class="hint">The VIX is how much the S&amp;P 500 is expected to move over the next '
            '30 days, from options prices. Low = calm, high = fear. It usually rises when stocks fall.</div>'
            '<div class="vix" id="vix"><div class="vxn">'
            f'<div class="lbl">VIX close {v.index[-1].strftime("%b %-d")}</div>'
            f'<div class="val">{now:.2f} <span class="vxz" style="background:color-mix(in srgb,{zone[3]} 18%,transparent);color:{zone[3]}">{zone[2]}</span></div>'
            f'<div class="sub"><span class="{"dn" if chg > 0 else "up" if chg < 0 else ""}">{chg:+.2f} ({chg / prev:+.1%})</span> vs the day before · '
            f'{now - wk:+.2f} vs 5 days ago</div>'
            f'<div class="sub">Higher than {rank:.0f}% of the last year\'s days · 1-year range {lo:.1f} to {hi:.1f}, average {avg:.1f}</div>'
            f'<div class="vxt">{tell}</div></div>'
            f'<div class="vxg">{svg}<div class="vxk">{keys}</div></div></div>')


BT_JS = Path(__file__).resolve().parent / "backtests.js"   # the Backtests tab (every backtest, with line graphs)
BT_PLANS = Path(__file__).resolve().parent / "history" / "plan_backtests.json"   # research/plan_backtest.py, Saturdays
PAPER_SRC = "https://raw.githubusercontent.com/txcoproducts-lang/Swing-Screener-/paper-trading/paper/"
# The research tests behind the page's lists and signals, from their reports (research/*_results.md); the Backtests tab
# shows them under the plans. Colors: blue = the tested idea, grey = what it's measured against, amber = a loss.
AI_YEARS = [("2014-10-01", 0, 0, 0), ("2014-12-31", 9.4, 8.4, 5.7), ("2015-12-31", -8.8, -0.4, 0.7), ("2016-12-30", 6.1, 18.6, 14.4),
            ("2017-12-29", 31.1, 23.7, 21.5), ("2018-12-31", -2.9, -6.3, -6.0), ("2019-12-31", 30.9, 32.5, 31.8),
            ("2020-12-31", 3.3, 12.8, 16.8), ("2021-12-31", 12.9, 35.5, 31.9), ("2022-12-30", -10.8, -8.5, -18.7),
            ("2023-12-29", 20.1, 17.0, 24.6), ("2024-12-31", 48.0, 16.0, 26.5), ("2025-12-31", 38.7, 16.0, 18.2),
            ("2026-10-14", 37.8, 13.6, 11.7)]   # research/picks_backtest.py, rerun 2026-10-15 with the overbought rule (breadth only)


def bt_research(df):
    """The research list for the Backtests tab: each test's name, scope, one-line verdict, what it found, and a chart
    (bars: [label, value, color], or a line chart)."""
    blue, grey, amber = "#2f6fed", "#8a94a3", "#c27a00"
    grow = lambda k: [round(v, 2) for v in np.cumprod([1000] + [1 + r[k] / 100 for r in AI_YEARS[1:]])]
    out = [
        dict(name="AI picks list", scope="S&P 500 as it was each day, 2014-2026", verdict="+16.6% a year vs SPY +14.0%",
             text="Hold the 10 stocks with the best relative strength (at most 3 per sector), keep each while it ranks in the top 20, "
                  "with your overbought rule (no new pick while its sector's or the market's breadth is over 75). It trailed from 2014 "
                  "to 2021 (+10.4% a year vs SPY +15.4%) and led from 2022 (+26.7% vs +11.9%). Its edge over the average stock, 3.7% "
                  "a year, isn't proven: the 95% range runs from -5.4% to +12.8%. This is the list Claude's picks "
                  "trades; its plan backtest above adds your exit and overbought rule.",
             line=dict(dates=[r[0] for r in AI_YEARS], lines=[dict(name="AI picks", color="#d6453d", vals=grow(1)),
                                                              dict(name="Average stock", color=amber, dash=True, vals=grow(2)),
                                                              dict(name="SPY", color=grey, dash=True, vals=grow(3))])),
        dict(name="Order blocks", scope="1,000 stocks, 10 years, daily bars", verdict="No proven edge as support", unit="R", sign=True,
             text="Rerun 2026-10-15. Buying the first pullback into a bullish block (the strong-move blocks the charts draw) made "
                  "+0.17R a trade, against +0.10R for random price zones; that 0.08R edge isn't proven (95% range -0.02R to +0.25R), "
                  "and most of the profit came from the stocks rising. Bearish blocks held as resistance a little better than random "
                  "zones. 1R = the amount risked; 2:1 target, 20-day limit.",
             bars=[["Bullish blocks", 0.17, blue], ["Random zones", 0.10, grey]]),
        dict(name="Breakout watch", scope="S&P 500, 2014-2026", verdict="Breaks out more, returns don't", unit="%",
             text="The tightest setups within 5% of a 50-day high broke out within 10 days 46% of the time, against 27% for the "
                  "average stock, but did 0.31% worse than it over the next 20 days because many breakouts fail. Rerun with your "
                  "overbought rule (breadth over 75).",
             bars=[["Broke out in 10 days", 46, blue], ["Average stock", 27, grey]]),
        dict(name="New uptrends", scope="S&P 500, 2014-2026", verdict="Same as the average stock", unit="%", sign=True,
             text="About 7 stocks a day turned into an uptrend by your rule (leaving out sectors and markets over 75). Over the next "
                  "20 trading days they did -0.19% against the average stock, and half of them beat it. A good place to look, not a "
                  "buy signal on its own.",
             bars=[["Next 20 days vs average", -0.19, amber], ["Average stock", 0, grey]]),
    ]
    if "bt_rules" in df and df.bt_rules.notna().any():
        b = df.dropna(subset=["bt_rules", "bt_hold"])
        n, won = len(b), int((b.bt_rules > b.bt_hold).sum())
        med = lambda c: round(float(b[c].median()))
        out.append(dict(name="10-year rules vs hold", scope=f"Each of tonight's {n} liquid stocks", unit="%", sign=True,
                        verdict=f"Holding won on {n - won} of {n}",
                        text=f"Each stock's last 10 years traded on your rules (buy a setup on the strongest sector, "
                             f"strongest stock list, sell on your exit or an 8% stop) against just holding it. Your rules beat holding on {won} of {n}: in long rising markets they "
                             "sit in cash much of the time. Medians below; click any ticker in the Stocks tab for its own numbers.",
                        bars=[["Your rules (median)", med("bt_rules"), blue], ["Holding the stock", med("bt_hold"), grey]]
                             + ([["Holding SPY", med("bt_spy"), grey]] if "bt_spy" in b else [])))
    out.append(dict(name="Strongest sector score", scope="40% market, 40% sector, 20% stock", verdict="Tested inside Your system",
                    text="It has no test of its own: Your system and Your system, after 2 PM buy only from this list, highest score "
                         "first, so their 10-year backtests above are its test."))
    return out


def bt_tab(df):
    """The Backtests tab's section and its data."""
    if not BT_JS.exists():
        return "", ""
    plans = json.loads(BT_PLANS.read_text(encoding="utf-8")) if BT_PLANS.exists() else None
    data = dict(bench="SPY", unit="stock", paperSrc=PAPER_SRC, plans=plans, research=bt_research(df),
                note=("Plan backtests: 10 years of daily bars on the S&P 500 as it was each day (" + (plans or {}).get("universe", "")
                      + "), $5,000 each as in the paper accounts, shares filled 0.05% worse than the price. A daily test can't copy "
                      "everything the paper accounts do: there's no free history of option prices, so the plans are tested with shares "
                      "(each card also shows the same plan with calls priced by a model: Black-Scholes on the stock's own 30-day "
                      "volatility, 30 days out, 3% worse each way plus $0.65 a contract, a rough guide only), your 4-hour exit is checked on daily closes, the after-2 PM plan buys at the next day's close, and OVTLYR's order block and earnings checks are "
                      "left out. Stocks that left the index and stopped trading are missing. Rebuilt every Saturday"
                      + (f" (last: {plans['asof']})" if plans else "") + ". Past results don't promise future ones. Not financial advice."))
    html = ('<h2>Backtests</h2>' + hk("backtests") + '<div class="hint">Every test we\'ve run: your four plans side by side, each plan\'s own 10-year '
            'backtest and paper trial, then the research behind the page\'s lists and signals.</div><div id="btx"></div>')
    js = "window.BTDATA=" + json.dumps(data, separators=(",", ":")).replace("</", "<\\/") + ";\n" + BT_JS.read_text(encoding="utf-8")
    return html, js


PAPER_JS = Path(__file__).resolve().parent / "paper.js"   # the paper trading widgets (accounts traded by paper.py)
PAPER_HINT = ("Four paper accounts with $5,000 each (restarted Oct 15), trading until Apr 6, 2027; each buys a call by your "
              "option rules when one fits, else shares. <b>Your system</b> trades your screener "
              "setups on the strongest sector, strongest stock list with your option rules at about 10:00 AM New York time; <b>Your system, after 2 PM</b> uses the same rules but "
              "only buys after 2:00 PM Central; <b>Claude's picks</b> trades my AI picks list; <b>OVTLYR plan</b> trades the "
              "OVTLYR plan section below. They trade on their own and check every 30 minutes. Click one for every trade and "
              "the reason behind it.")

PICK_TEXT = {    # how each list is ordered, in plain words, for the versions in use (others fall back to their description)
    "nu": {"all": "Strongest relative strength (RS, 1-99) first."},
    "bo": {"tight": "{n} stocks in an uptrend are within 5% of a 50-day high set at least 5 days ago (a base). Tightest first: "
                    "a narrow 10-day range, daily ranges and volume shrinking, and the price close to the level.",
           "squeeze": "{n} stocks in an uptrend are within 5% of a 50-day high set at least 5 days ago (a base), with Bollinger "
                      "Bands near their tightest in 6 months (a squeeze). Strongest RS first."},
    "ai": {"rs": "every liquid S&amp;P 500 and Nasdaq-100 stock ranked by relative strength (the IBD formula: 40% weight on "
                 "the last 3 months, 20% each on 6, 9 and 12 months)"},
}
_RES = '<a href="https://github.com/txcoproducts-lang/Swing-Screener-/blob/main/research/picks_backtest_results.md">Full results</a>'
PICK_NOTES = {   # one line per list on how it did in research/picks_backtest.py (S&P 500 as it was each day, 2014-2026)
    "nu": "Backtest, S&amp;P 500 2014-2026: over the next 20 days these did about the same as the average stock (-0.10%, "
          "95% range -0.28% to +0.08%), and no way of ordering them did better. Treat it as a watch list, not a buy signal. " + _RES,
    "bo": "Backtest, S&amp;P 500 2014-2026: 47% of these closed above the level within 10 days, against 27% of all stocks. "
          "Their 20-day return was no better than the average stock (-0.30%), so a breakout is more likely here, but a gain is not. " + _RES,
    "ai": "Backtest, S&amp;P 500 as it was each day, 2014-2026, after 0.1% costs per trade: 6.2% a year better than the average "
          "stock in the same test, but that edge is not proven (95% range -3.4% to +15.8%). It lagged from 2014 to 2021, led from "
          "2022 to 2026, and its worst drop was -31%. " + _RES,
}


def next_earnings(tickers):
    """Next earnings date per ticker from Yahoo (often an estimate until the company confirms it)."""
    import yfinance as yf
    out, today = {}, dt.date.today()
    for t in tickers:
        try:
            cal = yf.Ticker(t).calendar
            ds = cal.get("Earnings Date") if isinstance(cal, dict) else None
            ds = [d for d in (ds or []) if isinstance(d, dt.date) and d >= today]
            if ds:
                out[t] = min(ds).isoformat()[:10]
        except Exception:
            pass
    return out


def picks_html(L, earn=None, calls=None):
    """Top picks section: New uptrends / Breakout watch / AI picks tabs."""
    if not L:
        return ""
    earn, calls = earn or {}, calls or {}
    asof = dt.date.fromisoformat(L["asof"])
    def pc(v, d=1):
        return ("", "") if v is None or v != v else (f'<span class="{"up" if v > 0 else "dn" if v < 0 else ""}">{v:+.{d}f}%</span>', round(v, 3))
    def tk(r):
        return (f'<b class="tk" data-tk="{r["ticker"]}">{r["ticker"]}</b><div class="sec">{r["sector"]}</div>', r["ticker"])
    def num(v, f="{:.2f}"):
        return ("", "") if v is None or v != v else (f.format(v), round(v, 4))
    def er(t):
        d = earn.get(t)
        if not d:
            return ("", "")
        dd = dt.date.fromisoformat(d)
        n = (dd - asof).days
        txt = f'{dd.strftime("%b")} {dd.day} · {n}d'
        return (f'<span class="warn" title="Earnings within a week">{txt}</span>' if n <= 7 else txt, n)
    def vol(v):
        return ("", "") if v is None or v != v else (f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}K", round(v))
    def opt(t):
        o = calls.get(t)
        if not isinstance(o, dict):
            if o == "lookup failed":
                return [('<span class="mut" title="Yahoo did not answer for this stock tonight">n/a</span>', "")] + [("", "")] * 3
            return [(f'<span class="mut" title="{o}">none fits</span>' if o else "", "")] + [("", "")] * 3
        d = dt.date.fromisoformat(o["exp"])
        e = earn.get(t)
        flag = (f' <span class="warn ef" title="Earnings on {e} is before this contract expires">E</span>'
                if e and dt.date.fromisoformat(e) <= d else "")
        px = (o["bid"] + o["ask"]) / 2 if o["quote"] == "live" else o["last"]
        tip = f'bid {o["bid"]:.2f} / ask {o["ask"]:.2f}' if o["quote"] == "live" else "last trade"
        miss = o.get("miss") or []
        n = f'{o["fits"]} contract{"s" if o["fits"] != 1 else ""}'
        if miss:
            fit = ("No call fits all your rules, so this is the closest one"
                   + (f": no expiry is {CFG['PK_DTE'][0]}-{CFG['PK_DTE'][1]} days out, so it is the next one after" if "dte" in miss else "")
                   + (f"{' and' if 'dte' in miss else ':'} its open interest is only {o['oi']:,} (your rule is over {CFG['PK_OI_OVER']})"
                      if "oi" in miss else ""))
        elif o["oi"] is None:
            fit = f"{n} fit the delta and expiry; Yahoo did not report open interest, so it was not checked"
        else:
            fit = f"{n} fit your rules"
        g = ' class="miss"' if miss else ""
        red = lambda k, txt: f'<span class="warn">{txt}</span>' if k in miss else txt
        days, oi = red("dte", f'{o["dte"]} days'), (red("oi", f'{o["oi"]:,}') if o["oi"] is not None else "n/a")
        return [(f'<span{g} title="{fit}; IV {o["iv"]:.0f}%">'
                 f'{d.strftime("%b")} {d.day} ${o["strike"]:g}</span>{flag}<div class="dte">{days}</div>', o["exp"]),
                (f'<span{g}>{o["delta"]:.2f}</span>', round(o["delta"], 3)), (f'<span{g} title="{tip}">{px:.2f}</span>', round(px, 2)),
                (f'<span{g}>{oi}</span>', o["oi"] if o["oi"] is not None else "")]
    VO = ["Volume", "5-day volume", "Call 15-30d", "Δ", "Premium", "OI"]
    vo = lambda r: [vol(r.get("vol1")), vol(r.get("vol5"))] + opt(r["ticker"])
    def table(tid, head, rows, empty):
        if not rows:
            return f'<div class="hint pke">{empty}</div>'
        wi = head.index("Why") if "Why" in head else -1
        th = "".join(f'<th{" class=why" if i == wi else ""}>{h}</th>' for i, h in enumerate(head))
        body = "".join("<tr>" + "".join(f'<td data-v="{v}"{" class=why" if i == wi else ""}>{c}</td>'
                                         for i, (c, v) in enumerate(r)) + "</tr>" for r in rows)
        return f'<div class="wrap"><table id="{tid}" class="pkt"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'
    note = lambda k: f'<div class="note">{PICK_NOTES[k]}</div>' if PICK_NOTES.get(k) else ""
    mh = L.get("mkt_hot") or ""
    def left_out(hot):
        """The stocks a list left out tonight under the user's overbought rule, with why."""
        if not hot:
            return ""
        return ('<div class="hint obo">Left out as overbought (your rule: '
                f'the sector\'s breadth over {CFG["OB_BREADTH"]}): '
                + "; ".join(f'<span class="tk" data-tk="{h["ticker"]}">{h["ticker"]}</span> ({html_esc(h["why"])})' for h in hot)
                + '</div>')
    hot_empty = (f'None tonight: the market is overbought ({html_esc(mh)}), and your rule gives nothing a buy signal then.'
                 if mh else "")

    nu, bo, ai = L["nu"], L["bo"], L["ai"]
    E = "Earnings"
    nu_rows = [[tk(r), num(r["close"]), pc(r["chg1d"]), num(r["days_out"], "{:.0f}"), num(r["rs"], "{:.0f}"),
                pc(r["from_hi"]), num(r["relvol"], "{:.1f}x")] + vo(r) + [er(r["ticker"])] for r in nu["rows"]]
    nu_html = (f'<div class="hint">{nu["total"]} stock{"s" if nu["total"] != 1 else ""} turned into an uptrend on {L["asof"]} '
               f'(EMA10 &gt; EMA20, price &gt; EMA50 and &gt; 150 MA, after missing it the day before). '
               f'{PICK_TEXT["nu"].get(CFG["NEW_UP"], nu["desc"])} "Out" = days it had been out of an uptrend. '
               f'Vol vs avg = that day\'s volume vs the 20-day average.</div>'
               + table("pk-nu", ["Ticker", "Close", "1D %", "Out (days)", "RS", "From 52w hi", "Vol vs avg"] + VO + [E], nu_rows,
                       hot_empty or (f"Every stock that turned into an uptrend on {L['asof']} is overbought, so none is listed."
                                     if nu.get("hot") else f"No stock turned into an uptrend on {L['asof']}."))
               + left_out(nu.get("hot")) + note("nu"))
    bo_rows = [[tk(r), num(r["close"]), num(r["piv"]), pc((r["close"] / r["piv"] - 1) * 100), num(r["base_days"], "{:.0f}"), num(r["tight"], "{:.1f}%"),
                num(r["dry"], "{:.2f}x"), num(r["rs"], "{:.0f}")] + vo(r) + [er(r["ticker"])] for r in bo["rows"]]
    bo_txt = PICK_TEXT["bo"].get(CFG["BREAKOUT"], "{n} stocks fit: " + bo["desc"] + ".")
    bo_html = (f'<div class="hint">{bo_txt.format(n=bo["total"])} Level = the 50-day high; a breakout is a close above it. '
               f'Range = high to low of the last 10 days; '
               f'Vol 10d/50d = average volume of the last 10 days vs the last 50.</div>'
               + table("pk-bo", ["Ticker", "Close", "Breakout level", "Below it", "Base (days)", "10-day range", "Vol 10d/50d", "RS"] + VO + [E],
                       bo_rows, hot_empty or ("Every stock that fits the breakout rules today is overbought, so none is listed."
                                              if bo.get("hot") else "No stock fits the breakout rules today."))
               + left_out(bo.get("hot")) + note("bo"))
    new = lambda r, cell: ('<span class="mut">new today</span>', 0) if r["added"] == L["asof"] else cell
    why = lambda r: ", ".join(r["why"]) + (f'{", " if r["why"] else ""}<span class="warn">overbought tonight: {html_esc(r["ob"])}</span>'
                                           if r.get("ob") else "")
    ai_rows = [[tk(r), num(r.get("rank"), "{:.0f}"), (r["added"], r["added"]), num(r["price"]), num(r.get("now")),
                new(r, pc(r.get("ret"))), new(r, pc(r.get("spy_ret")))] + vo(r) + [(why(r), ""), er(r["ticker"])]
               for r in ai["rows"]]
    tr = ai["track"]
    track = f'<div class="hint">Track record starts {ai["since"]}: each pick is measured from its close on the day it was picked.</div>'
    if tr:
        beat = [a_ - b_ for a_, b_ in tr if b_ is not None]
        track = (f'<div class="hint">Track record since {ai["since"]}: {len(tr)} pick{"s" if len(tr) != 1 else ""}, average '
                 f'{sum(a_ for a_, _ in tr) / len(tr):+.1f}% vs SPY {sum(b_ for _, b_ in tr if b_ is not None) / max(1, len(beat)):+.1f}% '
                 f'over the same days; {sum(x > 0 for x in beat)} of {len(beat)} beat SPY. Prices are closes on the day picked.</div>')
    dropped = "".join(f'<span class="tk" data-tk="{p["ticker"]}">{p["ticker"]}</span> ({(p["out"] / p["price"] - 1) * 100:+.1f}%, {p["why"]}) '
                      for p in ai["dropped"])
    mkt = "" if ai["market_ok"] else '<div class="hint warn">Market filter is on: SPY is below its 200-day average, so no new picks until it recovers.</div>'
    if mh and ai.get("step", True):
        mkt += (f'<div class="hint warn">No new picks tonight: the market is overbought ({html_esc(mh)}), and your rule adds '
                'nothing then. The picks already on the list stay.</div>')
    if L.get("live_at"):
        mkt += (f'<div class="hint warn">This page was built at {L["live_at"]} New York time, before the close, so these are the '
                f'picks from the last run after a close, with prices as of {L["live_at"]}. The list only changes on a run after the close.</div>')
    ai_html = (f'<div class="hint">My own list, rebuilt every night by rules I chose and tested: {PICK_TEXT["ai"].get(CFG["AI_SCORE"], ai["desc"])}. '
               f'I hold up to {CFG["AI_N"]}, at most {CFG["AI_CAP"]} per sector. A pick stays while it ranks in the top {CFG["AI_KEEP"]}; '
               f'open spots go to the best-ranked stocks in the top {CFG["AI_KEEP"]} that fit the sector limit, and a spot stays empty '
               f'(cash) when none fits, as in the test. Your overbought rule: a stock that is overbought on the night a spot opens '
               f'(its sector\'s breadth over {CFG["OB_BREADTH"]}) is passed '
               f'over for the next one, and nothing is added while the market\'s breadth is over {CFG["OB_BREADTH"]}. '
               f'Rank = today\'s rank of all liquid stocks.</div>'
               + mkt + table("pk-ai", ["Ticker", "Rank", "Picked", "Price then", "Now", "Since picked", "SPY since"] + VO + ["Why", E],
                             ai_rows, "No picks yet.")
               + (f'<div class="hint">Dropped today: {dropped}</div>' if dropped else "") + track + note("ai"))
    tab = lambda k, label, n, on: f'<button{" class=on" if on else ""} data-pk="{k}">{label} <span class="n">{n}</span></button>'
    n_nu = 0 if mh else max(0, nu["total"] - len(nu.get("hot") or []))
    return ('<h2>Top picks</h2>' + hk("picks")
            + (f'<div class="hint warn obn">The market is overbought tonight ({html_esc(mh)}), so by your rule nothing gets a '
               'buy signal: New uptrends and Breakout watch are empty, and AI picks adds no new stocks.</div>' if mh else "")
            + '<div class="bar pk">' + tab("nu", "New uptrends", n_nu, True)
            + tab("bo", "Breakout watch", len(bo["rows"]), False) + tab("ai", "AI picks", len(ai["rows"]), False) + '</div>'
            + f'<div class="pkl" data-pk="nu">{nu_html}</div><div class="pkl" data-pk="bo" hidden>{bo_html}</div>'
            + f'<div class="pkl" data-pk="ai" hidden>{ai_html}</div>'
            + f'<div class="hint">Volume = shares traded on {L["asof"]}; 5-day volume = shares traded over the last 5 trading days '
            f'(the total). Call 15-30d = the call nearest {sum(CFG["PK_DELTA"]) / 2:.2f} delta among contracts {CFG["PK_DTE"][0]}-'
            f'{CFG["PK_DTE"][1]} days out with delta {CFG["PK_DELTA"][0]:.2f}-{CFG["PK_DELTA"][1]:.2f} and open interest over '
            f'{CFG["PK_OI_OVER"]} (hover it for how many fit and the IV). <span class="miss">Grey</span> = no call fits all three '
            f'rules, so the closest one is shown, with the rule it misses in <span class="warn">red</span>. '
            f'<span class="warn">E</span> = earnings come before it expires. Premium = the bid/ask midpoint, or the last trade when there are no live quotes (after hours). Delta is '
            f'Black-Scholes from that price; confirm in your broker.</div>')


def ov_html(ov):
    """OVTLYR plan section: the market, sector and Plan ETF checks, then the Plan M setups."""
    if not ov:
        return ""
    ok = lambda b: '<span class="up">✓</span>' if b else '<span class="dn">✗</span>'
    li = lambda c: f'<li>{ok(c["ok"])} {html_esc(c["text"])}</li>'
    m, f = ov["market"], ov["funnel"]
    mk = (f'<div class="ovb"><div class="ovh">Market <a href="#ovm" class="ovl {"up" if m["ok"] else "dn"}">Plan M is {"on" if m["ok"] else "off"} ›</a></div>'
          f'<ul>{"".join(li(c) for c in m["checks"])}</ul><div class="mut">All {len(m["checks"])} must pass for new Plan M trades.</div></div>')
    secs = sorted(ov["sectors"].items(), key=lambda kv: (not kv[1]["ok"], kv[0]))
    n_ok = sum(v["ok"] for _, v in secs)
    sc = (f'<div class="ovb"><div class="ovh">Sectors <span class="mut">{n_ok} of {len(secs)} pass</span></div><ul>'
          + "".join(f'<li>{ok(v["ok"])} {html_esc(k)} <span class="mut">breadth {v["bull"]:.0f}% vs {v["bull_ema"]:.0f}% avg, RSI {v["rsi"]:.0f}'
                    + (f' · {html_esc(v["miss"][0])}' if v["miss"] else "") + '</span></li>' for k, v in secs)
          + '</ul><div class="mut">Breadth above its 10-day average, average RSI above SPY\'s, under 70 and rising. '
            'Health Care is excluded in the plan. Your overbought rule: no sector whose breadth on the breadth view (its '
            f'S&amp;P 500 stocks with the 10 EMA over the 20 and price over the 50 EMA) is over the {CFG["OB_BREADTH"]} line.</div></div>')
    et = ('<div class="ovb"><div class="ovh">Plan ETF <span class="mut">spare cash</span></div>'
          + "".join(f'<div><b>{k}</b> {ok(e["ok"])} <span class="mut">on {e["under"]}\'s signals</span></div><ul>'
                    + "".join(li(c) for c in e["checks"]) + "</ul>"
                    + ("".join(f'<div class="warn">Sell signal: {html_esc(x)}</div>' for x in e["sell"]))
                    for k, e in ov["etf"].items())
          + '<div class="mut">When neither Plan M nor Plan ETF is set up, cash waits in SGOV (Plan #SICADFU).</div></div>')

    def pc(v):
        return f'<span class="{"up" if v > 0 else "dn" if v < 0 else ""}">{v:+.1f}%</span>'
    rows, day = [], dt.date.fromisoformat(ov["asof"])
    for s in ov["setups"]:
        cd = dt.date.fromisoformat(s["cross"])
        if s.get("new") or not s.get("since"):
            on_list, n_on = '<span class="new">New</span>', 0
        else:
            on_list, n_on = f'since {md(s["since"])}', int(np.busday_count(s["since"], day))
        sig = f'{cd:%b} {cd.day} <span class="mut">{"today" if s["age"] == 0 else str(s["age"]) + "d ago"}</span>'
        up = (f'{s["ob_up"]:.2f} <span class="mut">{(s["ob_up"] / s["close"] - 1) * 100:+.1f}%</span>' if s["ob_up"] else
              '<span class="mut">none</span>')
        if s["earn"]:
            ed = dt.date.fromisoformat(s["earn"])
            er = f'{ed:%b} {ed.day} <span class="mut">{(ed - dt.date.fromisoformat(ov["asof"])).days}d</span>'
        else:
            er = '<span class="mut">n/a</span>'
        cells = [(f'<b class="tk" data-tk="{s["ticker"]}">{s["ticker"]}</b><div class="sec">{s["sector"]}</div>', s["ticker"]),
                 (on_list, n_on), (sig, s["age"]), (f'{s["close"]:.2f}', s["close"]),
                 (f'{s["rsi"]:.0f} <span class="mut">from {s["rsi_prev"]:.0f}</span>', s["rsi"]),
                 (pc((s["close"] / s["e10"] - 1) * 100), round((s["close"] / s["e10"] - 1) * 100, 2)),
                 (f'{s["atr"]:.2f}', s["atr"]), (up, s["ob_up"] or ""), (er, s["earn"] or ""),
                 ("" if s["rs"] is None else str(s["rs"]), "" if s["rs"] is None else s["rs"])]
        rows.append("<tr>" + "".join(f'<td data-v="{v}">{c}</td>' for c, v in cells) + "</tr>")
    head = ["Ticker", "On the list", "Buy signal", "Close", "RSI", "vs 10 EMA", "ATR", "Order block above", "Earnings", "RS"]
    if rows:
        table = (f'<div class="wrap"><table id="ov-m"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        table = '<div class="hint pke">No stock passes every Plan M stock and sector rule tonight.</div>'
    drop, n_new = ov.get("dropped") or [], sum(1 for s in ov["setups"] if s.get("new"))
    gone = (f'<div class="ovd"><b>Dropped</b> <span class="mut">(on the {md(ov["prev_asof"])} list, not this one)</span><ul>'
            + "".join(f'<li><b class="tk" data-tk="{d["ticker"]}">{d["ticker"]}</b> <span class="mut">{html_esc(d["sector"])}, on the '
                      f'list since {md(d["since"])}</span>: {html_esc(d["why"])}</li>' for d in drop) + '</ul></div>') if drop else ""
    n = len(ov["setups"])
    summ = (f'<summary><b>Plan M stocks:</b> <span class="ovc">{n if n else "none tonight"}</span>'
            + (f' <span class="up">{n_new} new</span>' if n_new else "") + (f' <span class="dn">{len(drop)} dropped</span>' if drop else "")
            + (' <span class="mut">Plan M is off, so none are buys</span>' if not m["ok"] and n else "") + '</summary>')
    earn_txt = (f'{f["earnings"]} reported earnings within {OV["EARN_DAYS"]} days of the next market day' if f["earn_checked"]
                else "earnings dates were not checked (demo)")
    funnel = (f'<div class="hint">Plan M setups tonight: {f["signal"]} liquid stocks priced ${OV["PRICE"][0]:.0f}-${OV["PRICE"][1]:.0f} had a buy '
              f'signal in the last {OV["SIGNAL_DAYS"]} trading days; {f["rules"]} also had the 10/20/50 uptrend, price over the 10 EMA '
              f'and a rising RSI; {f["sector"]} of those were in passing sectors; '
              + (f'{f["hot"]} were overbought by your rule (RSI over {CFG["OB_RSI"]} or CCI over {CFG["OB_CCI"]}); ' if f.get("hot") else "")
              + f'{f["near_ob"]} were within {OV["OB_GAP"]:.0%} of an '
              f'order block and {earn_txt}, which leaves {f["setups"]}. Freshest signal first, then relative strength (RS, 1-99).'
              + ("" if m["ok"] else " The market rules fail tonight, so the paper account won't buy these.") + "</div>")
    live = (f'<div class="hint warn">Built at {ov["live_at"]} New York time, before the close, from prices that are not closes yet. '
            'The paper account only trades on the plan from a run after the close.</div>' if ov.get("live_at") else "")
    return ('<h2>OVTLYR plan</h2>' + hk("ovtlyr") + '<div class="ovseg"><button data-ov="plan" class="on">Plan</button>'
            '<button data-ov="scr">Screener</button></div><div id="ov-plan"><div class="hint">OVTLYR\'s Plan M, Plan ETF and Plan #SICADFU from the trading-plan deck, '
            'rebuilt from this page\'s data; the <b>OVTLYR plan</b> paper account trades it. OVTLYR\'s fear &amp; greed heatmap and '
            'buy/sell signals are private, so this uses stand-ins: heatmap = 14-day RSI; buy signal = the 10 EMA crossing above the '
            f'20 EMA (it counts for {OV["SIGNAL_DAYS"]} trading days); sell signal = the 10 EMA under the 20; breadth = the share of '
            'stocks with the 10 EMA above the 20, against its 10-day average. Left out: OVTLYR channels and the per-stock backtest '
            'check.</div>'
            f'{live}<div class="ovg">{mk}{sc}{et}</div><details id="ovm" class="ovm">{summ}{table}{gone}{funnel}</details>'
            '<div class="hint">Click <b>Plan M stocks</b> for every stock that passes the plan tonight. The list is rebuilt each '
            'night: stocks that newly pass are marked New, and stocks that stop passing drop off, with the reason.</div></div>'
            + ov_screen_html(ov))


OV_LABELS = dict(  # the screener's columns: short name, what it checks
    sig=("Buy signal", f"the 10 EMA crossed over the 20 in the last {OV['SIGNAL_DAYS']} trading days"),
    trend=("Uptrend", "10 EMA over the 20 and the close over the 50 EMA"),
    e10=("Over 10 EMA", "the close above the 10 EMA"),
    rsi=("RSI rising", "the heatmap stand-in warming up"),
    px=("$10-$350", "the deck's price range"),
    sec=("Sector passes", "its sector passes the plan's sector rules (Health Care is excluded)"),
    hot=("Not overbought", "RSI and CCI no longer count (dropped Oct 15), so every row passes"),
    ob=("Clear of order blocks", f"more than {OV['OB_GAP']:.0%} from an untouched order block"),
    earn=("No earnings soon", f"{OV['EARN_DAYS']}+ days to earnings; looked up for stocks one rule or less from a setup"))
OV_MKT = dict(heat="SPY heat rising", signal="SPY buy signal", trend="SPY uptrend", breadth="Breadth rising", hot="Not overbought")


def ov_screen_html(ov, unit="stock", group="Sector"):
    """The OVTLYR screener view: the market checks, then every stock against Plan M's 9 rules, closest to a setup first.
    The rows go in as JSON and the page builds the table, so 500 stocks stay small."""
    rows = ov.get("screen")
    if rows is None:
        return ""
    m = ov["market"]
    chips = "".join(f'<span class="ovk {"y" if c["ok"] else "n"}" title="{html_esc(c["text"])}">{"✓" if c["ok"] else "✗"} '
                    f'{OV_MKT.get(c["k"], c["k"])}</span>' for c in m["checks"])
    keys = [k for k in OV_RULES if any(r[5][OV_RULES.index(k)] != "-" for r in rows) or k in ("ob",)]
    keys = [k for k in keys if k != "hot"]       # RSI / CCI no longer count (2026-10-15): the column would always pass
    data = json.dumps(dict(rules=[[OV_RULES.index(k), *OV_LABELS[k]] for k in keys], rows=rows, unit=unit, ch=ov.get("charted") or []),
                      separators=(",", ":")).replace("</", "<\\/")
    legend = " · ".join(f"<b>{OV_LABELS[k][0]}</b>: {html_esc(OV_LABELS[k][1])}" for k in keys)
    secs = sorted({r[1] for r in rows if r[1]})
    return (f'<div id="ov-scr" hidden><div class="ovmk"><b>Market</b> <span class="pill {"y" if m["ok"] else "n"}">Plan M '
            f'{"on" if m["ok"] else "off"}</span>{chips}</div>'
            f'<div class="hint">Every {unit} with 1M+ shares a day, checked against Plan M\'s {len(keys)} {unit} rules, closest to a '
            f'setup first. Heat is the 14-day RSI, the plan\'s stand-in for OVTLYR\'s fear &amp; greed. Signal is days since the '
            f'10 EMA crossed over the 20. Tap a blue ticker for its chart.</div>'
            f'<div class="ovf"><span class="ovfc" data-f="0"></span><span class="ovfc on" data-f="2"></span><span class="ovfc" data-f="99"></span>'
            f'<select id="ovsec"><option value="">All {group.lower()}s</option>'
            + "".join(f'<option>{html_esc(x)}</option>' for x in secs)
            + f'</select></div><div class="wrap"><table id="ov-s"></table></div><div class="hint">{legend}</div>'
            f'<script type="application/json" id="ov-data">{data}</script></div>' + OV_SCREEN_JS)


# the screener's look and the Plan | Screener switch; plain strings, so no doubled braces
OV_SCREEN_JS = """<style>
.ovseg{display:inline-flex;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:3px;margin:2px 0 12px}
.ovseg button{border:0;background:none;padding:6px 18px;border-radius:8px;font:inherit;font-weight:700;font-size:13px;color:var(--mut);cursor:pointer}
.ovseg button.on{background:var(--card);color:var(--fg);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.ovmk{display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:8px}
.ovmk b{margin-right:4px}.ovk,.ovmk .pill,.ovfc{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;background:var(--bg)}
.ovk.y,.ovmk .pill.y{background:#e5f6ef;color:var(--up)}.ovk.n,.ovmk .pill.n{background:#fdeceb;color:var(--dn)}
.ovf{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0}.ovfc{cursor:pointer;border:1px solid var(--line)}.ovfc.on{background:var(--fg);color:var(--card);border-color:var(--fg)}
.ovf select{font:inherit;font-size:12px;padding:3px 8px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
#ov-s{width:100%;border-collapse:collapse}#ov-s th{white-space:nowrap}#ov-s th.c{white-space:normal;font-size:11px;line-height:1.2;min-width:52px;text-align:center}#ov-s td{white-space:nowrap}#ov-s td.c{text-align:center}
.od{display:inline-flex;width:18px;height:18px;border-radius:50%;align-items:center;justify-content:center;font-size:10px;font-weight:800;font-style:normal}
.od.y{background:#e5f6ef;color:var(--up)}.od.n{background:#fdeceb;color:var(--dn)}.od.u{background:var(--bg);color:var(--mut)}
.oh{display:inline-block;min-width:30px;text-align:center;border-radius:6px;padding:1px 6px;font-weight:800;font-size:12px;color:#14202e}
.oa{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;background:var(--bg);color:var(--mut)}
.oa.r{background:#e5f6ef;color:var(--up)}.oa.w{background:#fff4de;color:#a86700}
#ov-s td.ow{color:var(--dn);font-size:12px;white-space:normal;min-width:160px;text-align:left}#ov-s td.oz{display:none}
@media(max-width:760px){#ov-s .c,#ov-s .os,#ov-s th.c,#ov-s td.ow,#ov-s .oc,#ov-s th{display:none}
#ov-s,#ov-s tbody{display:block}#ov-s tr{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:9px 2px;border-bottom:1px solid var(--line)}
#ov-s td{border:0;padding:0}#ov-s td.oz{display:block;flex-basis:100%;white-space:normal}.oz .odr{display:flex;gap:3px;margin:2px 0}.oz .om{color:var(--dn);font-size:12px;text-align:left}#ov-s thead{display:none}}
</style><script>(function(){
const D=JSON.parse(document.getElementById('ov-data').textContent),CH=new Set(D.ch),T=document.getElementById('ov-s'),S=document.getElementById('ovsec');
let lim=2;
const miss=r=>D.rules.filter(q=>r[5][q[0]]==='0'),n0=r=>miss(r).length;
function heat(v,up){return v>=70?'#f4a6a0':v<30||!up?'#f7dc7a':'#a8e0bf'}   // green only while rising
const dot=c=>c==='1'?'<i class="od y">✓</i>':c==='0'?'<i class="od n">✗</i>':'<i class="od u" title="not checked">·</i>';
function away(k){return k?'<span class="oa'+(k<=2?' w':'')+'">'+k+' away</span>':'<span class="oa r">Ready</span>'}
function draw(){
 const rows=D.rows.filter(r=>(!S.value||r[1]===S.value)&&(lim>=99||n0(r)<=lim));
 const head='<thead><tr><th>Ticker</th><th class="os">'+(D.unit==='coin'?'Category':'Sector')+'</th><th class="oc">Close</th><th>Heat</th><th class="oc">Signal</th>'
  +D.rules.map(q=>'<th class="c" title="'+q[2]+'">'+q[1]+'</th>').join('')+'<th></th><th class="ow">Missing</th></tr></thead>';
 T.innerHTML=head+'<tbody>'+(rows.length?rows.slice(0,400).map(r=>{const m=miss(r),k=m.length,ms=m.map(q=>q[1]).join(', ');
  return '<tr><td>'+(CH.has(r[0])?'<b class="tk" data-tk="'+r[0]+'">'+r[0]+'</b>':'<b>'+r[0]+'</b>')+'</td><td class="os mut">'+r[1]+'</td><td class="oc">'+r[2]+'</td>'
  +'<td><span class="oh" style="background:'+heat(r[3],r[5][3]==='1')+'">'+Math.round(r[3])+'</span></td><td class="oc">'+(r[4]===null?'<span class="mut">—</span>':r[4]+'d')+'</td>'
  +D.rules.map(q=>'<td class="c">'+dot(r[5][q[0]])+'</td>').join('')+'<td>'+away(k)+'</td><td class="ow">'+ms+'</td>'
  +'<td class="oz"><div class="odr">'+D.rules.map(q=>dot(r[5][q[0]])).join('')+'</div><div class="om">'+(k?'Missing: '+ms:'Passes every rule')+'</div></td></tr>'}).join('')
  :'<tr><td colspan="20" class="mut">No '+D.unit+' is that close tonight.</td></tr>')+'</tbody>';
}
const cnt=l=>D.rows.filter(r=>(!S.value||r[1]===S.value)&&(l>=99||n0(r)<=l)).length;
function chips(){document.querySelectorAll('.ovfc').forEach(c=>{const l=+c.dataset.f;c.classList.toggle('on',l===lim);
 c.textContent=(l===0?'Ready ':l===2?'2 rules away or fewer ':'All ')+cnt(l)})}
document.querySelectorAll('.ovfc').forEach(c=>c.onclick=()=>{lim=+c.dataset.f;chips();draw()});
S.onchange=()=>{chips();draw()};
T.onclick=e=>{const t=e.target.closest('.tk');if(t&&window.openChart){e.stopPropagation();openChart(t.dataset.tk)}};
if(!cnt(2))lim=99;chips();draw();
document.querySelectorAll('.ovseg button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.ovseg button').forEach(x=>x.classList.toggle('on',x===b));
 document.getElementById('ov-plan').hidden=b.dataset.ov!=='plan';document.getElementById('ov-scr').hidden=b.dataset.ov!=='scr';
 try{localStorage.setItem('ovview',b.dataset.ov)}catch(e){}});
try{if(localStorage.getItem('ovview')==='scr')document.querySelector('.ovseg [data-ov=scr]').click()}catch(e){}
})();</script>"""


def ss_html(df, sw, mkt_hot=""):
    """Strongest sector, strongest stock: the market and the sectors, strongest first, each with its strongest stocks,
    then the list itself ranked by the 40 / 40 / 20 score, with each part shown."""
    if not sw or "S&P 500" not in sw or "strength" not in df:
        return ""
    m = sw["S&P 500"]
    ok = df[df.ss_ok].sort_values("strength", ascending=False)
    tk = lambda t: f'<b class="tk" data-tk="{t}">{t}</b>'
    srows = []
    secs = sorted((n for n in sw if n != "S&P 500"), key=lambda n: -sw[n]["rise"])
    for i, n in enumerate(secs):
        w = sw[n]
        top = ok[ok.sector == n].sort_values("rs_n").head(SS["PER_SECTOR"])
        best = ", ".join(tk(t) for t in top.ticker) or (
            '<span class="mut">none: ' + ("over the 75 line" if w["z"] == 2 else "fading") + "</span>" if not (w["on"] and w["z"] != 2)
            else '<span class="mut">' + (f'{hot} in your uptrend, all overbought' if (hot := int((df.core & (df.sector == n)).sum())) else 'no stock in your uptrend') + '</span>')
        srows.append(f'<tr><td data-v="{i + 1}">{i + 1}</td><td data-v="{html_esc(n)}">{html_esc(SHORT_SECTOR.get(n, n))}</td>'
                     f'<td data-v="{w["rise"]}">{w["rise"]:.0f}%</td><td data-v="{w["avg"]}">{w["avg"]:.0f}%</td>'
                     f'<td data-v="{int(w["on"] and w["z"] != 2)}">{swing_tag(w)}</td><td data-v="{len(top)}" class="why">{best}</td></tr>')
    rows = []
    for i, r in enumerate(ok.head(SS["N"]).itertuples()):
        st = (f'<b class="{"up" if r.setup == "Momentum" else ""}">{r.tier} {r.setup}</b>' if r.has_setup else '<span class="mut">no setup</span>')
        rows.append("<tr>" + "".join(f'<td data-v="{v}">{c}</td>' for c, v in [
            (i + 1, i + 1), (f'{tk(r.ticker)}<div class="sec">{html_esc(r.sector)}</div>', r.ticker),
            (f"<b>{r.strength:.1f}</b>", r.strength), (f"{r.ss_mkt:.1f}", r.ss_mkt), (f"{r.ss_sec:.1f}", r.ss_sec),
            (f"{r.ss_stk:.1f}", r.ss_stk), (f"{int(r.rs_n)} of {int(r.rs_of)}", r.rs_n),
            (f'<span class="{"up" if r.rs > 0 else "dn"}">{r.rs * 100:+.0f}%</span>', round(r.rs, 4)),
            (st, int(r.has_setup)), (f"{r.close:.2f}", r.close),
            (f'<span class="{"up" if r.chg1m > 0 else "dn"}">{r.chg1m:+.1f}%</span>', round(r.chg1m, 2))]) + "</tr>")
    head = ["#", "Stock", "Score", "Market (40)", "Sector (40)", "Stock (20)", "RS rank in sector", "RS", "Setup", "Close", "1M"]
    lst = (f'<div class="wrap"><table id="ss" class="pkt"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table></div>' if rows else
           '<div class="hint pke">No stock passes tonight: none is in your uptrend in a sector that is turning up and rising.</div>')
    n_set = int(ok.has_setup.sum())
    warn = (f'<div class="hint warn obn">The market is overbought tonight ({html_esc(mkt_hot)}), so by your rule nothing gets '
            'bought from this list.</div>') if mkt_hot else ""
    return ('<h2 id="ssh">Strongest sector, strongest stock</h2>' + hk("strongest")
            +
            '<div class="hint">Your rule: find the strongest sector, then the strongest stock inside it. A move is 40% the '
            'market, 40% the sector and 20% the stock, so the score adds up those three parts (100 at most). '
            '<b>Market</b> = 40% of the S&amp;P 500\'s Rising, the share of its stocks with the 10 EMA over the 20 and price over the 50 EMA (the breadth '
            'view). <b>Sector</b> = 40% of the stock\'s sector\'s Rising. <b>Stock</b> = 20% of how it ranks on relative '
            'strength (IBD-style: 40% on the last 3 months, 20% each on 6, 9 and 12) among the liquid stocks in its sector, '
            '20 for the strongest. On the list: stocks in your uptrend or with a Regular setup (EMA10 over EMA20 and price over EMA50, under the 150 line), in a sector that is turning up and rising (Rising '
            f'above its 10-day average, ▲, and not over your {CFG["OB_BREADTH"]} line), and not overbought themselves. '
            '<b>Your system</b> and <b>Your system, after 2 PM</b> buy from it: Super setups first, then Regular ones, highest score first.</div>' + warn
            + f'<div class="hint" style="margin-top:6px">Market tonight: S&amp;P 500 Rising <b>{m["rise"]:.0f}%</b> '
            f'(10-day average {m["avg"]:.0f}%) {swing_tag(m)}, worth <b>{SS["W_MKT"] * m["rise"]:.1f}</b> of 40 points '
            f'for every stock. {len(ok)} stocks on the list, {n_set} of them setups.</div>'
            '<div class="wrap"><table id="ssec" class="pkt"><thead><tr><th>#</th><th>Sector</th><th>Rising</th>'
            '<th>10-day avg</th><th>State</th><th class="why">Strongest stocks</th></tr></thead>'
            f'<tbody>{"".join(srows)}</tbody></table></div>{lst}')


def html_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


SHORT_SECTOR = {"Information Technology": "Technology", "Consumer Discretionary": "Discretionary",
                "Communication Services": "Communication", "Consumer Staples": "Staples"}


def md(day):
    """Oct 1, from a date or an ISO date string."""
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d:%b} {d.day}"


def heat_html(bh, days=63):
    """Breadth heatmap: a row for the S&P 500, then one per sector (most stocks rising tonight first), a column per
    trading day for the last 3 months, colored by the share of stocks with the 10 EMA above the 20 and price above the 50 EMA.
    Returns the HTML and the numbers behind it (for the tap / hover tooltip)."""
    if not bh or "S&P 500" not in bh:
        return "", None
    names = ["S&P 500"] + sorted((n for n in bh if n != "S&P 500"), key=lambda n: -bh[n].rise.iloc[-1])
    idx = bh["S&P 500"].index[-days:]
    r1 = lambda v: [None if x != x else round(float(x), 1) for x in v]
    data, rows = dict(t=[d.strftime("%Y-%m-%d") for d in idx], rows=[]), []
    for i, n in enumerate(names):
        b, st = bh[n].reindex(idx), swing_state(bh[n])
        zc = {2: " o", -1: " u", 0: ""}
        zd = lambda v, on: zc[bzone(round(float(v), 1))] or (" d" if on == 0 else "")   # d = in the green zone but on a downswing: yellow
        cells = "".join(f'<i class="h{min(9, int(v // 10))}{zd(v, on)}"></i>' if v == v else "<i></i>"
                        for v, on in zip(b.rise, b.on))
        rows.append(f'<div class="hmr"><span class="hml">{html_esc(SHORT_SECTOR.get(n, n))}</span>'
                    f'<span class="hmc" data-i="{i}">{cells}</span><span class="hmv">{st["rise"]:.0f}% {swing_tag(st, False)}</span></div>')
        data["rows"].append(dict(n=n, r=r1(b.rise), a=r1(b.avg), u=r1(b.up), s=[None if v != v else int(v) for v in b.on]))
    ticks = [(k, d) for k, d in enumerate(idx) if k == 0 or d.month != idx[k - 1].month]
    if len(ticks) > 1 and ticks[1][0] < 8:          # a first month with only a few days would crowd the next label
        ticks = ticks[1:]
    axis = "".join(f'<b style="left:{k / len(idx) * 100:.1f}%">{d:%b}</b>' for k, d in ticks)
    zkey = (f'<span class="hmz"><i class="o"></i>over {CFG["OB_BREADTH"]}: overbought</span>'
            f'<span class="hmz"><i class="u"></i>under {CFG["OS_BREADTH"]}: oversold (red too)</span>'
            f'<span class="hmz"><i class="g d"></i>30-75% but falling (under its 10-day average): yellow</span>')
    return (f'<div class="hm" id="hm">{"".join(rows)}<div class="hmr"><span></span><span class="hmt">{axis}</span><span></span></div>'
            f'<div class="hmk"><span class="hmz"><i class="g"></i>{CFG["OS_BREADTH"]}-{CFG["OB_BREADTH"]}% and rising: green</span>{zkey}</div><div id="hmtip" class="hmtip" hidden></div></div>'), data


def bcls(w):
    """The user's breadth colours (2026-10-31): under 30 or over 75 = red, 30-75 and rising (above its 10-day average) =
    green, the only time it's green; 30-75 and falling = yellow. Returns the text class: dn / up / wn."""
    return "dn" if w["z"] != 0 else "up" if w["on"] else "wn"


def swing_tag(w, since=True):
    """A group's state for the page: OB (overbought, over 75: no upswing then, the user's rule), else ▲ upswing / ▼ fading,
    with OS when it's oversold (under 30); since = add the day the state began."""
    if w["z"] == 2:
        return '<span class="obt">OB</span>' + (f' <span class="mut">since {md(w["zsince"])}</span>' if since else "")
    arrow = f'<span class="{bcls(w)}">{"▲" if w["on"] else "▼"}' + (f' since {md(w["since"])}' if since else "") + '</span>'
    return arrow + (' <span class="ost">OS</span>' if w["z"] == -1 else "")


def line_data(bh):
    """The breadth line chart's numbers: for the S&P 500 and each sector, Rising and its 5-day and 10-day averages by
    day (rounded the same way the above / below states were decided, so the chart can't disagree with them), and those
    states as strings of 1 (above) and 0 (below)."""
    if not bh or "S&P 500" not in bh:
        return None
    names = ["S&P 500"] + sorted((n for n in bh if n != "S&P 500"), key=lambda n: SHORT_SECTOR.get(n, n))
    idx = bh["S&P 500"].index
    r1 = lambda v: [None if x != x else float(x) for x in v.round(1)]
    ud = lambda v: "".join("1" if x == 1 else "0" for x in v)
    g = []
    for n in names:
        b = bh[n].reindex(idx)
        g.append(dict(n=n, s=SHORT_SECTOR.get(n, n), r=r1(b.rise), a5=r1(b.a5), a10=r1(b.avg), u5=ud(b.on5), u10=ud(b.on)))
    return dict(t=[d.strftime("%Y-%m-%d") for d in idx], g=g)


# ------------------------------------------------------------ Today and News tabs
# The page opens on Today: your three steps in order (the market moving up, the strongest sector, the strongest stock
# in it), then every sector strongest first, the strongest stocks, and a glance at the other tabs.
def spy_checks(spy, w, mkt_hot=""):
    """SPY and the S&P 500's breadth against your rules, as (text, ok, detail)."""
    out = []
    if spy is not None and len(spy) > 150:
        c = spy.Close
        e10, e20, e50 = ema(c, 10).iloc[-1], ema(c, 20).iloc[-1], ema(c, 50).iloc[-1]
        m150 = (ema(c, 150) if CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()).iloc[-1]
        px = c.iloc[-1]
        out += [("SPY 10 EMA above the 20 EMA", e10 > e20, f"{e10:.2f} vs {e20:.2f}"),
                ("SPY closed above its 50 EMA", px > e50, f"{px:.2f} vs {e50:.2f}"),
                (f"SPY above its 150-day {'EMA' if CFG['LONG_MA_TYPE'] == 'EMA' else 'average'}", px > m150, f"{px:.2f} vs {m150:.2f}")]
    if w:
        out.append(("More S&amp;P 500 stocks turning up", bool(w["on"]) and w["z"] != 2,
                    f"{w['rise']:.0f}% rising, {'above' if w['rise'] > w['avg'] else 'below'} its 10-day average {w['avg']:.0f}%"))
    out.append(("Market not overbought", not mkt_hot,
                html_esc(mkt_hot) if mkt_hot else f"breadth {w['rise']:.0f}, under the {CFG['OB_BREADTH']} line" if w else "breadth not available"))
    return out


def popup_info(df, sws, spy=None, mkt_hot="", charts=None):
    """The ticker pop-up's info line: each stock's sector, that sector's rating (its rank by Rising, Rising tonight and
    its state) and the market's rating (SPY against your rules, as on Today, and the S&P 500's Rising). Returns the
    JSON the page uses: m = the market's line, s = each sector's line, t = each ticker's sector."""
    w = sws.get("S&P 500")
    if not w:
        return "null"
    def state(x):
        return ('<span class="obt">overbought</span> over the ' + str(CFG["OB_BREADTH"]) + ' line' if x["z"] == 2 else
                '<span class="ost">oversold</span> under the ' + str(CFG["OS_BREADTH"]) + ' line' if x["z"] == -1 else
                f'<span class="{bcls(x)}">{"▲ upswing" if x["on"] else "▼ fading"}</span> since {md(x["since"])}')
    checks = spy_checks(spy, w, mkt_hot)
    n_ok = sum(ok for _, ok, _ in checks)
    def today(n):
        """The group's ETF (index) price on the last bar and its change on the day."""
        c = ((charts or {}).get(n) or {}).get("D", {}).get("c") or []
        if len(c) < 2:
            return ""
        ch = (c[-1] / c[-2] - 1) * 100
        return f'{SECTOR_ETF[n]} ${c[-1]:,.2f} <b class="{"up" if ch >= 0 else "dn"}">{ch:+.2f}% today</b>'
    mkt = (f'<span class="lb">Market</span> ' + (today("S&P 500") + ' · ' if today("S&P 500") else '')
           + f'<b class="{"up" if n_ok == len(checks) else "dn"}">SPY '
           f'{"is moving up" if n_ok == len(checks) else "is not moving up"}</b> ({n_ok} of {len(checks)} checks) · '
           f'{w["rise"]:.0f}% of S&amp;P 500 stocks rising · {state(w)}')
    secs = sorted((n for n in sws if n != "S&P 500"), key=lambda n: -sws[n]["rise"])
    sec = {n: (f'<span class="lb">Sector</span> <b>{html_esc(SHORT_SECTOR.get(n, n))}</b> · #{i + 1} of {len(secs)} · '
               f'<b>{sws[n]["rise"]:.0f}%</b> rising · {state(sws[n])}' + (' · ' + today(n) if today(n) else '')) for i, n in enumerate(secs)}
    tks = {r.ticker: r.sector for r in df[["ticker", "sector"]].itertuples() if r.sector in sec}
    tks.update({e: n for n, e in SECTOR_ETF.items() if n in sec})
    return json.dumps(dict(m=mkt, s=sec, t=tks), separators=(",", ":")).replace("</", "<\\/")


def today_html(df, sws, spy=None, lists=None, ov=None, mkt_hot="", meta=""):
    w = sws.get("S&P 500")
    checks = spy_checks(spy, w, mkt_hot)
    mkt_ok = all(ok for _, ok, _ in checks)
    sh = lambda n: html_esc(SHORT_SECTOR.get(n, n))
    tk = lambda t: f'<b class="tk" data-tk="{t}">{t}</b>'
    tick = lambda ok: f'<span class="ok{"" if ok else " no"}">{"✓" if ok else "✕"}</span>'
    ss = df[df.ss_ok].sort_values("strength", ascending=False) if "ss_ok" in df else df.iloc[:0]
    secs = sorted((n for n in sws if n != "S&P 500"), key=lambda n: -sws[n]["rise"])
    n_on = {n: int((ss.sector == n).sum()) for n in secs}
    lead = next((n for n in secs if n_on[n]), None)

    # step 1: the market
    if spy is not None and len(spy) > 1:
        px, p1 = spy.Close.iloc[-1], spy.Close.iloc[-2]
        spark_ = spark(spy.Close.iloc[-30:], 96, 40, "var(--up)" if mkt_ok else "var(--dn)")
        spx = f'${px:,.2f} <span class="{"up" if px >= p1 else "dn"}">{(px / p1 - 1) * 100:+.2f}%</span>'
    else:
        spark_, spx = "", ""
    rtxt = f"{w['rise']:.0f}% of S&amp;P 500 stocks rising" if w else ""
    s1 = (f'<div class="step"><div class="n">Step 1 · The market</div><div class="sp">{spark_}</div>'
          f'<div class="big">{tick(mkt_ok)}SPY {"is moving up" if mkt_ok else "is not moving up"}</div>'
          f'<div class="sub">{spx}{" · " if spx and w else ""}{rtxt}</div>'
          '<div class="chks">' + "".join(f'<div class="chk">{tick(ok)}<span>{t}<div class="sub">{d}</div></span></div>' for t, ok, d in checks)
          + '</div>' + ('' if mkt_ok else '<div class="hint warn">Not everything is in your favor yet: wait for the market before buying.</div>') + '</div>')

    # step 2: the strongest sector
    def srow(i, n, short=False):
        x = sws[n]
        col = {"dn": "var(--dn)", "up": "var(--up)", "wn": "var(--yel)"}[bcls(x)]   # the user's breadth colours
        tag = ('<span class="pill p-dn">Over 75</span>' if x["z"] == 2 else
               '<span class="pill p-dn">Under 30</span>' if x["z"] == -1 else
               '<span class="pill p-w">Near 75</span>' if x["rise"] >= CFG["OB_BREADTH"] - 5 and n_on[n] == 0 else
               f'<span class="pill p-up">{n_on[n]} stock{"s" if n_on[n] != 1 else ""}</span>' if n_on[n] else
               '<span class="pill p-n">' + ("fading" if not x["on"] else "none pass") + '</span>')
        return (f'<div class="sr" data-sector="{html_esc(n)}" role="button" tabindex="0" title="Show {sh(n)} in the stock table">'
                f'<span class="rk">{i + 1}</span><span class="nm">{sh(n)}</span>'
                f'<span class="sbar"><b style="width:{min(x["rise"], 100):.0f}%;background:{col}"></b><i style="left:{min(x["avg"], 100):.0f}%"></i>'
                f'<u style="left:{CFG["OB_BREADTH"]}%"></u></span><span class="v">{x["rise"]:.0f}%</span><span class="tag">{tag}</span></div>')
    if lead:
        L = sws[lead]
        top = secs[0]
        why = ""
        if top != lead:
            t = sws[top]
            why = (f'{sh(top)} is higher ({t["rise"]:.0f}%) but ' + ("is over the 75 line." if t["z"] == 2 else "is fading." if not t["on"] else
                   "every one of its uptrend stocks is overbought." if int((df.core & (df.sector == top)).sum()) else "has no stock in your uptrend."))
        s2 = (f'<div class="step"><div class="n">Step 2 · Strongest sector</div><div class="big">{sh(lead)} '
              f'<span class="pill p-up">{L["rise"]:.0f}% rising</span></div><div class="sub">{why or f"{sh(lead)} leads the sectors you can trade tonight."}</div>'
              '<div class="mini">' + "".join(srow(i, n) for i, n in enumerate(secs[:4])) + '</div></div>')
    else:
        s2 = ('<div class="step"><div class="n">Step 2 · Strongest sector</div><div class="big">None tonight</div>'
              '<div class="sub">No sector is turning up and rising with a stock in your uptrend that isn’t overbought.</div>'
              '<div class="mini">' + "".join(srow(i, n) for i, n in enumerate(secs[:4])) + '</div></div>')

    # step 3: the strongest stock
    def strow(r):
        return (f'<div class="st"><span>{tk(r.ticker)}<div class="sub">{sh(r.sector)}</div></span>'
                f'<span><span class="score"><b style="width:{r.ss_mkt:.1f}%;background:var(--sc1)"></b><b style="width:{r.ss_sec:.1f}%;background:var(--acc)"></b>'
                f'<b style="width:{r.ss_stk:.1f}%;background:var(--up)"></b></span><span class="sub">{r.tier + " " + r.setup if r.has_setup else "no setup"} · RSI {r.rsi:.0f}</span></span>'
                f'<span class="chg"><span>${r.close:,.2f}</span><span class="{"up" if r.chg1d >= 0 else "dn"}">{r.chg1d:+.2f}%</span></span>'
                f'<span class="sc">{r.strength:.0f}</span></div>')
    if len(ss):
        b = ss.iloc[0]
        s3 = (f'<div class="step"><div class="n">Step 3 · Strongest stock</div><div class="big">{tk(b.ticker)} '
              f'<span class="pill p-up">score {b.strength:.0f}</span></div><div class="sub">#1 in {sh(b.sector)} · '
              f'{b.tier + " " + b.setup if b.has_setup else "no setup"} · ${b.close:,.2f}</div>'
              '<div class="mini">' + "".join(strow(r) for r in ss.iloc[1:5].itertuples()) + '</div></div>')
    else:
        s3 = ('<div class="step"><div class="n">Step 3 · Strongest stock</div><div class="big">None tonight</div>'
              '<div class="sub">No stock passes every check.</div></div>')

    secs_card = ('<div class="tcard"><h3>All sectors, strongest first <a data-go="sectors">Sector charts ›</a></h3>'
                 '<div class="hint">Share of each sector\'s S&amp;P 500 stocks with the 10 EMA over the 20 and price over the 50 EMA · tick = its 10-day '
                 f'average · dashed = your {CFG["OB_BREADTH"]} line. Tap a sector to see its stocks.</div>'
                 + "".join(srow(i, n) for i, n in enumerate(secs))
                 + f'<div class="lgd"><span><i style="background:var(--up)"></i>{CFG["OS_BREADTH"]}-{CFG["OB_BREADTH"]}% and rising</span><span><i style="background:var(--yel)"></i>{CFG["OS_BREADTH"]}-{CFG["OB_BREADTH"]}% and falling</span>'
                 f'<span><i style="background:var(--dn)"></i>Over {CFG["OB_BREADTH"]} overbought or under {CFG["OS_BREADTH"]} oversold</span></div></div>') if secs else ""
    st_card = ('<div class="tcard"><h3>Strongest stocks in the strongest sectors <a data-go="stocks">All ' + str(len(ss)) + ' ›</a></h3>'
               '<div class="hint">Score out of 100 = market 40% + sector 40% + the stock\'s strength in its sector 20%</div>'
               + ("".join(strow(r) for r in ss.head(10).itertuples()) or '<div class="hint pke">No stock passes tonight.</div>')
               + '<div class="lgd"><span><i style="background:var(--sc1)"></i>Market</span><span><i style="background:var(--acc)"></i>Sector</span>'
               '<span><i style="background:var(--up)"></i>Stock</span></div></div>')

    chips = lambda rows: "".join(f'<span>{tk(r["ticker"])}</span>' for r in rows) or '<span class="mut">none tonight</span>'
    pk = ('<div class="tcard"><h3>Top picks <a data-go="picks">Open ›</a></h3><div class="hint">With calls by your rules</div>'
          + "".join(f'<div class="sub">{lbl}</div><div class="chips">{chips(lists[k]["rows"][:8])}</div>'
                    for k, lbl in (("nu", "New uptrends"), ("bo", "Breakout watch"), ("ai", "AI picks")))
          + '</div>') if lists else ""
    pp = ('<div class="tcard"><h3>Paper trading <a data-go="paper">Open ›</a></h3><div class="hint">Four $5,000 accounts (restarted Oct 15). Tap one for its trades.</div>'
          '<div id="tdpp"><div class="hint">Loading…</div></div></div>')
    if ov:
        m, f = ov["market"], ov["funnel"]
        ovc = ('<div class="tcard"><h3>OVTLYR plan <a data-go="ovtlyr">Open ›</a></h3>'
               f'<div class="hint">Plan M is {"on" if m["ok"] else "off"}: market checks {sum(c["ok"] for c in m["checks"])} of {len(m["checks"])} · '
               f'{f["setups"]} Plan M setup{"s" if f["setups"] != 1 else ""}</div>'
               + "".join(f'<div class="chk">{tick(c["ok"])}<span>{html_esc(c["text"])}</span></div>' for c in m["checks"] if not c["ok"])
               + "".join(f'<div class="chk">{tick(e["ok"])}<span>Plan ETF {k} {"set up" if e["ok"] else "not set up"}</span></div>' for k, e in ov["etf"].items())
               + '</div>')
    else:
        ovc = ""
    return (f'<div class="meta">{meta}</div>{hk("today")}<div class="steps">{s1}{s2}{s3}</div>'
            f'<div class="tgrid">{secs_card}{st_card}</div><div class="trow">{pk}{pp}{ovc}</div>')


def sector_tiles(df, sws, bh, etfs=None, unit="stock"):
    """A colored tile per sector, strongest first: Rising tonight, its last 5 days as a line, and its state."""
    etfs = etfs if etfs is not None else SECTOR_ETF
    ss = df[df.ss_ok] if "ss_ok" in df else df.iloc[:0]
    secs = sorted((n for n in sws if n != "S&P 500" and n in (bh or {})), key=lambda n: -sws[n]["rise"])
    out = []
    for n in secs:
        w, k = sws[n], int((ss.sector == n).sum())
        r = w["rise"]
        bg, dark = {"dn": "#f4a6a0", "up": "#a8e0bf", "wn": "#f7dc7a"}[bcls(w)], 1   # the user's 3 colours: over 75 or under 30 / 30-75 rising / 30-75 falling
        tag = ("OVER 75" if w["z"] == 2 else "UNDER 30" if w["z"] == -1 else "NEAR 75" if r >= CFG["OB_BREADTH"] - 5 else "RISING" if w["on"] else "FADING")
        line = spark(bh[n].rise.iloc[-5:], 64, 28, "#14202e" if dark else "#fff")
        sub = (f'{etfs[n]} · ' if etfs.get(n) else "") + (f"{k} on list" if k else "none pass")
        out.append(f'<div class="stile{" dk" if dark else ""}" data-sector="{html_esc(n)}" role="button" tabindex="0" style="background:{bg}" '
                   f'title="Show {html_esc(n)} in the {unit} table"><span class="nm">{html_esc(SHORT_SECTOR.get(n, n))}</span>'
                   f'<span class="e">{sub}</span><span class="bd">{tag}</span><span class="v">{r:.0f}%</span><span class="spk">{line}</span></div>')
    return ('<div class="hint">Red = overbought (over 75% of stocks rising) or oversold (under 30%), green = 30-75% and rising (above its 10-day average), yellow = 30-75% and falling, strongest first · line = the last 5 days. '
            f'Tap one to see its {unit}s.</div><div class="stiles">' + "".join(out) + '</div>') if out else ""


def news_html(df, sws, etfs=None, market="stock", suf="", lbl="Strongest stocks"):
    """News tab: TradingView's free news feed, for the whole market or one sector (its ETF) or one of its strongest stocks."""
    etfs = etfs if etfs is not None else SECTOR_ETF
    ss = df[df.ss_ok].sort_values("strength", ascending=False) if "ss_ok" in df else df.iloc[:0]
    secs = sorted((n for n in sws if n != "S&P 500" and n in etfs), key=lambda n: -sws[n]["rise"]) or [n for n in etfs if n != "S&P 500"]
    lead = {n: list(ss[ss.sector == n].ticker.head(4)) for n in secs}
    btn = lambda n: (f'<button data-n="{html_esc(n)}" data-sym="{"AMEX:" + etfs[n] if etfs.get(n) else ""}">{html_esc(SHORT_SECTOR.get(n, n))}'
                     + (f' <span class="mut">{sws[n]["rise"]:.0f}%</span>' if n in sws else '') + '</button>')
    return ('<h2>News</h2>' + hk("news") + '<div class="hint">Market news first. Tap a sector for news on its SPDR ETF (strongest sector first), '
            'then any of its strongest stocks for news on that stock. From TradingView\'s free news feed.</div>'
            f'<div class="bar nw"><button class="on" data-n="" data-sym="">Market</button>{"".join(btn(n) for n in secs)}</div>'
            f'<div class="nwl" id="nwl" hidden></div><div class="nwh" id="nwh"></div><div id="nwc" class="nwc"></div>'
            f'<script>const NEWS={json.dumps(dict(lead=lead, market=market, suf=suf, lbl=lbl), separators=(",", ":"))};</script>')


def render(picks, breadth, secb, df, asof, demo, charts=None, lists=None, earn=None, calls=None, live_at=None, ov=None, bh=None, sw=None, spy=None, vix=None):
    x, p = breadth.iloc[-1], breadth.iloc[-6]
    reg, rcls = regime(breadth)
    arrow = lambda a, b: "▲" if a > b else "▼" if a < b else "–"
    cards = "".join([
        card("% above 20-day", f"{x.pct20:.0f}%", f"{arrow(x.pct20, p.pct20)} vs 5d ago {p.pct20:.0f}%", breadth.pct20, x.pct20 > 50),
        card("% above 50-day", f"{x.pct50:.0f}%", f"{arrow(x.pct50, p.pct50)} vs 5d ago {p.pct50:.0f}%", breadth.pct50, x.pct50 > 50),
        card("% above 200-day", f"{x.pct200:.0f}%", f"{arrow(x.pct200, p.pct200)} vs 5d ago {p.pct200:.0f}%", breadth.pct200, x.pct200 > 50),
        card("Advance / Decline", f"{int(x.adv)} / {int(x.dec)}", "A/D line, last 60 days", breadth.ad_line, x.adv > x.dec),
        card("New 52w highs / lows", f"{int(x.nh)} / {int(x.nl)}", "highs (net) over time", breadth.nh - breadth.nl, x.nh > x.nl),
        card("Up / down volume", f"{x.udvol:.2f}", ">1 = volume favors buyers", breadth.udvol, x.udvol > 1),
    ])
    up_n, liq_n = int(df.core.sum()), len(df)
    up_pct = up_n / liq_n * 100 if liq_n else 0
    sws = {n: swing_state(b) for n, b in (bh or {}).items()}
    w = sws.get("S&P 500")
    rise_card = card("S&amp;P 500 stocks rising (EMA10 &gt; 20, price &gt; EMA50)", f"{w['rise']:.0f}%",
                     (f"overbought (over {CFG['OB_BREADTH']}) since {md(w['zsince'])}" if w["z"] == 2 else
                      f"{'▲ upswing' if w['on'] else '▼ fading'} since {md(w['since'])}"
                      + (f", oversold (under {CFG['OS_BREADTH']})" if w["z"] == -1 else ""))
                     + f", 10-day avg {w['avg']:.0f}%", bh["S&P 500"].rise.iloc[-60:], bcls(w)) if w else ""
    cards = (f'<div class="card"><div class="lbl">In uptrend (EMA10 &gt; 20, price &gt; EMA50 &amp; 150)</div>'
             f'<div class="val {"up" if up_pct > 50 else "dn"}">{up_n} / {liq_n}</div>'
             f'<div class="sub">{up_pct:.0f}% of stocks averaging 1M+ shares/day</div></div>') + rise_card + cards

    def bar(v, good=50):
        c = "var(--up)" if v >= good else "var(--dn)"
        return f'<div class="bar2"><i style="width:{max(v, 0):.0f}%;background:{c}"></i></div>'
    def delta(now, then):
        d = now - then
        return f'<span class="{"up" if d > 0 else "dn" if d < 0 else ""}">{d:+.0f}</span>'
    def rising(n):
        w = sws.get(n)
        if "S&P 500" not in sws:           # no breadth view tonight: no column
            return ""
        if not w:
            return '<td data-v=""></td>'
        return f'<td data-v="{w["rise"] - w["avg"]:.1f}">{w["rise"]:.0f}% {swing_tag(w)}</td>'
    srows = []
    for _, s_ in secb.iterrows():
        srows.append(
            f'<tr data-sector="{s_.sector}"><td><b>{s_.sector}</b></td>'
            f'<td data-v="{s_.up_pct}"><b>{s_.uptrend}</b> / {s_.liquid} <span class="mut">({s_.up_pct:.0f}%)</span>{bar(s_.up_pct)}</td>'
            + rising(s_.sector) +
            f'<td data-v="{s_.momentum}">{s_.momentum}</td><td data-v="{s_.pullback}">{s_.pullback}</td>'
            f'<td data-v="{s_.pct20}">{s_.pct20:.0f}% {delta(s_.pct20, s_.pct20_5d)}</td>'
            f'<td data-v="{s_.pct50}">{s_.pct50:.0f}% {delta(s_.pct50, s_.pct50_5d)}</td>'
            f'<td data-v="{s_.pct200}">{s_.pct200:.0f}% {delta(s_.pct200, s_.pct200_5d)}</td>'
            f'<td data-v="{s_.adv - s_.dec}">{s_.adv} / {s_.dec}</td>'
            f'<td data-v="{s_.nh - s_.nl}">{s_.nh} / {s_.nl}</td></tr>')
    try:
        vx_html = vix_html(vix)
    except Exception as e:                 # an extra; never block the page
        print("  VIX panel failed:", e)
        vx_html = ""
    heat, hm_data = heat_html(bh)
    try:
        bl_data = line_data(bh)
    except Exception as e:                 # an extra; never block the page
        print("  breadth line failed:", e)
        bl_data = None
    line_html = ('<div class="hint">The breadth line: Rising for the S&amp;P 500 or the sector you pick (or tap its row in the '
                 'heatmap), day by day, with its 5-day and 10-day averages (both exponential moving averages). Rising crossing '
                 'above its 10-day average is what the heatmap calls an upswing. The dashed lines at '
                 f'{CFG["OB_BREADTH"]} and {CFG["OS_BREADTH"]} are your overbought and oversold lines: over '
                 f'{CFG["OB_BREADTH"]} there is no upswing and no buy signal (your rule).</div>'
                 '<div class="bln" id="bln"><div class="blh"><b>Breadth line</b><select id="blg" aria-label="S&amp;P 500 or sector">'
                 + "".join(f'<option value="{i}">{html_esc(g["s"])}</option>' for i, g in enumerate(bl_data["g"]))
                 + '</select><div class="bar blr">'
                 + "".join(f'<button data-r="{k}"' + (' class="on"' if k == 63 else '') + f'>{lbl}</button>'
                           for lbl, k in (("3M", 63), ("6M", 126), ("1Y", 252), ("All", 0)))
                 + '</div></div><div class="blk" id="blk"></div><div class="blc"></div></div>') if bl_data and heat else ""
    bt_html = ('<h2>Breadth over time</h2>' + hk("breadth") + '<div class="hint">Rising = the share of S&amp;P 500 stocks with the 10 EMA above the 20 and the close above the 50 EMA '
                      '(your rule), by day for the last 3 months; green = 30-75% and rising (above its 10-day average), the only time it is green; yellow = 30-75% and falling (under its 10-day average); red = over 75 (overbought) or under 30 (oversold). ▲ = an upswing (Rising '
                      'above its own 10-day average), ▼ = fading. Your lines: <span class="obt">OB</span> = overbought, Rising '
                      f'over {CFG["OB_BREADTH"]} (no upswing then, and nothing in it gets bought); <span class="ost">OS</span> = '
                      f'oversold, under {CFG["OS_BREADTH"]}. Tap or hover a row for the numbers.</div>' + heat + line_html) if heat else ""
    sector_html = ('<h2>Sector breadth</h2>' + hk("sector_table")
                   + '<div class="hint">Click a sector to filter the stock list. ± is the change vs 5 trading days ago. '
                   + ('Rising counts S&amp;P 500 stocks only, so each sector matches its SPDR ETF; the other columns count '
                      'every stock in the scan.' if heat else '')
                   + '</div><div class="wrap"><table id="s"><thead><tr>'
                   '<th>Sector</th><th>In uptrend</th>' + ('<th>Rising (10 &gt; 20, &gt; 50)</th>' if "S&P 500" in sws else '') + '<th>Momentum</th><th>Pullback</th><th>% &gt; 20d</th>'
                   '<th>% &gt; 50d</th><th>% &gt; 200d</th><th>Adv / Dec</th><th>52w Hi / Lo</th></tr></thead>'
                   f'<tbody>{"".join(srows)}</tbody></table></div>')

    order = ["S&P 500"] + [n for n in secb.sector if n != "S&P 500"]
    order += [n for n in SECTOR_ETF if n not in order]
    charts = {n: charts[n] for n in order if charts and n in charts}
    if charts:
        strip = any(c.get("sw") for c in charts.values())
        chart_html = ('<h2>Sector charts</h2>' + hk("sector_charts") + '<div class="hint">Sector SPDR ETFs with EMA 10 (orange), 20 (blue) and 50 (purple). '
                      'Daily shows ~6 months, weekly ~2 years, monthly ~10 years.'
                      + (' The strip under each chart is its breadth: the solid line is Rising (the share of the S&amp;P 500 '
                         'stocks in it with the 10 EMA above the 20 and price above the 50 EMA), the dotted line the share in your full uptrend. Green '
                         f'shading = {CFG["OS_BREADTH"]}-{CFG["OB_BREADTH"]}% and rising (above its 10-day average), yellow = {CFG["OS_BREADTH"]}-{CFG["OB_BREADTH"]}% and falling, red = over '
                         f'your {CFG["OB_BREADTH"]} line (overbought, no upswing) or under {CFG["OS_BREADTH"]} (oversold). Daily and weekly only: the '
                         'stock prices go back 2 years.' if strip else '') + '</div>'
                      '<div class="bar tf"><button class="on" data-tf="D">Daily</button><button data-tf="W">Weekly</button>'
                      '<button data-tf="M">Monthly</button></div><div class="charts">'
                      + "".join(f'<div class="ch" data-sector="{n}"><div class="chh"><b>{n}</b> <span class="tk mut" data-tk="{c["etf"]}">{c["etf"]}</span>'
                                f'<span class="chg"></span></div><div class="cv"></div>'
                                + ('<div class="bl"></div><div class="bv"></div>' if c.get("sw") else '') + '</div>' for n, c in charts.items())
                      + '</div><div id="chfail" class="hint" hidden>Charts could not load (chart library blocked).</div>')
    else:
        chart_html = ""
    chart_json = json.dumps(charts, separators=(",", ":"))

    def num(v, f="{:.1f}"): return "" if v is None or v != v else f.format(v)
    def flag(b): return '<span class="up">✓</span>' if b else '<span class="dn">✗</span>'
    def zone(v, hi, lo):
        """RSI or CCI with the user's lines: OB over the overbought line, OS under the oversold one."""
        if v is None or v != v:
            return ""
        tag = ('<span class="obt" title="Overbought (over ' f'{hi})">OB</span>' if v > hi else
               '<span class="ost" title="Oversold (under ' f'{lo})">OS</span>' if v < lo else "")
        txt = f"{v:.1f}" if round(v) in (hi, lo) else f"{v:.0f}"         # 70.4 reads "70.4", not "70", next to its tag
        return f"{txt}{' ' + tag if tag else ''}"
    mkt_hot = breadth_hot(None, {g: round(float(b.rise.iloc[-1]), 1) for g, b in (bh or {}).items()})
    def btc(r):
        """10-year backtest cell: points the rules beat (or trailed) holding the stock, with both returns under it."""
        ru, ho = r.get("bt_rules"), r.get("bt_hold")
        if ru is None or ru != ru:
            return ""
        e = ru - ho
        return (f'<span class="{"up" if e > 0 else "dn"}">{e:+,.0f} pts</span>'
                f'<div class="sec">{ru:+,.0f}% vs {ho:+,.0f}%</div>')
    head = ["Ticker", "Setup", "Score", "10y rules vs hold", "Close", "Open", "1D %", "5D %", "1M %", "RSI", "CCI", "ATR %", "RelVol", "From 52w hi", "vs EMA10", "vs EMA20", "vs EMA50",
            ">150", ">200", "50x150", "Contract", "Δ", "Γ", "Θ/day", "Vega", "IV", "Bid/Ask", "OI"]
    rows = []
    for _, r in picks.iterrows():
        o = r.get("opt")
        if isinstance(o, dict):
            oc = [f'{o["exp"]} {o["dte"]}d ${o["strike"]:g}C', f'{o["delta"]:.2f}', f'{o["gamma"]:.3f}', f'{o["theta"]:.2f}',
                  f'{o["vega"]:.2f}', f'{o["iv"]:.0f}%', (f'{o["bid"]:.2f}/{o["ask"]:.2f}' if o.get("quote") != "last" else f'last {o["last"]:.2f}'), (f'{o["oi"]:,}' if o["oi"] is not None else 'n/a')]
        else:
            oc = [""] * 8
        dsc = r.days_since_cross
        cross = f'new ({int(dsc)}d ago)' if r.cross else ("above" if dsc == dsc and dsc is not None else "")
        pct = lambda v: f'<span class="{"up" if v > 0 else "dn"}">{v:+.1f}</span>'
        why_ob = r.get("ob") or (mkt_hot if r.get("blocked") else "")
        st = (f'<span class="obl">Overbought</span><div class="sec">{html_esc(why_ob)}</div>' if r.setup == "Overbought" else
              f'<span class="{"tsup" if r.get("tier") == "Super" else "treg"}">{r.get("tier")}</span> {r.setup}' if r.has_setup else r.setup)
        cells = [f'<b class="tk" data-tk="{r.ticker}">{r.ticker}</b><div class="sec">{r.sector}</div>', st, f"{r.score:.0f}", btc(r), f"{r.close:.2f}",
                 f"{r.open:.2f}", pct(r.chg1d), pct(r.chg5d), pct(r.chg1m), zone(r.rsi, CFG["OB_RSI"], CFG["OS_RSI"]),
                 zone(r.get("cci"), CFG["OB_CCI"], CFG["OS_CCI"]), num(r.atr_pct), num(r.relvol, "{:.1f}x"), num(r.from_hi, "{:+.1f}%"),
                 num(r.vs10, "{:+.1f}%"), num(r.vs20, "{:+.1f}%"), num(r.vs50, "{:+.1f}%"),
                 flag(r.p150), flag(r.p200), cross] + oc
        bte = r.get("bt_rules") - r.get("bt_hold") if r.get("bt_rules") == r.get("bt_rules") and r.get("bt_rules") is not None else ""
        raw = [r.ticker, (f'{r.get("tier")} ' if r.has_setup else '') + r.setup, r.score, bte, r.close, r.open, r.chg1d, r.chg5d, r.chg1m, r.rsi, r.get("cci"), r.atr_pct, r.relvol, r.from_hi, r.vs10,
               r.vs20, r.vs50] + [""] * 11
        tds = "".join(f'<td data-v="{raw[i]}">{c}</td>' for i, c in enumerate(cells))
        rows.append(f'<tr data-setup="{r.setup}" data-tier="{r.get("tier") or ""}" data-sector="{r.sector or "Other"}" class="{"stack" if r.stack else ""}">{tds}</tr>')
    th = "".join(f"<th>{h}</th>" for h in head)
    banner = '<div class="demo">DEMO DATA, not real stocks</div>' if demo else ""
    n_m = int((picks.setup == "Momentum").sum()); n_p = int((picks.setup == "Pullback").sum())
    n_sup = int((picks.has_setup & (picks.tier == "Super")).sum()); n_reg = int((picks.has_setup & (picks.tier == "Regular")).sum())
    n_ob = int(picks.blocked.sum()) if "blocked" in picks else 0
    ob_html = ('<div class="hint warn obn">' + (f'The market is overbought tonight ({html_esc(mkt_hot)}), so by your rule no stock '
               'gets a setup: the ones that would have are marked Overbought.' if mkt_hot else
               f'Your overbought rule left out {n_ob} setup{"s" if n_ob != 1 else ""} tonight: they are marked Overbought, with why.')
               + '</div>') if n_ob or mkt_hot else ""
    paper_js = PAPER_JS.read_text(encoding="utf-8") if PAPER_JS.exists() else ""
    bt_sec, bt_js = bt_tab(picks)
    meta = (f'<span class="reg {rcls}">{reg}</span> ' if reg else "") + f"Data as of {asof}" + (f" {live_at} New York time (market open, so prices are not closes)" if live_at else " close") + " · " + (f"{n_sup} super · {n_reg} regular · {n_m} momentum · {n_p} pullback{f' · {n_ob} left out as overbought' if n_ob else ''} · stocks averaging 1M+ shares/day · "
            "S&amp;P 500 + Nasdaq 100")
    today = today_html(df, sws, spy, lists, ov, mkt_hot, meta)
    pinfo = popup_info(df, sws, spy, mkt_hot, charts)
    news = news_html(df, sws)
    tabs = [("today", "Today"), ("market", "Market"), ("sectors", "Sectors"), ("stocks", "Stocks")] + (
        [("picks", "Top picks")] if lists else []) + ([("ovtlyr", "OVTLYR plan")] if ov else []) + (
        [("paper", "Paper trading")] if paper_js else []) + ([("backtests", "Backtests")] if bt_js else []) + [("news", "News")]
    tabs_nav = "".join(f'<a href="#{k}" data-tab="{k}"{on}>{v}</a>' for k, v in tabs for on in [' class="on"' if k == "today" else ""])
    paper_html = f'<h2>Paper trading</h2>{hk("paper")}<div class="hint">{PAPER_HINT}</div><div id="pp" class="pp"></div>' if paper_js else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swing Screener {asof}</title><style>
:root{{--bg:#f4f6f9;--fg:#14202e;--mut:#6b7686;--card:#fff;--line:#e4e8ee;--up:#12936b;--dn:#d6453d;--acc:#2f6fed;--b5:#c96a12;--b10:#2a5bd7;--warn:#e0a020;--yel:#e5b800;--sc1:#a9bff5;color-scheme:light}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
html{{scroll-padding-top:112px}}
header.top{{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:30}}
.hd{{max-width:1240px;margin:auto;padding:12px 20px 0;display:flex;align-items:center;gap:8px 14px;flex-wrap:wrap}}
h1{{font-size:19px;margin:0;font-weight:800;letter-spacing:-.3px;display:flex;align-items:center}}h1::before{{content:'';width:10px;height:10px;border-radius:3px;background:var(--acc);margin-right:8px}}
.asof{{margin-left:auto;color:var(--mut);font-size:12px}}
nav.tabs{{max-width:1240px;margin:auto;padding:0 12px;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}}nav.tabs::-webkit-scrollbar{{display:none}}
nav.tabs a{{padding:11px 10px 9px;color:var(--mut);font-weight:600;text-decoration:none;border-bottom:2.5px solid transparent;white-space:nowrap}}
nav.tabs a.on{{color:var(--fg);border-color:var(--acc)}}
main{{max-width:1240px;margin:auto;padding:16px 20px 40px}}.tab[hidden]{{display:none}}.tab>h2:first-child{{margin-top:4px}}
.meta{{color:var(--mut);font-size:12px;margin-bottom:12px}}.meta .reg{{margin:0 4px 0 0;padding:1px 8px}}@media(min-width:601px){{.meta .reg{{display:none}}}}
.steps{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
.step,.tcard{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 1px 2px rgba(20,32,46,.05);padding:16px 18px;position:relative;min-width:0}}
.step .n{{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}}
.step .big{{font-size:22px;font-weight:800;letter-spacing:-.4px;margin:4px 0 2px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.step .big .tk{{text-decoration:none}}
.step .sp{{position:absolute;right:16px;top:14px}}.step .sub,.tcard .sub{{color:var(--mut);font-size:12px}}.step>.sub{{font-size:13px}}
.ok{{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:color-mix(in srgb,var(--up) 14%,transparent);color:var(--up);font-size:12px;font-weight:800;flex:none}}
.ok.no{{background:color-mix(in srgb,var(--dn) 14%,transparent);color:var(--dn)}}
.chks{{margin-top:10px}}.chk{{display:flex;gap:8px;align-items:flex-start;padding:4px 0;font-size:13px}}.chk .ok{{width:18px;height:18px;font-size:10px;margin-top:1px}}
.mini{{margin-top:10px}}.pill{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap}}
.p-up{{background:color-mix(in srgb,var(--up) 13%,transparent);color:var(--up)}}.p-w{{background:color-mix(in srgb,var(--warn) 20%,transparent);color:#9a6700}}.p-n{{background:var(--bg);color:var(--mut)}}.p-dn{{background:color-mix(in srgb,var(--dn) 13%,transparent);color:var(--dn)}}
.tgrid{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;margin-top:14px}}.trow{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}}
.tcard h3{{margin:0 0 2px;font-size:15px;display:flex;align-items:center;gap:8px}}.tcard h3 a{{margin-left:auto;font-size:12px;color:var(--acc);font-weight:600;cursor:pointer}}.tcard .hint{{margin-bottom:8px}}
.sr{{display:grid;grid-template-columns:22px 112px minmax(40px,1fr) 42px 82px;align-items:center;gap:8px;padding:7px 0;border-top:1px solid var(--line);font-size:13px;cursor:pointer}}
.sr:first-of-type{{border-top:0}}.sr:hover .nm{{color:var(--acc)}}.sr .rk{{color:var(--mut);font-weight:700;font-size:12px}}.sr .nm{{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.sr .v{{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}}
.step .sr{{grid-template-columns:16px 92px minmax(30px,1fr) 38px 78px}}
.sbar{{position:relative;height:8px;background:var(--bg);border-radius:4px}}.sbar b{{position:absolute;left:0;top:0;bottom:0;border-radius:4px}}
.sbar i{{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--fg);opacity:.45}}.sbar u{{position:absolute;top:-4px;bottom:-4px;border-left:1.5px dashed var(--warn)}}
.st{{display:grid;grid-template-columns:96px minmax(0,1fr) 80px 34px;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--line)}}.st:first-of-type{{border-top:0}}
.score{{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--bg);margin-bottom:3px}}.score b{{display:block}}
.st>span:first-child .sub{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.st .sc{{font-weight:800;text-align:right;font-size:16px;font-variant-numeric:tabular-nums}}.st .chg{{text-align:right;font-size:12px;font-variant-numeric:tabular-nums;display:flex;flex-direction:column}}
.lgd{{display:flex;gap:12px;flex-wrap:wrap;color:var(--mut);font-size:11px;margin-top:8px}}.lgd i{{display:inline-block;width:10px;height:8px;border-radius:2px;margin-right:4px;vertical-align:middle}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin:3px 0 8px}}.chips>span{{background:var(--bg);border-radius:8px;padding:3px 8px;font-size:12px}}.chips .tk{{text-decoration:none}}
.tdp{{display:grid;grid-template-columns:1fr auto;gap:0 8px;padding:7px 0;border-top:1px solid var(--line);font-size:13px;cursor:pointer}}.tdp:first-child{{border-top:0}}.tdp b:nth-child(2){{text-align:right}}.tdp .sub:nth-child(4){{text-align:right}}
.stiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin:10px 0 6px}}
.stile{{border-radius:14px;padding:12px;color:#fff;position:relative;min-height:112px;display:flex;flex-direction:column;cursor:pointer}}.stile:hover{{filter:brightness(1.06)}}
.stile .nm{{font-weight:700;font-size:15px;padding-right:64px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.stile .e{{font-size:11px;opacity:.85}}.stile .v{{font-size:28px;font-weight:800;margin-top:auto;letter-spacing:-.5px}}
.stile .bd{{position:absolute;right:10px;top:10px;font-size:10px;font-weight:700;background:rgba(255,255,255,.25);border-radius:999px;padding:2px 7px}}.stile .spk{{position:absolute;right:10px;bottom:12px}}
.stile.dk{{color:var(--fg)}}.stile.dk .bd{{background:rgba(0,0,0,.08)}}
.bar.nw{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}.bar.nw button{{margin:0}}.nwl{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:10px;font-size:12px;color:var(--mut)}}.nwl[hidden]{{display:none}}
.nwl button{{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:4px 10px;font-weight:700;color:var(--fg);cursor:pointer}}.nwl button.on{{border-color:var(--acc);color:var(--acc)}}
.nwh{{font-size:12px;color:var(--mut);margin:10px 0 6px}}.nwh a{{color:var(--acc)}}.nwc{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;min-height:200px}}
@media(max-width:900px){{.steps,.tgrid,.trow{{grid-template-columns:minmax(0,1fr)}}}}
@media(max-width:600px){{.hd{{padding:10px 14px 0}}.asof{{width:100%;margin:0}}main{{padding:12px 12px 30px}}nav.tabs{{padding:0 4px}}.step,.tcard{{padding:14px}}.step .big{{font-size:20px}}
.hd .reg,.asof,.step .sp{{display:none}}.stiles{{grid-template-columns:1fr 1fr;gap:8px}}.stile{{min-height:98px}}.stile .v{{font-size:24px}}.sr,.step .sr{{grid-template-columns:18px 96px minmax(30px,1fr) 38px}}.sr .tag{{display:none}}.st{{grid-template-columns:86px minmax(0,1fr) 34px}}.st .chg{{display:none}}html{{scroll-padding-top:120px}}}}
.reg{{display:inline-block;padding:3px 10px;border-radius:99px;font-weight:600;margin-left:8px}}
.reg.good{{background:color-mix(in srgb,var(--up) 20%,transparent);color:var(--up)}}.reg.bad{{background:color-mix(in srgb,var(--dn) 20%,transparent);color:var(--dn)}}.reg.mid{{background:var(--bg);color:var(--mut)}}
.vix{{display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:14px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0 18px;color:var(--mut)}}
.vix .val{{font-size:28px}}.vxz{{font-size:12px;font-weight:700;padding:2px 9px;border-radius:99px;vertical-align:middle}}.vix .sub{{font-size:12px;margin:4px 0}}.vxt{{font-size:12px;color:var(--fg);margin-top:8px;line-height:1.45}}
.vxw{{position:relative}}.vxc{{width:100%;height:150px;display:block}}.vy{{position:absolute;left:4px;font-size:10px;transform:translateY(-110%)}}
.vxd{{position:absolute;right:-4px;width:8px;height:8px;border-radius:50%;transform:translateY(-50%)}}.vxm{{position:relative;height:14px;font-size:10px;margin-top:3px}}.vxm span{{position:absolute;transform:translateX(-50%)}}
.vxk{{display:flex;flex-wrap:wrap;gap:12px;font-size:11px;margin-top:8px}}.vxk i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:4px;vertical-align:-1px;opacity:.6}}
@media(max-width:700px){{.vix{{grid-template-columns:minmax(0,1fr)}}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin-bottom:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;color:var(--mut)}}.lbl{{font-size:12px}}.val{{font-size:24px;font-weight:700;color:var(--fg)}}.sub{{font-size:11px;margin-bottom:4px}}
.up{{color:var(--up)}}.wn{{color:#a87a00}}.dn{{color:var(--dn)}}
.bar button{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;margin-right:6px;font-size:13px;cursor:pointer}}.bar button.on{{border-color:var(--acc);color:var(--acc);background:color-mix(in srgb,var(--acc) 7%,var(--card))}}
.wrap{{overflow-x:auto;margin-top:10px;background:var(--card);border:1px solid var(--line);border-radius:12px}} table{{border-collapse:collapse;white-space:nowrap;font-size:13px}}
th,td{{padding:6px 9px;border-bottom:1px solid var(--line);text-align:right}}th{{position:sticky;top:0;background:var(--card);cursor:pointer;color:var(--mut);font-weight:600}}
td:first-child,th:first-child,td:nth-child(2),th:nth-child(2),td:nth-child(19),td:nth-child(20){{text-align:left}}
.obt,.ost{{font-size:10px;font-weight:700;padding:1px 4px;border-radius:4px;color:var(--fg)}}.obt{{background:color-mix(in srgb,var(--dn) 25%,transparent)}}
.ost{{background:color-mix(in srgb,var(--dn) 25%,transparent)}}.tsup,.treg{{font-size:11px;font-weight:700;padding:1px 5px;border-radius:4px;margin-right:3px}}.tsup{{background:color-mix(in srgb,var(--up) 25%,transparent)}}.treg{{background:color-mix(in srgb,var(--mut) 20%,transparent)}}.obl{{font-weight:600;background:color-mix(in srgb,var(--warn) 30%,transparent);padding:1px 6px;border-radius:4px}}
#t td:nth-child(2) .sec{{white-space:normal;min-width:150px;max-width:220px}}
td:first-child,th:first-child{{position:sticky;left:0;background:var(--card);z-index:1}}th:first-child{{z-index:2}}
.sec{{font-size:10px;color:var(--mut)}} tr.stack td:first-child{{box-shadow:inset 3px 0 var(--up)}}
.demo{{background:var(--dn);color:#fff;padding:6px 10px;border-radius:6px;margin-bottom:10px;font-weight:700}}
h2{{font-size:16px;margin:18px 0 2px}}.hint,.mut{{color:var(--mut);font-size:12px}}
.bar2{{height:4px;background:var(--line);border-radius:2px;margin-top:3px;min-width:90px}}.bar2 i{{display:block;height:100%;border-radius:2px}}
#s tbody tr{{cursor:pointer}}#s tbody tr.sel td{{background:color-mix(in srgb,var(--acc) 9%,var(--card))}}#s td:nth-child(2){{text-align:left}}
.chip{{font-size:12px;font-weight:600;background:var(--card);color:var(--acc);padding:2px 8px;border-radius:99px;cursor:pointer;margin-left:6px}}
.note{{color:var(--mut);font-size:12px;margin-top:14px;line-height:1.5}}
.pkt td:nth-child(2),.pkt th:nth-child(2){{text-align:right}}.pkt td.why,.pkt th.why{{text-align:left;white-space:normal;min-width:240px;color:var(--mut);font-size:12px}}
.ovg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:10px;margin:8px 0}}
.ovb{{background:var(--card);border-radius:10px;padding:10px 12px;font-size:12px;line-height:1.5}}.ovb ul{{margin:2px 0 6px;padding:0;list-style:none}}
.ovh{{display:flex;justify-content:space-between;gap:8px;font-weight:600;font-size:13px;margin-bottom:2px}}a.ovl{{text-decoration:none}}
.ovm{{margin-top:10px}}.ovm summary{{cursor:pointer;list-style:none;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-size:14px}}
.ovm summary::-webkit-details-marker{{display:none}}.ovm summary::before{{content:'▸';display:inline-block;width:16px;color:var(--mut)}}.ovm[open] summary::before{{content:'▾'}}
.ovm summary .ovc{{font-weight:700;margin-left:6px}}.ovm summary span:not(.ovc){{font-size:12px;font-weight:600;margin-left:10px}}
.new{{display:inline-block;font-size:11px;font-weight:700;color:var(--up);background:color-mix(in srgb,var(--up) 18%,transparent);padding:1px 7px;border-radius:99px}}
.ovd{{font-size:12px;margin-top:10px;line-height:1.5}}.ovd ul{{margin:2px 0;padding-left:18px}}.ovm .hint,.ovm+.hint{{margin-top:8px}}
.pkt .dte{{font-size:10px;color:var(--mut)}}.miss{{color:var(--mut)}}.bar.pk{{margin-top:8px}}.bar.pk .n{{color:var(--mut);font-weight:400}}.pkl .note{{margin-top:6px}}.note a{{color:var(--acc)}}.pke{{padding:10px 0}}.warn{{color:var(--dn);font-weight:600}}
#ss td:nth-child(2),#ss th:nth-child(2),#ssec td:nth-child(2),#ssec th:nth-child(2){{text-align:left}}
.obn{{color:var(--fg);font-weight:400;background:color-mix(in srgb,var(--warn) 18%,transparent);border-radius:8px;padding:6px 10px;margin:8px 0}}
.charts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:10px;margin-top:10px}}
.ch{{background:var(--card);border-radius:10px;padding:8px 10px}}.chh{{font-size:13px;margin-bottom:4px}}.chg{{float:right;font-weight:600}}.cv{{height:240px}}.bar.tf{{margin-top:8px}}
.bv{{height:64px}}.bl{{font-size:11px;color:var(--mut);margin-top:2px;min-height:15px}}.bl b{{color:var(--fg)}}.bv[hidden],.bl[hidden]{{display:none}}
.hm{{position:relative;background:var(--card);border-radius:10px;padding:10px 12px;margin:8px 0 6px;font-size:12px}}
.hmr{{display:grid;grid-template-columns:84px 1fr 62px;align-items:center;gap:6px;margin-bottom:2px}}
.hml{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px}}.hmv{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.hmc{{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;height:18px;border-radius:3px;overflow:hidden;cursor:crosshair;touch-action:pan-y}}
.hmc i{{display:block;background:var(--line)}}.hmc i.cur{{box-shadow:inset 0 0 0 2px var(--fg)}}
.hmz{{display:inline-flex;align-items:center;gap:4px}}.hmz i{{width:14px;height:8px;background:var(--line)}}.hmz i.o{{background:#f4a6a0}}.hmz i.u{{background:#f4a6a0}}.hmz i.g{{background:#a8e0bf}}.hmz i.d{{background:#f7dc7a}}
.hmt{{position:relative;height:13px;color:var(--mut);font-size:10px}}.hmt b{{position:absolute;top:0;font-weight:400}}
.hmk{{display:flex;flex-wrap:wrap;row-gap:4px;align-items:center;margin-top:6px;color:var(--mut);font-size:10px}}.hmk i{{display:block;width:14px;height:8px}}.hmk span{{margin:0 6px}}.hmk span:first-child{{margin-left:0}}
.hmtip{{position:absolute;z-index:5;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12px;line-height:1.45;box-shadow:0 2px 10px rgba(0,0,0,.18);pointer-events:none;white-space:nowrap}}.hmtip[hidden]{{display:none}}
.hm .hmc i[class^=h]{{background:#a8e0bf}}.hm .hmc i.o{{background:#f4a6a0}}.hm .hmc i.u{{background:#f4a6a0}}.hm .hmc i.d{{background:#f7dc7a}}
.hml{{cursor:pointer}}.hmr.sel .hml{{color:var(--acc);font-weight:700}}
.bln{{background:var(--card);border-radius:10px;padding:10px 12px;margin:8px 0 6px}}
.blh{{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}}.blh>b{{font-size:13px}}
.blh select{{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:13px}}
.bar.blr{{margin-left:auto}}.bar.blr button{{padding:4px 10px;margin:0 0 0 4px}}
.blk{{font-size:12px;color:var(--mut);margin:8px 0 4px;line-height:1.6;min-height:38px}}.blk b{{color:var(--fg);font-variant-numeric:tabular-nums}}
.blk .li{{display:inline-block;white-space:nowrap;margin-right:14px}}.blk .lk{{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:5px}}
.blc{{height:240px}}.blc[hidden]{{display:none}}
.tk{{cursor:pointer;color:var(--acc);text-decoration:underline dotted;text-underline-offset:3px}}
#cm{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:50;display:flex;align-items:center;justify-content:center}}#cm[hidden]{{display:none}}
#cm .box{{background:var(--bg);border-radius:12px;width:min(1200px,96vw);height:min(820px,92vh);display:flex;flex-direction:column;overflow:hidden}}
#cm .top{{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--line);flex-wrap:wrap}}#cm .top b{{font-size:16px}}
#cmi{{padding:6px 12px;border-bottom:1px solid var(--line);font-size:13px;line-height:1.5}}#cmi[hidden]{{display:none}}#cmi .lb{{display:inline-block;min-width:52px;color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
#cm .top .sp{{flex:1}}#cm .top a{{color:var(--acc);font-size:12px}}#cm .x{{background:none;border:0;color:var(--fg);font-size:22px;cursor:pointer;padding:0 4px}}
#cmbt{{padding:6px 12px;border-bottom:1px solid var(--line);font-size:12px;line-height:1.5;max-height:45%;overflow:auto}}#cmbt .btl b{{white-space:nowrap}}#cmbt details summary{{cursor:pointer;color:var(--acc)}}
#cmbt .btt{{overflow:auto;max-height:180px;margin-top:4px}}#cmbt table{{border-collapse:collapse;font-size:12px}}#cmbt th,#cmbt td{{padding:2px 8px 2px 0;text-align:left;white-space:nowrap}}
#cmlg{{padding:4px 12px 0}}#cmlg .up,#cmlg .dn{{font-weight:600}}#cmw{{flex:1;min-height:0}}.trl{{position:absolute;inset:0 0 26px 0;pointer-events:none;z-index:2}}.trl i{{position:absolute;top:0;bottom:0;opacity:.13}}#cmw>div{{height:100%}}
@media(max-width:600px){{#cm .box{{width:100vw;height:100dvh;border-radius:0}}}}
.mkt{{display:inline-flex;background:var(--bg);border-radius:999px;padding:3px;gap:2px}}.mkt a{{padding:4px 14px;border-radius:999px;color:var(--mut);text-decoration:none;font-weight:600;font-size:13px}}.mkt a.on{{background:var(--card);color:var(--fg);box-shadow:0 1px 3px rgba(0,0,0,.12)}}
{hk_css()}
#cmk{{padding:2px 12px 0}}#cmk .hk-b{{max-height:38vh;overflow:auto}}</style></head><body>
<header class="top"><div class="hd"><h1>Swing Screener</h1>
<nav class="mkt" aria-label="Market"><a class="on" href="./" aria-current="page">Stocks</a><a href="crypto/">Crypto</a><a href="ovtlyr/">OVTLYR</a></nav>
<span class="reg {rcls}">{reg}</span><span class="asof">{"Prices at " + live_at + " New York time, " + asof if live_at else "Closing data · " + asof}</span></div>
<nav class="tabs" aria-label="Sections">{tabs_nav}</nav></header>
<main>{banner}
<section class="tab" id="tab-today">{today}</section>
<section class="tab" id="tab-market" hidden><h2>Market</h2>{hk('market')}<div class="cards">{cards}</div>{vx_html}{bt_html}</section>
<section class="tab" id="tab-sectors" hidden><h2>Sectors</h2>{hk('tiles')}{sector_tiles(df, sws, bh)}{sector_html}{chart_html}</section>
<section class="tab" id="tab-stocks" hidden>{ss_html(df, sw, mkt_hot)}
<h2>Stocks <span id="secf" class="chip" hidden></span></h2>
{hk('stock_table')}{ob_html}<div class="bar"><button class="on" data-f="setups">Setups</button><button data-f="Super">Super</button><button data-f="Regular">Regular</button><button data-f="Momentum">Momentum</button><button data-f="Pullback">Pullback</button><button data-f="Overbought">Overbought</button><button data-f="all">All uptrend</button></div>
<div class="wrap"><table id="t"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<div class="note">Green bar = full stack (EMA10 &gt; 20 &gt; 50 &gt; {CFG["LONG_MA_TYPE"]}150 &gt; {CFG["LONG_MA_TYPE"]}200). Score = trend structure (70%) + setup quality (30 pts).
Uptrend = EMA10 &gt; EMA20, price &gt; EMA50 and price &gt; {CFG["LONG_MA_TYPE"]}150. Momentum requires EMA10 &gt; EMA20, price &gt; EMA50, RSI 55–80 and a 20-day breakout or within 3% of the 52w high; pullbacks require price &gt; EMA50, EMA20 &gt; EMA50, RSI ≤ 50, 3%+ off the 15-day high and back near/below the EMA20 (EMA10 may dip).
Your tiers: a <b>Super</b> setup also has the price over the {CFG["LONG_MA_TYPE"]}150; a <b>Regular</b> setup doesn't. Super setups are listed first; since Oct 28 the paper accounts buy both, Super first (a Regular one needs EMA10 &gt; EMA20 and price &gt; EMA50).
Your overbought rule: a stock whose sector's breadth is over the {CFG["OB_BREADTH"]} line, gets no setup and shows as Overbought; while the market's breadth is over {CFG["OB_BREADTH"]}, nothing does. OB / OS next to RSI and CCI = overbought (over {CFG["OB_RSI"]} / {CFG["OB_CCI"]}) / oversold (under {CFG["OS_RSI"]} / {CFG["OS_CCI"]}), information only: since Oct 15 RSI and CCI no longer block a setup. Options shown for top {CFG["OPT_TOP_N"]} picks:
call nearest {CFG["TARGET_DELTA"]} delta, ~{CFG["TARGET_DTE"]} DTE, OI ≥ {CFG["MIN_OI"]}, spread ≤ {CFG["MAX_SPREAD_PCT"]:.0f}%. Greeks are Black-Scholes from Yahoo's IV (Yahoo IV can be unreliable; confirm in your broker). When Yahoo has no live bid/ask (after hours, weekends) the last trade is shown and IV is solved from it. Click any ticker for a 4H / daily / weekly / monthly chart (the daily chart has 1Y and 5Y buttons): the Trend view shades uptrends green (EMA10 &gt; EMA20, price &gt; EMA50 and &gt; 150 MA) and downtrends red (all three reversed), with arrows where each trend starts; the Indicators view shows RSI, MACD and Bollinger Bands (the free chart allows about 3 studies at once; swap them from its Indicators menu).
Order blocks (Trend view, daily chart): blue boxes are bullish blocks, the last down candle before a rise of 2+ ATR within 3 bars; orange boxes are bearish blocks, the last up candle before a drop of 2+ ATR. A box ends where price first came back to it; bright boxes haven't been revisited yet. This was the best of 18 versions in a 10-year test on 1,000 stocks, but as support it did no better than random price zones, while bearish blocks held as resistance slightly better than random.
10y rules vs hold: each stock's last 10 years (less for newer stocks) traded on your rules, minus just holding it, in percentage points (rules +60% and holding +20% shows +40 pts). Buy at the next open after a close with a Super or Regular setup (Momentum or Pullback) on the strongest sector, strongest stock list, as Your system buys: EMA10 over EMA20 and the price over EMA50, its sector in an upswing and not over the {CFG["OB_BREADTH"]} line, the market not over it; sell at the next open after a close with EMA10 under EMA20 and the price under EMA50, or on an {BT["STOP"]:.0%} drop. That is your 4-hour exit on daily bars, since Yahoo only keeps about 2 years of 4-hour data. Click a ticker for the full numbers, SPY over the same years and every trade. Cash earns nothing while out, no trading costs; past results don't promise future ones. Not financial advice.</div></section>
<section class="tab" id="tab-picks" hidden>{picks_html(lists, earn, calls)}</section>
<section class="tab" id="tab-ovtlyr" hidden>{ov_html(ov)}</section>
<section class="tab" id="tab-paper" hidden>{paper_html}</section>
<section class="tab" id="tab-backtests" hidden>{bt_sec}</section>
<section class="tab" id="tab-news" hidden>{news}</section></main>
<div id="cm" hidden><div class="box"><div class="top"><b id="cmt"></b>
<div class="bar iv src"><button class="on" data-src="trend">Trend</button><button data-src="tv">Indicators</button></div>
<div class="bar iv tfb"><button data-iv="240">4H</button><button class="on" data-iv="D">Daily</button><button data-iv="W">Weekly</button><button data-iv="M">Monthly</button></div>
<div class="bar iv rng"><button class="on" data-rng="1Y">1Y</button><button data-rng="5Y">5Y</button></div>
<div class="bar iv obb"><button class="on" id="obt" title="Show or hide order blocks">Order blocks</button></div>
<span class="sp"></span><a id="cml" target="_blank" rel="noopener">Open on TradingView ↗</a><button class="x" aria-label="Close">×</button></div>
<div id="cmi" hidden></div><div id="cmbt" class="hint" hidden></div><div id="cmlg" class="hint"></div><div id="cmk">{hk('chart')}</div><div id="cmw"><div id="cmc"></div></div></div></div>
<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
// ---- tabs: one section at a time; the address keeps the tab (#stocks) so a reload or a shared link opens it
const TABS=[...document.querySelectorAll('section.tab')];let newsOn=false;
function showTab(id){{if(!document.getElementById('tab-'+id))id='today';TABS.forEach(t=>t.hidden=t.id!=='tab-'+id);
document.querySelectorAll('nav.tabs a').forEach(a=>a.classList.toggle('on',a.dataset.tab===id));
if(location.hash!=='#'+id)history.replaceState(null,'','#'+id);
// charts drawn while their tab was hidden had no width: refit them once the tab shows
const T=document.getElementById('tab-'+id);requestAnimationFrame(()=>requestAnimationFrame(()=>T.querySelectorAll('.bar.tf button.on,.bar.blr button.on').forEach(b=>b.click())));if(id==='news'&&!newsOn){{newsOn=true;newsInit()}}}}
window.showTabFor=e=>{{const t=e&&e.closest('section.tab');if(t&&t.hidden)showTab(t.id.slice(4))}};
const goTo=e=>{{if(!e)return;showTabFor(e);e.scrollIntoView({{behavior:'smooth',block:'start'}})}};
document.querySelectorAll('nav.tabs a').forEach(a=>a.onclick=e=>{{e.preventDefault();showTab(a.dataset.tab);window.scrollTo(0,0)}});
document.querySelectorAll('[data-go]').forEach(a=>a.onclick=()=>{{showTab(a.dataset.go);window.scrollTo(0,0)}});
window.addEventListener('hashchange',()=>showTab(location.hash.slice(1)));
// ---- News: TradingView's free news widget for the market, a sector ETF or a stock
function newsInit(){{const box=document.getElementById('nwc'),hd=document.getElementById('nwh'),ld=document.getElementById('nwl');if(!box)return;
function feed(sym,label){{box.innerHTML='<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div></div>';
const cfg={{isTransparent:true,displayMode:'regular',width:'100%',height:innerWidth<600?560:680,colorTheme:'light',locale:'en'}};
Object.assign(cfg,sym?{{feedMode:'symbol',symbol:sym}}:{{feedMode:'market',market:NEWS.market}});
const sc=document.createElement('script');sc.src='https://s3.tradingview.com/external-embedding/embed-widget-timeline.js';sc.async=true;sc.textContent=JSON.stringify(cfg);
sc.onerror=()=>{{box.innerHTML='<div class="hint" style="padding:16px">News could not load here. Use the TradingView link above.</div>'}};box.firstChild.appendChild(sc);
const u=sym?'https://www.tradingview.com/symbols/'+sym.replace(':','-')+'/news/':'https://www.tradingview.com/news/';
hd.innerHTML='News for <b>'+label+'</b> · <a href="'+u+'" target="_blank" rel="noopener">open on TradingView ↗</a>'}}
function lead(n){{const ts=n?(NEWS.lead[n]||[]):[];ld.hidden=!ts.length;ld.innerHTML=ts.length?NEWS.lbl+': '+ts.map(t=>'<button data-t="'+t+'">'+t+'</button>').join(''):'';
ld.querySelectorAll('button').forEach(b=>b.onclick=()=>{{ld.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));feed(b.dataset.t.replace(/-/g,'.')+NEWS.suf,b.dataset.t)}})}}
document.querySelectorAll('.bar.nw button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar.nw button').forEach(x=>x.classList.toggle('on',x===b));
const n=b.dataset.n,sym=b.dataset.sym;lead(n);
if(n&&!sym){{const f=ld.querySelector('button');if(f)f.click();else{{feed('','the market');hd.insertAdjacentHTML('afterbegin','No coin in '+b.firstChild.textContent.trim()+' passes tonight. ')}}return}}
feed(sym,n?b.firstChild.textContent.trim()+' ('+sym.split(':').pop()+')':'the market')}});
feed('','the market')}}
// ---- Today: tap a sector to see its stocks; the paper accounts in brief once they load
document.querySelectorAll('#tab-today .sr,.stile').forEach(r=>{{const go=()=>{{const s=document.querySelector('#s tbody tr[data-sector="'+r.dataset.sector+'"]');if(s){{if(!s.classList.contains('sel'))s.click();else goTo(document.getElementById('t'))}}}};
r.onclick=go;r.onkeydown=e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();go()}}}}}});
(function(){{const pp=document.getElementById('pp'),td=document.getElementById('tdpp');if(!pp||!td)return;
const sync=()=>{{const ts=[...pp.querySelectorAll('.pp-tile')];if(!ts.length){{const h=pp.querySelector('.hint');if(h)td.innerHTML='<div class="hint">'+h.textContent+'</div>';return}}
td.replaceChildren(...ts.map(t=>{{const r=document.createElement('div');r.className='tdp';r.setAttribute('role','button');r.tabIndex=0;
const d=t.querySelector('.pp-d span');r.innerHTML='<b></b><b></b><span class="sub"></span><span class="sub"></span>';
r.children[0].textContent=t.querySelector('.pp-h b').textContent;r.children[1].textContent=t.querySelector('.pp-val').textContent;
r.children[2].textContent=(t.querySelector('.pp-f span')||{{}}).textContent||'';if(d){{r.children[3].textContent=d.textContent;r.children[3].className='sub '+d.className;r.children[1].className=d.className}}
r.onclick=()=>t.click();return r}}))}};new MutationObserver(sync).observe(pp,{{childList:true}});sync()}})();
showTab(location.hash.slice(1)||'today');
</script>
<script>
const CH={chart_json},HM={json.dumps(hm_data, separators=(",", ":"))},BL={json.dumps(bl_data, separators=(",", ":"))};
const PINFO={pinfo};      // the pop-up's info line: m = the market, s = each sector, t = each ticker's sector
const OBL={CFG["OB_BREADTH"]},OSL={CFG["OS_BREADTH"]};      // your breadth lines: over 75 overbought (no upswing), under 30 oversold
const MD=t=>new Date(t+'T12:00:00').toLocaleDateString('en-US',{{month:'short',day:'numeric'}});
(function(){{const boxes=[...document.querySelectorAll('.ch')];if(!boxes.length)return;
if(!window.LightweightCharts){{document.getElementById('chfail').hidden=false;return}}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim();
const UP=V('--up'),DN=V('--dn'),WARN=V('--warn'),YEL=V('--yel'),PW=60;let tf='D';
// shading behind the strip (the user's breadth colours): green = 30-75 and rising, yellow = 30-75 and falling, red = over 75 or under 30
function bandPrim(){{let ch,runs=[],rs=[];
const rend={{draw:tg=>tg.useBitmapCoordinateSpace(sc=>{{const x=sc.context,hr=sc.horizontalPixelRatio,H=sc.bitmapSize.height;
rs.forEach(r=>{{x.fillStyle=r.col;x.fillRect(Math.round(r.x1*hr),0,Math.max(1,Math.round(r.x2*hr)-Math.round(r.x1*hr)),H)}})}})}};
const view={{zOrder:()=>'bottom',renderer:()=>rend}};
return {{attached:p=>{{ch=p.chart}},paneViews:()=>[view],set:v=>{{runs=v}},updateAllViews:()=>{{if(!ch)return;const ts=ch.timeScale(),sp=ts.options().barSpacing/2;rs=[];
runs.forEach(([a,b,z])=>{{const x1=ts.timeToCoordinate(a),x2=ts.timeToCoordinate(b);if(x1==null||x2==null)return;rs.push({{x1:x1-sp,x2:x2+sp,col:z===2?DN+'3d':z===1?UP+'3d':YEL+'4d'}})}})}}}}}}
// breadth line under a chart: the bar's (or tonight's) Rising, its 10-day average, Uptrend and the upswing state
function leg(m,i){{if(!m.bl)return;const s=m.d[tf];if(!s||!s.br){{m.bl.textContent='';return}}
const L=s.br.length,last=i==null||i<0||i>=L-1||s.br[i]==null;if(last)i=L-1;
const r=s.br[i],a=s.ba[i],u=s.bu[i],w=m.d.sw;if(r==null||a==null){{m.bl.textContent='';return}}
const on=last&&w?w.on:s.bs[i]===1,z=last&&w?w.z:r>OBL?2:r<OSL?-1:0;
m.bl.innerHTML=(last?'':MD(s.t[i])+' · ')+'Breadth <b>'+r.toFixed(0)+'%</b> rising, avg '+a.toFixed(0)+'%'+(u==null?'':' · '+u.toFixed(0)+'% in uptrend')
+' · '+(z===2?'<span class="obt">OB</span> overbought'+(last&&w?' since '+MD(w.zsince):''):
'<span class="'+(z===-1?'dn':on?'up':'wn')+'">'+(on?'▲ upswing':'▼ fading')+(last&&w?' since '+MD(w.since):'')+'</span>'+(z===-1?' · <span class="ost">OS</span> oversold':''))}}
const made=boxes.map(b=>{{const d=CH[b.dataset.sector];
const c=LightweightCharts.createChart(b.querySelector('.cv'),{{autoSize:true,localization:{{locale:'en-US'}},layout:{{background:{{color:'transparent'}},textColor:V('--mut'),fontSize:11}},
grid:{{vertLines:{{visible:false}},horzLines:{{color:V('--line')}}}},rightPriceScale:{{borderVisible:false,minimumWidth:PW}},timeScale:{{borderVisible:false}},handleScroll:false,handleScale:false}});
const k=c.addCandlestickSeries({{upColor:UP,downColor:DN,wickUpColor:UP,wickDownColor:DN,borderVisible:false}});
const vol=c.addHistogramSeries({{priceScaleId:'v',priceFormat:{{type:'volume'}},lastValueVisible:false,priceLineVisible:false}});
c.priceScale('v').applyOptions({{scaleMargins:{{top:0.82,bottom:0}}}});
const ln=[['e10','#e8a33d'],['e20',V('--acc')],['e50','#a259d9']].map(([key,col])=>[key,c.addLineSeries({{color:col,lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false}})]);
// the breadth strip, on the same bars: green / red shading = upswing / fading, solid = Rising, dotted = Uptrend, dashed = 50%
const bv=b.querySelector('.bv'),bl=b.querySelector('.bl');let st=null;
if(bv){{const bc=LightweightCharts.createChart(bv,{{autoSize:true,localization:{{locale:'en-US',priceFormatter:v=>Math.round(v)+'%'}},
layout:{{background:{{color:'transparent'}},textColor:V('--mut'),fontSize:10,attributionLogo:false}},grid:{{vertLines:{{visible:false}},horzLines:{{visible:false}}}},
rightPriceScale:{{borderVisible:false,minimumWidth:PW,scaleMargins:{{top:0.08,bottom:0.08}}}},timeScale:{{visible:false,borderVisible:false}},
crosshair:{{horzLine:{{visible:false,labelVisible:false}},vertLine:{{labelVisible:false}}}},handleScroll:false,handleScale:false}});
const fix=()=>({{priceRange:{{minValue:0,maxValue:100}}}});
const bu=bc.addLineSeries({{color:V('--mut'),lineWidth:1,lineStyle:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,autoscaleInfoProvider:fix}});
const br=bc.addLineSeries({{color:V('--fg'),lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,autoscaleInfoProvider:fix}});
br.createPriceLine({{price:50,color:V('--mut'),lineWidth:1,lineStyle:2,axisLabelVisible:true}});
br.createPriceLine({{price:OBL,color:DN,lineWidth:1,lineStyle:1,axisLabelVisible:false}});
br.createPriceLine({{price:OSL,color:DN,lineWidth:1,lineStyle:1,axisLabelVisible:false}});
const band=bandPrim();br.attachPrimitive(band);st={{bc,band,bu,br}}}}
const m={{b,d,c,k,vol,ln,st,bv,bl}};
const at=p=>p.point&&p.logical!=null?Math.round(p.logical):null;
c.subscribeCrosshairMove(p=>{{const i=at(p);leg(m,i);if(!st)return;const s=m.d[tf];
if(i==null||!s||!s.br||s.br[i]==null)st.bc.clearCrosshairPosition();else st.bc.setCrosshairPosition(s.br[i],s.t[i],st.br)}});
if(st)st.bc.subscribeCrosshairMove(p=>leg(m,at(p)));
return m}});
function draw(){{made.forEach(m=>{{const s=m.d[tf];if(!s)return;
m.k.setData(s.t.map((t,i)=>({{time:t,open:s.o[i],high:s.h[i],low:s.l[i],close:s.c[i]}})));
m.vol.setData(s.t.map((t,i)=>({{time:t,value:s.v[i],color:(s.c[i]>=s.o[i]?UP:DN)+'55'}})));
m.ln.forEach(([key,ser])=>ser.setData(s.t.map((t,i)=>({{time:t,value:s[key][i]}}))));
m.c.timeScale().fitContent();
if(m.st){{const has=!!s.br;m.bv.hidden=m.bl.hidden=!has;
if(has){{const f=a=>s.t.map((t,i)=>a[i]==null?{{time:t}}:{{time:t,value:a[i]}});
const runs=[];s.t.forEach((t,i)=>{{if(s.bs[i]==null)return;const z=s.br[i]>OBL||s.br[i]<OSL?2:s.bs[i]===1?1:0,r=runs[runs.length-1];
if(r&&r[2]===z&&r[3]===i-1){{r[1]=t;r[3]=i}}else runs.push([t,t,z,i])}});m.st.band.set(runs);
m.st.bu.setData(f(s.bu));m.st.br.setData(f(s.br));m.st.bc.timeScale().fitContent();
requestAnimationFrame(()=>requestAnimationFrame(()=>m.st.bc.timeScale().fitContent()))}}}}
leg(m,null);
const n=s.c.length,p=(s.c[n-1]/s.c[n-2]-1)*100,e=m.b.querySelector('.chg');
e.textContent=s.c[n-1].toFixed(2)+'  '+(p>=0?'+':'')+p.toFixed(1)+'% '+({{D:'1d',W:'1w',M:'1m'}})[tf];e.className='chg '+(p>=0?'up':'dn')}})}}
document.querySelectorAll('.bar.tf button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar.tf button').forEach(x=>x.classList.remove('on'));b.classList.add('on');tf=b.dataset.tf;draw()}});
draw()}})();
// breadth heatmap: tap or hover a row for that day's numbers
(function(){{const hm=document.getElementById('hm');if(!hm||!HM)return;const tip=document.getElementById('hmtip'),n=HM.t.length;
const off=()=>{{tip.hidden=true;hm.querySelectorAll('i.cur').forEach(x=>x.classList.remove('cur'))}};
function show(e){{const c=e.currentTarget,R=HM.rows[+c.dataset.i],r=c.getBoundingClientRect();
const i=Math.max(0,Math.min(n-1,Math.floor((e.clientX-r.left)/r.width*n))),v=R.r[i];off();if(v==null)return;
const a=R.a[i],u=R.u[i],d=new Date(HM.t[i]+'T12:00:00').toLocaleDateString('en-US',{{weekday:'short',month:'short',day:'numeric'}});
tip.innerHTML='<b>'+R.n+'</b> · '+d+'<br>'+v.toFixed(0)+'% rising (10 EMA over the 20, price over the 50), avg '+a.toFixed(0)+'%'
+(u==null?'':'<br>'+u.toFixed(0)+'% in your uptrend')+'<br>'+(v>OBL?'<span class="obt">OB</span> overbought (over '+OBL+')':
'<span class="'+(v<OSL?'dn':R.s[i]?'up':'wn')+'">'+(R.s[i]?'▲ upswing':'▼ fading')+'</span>'+(v<OSL?' · <span class="ost">OS</span> oversold (under '+OSL+')':''));
c.children[i].classList.add('cur');tip.hidden=false;const h=hm.getBoundingClientRect();
tip.style.left=Math.max(0,Math.min(e.clientX-h.left+12,h.width-tip.offsetWidth))+'px';tip.style.top=(r.bottom-h.top+6)+'px'}}
hm.querySelectorAll('.hmc').forEach(c=>{{c.addEventListener('pointermove',show);c.addEventListener('pointerdown',show);
c.addEventListener('pointerleave',e=>{{if(e.pointerType==='mouse')off()}})}});
document.addEventListener('pointerdown',e=>{{if(!e.target.closest('.hmc'))off()}})}})();
// breadth line: Rising for the S&P 500 or one sector by day, with its 5-day and 10-day averages
(function(){{const el=document.getElementById('bln');if(!el||!BL)return;
const box=el.querySelector('.blc'),lg=document.getElementById('blk'),sel=document.getElementById('blg'),N=BL.t.length;
if(!window.LightweightCharts){{box.hidden=true;lg.textContent='The chart could not load (chart library blocked).';return}}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim();let g=0,span=63;
const c=LightweightCharts.createChart(box,{{autoSize:true,localization:{{locale:'en-US',priceFormatter:v=>+v.toFixed(1)+'%'}},
layout:{{background:{{color:'transparent'}},textColor:V('--mut'),fontSize:11,attributionLogo:false}},grid:{{vertLines:{{visible:false}},horzLines:{{color:V('--line')}}}},
rightPriceScale:{{borderVisible:false,scaleMargins:{{top:0.1,bottom:0.1}}}},timeScale:{{borderVisible:false,lockVisibleTimeRangeOnResize:true}},
crosshair:{{horzLine:{{visible:false,labelVisible:false}}}},handleScroll:false,handleScale:false}});
const line=col=>c.addLineSeries({{color:col,lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerRadius:4}});
const s10=line(V('--b10')),s5=line(V('--b5')),sr=line(V('--fg'));          // Rising drawn last, on top
sr.createPriceLine({{price:50,color:V('--mut'),lineWidth:1,lineStyle:2,axisLabelVisible:false}});
sr.createPriceLine({{price:OBL,color:V('--dn'),lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'overbought'}});
sr.createPriceLine({{price:OSL,color:V('--dn'),lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'oversold'}});
// keep both lines in view, with a little room past them
sr.applyOptions({{autoscaleInfoProvider:o=>{{const r=o();if(!r||!r.priceRange)return r;
r.priceRange.minValue=Math.min(r.priceRange.minValue,OSL-5);r.priceRange.maxValue=Math.max(r.priceRange.maxValue,OBL+5);return r}}}});
const f1=v=>v==null?'–':v.toFixed(1)+'%',item=(v,lbl,x)=>'<span class="li"><i class="lk" style="background:var('+v+')"></i>'+lbl+' <b>'+f1(x)+'</b></span>';
const DAY=t=>new Date(t+'T12:00:00').toLocaleDateString('en-US',{{weekday:'short',month:'short',day:'numeric'}});
const hrows=HM?[...document.querySelectorAll('#hm .hmc')].map(x=>[x.closest('.hmr'),HM.rows[+x.dataset.i].n]):[];
// the numbers and above / below states for one day (or tonight, with the day each state began)
function leg(i){{const G=BL.g[g],last=i==null||i<0||i>=N-1;if(last)i=N-1;if(G.r[i]==null){{lg.textContent='';return}}
const zn=d=>G.r[d]==null?0:G.r[d]>OBL?2:G.r[d]<OSL?-1:0,z=zn(i);
const st=(u,lbl)=>{{const on=u[i]==='1';let k=i;while(last&&k>0&&u[k-1]===u[i])k--;
return '<span class="li '+(z===2?'':on?'up':'dn')+'">'+(on?'▲ above':'▼ below')+' its '+lbl+(last?' since '+MD(BL.t[k]):'')+'</span>'}};
let kz=i;while(last&&kz>0&&zn(kz-1)===z)kz--;
const zl=z===2?'<span class="li"><span class="obt">OB</span> overbought, over '+OBL+(last?' since '+MD(BL.t[kz]):'')+'</span>':
z===-1?'<span class="li"><span class="ost">OS</span> oversold, under '+OSL+(last?' since '+MD(BL.t[kz]):'')+'</span>':'';
lg.innerHTML='<div>'+(last?'':'<span class="li"><b>'+DAY(BL.t[i])+'</b></span>')+item('--fg','Rising',G.r[i])+item('--b5','5-day avg',G.a5[i])
+item('--b10','10-day avg',G.a10[i])+'</div><div>'+zl+st(G.u5,'5-day average')+st(G.u10,'10-day average')+'</div>'}}
function fit(){{const ts=c.timeScale();if(!span||span>=N)ts.fitContent();else ts.setVisibleLogicalRange({{from:N-span-0.5,to:N-0.5}})}}
function show(){{const G=BL.g[g],f=a=>BL.t.map((t,i)=>a[i]==null?{{time:t}}:{{time:t,value:a[i]}});
sr.setData(f(G.r));s5.setData(f(G.a5));s10.setData(f(G.a10));fit();requestAnimationFrame(()=>requestAnimationFrame(fit));leg(null);
hrows.forEach(([row,n])=>row.classList.toggle('sel',n===G.n))}}
const save=()=>{{try{{localStorage.setItem('bl',JSON.stringify({{n:BL.g[g].n,span}}))}}catch(e){{}}}};
const btns=[...el.querySelectorAll('.blr button')],setSpan=k=>{{span=k;btns.forEach(b=>b.classList.toggle('on',+b.dataset.r===k))}};
function pick(n){{const j=BL.g.findIndex(x=>x.n===n);if(j<0)return;g=j;sel.value=String(j);save();show()}}
sel.onchange=()=>{{g=+sel.value;save();show()}};
btns.forEach(b=>b.onclick=()=>{{setSpan(+b.dataset.r);save();fit()}});
hrows.forEach(([row,n])=>row.addEventListener('click',()=>pick(n)));
c.subscribeCrosshairMove(p=>leg(p.point&&p.logical!=null?Math.round(p.logical):null));
// on a phone, tap the chart for that day's numbers; a tap anywhere else goes back to tonight's
box.addEventListener('pointerdown',e=>{{if(e.pointerType==='mouse')return;const l=c.timeScale().coordinateToLogical(e.clientX-box.getBoundingClientRect().left);
if(l==null)return;const i=Math.max(0,Math.min(N-1,Math.round(l))),v=BL.g[g].r[i];if(v==null)return;c.setCrosshairPosition(v,BL.t[i],sr);leg(i)}});
document.addEventListener('pointerdown',e=>{{if(e.pointerType!=='mouse'&&!box.contains(e.target)){{c.clearCrosshairPosition();leg(null)}}}});
try{{const s=JSON.parse(localStorage.getItem('bl')||'null'),j=s?BL.g.findIndex(x=>x.n===s.n):-1;
if(j>=0){{g=j;sel.value=String(j)}}if(s&&btns.some(b=>+b.dataset.r===s.span))setSpan(s.span)}}catch(e){{}}
show()}})();
const rows=[...document.querySelectorAll('#t tbody tr')];let fSet='setups',fSec=null;
const chip=document.getElementById('secf');
function apply(){{rows.forEach(r=>{{const st=r.dataset.setup;const isS=st==='Momentum'||st==='Pullback';const okS=fSet==='all'||(fSet==='setups'?isS:fSet==='Super'||fSet==='Regular'?isS&&r.dataset.tier===fSet:st===fSet);
r.style.display=okS&&(!fSec||r.dataset.sector===fSec)?'':'none'}});chip.hidden=!fSec;chip.textContent=(fSec||'')+'  ✕';
document.querySelectorAll('#s tbody tr').forEach(r=>r.classList.toggle('sel',r.dataset.sector===fSec))}}
document.querySelectorAll('.bar:not(.tf):not(.iv):not(.pk):not(.blr) button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar:not(.tf):not(.iv):not(.pk):not(.blr) button').forEach(x=>x.classList.remove('on'));b.classList.add('on');fSet=b.dataset.f;apply()}});
document.querySelectorAll('#s tbody tr').forEach(r=>r.onclick=()=>{{fSec=fSec===r.dataset.sector?null:r.dataset.sector;apply();goTo(document.getElementById('t'))}});
chip.onclick=()=>{{fSec=null;apply()}};
function sortable(id){{const tb=document.querySelector('#'+id+' tbody');document.querySelectorAll('#'+id+' th').forEach((h,i)=>h.onclick=()=>{{const d=h.dataset.d=h.dataset.d==='1'?-1:1;
[...tb.rows].sort((a,b)=>{{const x=a.cells[i].dataset.v??a.cells[i].textContent,y=b.cells[i].dataset.v??b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);return (isNaN(nx)||isNaN(ny)?String(x).localeCompare(String(y)):nx-ny)*d}}).forEach(r=>tb.appendChild(r))}})}}
sortable('t');sortable('s');apply();
document.querySelectorAll('.bar.pk button').forEach(b=>b.onclick=()=>{{setOn('.bar.pk',b.dataset.pk,'pk');
document.querySelectorAll('.pkl').forEach(d=>d.hidden=d.dataset.pk!==b.dataset.pk);try{{localStorage.setItem('pk',b.dataset.pk)}}catch(e){{}}}});
try{{const k=localStorage.getItem('pk'),b=k&&document.querySelector('.bar.pk button[data-pk="'+k+'"]');if(b)b.click()}}catch(e){{}}
['ss','ssec','pk-nu','pk-bo','pk-ai','ov-m'].forEach(id=>{{if(document.getElementById(id))sortable(id)}});
(function(){{const d=document.getElementById('ovm');if(!d)return;
try{{if(localStorage.getItem('ovm')==='1')d.open=true}}catch(e){{}}
d.addEventListener('toggle',()=>{{try{{localStorage.setItem('ovm',d.open?'1':'0')}}catch(e){{}}}});
document.querySelectorAll('a[href="#ovm"]').forEach(a=>a.onclick=e=>{{e.preventDefault();d.open=true;goTo(d)}})}})();
// ---- ticker chart pop-up (TradingView widget: 4H/D/W/M, indicators preloaded, more via its Indicators menu)
const cm=document.getElementById('cm');let cmSym=null,cmIv='D',tvLoading=null;
const tvSym=t=>t.replace(/-/g,'.');
function tvLib(){{return tvLoading||(tvLoading=new Promise((ok,no)=>{{const s=document.createElement('script');s.src='https://s3.tradingview.com/tv.js';s.onload=ok;s.onerror=no;document.head.appendChild(s)}}))}}
function tvDraw(){{document.getElementById('cmw').innerHTML='<div id="cmc"></div>';
const dark=false;          // the page is light on every device
tvLib().then(()=>new TradingView.widget({{container_id:'cmc',autosize:true,symbol:tvSym(cmSym),interval:cmIv,timezone:'America/Chicago',
theme:dark?'dark':'light',style:'1',locale:'en',allow_symbol_change:true,hide_side_toolbar:false,withdateranges:true,details:true,
studies:['RSI@tv-basicstudies','MACD@tv-basicstudies','BB@tv-basicstudies']}}))
.catch(()=>{{document.getElementById('cmw').innerHTML='<div class="hint" style="padding:16px">Chart could not load. Use “Open on TradingView” above.</div>'}})}}
function openChart(t){{cmSym=t;document.getElementById('cmt').textContent=t;
document.getElementById('cml').href='https://www.tradingview.com/chart/?symbol='+encodeURIComponent(tvSym(t));
cm.hidden=false;document.body.style.overflow='hidden';cmInfo(t);draw();btDraw(t)}}
function cmInfo(t){{const el=document.getElementById('cmi');if(!PINFO){{el.hidden=true;return}}const sec=PINFO.t[t];
el.innerHTML=(sec?'<div>'+PINFO.s[sec]+'</div>':'')+'<div>'+PINFO.m+'</div>';el.hidden=false}}
function loadData(sym){{return dataCache[sym]||(dataCache[sym]=fetch('data/'+encodeURIComponent(sym)+'.json').then(r=>{{if(!r.ok)throw 0;return r.json()}}))}}
// ---- 10-year backtest strip: your rules on this stock vs holding it vs holding SPY, and every trade
function btDraw(sym){{const el=document.getElementById('cmbt');el.hidden=true;el.innerHTML='';
loadData(sym).then(D=>{{if(sym!==cmSym||!D.bt)return;const b=D.bt,p=v=>v==null?'n/a':(v>=0?'+':'')+Math.round(v).toLocaleString('en-US')+'%',
pts=(a,c)=>{{const e=a-c;return'<b class="'+(e>0?'up':'dn')+'">'+(e>=0?'+':'')+Math.round(e).toLocaleString('en-US')+' pts</b>'}},
y=b.years>=9.9?'10 years':b.years+' years',m=v=>'$'+Math.round(1000*(1+v/100)).toLocaleString('en-US');
const tr=b.trades.slice().reverse().map(t=>{{const r=(t[3]/t[2]-1)*100;return'<tr><td>'+t[0]+'</td><td>'+(t[4]==='open'?'still in':t[1])+'</td><td>'+t[2].toFixed(2)+'</td><td>'+t[3].toFixed(2)+
'</td><td class="'+(r>0?'up':'dn')+'">'+(r>=0?'+':'')+r.toFixed(1)+'%</td><td>'+(t[4]==='stop'?'8% stop':t[4]==='exit'?'trend exit':'open')+'</td></tr>'}}).join('');
el.innerHTML='<div class="btl"><b>Backtest, '+y+'</b> <span class="mut">('+b.start+' to '+b.end+')</span>: '+
'your rules <b>'+p(b.rules)+'</b> · holding '+sym+' <b>'+p(b.hold)+'</b> · holding SPY <b>'+p(b.spy)+'</b></div>'+
'<div class="btl">Rules vs holding '+sym+': '+pts(b.rules,b.hold)+(b.spy==null?'':' · rules vs SPY: '+pts(b.rules,b.spy))+
' · $1,000 became '+m(b.rules)+' on the rules, '+m(b.hold)+' holding'+'</div>'+
'<details><summary>'+b.n+' trades, '+(b.win==null?'none':b.win+'% winners')+', in the market '+b.inmkt+'% of days'+(b.holding?', in a trade now':'')+'</summary>'+
'<div class="mut">Buy at the next open after a setup (Momentum or Pullback) that isn’t overbought; sell at the next open after a daily close with EMA10 under EMA20 and the price under EMA50 (your 4-hour exit on daily bars: Yahoo only keeps about 2 years of 4-hour data), or on an 8% drop. Breadth isn’t checked this far back; cash earns nothing while out; no trading costs.</div>'+
(tr?'<div class="btt"><table><thead><tr><th>Bought</th><th>Sold</th><th>In</th><th>Out</th><th>Return</th><th>Why</th></tr></thead><tbody>'+tr+'</tbody></table></div>':'')+'</details>';el.hidden=false}}).catch(()=>{{}})}}
function closeChart(){{cm.hidden=true;document.body.style.overflow='';document.getElementById('cmw').innerHTML=''}}
document.querySelectorAll('.tk').forEach(e=>e.onclick=ev=>{{ev.stopPropagation();openChart(e.dataset.tk)}});
let cmSrc='trend',cmOB=true,cmRng='1Y';const dataCache={{}};
function draw(){{cmSrc==='trend'?trendDraw():tvDraw();const day=cmSrc==='trend'&&cmIv==='D';
document.getElementById('cmlg').hidden=cmSrc!=='trend';document.querySelector('.obb').hidden=document.querySelector('.rng').hidden=!day}}
// order block boxes: [start, end, top, bottom, side, fresh], drawn under the candles; fresh ones run to the right edge
function obPrim(zs){{let ch,se,rs=[];
const rend={{draw:tg=>tg.useBitmapCoordinateSpace(sc=>{{const x=sc.context,hr=sc.horizontalPixelRatio,vr=sc.verticalPixelRatio,lw=Math.max(1,Math.round(hr));
rs.forEach(r=>{{const X=Math.round(r.x1*hr),Y=Math.round(r.y1*vr),W=Math.max(lw,Math.round((r.x2-r.x1)*hr)),H=Math.max(lw,Math.round((r.y2-r.y1)*vr));
x.fillStyle=r.col+(r.fresh?'40':'1c');x.fillRect(X,Y,W,H);x.lineWidth=lw;x.strokeStyle=r.col+(r.fresh?'e6':'73');x.strokeRect(X+lw/2,Y+lw/2,Math.max(0,W-lw),Math.max(0,H-lw))}})}})}};
const view={{zOrder:()=>'bottom',renderer:()=>rend}};
return {{attached:p=>{{ch=p.chart;se=p.series}},paneViews:()=>[view],updateAllViews:()=>{{const ts=ch.timeScale(),sp=ts.options().barSpacing/2;rs=[];
zs.forEach(z=>{{const x1=ts.timeToCoordinate(z[0]),x2=z[5]?ts.width():ts.timeToCoordinate(z[1]),y1=se.priceToCoordinate(z[2]),y2=se.priceToCoordinate(z[3]);
if(x1==null||x2==null||y1==null||y2==null)return;rs.push({{x1:x1-sp,x2:z[5]?x2:x2+sp,y1:Math.min(y1,y2),y2:Math.max(y1,y2),col:z[4]>0?'#2962ff':'#f57c00',fresh:z[5]}})}})}}}}}}
function trendDraw(){{const w=document.getElementById('cmw');w.innerHTML='<div id="cmc"></div>';const lg=document.getElementById('cmlg');lg.textContent='Loading…';
const tf=cmIv==='240'?'4H':cmIv,sym=cmSym;
loadData(sym).then(D=>{{
if(sym!==cmSym||cmSrc!=='trend')return;const s=D[tf];if(!s){{lg.textContent='No '+tf+' data for '+sym+'.';return}}
if(!window.LightweightCharts){{lg.textContent='Chart library blocked.';return}}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim(),UP=V('--up'),DN=V('--dn');
const c=LightweightCharts.createChart(document.getElementById('cmc'),{{autoSize:true,localization:{{locale:'en-US'}},layout:{{background:{{color:'transparent'}},textColor:V('--mut')}},
grid:{{vertLines:{{visible:false}},horzLines:{{color:V('--line')}}}},rightPriceScale:{{borderVisible:false}},timeScale:{{borderVisible:false,timeVisible:tf==='4H',minBarSpacing:0.05}}}});
const runs=[];s.tr.forEach((v,i)=>{{if(!v)return;const r=runs[runs.length-1];if(r&&r.v===v&&r.b===i-1)r.b=i;else runs.push({{v,a:i,b:i}})}});
const box=document.getElementById('cmc');box.style.position='relative';const lay=document.createElement('div');lay.className='trl';box.appendChild(lay);
function shade(){{const ts=c.timeScale(),sp=ts.options().barSpacing,w=box.clientWidth-c.priceScale('right').width();
lay.innerHTML=runs.map(r=>{{let x1=ts.timeToCoordinate(s.t[r.a]),x2=ts.timeToCoordinate(s.t[r.b]);if(x1==null||x2==null)return'';
x1=Math.max(0,x1-sp/2);x2=Math.min(w,x2+sp/2);return x2>x1?`<i style="left:${{x1}}px;width:${{x2-x1}}px;background:${{r.v>0?UP:DN}}"></i>`:''}}).join('')}}
c.timeScale().subscribeVisibleLogicalRangeChange(()=>requestAnimationFrame(shade));new ResizeObserver(()=>requestAnimationFrame(shade)).observe(box);
const vol=c.addHistogramSeries({{priceScaleId:'v',priceFormat:{{type:'volume'}},lastValueVisible:false,priceLineVisible:false}});c.priceScale('v').applyOptions({{scaleMargins:{{top:0.85,bottom:0}}}});
vol.setData(s.t.map((t,i)=>({{time:t,value:s.v[i],color:(s.c[i]>=s.o[i]?UP:DN)+'55'}})));
const k=c.addCandlestickSeries({{upColor:UP,downColor:DN,wickUpColor:UP,wickDownColor:DN,borderVisible:false}});
k.setData(s.t.map((t,i)=>({{time:t,open:s.o[i],high:s.h[i],low:s.l[i],close:s.c[i]}})));
[['e10','#e8a33d',0],['e20',V('--acc'),0],['e50','#a259d9',0],['m150',V('--mut'),2]].forEach(([key,col,ls])=>{{
const l=c.addLineSeries({{color:col,lineWidth:key==='m150'?2:1,lineStyle:ls,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false}});
l.setData(s.t.map((t,i)=>s[key][i]==null?{{time:t}}:{{time:t,value:s[key][i]}}))}});
const mk=[];for(let i=1;i<s.t.length;i++)if(s.tr[i]!==s.tr[i-1]&&s.tr[i]!==0)mk.push(s.tr[i]>0?{{time:s.t[i],position:'belowBar',color:UP,shape:'arrowUp'}}:{{time:s.t[i],position:'aboveBar',color:DN,shape:'arrowDown'}});
const five=tf==='D'&&cmRng==='5Y';k.setMarkers(five?[]:mk);if(cmOB&&tf==='D'&&s.ob)k.attachPrimitive(obPrim(s.ob));
const n=s.t.length;if(tf==='D'&&cmRng==='1Y'&&n>252)c.timeScale().setVisibleLogicalRange({{from:n-252,to:n+1}});else c.timeScale().fitContent();
let i=s.tr.length-1;const st=s.tr[i];while(i>0&&s.tr[i-1]===st)i--;
const since=typeof s.t[i]==='number'?new Date(s.t[i]*1000).toISOString().slice(0,10):s.t[i];
const last=s.c[s.c.length-1],fresh=(s.ob||[]).filter(z=>z[5]),pct=v=>{{const p=(v/last-1)*100;return(p>=0?'+':'')+p.toFixed(1)+'%'}};
const sup=fresh.filter(z=>z[4]>0&&z[2]<=last).sort((a,b)=>b[2]-a[2])[0],res=fresh.filter(z=>z[4]<0&&z[3]>=last).sort((a,b)=>a[3]-b[3])[0];
const obTxt=!cmOB||tf!=='D'?'':' · <span title="Order block: the last opposite candle before a strong move, where traders got caught on the wrong side. Blue = bullish (support), orange = bearish (resistance). A box ends where price first came back; solid boxes are still untouched.">order blocks</span>: '+
(sup?'<span style="color:#2962ff">support '+sup[3].toFixed(2)+'–'+sup[2].toFixed(2)+' ('+pct(sup[2])+')</span>':'no untouched support')+', '+
(res?'<span style="color:#f57c00">resistance '+res[3].toFixed(2)+'–'+res[2].toFixed(2)+' ('+pct(res[3])+')</span>':'no untouched resistance');
lg.innerHTML=(st>0?'<span class="up">Uptrend</span>':st<0?'<span class="dn">Downtrend</span>':'<b>No trend</b>')+' since '+since+
' · <span title="Uptrend: EMA10 &gt; EMA20, price &gt; EMA50 and price &gt; 150 MA. Downtrend: the reverse.">green = uptrend, red = downtrend</span> · EMA 10 orange, 20 blue, 50 purple, 150 dashed'+obTxt}})
.catch(()=>{{if(sym!==cmSym)return;lg.textContent='Trend data not available for '+sym+' here, showing the indicator chart.';cmSrc='tv';setOn('.bar.src','tv','src');tvDraw()}})}}
function setOn(sel,val,key){{document.querySelectorAll(sel+' button').forEach(x=>x.classList.toggle('on',x.dataset[key]===val))}}
document.querySelectorAll('.bar.tfb button').forEach(b=>b.onclick=()=>{{cmIv=b.dataset.iv;setOn('.bar.tfb',cmIv,'iv');draw()}});
document.querySelectorAll('.bar.src button').forEach(b=>b.onclick=()=>{{cmSrc=b.dataset.src;setOn('.bar.src',cmSrc,'src');draw()}});
document.getElementById('obt').onclick=e=>{{cmOB=!cmOB;e.currentTarget.classList.toggle('on',cmOB);draw()}};
document.querySelectorAll('.bar.rng button').forEach(b=>b.onclick=()=>{{cmRng=b.dataset.rng;setOn('.bar.rng',cmRng,'rng');draw()}});
cm.querySelector('.x').onclick=closeChart;cm.onclick=e=>{{if(e.target===cm)closeChart()}};
document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&!cm.hidden)closeChart()}});
</script>
<script>{paper_js}</script><script>{bt_js}</script></body></html>"""

# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-options", action="store_true")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()

    print("Loading universe + prices...")
    if a.demo:
        frames = demo_frames()
        secs = ["Information Technology", "Health Care", "Financials", "Energy", "Industrials",
                "Consumer Discretionary", "Communication Services", "Utilities"]
        sectors = {t: secs[i % len(secs)] for i, t in enumerate(frames)}
        subs = {t: f"{sectors[t]} {i % 3}" for i, t in enumerate(frames)}
        sp500 = set(frames)
    else:
        tickers, sectors, subs, sp500 = get_universe()
        frames = download_with_retry(tickers)
        if len(frames) < 0.8 * len(tickers):
            sys.exit(f"Only got data for {len(frames)} of {len(tickers)} tickers; not publishing a partial scan.")
    print(f"{len(frames)} tickers with enough history")

    breadth = build_breadth(frames)
    asof = breadth.index[-1].date().isoformat()
    rows = [r for r in (analyze(t, d) for t, d in frames.items()) if r]
    df = pd.DataFrame(rows)
    df["sector"] = df.ticker.map(sectors).fillna("")
    bh = {}
    try:
        bh = breadth_history(frames, sectors, sp500)
    except Exception as e:                 # extras; never block the scan
        print("  breadth history failed:", e)
    # the user's overbought rule (RSI / CCI dropped 2026-10-15): nothing with its sector's or the market's breadth over the
    # 75 line gets a setup ("Overbought" instead), a Top picks spot, a Plan M spot or a paper buy
    br = {g: round(float(b.rise.iloc[-1]), 1) for g, b in bh.items()}       # tonight's breadth, as the page shows it
    mkt_hot = breadth_hot(None, br)
    obr = overbought(frames, sectors, br)
    ob = {t: " and ".join(own + ([sec] if sec else [])) for t, (own, sec) in obr.items()}
    df["ob"] = df.ticker.map(ob).fillna("")
    would = df.setup.notna()
    df["blocked"] = would & ((df.ob != "") | bool(mkt_hot))
    df["has_setup"] = would & ~df.blocked
    df["setup"] = np.where(df.has_setup, df.setup, np.where((df.ob != "") | df.blocked, "Overbought", "Uptrend"))
    sw = {}
    try:
        sw = strength(df, frames, bh)
        print(f"  strongest sector, strongest stock: {int(df.ss_ok.sum())} stocks on the list, "
              f"{int((df.ss_ok & df.has_setup).sum())} of them setups")
    except Exception as e:                 # never block the scan; the paper accounts then keep the stock table's order
        import traceback
        traceback.print_exc()
        print("  strength score failed:", e)
    secb = sector_breadth(frames, df, sectors)
    df["super"] = df.has_setup & (df.tier == "Super")
    picks = df[df.has_setup | df.core | df.blocked].sort_values(["has_setup", "super", "score"], ascending=False).reset_index(drop=True)
    print(f"{int(df.core.sum())} of {len(df)} liquid stocks in uptrend; {int(picks.has_setup.sum())} setups ({int(picks.super.sum())} super, {int((picks.has_setup & ~picks.super).sum())} regular; {(picks.setup == 'Momentum').sum()} momentum, {(picks.setup == 'Pullback').sum()} pullback)")
    print(f"  overbought: {len(ob)} stocks sector breadth over "
          f"{CFG['OB_BREADTH']}); the market is {'overbought: ' + mkt_hot if mkt_hot else 'not overbought'}; "
          f"{int(df.blocked.sum())} setups left out")

    picks["opt"] = None
    if not a.demo and not a.no_options:
        print(f"Looking up options for top {CFG['OPT_TOP_N']}...", flush=True)
        why_n = {}
        for i in picks.index[picks.has_setup][:CFG["OPT_TOP_N"]]:
            try:
                o, why = pick_call(picks.at[i, "ticker"], picks.at[i, "close"])
                picks.at[i, "opt"] = o
                why_n[why if o else "none"] = why_n.get(why if o else "none", 0) + 1
                if o is None:
                    print("  no contract", picks.at[i, "ticker"], why)
            except Exception as e:
                print("  options failed", picks.at[i, "ticker"], e)
        print(f"  options: {why_n}", flush=True)

    print("Loading sector ETF charts...")
    etf_frames = {}
    try:
        if a.demo:
            ef = demo_frames(n=len(SECTOR_ETF), days=2600)
            etf_frames = dict(zip(SECTOR_ETF.values(), ef.values()))
        else:
            etf_frames = download_etfs()
        charts = chart_data(etf_frames)
    except Exception as e:                 # charts are extras; never block the scan on them
        print("  sector charts failed:", e)
        charts = {}
    try:
        chart_breadth(charts, bh)
    except Exception as e:
        print("  breadth strips failed:", e)
    print(f"  charts for {len(charts)} of {len(SECTOR_ETF)} sectors")

    vix = None
    try:
        vix = demo_vix() if a.demo else download_vix()
        print(f"  VIX {vix.iloc[-1]:.2f} ({len(vix)} days)")
    except Exception as e:                 # an extra; never block the scan on it
        print("  VIX failed:", e)

    out = Path(a.out); out.mkdir(exist_ok=True)
    now = pd.Timestamp.now(tz="America/New_York")
    live_at = None if a.demo or asof != now.date().isoformat() or now.time() >= dt.time(16, 15) else now.strftime("%H:%M")
    if live_at:
        print(f"Run at {live_at} New York time, before the close: today's prices are not closes, so the AI picks list is not changed.")
    print("Building the top picks lists...")
    lists, earn, calls = None, {}, {}
    try:
        state_file = Path(__file__).resolve().parent / "history" / "ai_picks.json"   # yesterday's AI picks
        prev = None if a.demo or not state_file.exists() else json.loads(state_file.read_text(encoding="utf-8"))
        spy = etf_frames["SPY"]["Close"] if "SPY" in etf_frames else None
        lists, state = pick_lists(frames, sectors, subs, spy, prev, a.demo, step=live_at is None, ob=ob, mkt_hot=mkt_hot)
        lists["live_at"] = live_at
        if live_at is None:                # the saved list only moves on closing prices
            (out / "ai_picks.json").write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"  new uptrends {lists['nu']['total']}, breakout watch {len(lists['bo']['rows'])}, AI picks {len(lists['ai']['rows'])}")
        if not a.demo:
            earn = next_earnings(sorted({r["ticker"] for k in ("nu", "bo", "ai") for r in lists[k]["rows"]}))
            print(f"  earnings dates for {len(earn)} tickers")
        if not a.no_options:
            try:
                px = {r["ticker"]: r["close"] for k in ("nu", "bo", "ai") for r in lists[k]["rows"] if r.get("close")}
                print(f"  looking up calls for {len(px)} tickers...", flush=True)
                calls = list_calls(px, a.demo)
                why_n = {}
                for t, o in calls.items():
                    k = ("fits" if not o["miss"] else "closest, misses " + "+".join(o["miss"])) if isinstance(o, dict) else o
                    why_n[k] = why_n.get(k, 0) + 1
                    if isinstance(o, dict) and o["miss"]:
                        print(f"    {t}: closest {o['exp']} ${o['strike']:g} delta {o['delta']:.2f} OI {o['oi']} ({'+'.join(o['miss'])})")
                print(f"  calls: {why_n}", flush=True)
            except Exception as e:         # extras; never block the lists
                print("  list calls failed:", e)
        oc = lambda t: calls[t] if isinstance(calls.get(t), dict) else {}
        prem = lambda o: ((o["bid"] + o["ask"]) / 2 if o["quote"] == "live" else o["last"]) if o else None
        pd.DataFrame([dict(list=k, rank=i + 1, **{c: r.get(c) for c in ("ticker", "sector", "close", "rs", "added", "price", "vol1", "vol5")},
                           **{f"call_{c}": oc(r["ticker"]).get(c) for c in ("exp", "dte", "strike", "delta", "oi", "quote", "fits")},
                           call_premium=prem(oc(r["ticker"])), call_misses="+".join(oc(r["ticker"]).get("miss") or []),
                           ai_rank=r.get("rank"), why="; ".join(r.get("why") or []))
                      for k in ("nu", "bo", "ai") for i, r in enumerate(lists[k]["rows"])]).to_csv(out / f"toppicks_{asof}.csv", index=False)
    except Exception as e:                 # never block the scan on the lists
        import traceback
        traceback.print_exc()
        print("  top picks failed:", e)
    print("Building the OVTLYR plan...")
    ov = None
    try:
        if a.demo:
            qqq = list(demo_frames(n=1, days=600).values())[0]
        else:
            qqq = yf_batch(["QQQ"], period="2y", interval="1d").get("QQQ")
        saved = sorted(f for f in (Path(__file__).resolve().parent / "history").glob("ovtlyr_*.json") if f.stem[7:] < asof)
        prev_ov = None if a.demo or not saved else json.loads(saved[-1].read_text(encoding="utf-8"))   # the last list
        ov = ovtlyr_plan(frames, sectors, etf_frames["SPY"], qqq, None if a.demo else next_earnings, prev_ov, br,
                         {t: " and ".join(own) for t, (own, _) in obr.items() if own})
        ov["live_at"] = live_at
        if live_at is None:                # paper.py's OVTLYR account trades the next morning on closing prices only
            (out / f"ovtlyr_{asof}.json").write_text(json.dumps(ov, indent=1), encoding="utf-8")
        f = ov["funnel"]
        print(f"  market {'on' if ov['market']['ok'] else 'off'}, {sum(v['ok'] for v in ov['sectors'].values())} sectors pass, "
              f"{f['setups']} Plan M setups (of {f['signal']} buy signals; {sum(x['new'] for x in ov['setups'])} new, "
              f"{len(ov['dropped'])} dropped since {ov['prev_asof']}), "
              + ", ".join(f"{k} {'set up' if e['ok'] else 'not set up'}" for k, e in ov["etf"].items()))
    except Exception as e:                 # never block the scan on it
        import traceback
        traceback.print_exc()
        print("  OVTLYR plan failed:", e)
    listed = [r["ticker"] for k in ("nu", "bo", "ai") for r in (lists or {}).get(k, {}).get("rows", [])]
    listed += [h["ticker"] for k in ("nu", "bo") for h in (lists or {}).get(k, {}).get("hot", [])]
    listed += [s["ticker"] for s in (ov or {}).get("setups", [])]
    listed += [r[0] for r in (ov or {}).get("screen") or [] if r[5].count("0") <= 2]   # the OVTLYR screener's closest
    chart_tks = list(dict.fromkeys(list(picks.ticker) + listed + list(SECTOR_ETF.values())))
    print(f"Building trend charts and 10-year backtests for {len(chart_tks)} tickers...")
    bts = {}
    try:
        groups = {**{f: g for g, f in SECTOR_ETF.items()}, **{t: g for t, g in sectors.items() if isinstance(g, str) and g}}
        n, bts = write_stock_charts(chart_tks, out, a.demo, frames, bt_breadth(bh), groups)
        print(f"  wrote {n} chart files, {len(bts)} backtests")
        if bts:
            e = [b["rules"] - b["hold"] for b in bts.values()]
            print(f"  rules beat holding the stock on {sum(x > 0 for x in e)} of {len(e)}, median {np.median(e):+.0f} points")
    except Exception as e:                 # extras; never block the scan
        print("  stock charts failed:", e)
    if ov:                                 # the OVTLYR screener links only the tickers that have a chart file
        ov["charted"] = [r[0] for r in ov.get("screen") or [] if (out / "data" / f"{r[0]}.json").exists()]
    for k in ("rules", "hold", "spy", "start"):
        picks[f"bt_{k}"] = picks.ticker.map({t: b[k] for t, b in bts.items()})
    if ov:                                 # the OVTLYR screener page (ovtlyr/): the deck's rules only
        try:
            import ovtlyr_page
            n = ovtlyr_page.build(ov, out)
            print(f"  OVTLYR page: {n['ready']} ready, {n['one']} one rule away, {n['rows']} stocks")
        except Exception as e:             # never block the scan on it
            import traceback
            traceback.print_exc()
            print("  OVTLYR page failed:", e)
    html = render(picks, breadth, secb, df, asof, a.demo, charts, lists, earn, calls, live_at, ov, bh, sw, etf_frames.get("SPY"), vix)
    (out / "latest.html").write_text(html, encoding="utf-8")
    (out / f"screener_{asof}.html").write_text(html, encoding="utf-8")
    picks.drop(columns=["opt"]).to_csv(out / f"screener_{asof}.csv", index=False)
    secb.round(1).to_csv(out / f"sectors_{asof}.csv", index=False)
    if bh:                                 # paper.py's overbought rule reads the market's and each sector's breadth from here
        pd.DataFrame([dict(group=g, date=b.index[-1].date().isoformat(), rise=br[g], avg5=round(float(b.a5.iloc[-1]), 1),
                           avg10=round(float(b.avg.iloc[-1]), 1), upswing=int(b.on.iloc[-1]), overbought=int(br[g] > CFG["OB_BREADTH"]),
                           oversold=int(br[g] < CFG["OS_BREADTH"])) for g, b in bh.items()]).to_csv(out / f"breadth_{asof}.csv", index=False)
    print(f"Done. Open {out / 'latest.html'}")


if __name__ == "__main__":
    main()
