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


def write_stock_charts(tickers, out, demo=False, known=None):
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
        daily = fetch(period="10y", interval="1d")
        monthly = fetch(period="max", interval="1mo")
        # explicit dates: with period= yfinance starts at the listing date for some recent IPOs (GEV) and Yahoo rejects it
        hourly = fetch(start=(dt.date.today() - dt.timedelta(days=700)).isoformat(), interval="60m")
    dd = out / "data"; dd.mkdir(parents=True, exist_ok=True)
    n = 0
    for t in tickers:
        d = daily.get(t)
        if d is None or len(d) < 60:
            continue
        rec = {"D": trend_series(d, STOCK_BARS["D"], blocks=True), "W": trend_series(to_period(d, "W"), STOCK_BARS["W"])}
        if t in monthly and len(monthly[t]) > 20:
            rec["M"] = trend_series(monthly[t], STOCK_BARS["M"])
        if t in hourly and len(hourly[t]) > 60:
            rec["4H"] = trend_series(to_4h(hourly[t]), STOCK_BARS["4H"], intraday=True)
        (dd / f"{t}.json").write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
        n += 1
    return n

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

    # ---- momentum breakout
    setup, pts = None, 0
    if core and 55 <= r.iloc[-1] <= 80 and ext <= 3.0:
        near_hi = px >= 0.97 * hi252
        brk = px > prior20hi
        if brk or near_hi:
            setup = "Momentum"
            pts = 12 * brk + 6 * near_hi + (8 if relv >= 1.5 else 4 if relv >= 1.2 else 0) \
                + (5 if r.iloc[-1] <= 75 else 0) + (5 if ext <= 2 else 0)
    # ---- oversold pullback inside an uptrend (10>20 may dip, so not required)
    if setup is None and p_e50 and x2050 and (p150 or x50150):
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
        ticker=t, setup=setup, score=round(score, 1), close=px,
        open=d["Open"].iloc[-1], chg1d=(px / c.iloc[-2] - 1) * 100,
        chg5d=(px / c.iloc[-6] - 1) * 100, chg1m=(px / c.iloc[-22] - 1) * 100, rsi=r.iloc[-1], atr_pct=atr_pct, relvol=relv,
        from_hi=(px / hi252 - 1) * 100,
        vs10=(px / e10.iloc[-1] - 1) * 100, vs20=(px / e20.iloc[-1] - 1) * 100, vs50=(px / e50.iloc[-1] - 1) * 100,
        p150=bool(p150), p200=bool(p200), x1020=bool(x1020), core=core,
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
# Rising = the share of stocks with the 10 EMA above the 20 (the fast half of the uptrend rule); uptrend = the share
# passing the full rule; an upswing = Rising above its own 10-day EMA (the same test as the OVTLYR section's breadth).
def breadth_history(frames, sectors, members):
    tks = [t for t in frames if t in members]
    per = lambda f: pd.DataFrame({t: f(frames[t]["Close"]) for t in tks}).sort_index()   # each on its own dates
    C = per(lambda c: c)
    e10, e20, e50 = (per(lambda c, n=n: ema(c, n)) for n in (10, 20, 50))
    m150 = per(lambda c: ema(c, 150) if CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean())
    rise = (e10 > e20).astype(float).where(C.notna())
    up = ((e10 > e20) & (C > e50) & (C > m150)).astype(float).where(C.notna() & m150.notna())
    groups = {"S&P 500": tks}
    for t in tks:
        groups.setdefault(sectors.get(t) or "Other", []).append(t)
    out = {}
    for name, cols in groups.items():
        if name not in SECTOR_ETF or len(cols) < 5:
            continue
        r = rise[cols].mean(axis=1) * 100
        b = pd.DataFrame(dict(rise=r, avg=r.ewm(span=10, adjust=False).mean(), up=up[cols].mean(axis=1) * 100))
        r1, a1 = b.rise.round(1), b.avg.round(1)    # the numbers the page shows; a tie keeps the day before's state
        b["on"] = pd.Series(np.where(r1 > a1, 1.0, np.where(r1 < a1, 0.0, np.nan)), index=b.index).ffill().fillna(0.0)
        b.index = pd.DatetimeIndex([pd.Timestamp(i.strftime("%Y-%m-%d")) for i in b.index])
        out[name] = b.iloc[30:]                      # skip the EMA warm-up at the start of the 2 years
    return out


def swing_state(b):
    """Tonight's state for one group: Rising, its 10-day average, Uptrend, whether it's an upswing (Rising above the
    average), the day that state began and how many trading days it has lasted."""
    on = b.on > 0
    k = int(np.flatnonzero(on.ne(on.shift()).to_numpy())[-1])
    x = b.iloc[-1]
    return dict(rise=round(float(x.rise), 1), avg=round(float(x.avg), 1), up=None if x.up != x.up else round(float(x.up), 1),
                on=bool(on.iloc[-1]), since=b.index[k].date().isoformat(), days=len(b) - k)


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


def ai_step(held, score, sector, n=10, keep=30, cap=3, allow_new=True, sell=()):
    """One night of the AI picks list. held: the current picks; score: today's AI score for every liquid
    stock (Series). A pick stays while it ranks in the top `keep` and isn't in `sell`; open slots go to
    the best-ranked stocks, at most `cap` per sector. Returns (kept, added, dropped)."""
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
            if t not in kept and t not in dropped and t not in sell and cnt[grp(t)] < cap:
                added.append(t)
                cnt[grp(t)] += 1
    return kept, added, dropped


def ai_update(prev, score, sector, close, spy_now, asof, present, sell=(), allow_new=True):
    """Step the saved AI picks list once per trading day. State: {as_of, picks, closed}; each pick keeps
    the day it was added and that day's close (and SPY's) so the page can show how it has done."""
    st = prev if prev and prev.get("picks") is not None else dict(as_of=None, picks=[], closed=[])
    if st.get("as_of") == asof:                       # already stepped for this day (a re-run)
        return st
    old = {p["ticker"]: p for p in st["picks"]}
    gone = [t for t in old if t not in present]       # no prices tonight: hold, don't guess
    kept, added, dropped = ai_step([t for t in old if t in present], score, sector, n=CFG["AI_N"] - len(gone),
                                   keep=CFG["AI_KEEP"], cap=CFG["AI_CAP"], allow_new=allow_new, sell=sell)
    px = lambda t: round(float(close[t]), 2)
    spy = round(float(spy_now), 2) if spy_now == spy_now and spy_now is not None else None
    closed = list(st.get("closed", []))
    for t in dropped:
        why = (f"closed below its 50-day EMA" if t in sell else f"fell out of the top {CFG['AI_KEEP']}"
               if t in score.index else "no longer passes the liquidity filter")
        closed.append(dict(old[t], dropped=asof, out=px(t), spy_out=spy, why=why))
    picks = [old[t] for t in kept + gone] + [dict(ticker=t, added=asof, price=px(t), spy=spy) for t in added]
    return dict(as_of=asof, picks=picks, closed=closed)


def pick_lists(frames, sectors, subs, spy, prev, demo=False, step=True):
    """The three lists for tonight. Returns (lists for the page, new AI picks state).
    step=False (a run before the close) shows the saved AI picks without changing them."""
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
    nu = dict(desc=desc, total=int((F["new_up"].iloc[-1] & ok.iloc[-1]).sum()), rows=[
        row(t, days_out=None if last["days_out"][t] != last["days_out"][t] else int(last["days_out"][t]),
            relvol=float(last["relvol"][t])) for t in tks[:CFG["NEW_UP_N"]]])

    desc, cand, rank = breakout_lists(F, ok)[CFG["BREAKOUT"]]
    s = ranked(rank, cand)
    bo = dict(desc=desc, total=int(cand.iloc[-1].sum()), rows=[
        row(t, piv=float(last["piv"][t]), dist=float(last["dist"][t]) * 100, base_days=int(last["base_days"][t]),
            tight=float(last["tight"][t]) * 100, dry=float(last["dry"][t])) for t in s.index[:CFG["BREAKOUT_N"]]])

    score = ai.iloc[-1].dropna()
    present = set(c.dropna().index)
    sell = set(c.index[(c < last["e50"]).to_numpy(bool)]) if CFG["AI_TREND_EXIT"] else set()
    spy_now = float(spy.iloc[-1]) if spy is not None and len(spy) else float("nan")
    market_ok = True
    if CFG["AI_MARKET_FILTER"] and spy is not None and len(spy) > 200:
        market_ok = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
    st = (ai_update(prev, score, sectors, c, spy_now, asof, present, sell, market_ok) if step else
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
        ai_rows.append(row(t, added=p["added"], price=p["price"], now=now,
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
    ai_list = dict(desc=A[CFG["AI_SCORE"]][0], rows=ai_rows, market_ok=market_ok, as_of=st["as_of"],
                   dropped=[p for p in st["closed"] if p["dropped"] == asof], since=min(
                       [p["added"] for p in st["picks"]] + [p["added"] for p in st["closed"]], default=asof), track=track)
    return dict(asof=asof, nu=nu, bo=bo, ai=ai_list), st

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
    """SPY or QQQ tonight: close, high, 10 / 20 / 50-day EMAs, RSI today and the day before, ATR."""
    c = d["Close"]
    e = {n: ema(c, n).iloc[-1] for n in (10, 20, 50)}
    r = rsi(c)
    return dict(date=d.index[-1].date().isoformat(), close=round(float(c.iloc[-1]), 2), high=round(float(d["High"].iloc[-1]), 2),
                e10=round(float(e[10]), 2), e20=round(float(e[20]), 2), e50=round(float(e[50]), 2),
                rsi=round(float(r.iloc[-1]), 1), rsi_prev=round(float(r.iloc[-2]), 1), atr=round(float(atr(d).iloc[-1]), 2))


def ovtlyr_plan(frames, sectors, spy, qqq, earn=None):
    """Tonight's OVTLYR plan: the market and sector checks, Plan ETF's checks and sell signals, and the Plan M setups
    (stocks passing every stock and sector rule, freshest signal first). frames: the universe's daily bars; spy / qqq:
    daily bars; earn: a function giving next earnings dates for a list of tickers (None skips that check)."""
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
    n_back = lambda n: C.iloc[-1] / C.iloc[-1 - n] - 1 if len(C) > n else np.nan
    rs = (0.4 * n_back(63) + 0.2 * n_back(126) + 0.2 * n_back(189) + 0.2 * n_back(252)).where(liquid).rank(pct=True)
    clear, near_n = [], 0
    for t in in_sec:
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
        sell = (([f"{und}'s 10 EMA is under its 20 EMA (a 10/20 bearish cross, the sell signal here)"] if x["e10"] < x["e20"] else [])
                + ([f"{und} closed more than {OV['HOT_ATR']:g} ATR above its 20 EMA"] if x["close"] > x["e20"] + OV["HOT_ATR"] * x["atr"] else []))
        hit = ob_hit(blocks, day, OV["ETF_OB_AGE"])
        if hit:
            sell.append(f"{und} reached an order block from {hit['start']:%b} {hit['start'].day} ({hit['bot']:.2f}-{hit['top']:.2f})")
        etf[fund] = dict(under=und, ok=all(c["ok"] for c in ch), checks=ch, sell=sell, **x)

    funnel = dict(signal=int(sig.sum()), rules=int(rules.sum()), sector=len(in_sec), near_ob=near_n, earnings=earn_n,
                  setups=len(setups), earn_checked=bool(earn))
    return dict(asof=asof.isoformat(), market=market, sectors=secs, etf=etf, setups=setups, funnel=funnel)

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
    cls = "" if good is None else ("up" if good else "dn")
    return f'<div class="card"><div class="lbl">{label}</div><div class="val {cls}">{value}</div><div class="sub">{sub}</div>{spark(series)}</div>'


PAPER_JS = Path(__file__).resolve().parent / "paper.js"   # the paper trading widgets (accounts traded by paper.py)
PAPER_HINT = ("Four paper accounts with $1,000 each, trading until Apr 6, 2027. <b>Your system</b> trades your screener "
              "setups and option rules at about 10:00 AM New York time; <b>Your system, after 2 PM</b> uses the same rules but "
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

    nu, bo, ai = L["nu"], L["bo"], L["ai"]
    E = "Earnings"
    nu_rows = [[tk(r), num(r["close"]), pc(r["chg1d"]), num(r["days_out"], "{:.0f}"), num(r["rs"], "{:.0f}"),
                pc(r["from_hi"]), num(r["relvol"], "{:.1f}x")] + vo(r) + [er(r["ticker"])] for r in nu["rows"]]
    nu_html = (f'<div class="hint">{nu["total"]} stock{"s" if nu["total"] != 1 else ""} turned into an uptrend on {L["asof"]} '
               f'(EMA10 &gt; EMA20, price &gt; EMA50 and &gt; 150 MA, after missing it the day before). '
               f'{PICK_TEXT["nu"].get(CFG["NEW_UP"], nu["desc"])} "Out" = days it had been out of an uptrend. '
               f'Vol vs avg = that day\'s volume vs the 20-day average.</div>'
               + table("pk-nu", ["Ticker", "Close", "1D %", "Out (days)", "RS", "From 52w hi", "Vol vs avg"] + VO + [E], nu_rows,
                       f"No stock turned into an uptrend on {L['asof']}.") + note("nu"))
    bo_rows = [[tk(r), num(r["close"]), num(r["piv"]), pc((r["close"] / r["piv"] - 1) * 100), num(r["base_days"], "{:.0f}"), num(r["tight"], "{:.1f}%"),
                num(r["dry"], "{:.2f}x"), num(r["rs"], "{:.0f}")] + vo(r) + [er(r["ticker"])] for r in bo["rows"]]
    bo_txt = PICK_TEXT["bo"].get(CFG["BREAKOUT"], "{n} stocks fit: " + bo["desc"] + ".")
    bo_html = (f'<div class="hint">{bo_txt.format(n=bo["total"])} Level = the 50-day high; a breakout is a close above it. '
               f'Range = high to low of the last 10 days; '
               f'Vol 10d/50d = average volume of the last 10 days vs the last 50.</div>'
               + table("pk-bo", ["Ticker", "Close", "Breakout level", "Below it", "Base (days)", "10-day range", "Vol 10d/50d", "RS"] + VO + [E],
                       bo_rows, "No stock fits the breakout rules today.") + note("bo"))
    new = lambda r, cell: ('<span class="mut">new today</span>', 0) if r["added"] == L["asof"] else cell
    ai_rows = [[tk(r), num(r.get("rank"), "{:.0f}"), (r["added"], r["added"]), num(r["price"]), num(r.get("now")),
                new(r, pc(r.get("ret"))), new(r, pc(r.get("spy_ret")))] + vo(r) + [(", ".join(r["why"]), ""), er(r["ticker"])]
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
    if L.get("live_at"):
        mkt += (f'<div class="hint warn">This page was built at {L["live_at"]} New York time, before the close, so these are the '
                f'picks from the last run after a close, with prices as of {L["live_at"]}. The list only changes on a run after the close.</div>')
    ai_html = (f'<div class="hint">My own list, rebuilt every night by rules I chose and tested: {PICK_TEXT["ai"].get(CFG["AI_SCORE"], ai["desc"])}. '
               f'I hold up to {CFG["AI_N"]}, at most {CFG["AI_CAP"]} per sector. A pick stays while it ranks in the top {CFG["AI_KEEP"]}; '
               f'open spots go to the best-ranked stocks in the top {CFG["AI_KEEP"]} that fit the sector limit, and a spot stays empty '
               f'(cash) when none fits, as in the test. Rank = today\'s rank of all liquid stocks.</div>'
               + mkt + table("pk-ai", ["Ticker", "Rank", "Picked", "Price then", "Now", "Since picked", "SPY since"] + VO + ["Why", E],
                             ai_rows, "No picks yet.")
               + (f'<div class="hint">Dropped today: {dropped}</div>' if dropped else "") + track + note("ai"))
    tab = lambda k, label, n, on: f'<button{" class=on" if on else ""} data-pk="{k}">{label} <span class="n">{n}</span></button>'
    return ('<h2>Top picks</h2><div class="bar pk">' + tab("nu", "New uptrends", nu["total"], True)
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
    mk = (f'<div class="ovb"><div class="ovh">Market <span class="{"up" if m["ok"] else "dn"}">Plan M is {"on" if m["ok"] else "off"}</span></div>'
          f'<ul>{"".join(li(c) for c in m["checks"])}</ul><div class="mut">All four must pass for new Plan M trades.</div></div>')
    secs = sorted(ov["sectors"].items(), key=lambda kv: (not kv[1]["ok"], kv[0]))
    n_ok = sum(v["ok"] for _, v in secs)
    sc = (f'<div class="ovb"><div class="ovh">Sectors <span class="mut">{n_ok} of {len(secs)} pass</span></div><ul>'
          + "".join(f'<li>{ok(v["ok"])} {html_esc(k)} <span class="mut">breadth {v["bull"]:.0f}% vs {v["bull_ema"]:.0f}% avg, RSI {v["rsi"]:.0f}'
                    + (f' · {html_esc(v["miss"][0])}' if v["miss"] else "") + '</span></li>' for k, v in secs)
          + '</ul><div class="mut">Breadth above its 10-day average, average RSI above SPY\'s, under 70 and rising. '
            'Health Care is excluded in the plan.</div></div>')
    et = ('<div class="ovb"><div class="ovh">Plan ETF <span class="mut">spare cash</span></div>'
          + "".join(f'<div><b>{k}</b> {ok(e["ok"])} <span class="mut">on {e["under"]}\'s signals</span></div><ul>'
                    + "".join(li(c) for c in e["checks"]) + "</ul>"
                    + ("".join(f'<div class="warn">Sell signal: {html_esc(x)}</div>' for x in e["sell"]))
                    for k, e in ov["etf"].items())
          + '<div class="mut">When neither Plan M nor Plan ETF is set up, cash waits in SGOV (Plan #SICADFU).</div></div>')

    def pc(v):
        return f'<span class="{"up" if v > 0 else "dn" if v < 0 else ""}">{v:+.1f}%</span>'
    rows = []
    for s in ov["setups"]:
        cd = dt.date.fromisoformat(s["cross"])
        sig = f'{cd:%b} {cd.day} <span class="mut">{"today" if s["age"] == 0 else str(s["age"]) + "d ago"}</span>'
        up = (f'{s["ob_up"]:.2f} <span class="mut">{(s["ob_up"] / s["close"] - 1) * 100:+.1f}%</span>' if s["ob_up"] else
              '<span class="mut">none</span>')
        if s["earn"]:
            ed = dt.date.fromisoformat(s["earn"])
            er = f'{ed:%b} {ed.day} <span class="mut">{(ed - dt.date.fromisoformat(ov["asof"])).days}d</span>'
        else:
            er = '<span class="mut">n/a</span>'
        cells = [(f'<b class="tk" data-tk="{s["ticker"]}">{s["ticker"]}</b><div class="sec">{s["sector"]}</div>', s["ticker"]),
                 (sig, s["age"]), (f'{s["close"]:.2f}', s["close"]),
                 (f'{s["rsi"]:.0f} <span class="mut">from {s["rsi_prev"]:.0f}</span>', s["rsi"]),
                 (pc((s["close"] / s["e10"] - 1) * 100), round((s["close"] / s["e10"] - 1) * 100, 2)),
                 (f'{s["atr"]:.2f}', s["atr"]), (up, s["ob_up"] or ""), (er, s["earn"] or ""),
                 ("" if s["rs"] is None else str(s["rs"]), "" if s["rs"] is None else s["rs"])]
        rows.append("<tr>" + "".join(f'<td data-v="{v}">{c}</td>' for c, v in cells) + "</tr>")
    head = ["Ticker", "Buy signal", "Close", "RSI", "vs 10 EMA", "ATR", "Order block above", "Earnings", "RS"]
    if rows:
        table = (f'<div class="wrap"><table id="ov-m"><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        table = '<div class="hint pke">No stock passes every Plan M stock and sector rule tonight.</div>'
    earn_txt = (f'{f["earnings"]} reported earnings within {OV["EARN_DAYS"]} days of the next market day' if f["earn_checked"]
                else "earnings dates were not checked (demo)")
    funnel = (f'<div class="hint">Plan M setups tonight: {f["signal"]} liquid stocks priced ${OV["PRICE"][0]:.0f}-${OV["PRICE"][1]:.0f} had a buy '
              f'signal in the last {OV["SIGNAL_DAYS"]} trading days; {f["rules"]} also had the 10/20/50 uptrend, price over the 10 EMA '
              f'and a rising RSI; {f["sector"]} of those were in passing sectors; {f["near_ob"]} were within {OV["OB_GAP"]:.0%} of an '
              f'order block and {earn_txt}, which leaves {f["setups"]}. Freshest signal first, then relative strength (RS, 1-99).'
              + ("" if m["ok"] else " The market rules fail tonight, so the paper account won't buy these.") + "</div>")
    live = (f'<div class="hint warn">Built at {ov["live_at"]} New York time, before the close, from prices that are not closes yet. '
            'The paper account only trades on the plan from a run after the close.</div>' if ov.get("live_at") else "")
    return ('<h2>OVTLYR plan</h2><div class="hint">OVTLYR\'s Plan M, Plan ETF and Plan #SICADFU from the trading-plan deck, '
            'rebuilt from this page\'s data; the <b>OVTLYR plan</b> paper account trades it. OVTLYR\'s fear &amp; greed heatmap and '
            'buy/sell signals are private, so this uses stand-ins: heatmap = 14-day RSI; buy signal = the 10 EMA crossing above the '
            f'20 EMA (it counts for {OV["SIGNAL_DAYS"]} trading days); sell signal = the 10 EMA under the 20; breadth = the share of '
            'stocks with the 10 EMA above the 20, against its 10-day average. Left out: OVTLYR channels and the per-stock backtest '
            'check.</div>'
            f'{live}<div class="ovg">{mk}{sc}{et}</div>{funnel}{table}')


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
    trading day for the last 3 months, colored by the share of stocks with the 10 EMA above the 20.
    Returns the HTML and the numbers behind it (for the tap / hover tooltip)."""
    if not bh or "S&P 500" not in bh:
        return "", None
    names = ["S&P 500"] + sorted((n for n in bh if n != "S&P 500"), key=lambda n: -bh[n].rise.iloc[-1])
    idx = bh["S&P 500"].index[-days:]
    r1 = lambda v: [None if x != x else round(float(x), 1) for x in v]
    data, rows = dict(t=[d.strftime("%Y-%m-%d") for d in idx], rows=[]), []
    for i, n in enumerate(names):
        b, st = bh[n].reindex(idx), swing_state(bh[n])
        cells = "".join(f'<i class="h{min(9, int(v // 10))}"></i>' if v == v else "<i></i>" for v in b.rise)
        rows.append(f'<div class="hmr"><span class="hml">{html_esc(SHORT_SECTOR.get(n, n))}</span>'
                    f'<span class="hmc" data-i="{i}">{cells}</span><span class="hmv">{st["rise"]:.0f}% '
                    f'<span class="{"up" if st["on"] else "dn"}">{"▲" if st["on"] else "▼"}</span></span></div>')
        data["rows"].append(dict(n=n, r=r1(b.rise), a=r1(b.avg), u=r1(b.up), s=[None if v != v else int(v) for v in b.on]))
    ticks = [(k, d) for k, d in enumerate(idx) if k == 0 or d.month != idx[k - 1].month]
    if len(ticks) > 1 and ticks[1][0] < 8:          # a first month with only a few days would crowd the next label
        ticks = ticks[1:]
    axis = "".join(f'<b style="left:{k / len(idx) * 100:.1f}%">{d:%b}</b>' for k, d in ticks)
    key = "".join(f'<i class="h{k}"></i>' for k in range(10))
    return (f'<div class="hm" id="hm">{"".join(rows)}<div class="hmr"><span></span><span class="hmt">{axis}</span><span></span></div>'
            f'<div class="hmk"><span>0%</span>{key}<span>100% of stocks rising</span></div><div id="hmtip" class="hmtip" hidden></div></div>'), data


def render(picks, breadth, secb, df, asof, demo, charts=None, lists=None, earn=None, calls=None, live_at=None, ov=None, bh=None):
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
    rise_card = card("S&amp;P 500 stocks rising (EMA10 &gt; 20)", f"{w['rise']:.0f}%",
                     f"{'▲ upswing' if w['on'] else '▼ fading'} since {md(w['since'])}, 10-day avg {w['avg']:.0f}%",
                     bh["S&P 500"].rise.iloc[-60:], w["on"]) if w else ""
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
        return (f'<td data-v="{w["rise"] - w["avg"]:.1f}">{w["rise"]:.0f}% <span class="{"up" if w["on"] else "dn"}">'
                f'{"▲" if w["on"] else "▼"} since {md(w["since"])}</span></td>')
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
    heat, hm_data = heat_html(bh)
    sector_html = ('<h2>Sector breadth</h2>'
                   + ('<div class="hint">Rising = the share of S&amp;P 500 stocks with the 10 EMA above the 20 (the fast half of '
                      'your uptrend rule), by day for the last 3 months; greener = more stocks rising. ▲ = an upswing (Rising '
                      'above its own 10-day average), ▼ = fading. Tap or hover a row for the numbers.</div>' + heat if heat else "")
                   + '<div class="hint">Click a sector to filter the stock list. ± is the change vs 5 trading days ago. '
                   + ('Rising counts S&amp;P 500 stocks only, so each sector matches its SPDR ETF; the other columns count '
                      'every stock in the scan.' if heat else '')
                   + '</div><div class="wrap"><table id="s"><thead><tr>'
                   '<th>Sector</th><th>In uptrend</th>' + ('<th>Rising (10 &gt; 20)</th>' if "S&P 500" in sws else '') + '<th>Momentum</th><th>Pullback</th><th>% &gt; 20d</th>'
                   '<th>% &gt; 50d</th><th>% &gt; 200d</th><th>Adv / Dec</th><th>52w Hi / Lo</th></tr></thead>'
                   f'<tbody>{"".join(srows)}</tbody></table></div>')

    order = ["S&P 500"] + [n for n in secb.sector if n != "S&P 500"]
    order += [n for n in SECTOR_ETF if n not in order]
    charts = {n: charts[n] for n in order if charts and n in charts}
    if charts:
        strip = any(c.get("sw") for c in charts.values())
        chart_html = ('<h2>Sector charts</h2><div class="hint">Sector SPDR ETFs with EMA 10 (orange), 20 (blue) and 50 (purple). '
                      'Daily shows ~6 months, weekly ~2 years, monthly ~10 years.'
                      + (' The strip under each chart is its breadth: the solid line is Rising (the share of the S&amp;P 500 '
                         'stocks in it with the 10 EMA above the 20), the dotted line the share in your full uptrend. Green '
                         'shading = an upswing (Rising above its 10-day average), red = fading. Daily and weekly only: the '
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
    head = ["Ticker", "Setup", "Score", "Close", "Open", "1D %", "5D %", "1M %", "RSI", "ATR %", "RelVol", "From 52w hi", "vs EMA10", "vs EMA20", "vs EMA50",
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
        cells = [f'<b class="tk" data-tk="{r.ticker}">{r.ticker}</b><div class="sec">{r.sector}</div>', r.setup, f"{r.score:.0f}", f"{r.close:.2f}",
                 f"{r.open:.2f}", pct(r.chg1d), pct(r.chg5d), pct(r.chg1m), num(r.rsi, "{:.0f}"), num(r.atr_pct), num(r.relvol, "{:.1f}x"), num(r.from_hi, "{:+.1f}%"),
                 num(r.vs10, "{:+.1f}%"), num(r.vs20, "{:+.1f}%"), num(r.vs50, "{:+.1f}%"),
                 flag(r.p150), flag(r.p200), cross] + oc
        raw = [r.ticker, r.setup, r.score, r.close, r.open, r.chg1d, r.chg5d, r.chg1m, r.rsi, r.atr_pct, r.relvol, r.from_hi, r.vs10, r.vs20, r.vs50] + [""] * 11
        tds = "".join(f'<td data-v="{raw[i]}">{c}</td>' for i, c in enumerate(cells))
        rows.append(f'<tr data-setup="{r.setup}" data-sector="{r.sector or "Other"}" class="{"stack" if r.stack else ""}">{tds}</tr>')
    th = "".join(f"<th>{h}</th>" for h in head)
    banner = '<div class="demo">DEMO DATA, not real stocks</div>' if demo else ""
    n_m = int((picks.setup == "Momentum").sum()); n_p = int((picks.setup == "Pullback").sum())
    paper_js = PAPER_JS.read_text(encoding="utf-8") if PAPER_JS.exists() else ""
    paper_html = f'<h2>Paper trading</h2><div class="hint">{PAPER_HINT}</div><div id="pp" class="pp"></div>' if paper_js else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swing Screener {asof}</title><style>
:root{{--bg:#fff;--fg:#1b1b1f;--mut:#6b6b76;--card:#f4f4f7;--line:#e2e2e8;--up:#12803c;--dn:#c2271d;--acc:#2a5bd7}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111114;--fg:#ececf1;--mut:#9a9aa6;--card:#1b1b20;--line:#2c2c34;--up:#3ecf70;--dn:#ff6b61;--acc:#7aa2ff}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px -apple-system,system-ui,sans-serif}}
h1{{font-size:20px;margin:0 0 2px}} .meta{{color:var(--mut);margin-bottom:14px}}
.reg{{display:inline-block;padding:3px 10px;border-radius:99px;font-weight:600;margin-left:8px}}
.reg.good{{background:color-mix(in srgb,var(--up) 20%,transparent);color:var(--up)}}.reg.bad{{background:color-mix(in srgb,var(--dn) 20%,transparent);color:var(--dn)}}.reg.mid{{background:var(--card);color:var(--mut)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin-bottom:18px}}
.card{{background:var(--card);border-radius:10px;padding:10px 12px;color:var(--mut)}}.lbl{{font-size:12px}}.val{{font-size:24px;font-weight:700;color:var(--fg)}}.sub{{font-size:11px;margin-bottom:4px}}
.up{{color:var(--up)}}.dn{{color:var(--dn)}}
.bar button{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;margin-right:6px;font-size:13px}}.bar button.on{{border-color:var(--acc);color:var(--acc)}}
.wrap{{overflow-x:auto;margin-top:10px}} table{{border-collapse:collapse;white-space:nowrap;font-size:13px}}
th,td{{padding:6px 9px;border-bottom:1px solid var(--line);text-align:right}}th{{position:sticky;top:0;background:var(--bg);cursor:pointer;color:var(--mut);font-weight:600}}
td:first-child,th:first-child,td:nth-child(2),th:nth-child(2),td:nth-child(18),td:nth-child(19){{text-align:left}}
td:first-child,th:first-child{{position:sticky;left:0;background:var(--bg);z-index:1}}th:first-child{{z-index:2}}
.sec{{font-size:10px;color:var(--mut)}} tr.stack td:first-child{{box-shadow:inset 3px 0 var(--up)}}
.demo{{background:var(--dn);color:#fff;padding:6px 10px;border-radius:6px;margin-bottom:10px;font-weight:700}}
h2{{font-size:16px;margin:18px 0 2px}}.hint,.mut{{color:var(--mut);font-size:12px}}
.bar2{{height:4px;background:var(--line);border-radius:2px;margin-top:3px;min-width:90px}}.bar2 i{{display:block;height:100%;border-radius:2px}}
#s tbody tr{{cursor:pointer}}#s tbody tr.sel td{{background:var(--card)}}#s td:nth-child(2){{text-align:left}}
.chip{{font-size:12px;font-weight:600;background:var(--card);color:var(--acc);padding:2px 8px;border-radius:99px;cursor:pointer;margin-left:6px}}
.note{{color:var(--mut);font-size:12px;margin-top:14px;line-height:1.5}}
.pkt td:nth-child(2),.pkt th:nth-child(2){{text-align:right}}.pkt td.why,.pkt th.why{{text-align:left;white-space:normal;min-width:240px;color:var(--mut);font-size:12px}}
.ovg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:10px;margin:8px 0}}
.ovb{{background:var(--card);border-radius:10px;padding:10px 12px;font-size:12px;line-height:1.5}}.ovb ul{{margin:2px 0 6px;padding:0;list-style:none}}
.ovh{{display:flex;justify-content:space-between;gap:8px;font-weight:600;font-size:13px;margin-bottom:2px}}
.pkt .dte{{font-size:10px;color:var(--mut)}}.miss{{color:var(--mut)}}.bar.pk{{margin-top:8px}}.bar.pk .n{{color:var(--mut);font-weight:400}}.pkl .note{{margin-top:6px}}.note a{{color:var(--acc)}}.pke{{padding:10px 0}}.warn{{color:var(--dn);font-weight:600}}
.charts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:10px;margin-top:10px}}
.ch{{background:var(--card);border-radius:10px;padding:8px 10px}}.chh{{font-size:13px;margin-bottom:4px}}.chg{{float:right;font-weight:600}}.cv{{height:240px}}.bar.tf{{margin-top:8px}}
.bv{{height:64px}}.bl{{font-size:11px;color:var(--mut);margin-top:2px;min-height:15px}}.bl b{{color:var(--fg)}}.bv[hidden],.bl[hidden]{{display:none}}
.hm{{position:relative;background:var(--card);border-radius:10px;padding:10px 12px;margin:8px 0 6px;font-size:12px}}
.hmr{{display:grid;grid-template-columns:84px 1fr 46px;align-items:center;gap:6px;margin-bottom:2px}}
.hml{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px}}.hmv{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.hmc{{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;height:18px;border-radius:3px;overflow:hidden;cursor:crosshair;touch-action:pan-y}}
.hmc i{{display:block;background:var(--line)}}.hmc i.cur{{box-shadow:inset 0 0 0 2px var(--fg)}}
.hmt{{position:relative;height:13px;color:var(--mut);font-size:10px}}.hmt b{{position:absolute;top:0;font-weight:400}}
.hmk{{display:flex;align-items:center;margin-top:6px;color:var(--mut);font-size:10px}}.hmk i{{display:block;width:14px;height:8px}}.hmk span{{margin:0 6px}}.hmk span:first-child{{margin-left:0}}
.hmtip{{position:absolute;z-index:5;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12px;line-height:1.45;box-shadow:0 2px 10px rgba(0,0,0,.18);pointer-events:none;white-space:nowrap}}.hmtip[hidden]{{display:none}}
.hm i.h0{{background:color-mix(in srgb,var(--dn) 95%,var(--line))}}.hm i.h1{{background:color-mix(in srgb,var(--dn) 78%,var(--line))}}.hm i.h2{{background:color-mix(in srgb,var(--dn) 60%,var(--line))}}.hm i.h3{{background:color-mix(in srgb,var(--dn) 42%,var(--line))}}.hm i.h4{{background:color-mix(in srgb,var(--dn) 22%,var(--line))}}.hm i.h5{{background:color-mix(in srgb,var(--up) 22%,var(--line))}}.hm i.h6{{background:color-mix(in srgb,var(--up) 42%,var(--line))}}.hm i.h7{{background:color-mix(in srgb,var(--up) 60%,var(--line))}}.hm i.h8{{background:color-mix(in srgb,var(--up) 78%,var(--line))}}.hm i.h9{{background:color-mix(in srgb,var(--up) 95%,var(--line))}}
.tk{{cursor:pointer;color:var(--acc);text-decoration:underline dotted;text-underline-offset:3px}}
#cm{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:50;display:flex;align-items:center;justify-content:center}}#cm[hidden]{{display:none}}
#cm .box{{background:var(--bg);border-radius:12px;width:min(1200px,96vw);height:min(820px,92vh);display:flex;flex-direction:column;overflow:hidden}}
#cm .top{{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--line);flex-wrap:wrap}}#cm .top b{{font-size:16px}}
#cm .top .sp{{flex:1}}#cm .top a{{color:var(--acc);font-size:12px}}#cm .x{{background:none;border:0;color:var(--fg);font-size:22px;cursor:pointer;padding:0 4px}}
#cmlg{{padding:4px 12px 0}}#cmlg .up,#cmlg .dn{{font-weight:600}}#cmw{{flex:1;min-height:0}}.trl{{position:absolute;inset:0 0 26px 0;pointer-events:none;z-index:2}}.trl i{{position:absolute;top:0;bottom:0;opacity:.13}}#cmw>div{{height:100%}}
@media(max-width:600px){{#cm .box{{width:100vw;height:100dvh;border-radius:0}}}}</style></head><body>
{banner}<h1>Swing Screener<span class="reg {rcls}">{reg}</span></h1>
<div class="meta">Data as of {asof}{f" {live_at} New York time (market open, so prices are not closes)" if live_at else ""} · {n_m} momentum · {n_p} pullback · stocks averaging 1M+ shares/day · S&amp;P 500 + Nasdaq 100</div>
<div class="cards">{cards}</div>
{paper_html}
{picks_html(lists, earn, calls)}
{ov_html(ov)}
{sector_html}
{chart_html}
<h2>Stocks <span id="secf" class="chip" hidden></span></h2>
<div class="bar"><button class="on" data-f="setups">Setups</button><button data-f="Momentum">Momentum</button><button data-f="Pullback">Pullback</button><button data-f="all">All uptrend</button></div>
<div class="wrap"><table id="t"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<div class="note">Green bar = full stack (EMA10 &gt; 20 &gt; 50 &gt; {CFG["LONG_MA_TYPE"]}150 &gt; {CFG["LONG_MA_TYPE"]}200). Score = trend structure (70%) + setup quality (30 pts).
Uptrend = EMA10 &gt; EMA20, price &gt; EMA50 and price &gt; {CFG["LONG_MA_TYPE"]}150. Momentum requires an uptrend, RSI 55–80 and a 20-day breakout or within 3% of the 52w high; pullbacks require price &gt; EMA50, EMA20 &gt; EMA50, RSI ≤ 50, 3%+ off the 15-day high and back near/below the EMA20 (EMA10 may dip). Options shown for top {CFG["OPT_TOP_N"]} picks:
call nearest {CFG["TARGET_DELTA"]} delta, ~{CFG["TARGET_DTE"]} DTE, OI ≥ {CFG["MIN_OI"]}, spread ≤ {CFG["MAX_SPREAD_PCT"]:.0f}%. Greeks are Black-Scholes from Yahoo's IV (Yahoo IV can be unreliable; confirm in your broker). When Yahoo has no live bid/ask (after hours, weekends) the last trade is shown and IV is solved from it. Click any ticker for a 4H / daily / weekly / monthly chart (the daily chart has 1Y and 5Y buttons): the Trend view shades uptrends green (EMA10 &gt; EMA20, price &gt; EMA50 and &gt; 150 MA) and downtrends red (all three reversed), with arrows where each trend starts; the Indicators view shows RSI, MACD and Bollinger Bands (the free chart allows about 3 studies at once; swap them from its Indicators menu).
Order blocks (Trend view, daily chart): blue boxes are bullish blocks, the last down candle before a rise of 2+ ATR within 3 bars; orange boxes are bearish blocks, the last up candle before a drop of 2+ ATR. A box ends where price first came back to it; bright boxes haven't been revisited yet. This was the best of 18 versions in a 10-year test on 1,000 stocks, but as support it did no better than random price zones, while bearish blocks held as resistance slightly better than random. Not financial advice.</div>
<div id="cm" hidden><div class="box"><div class="top"><b id="cmt"></b>
<div class="bar iv src"><button class="on" data-src="trend">Trend</button><button data-src="tv">Indicators</button></div>
<div class="bar iv tfb"><button data-iv="240">4H</button><button class="on" data-iv="D">Daily</button><button data-iv="W">Weekly</button><button data-iv="M">Monthly</button></div>
<div class="bar iv rng"><button class="on" data-rng="1Y">1Y</button><button data-rng="5Y">5Y</button></div>
<div class="bar iv obb"><button class="on" id="obt" title="Show or hide order blocks">Order blocks</button></div>
<span class="sp"></span><a id="cml" target="_blank" rel="noopener">Open on TradingView ↗</a><button class="x" aria-label="Close">×</button></div>
<div id="cmlg" class="hint"></div><div id="cmw"><div id="cmc"></div></div></div></div>
<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
const CH={chart_json},HM={json.dumps(hm_data, separators=(",", ":"))};
const MD=t=>new Date(t+'T12:00:00').toLocaleDateString('en-US',{{month:'short',day:'numeric'}});
(function(){{const boxes=[...document.querySelectorAll('.ch')];if(!boxes.length)return;
if(!window.LightweightCharts){{document.getElementById('chfail').hidden=false;return}}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim();
const UP=V('--up'),DN=V('--dn'),PW=60;let tf='D';
// shading behind the strip: one box per run of upswing (green) or fading (red) days
function bandPrim(){{let ch,runs=[],rs=[];
const rend={{draw:tg=>tg.useBitmapCoordinateSpace(sc=>{{const x=sc.context,hr=sc.horizontalPixelRatio,H=sc.bitmapSize.height;
rs.forEach(r=>{{x.fillStyle=r.col;x.fillRect(Math.round(r.x1*hr),0,Math.max(1,Math.round(r.x2*hr)-Math.round(r.x1*hr)),H)}})}})}};
const view={{zOrder:()=>'bottom',renderer:()=>rend}};
return {{attached:p=>{{ch=p.chart}},paneViews:()=>[view],set:v=>{{runs=v}},updateAllViews:()=>{{if(!ch)return;const ts=ch.timeScale(),sp=ts.options().barSpacing/2;rs=[];
runs.forEach(([a,b,on])=>{{const x1=ts.timeToCoordinate(a),x2=ts.timeToCoordinate(b);if(x1==null||x2==null)return;rs.push({{x1:x1-sp,x2:x2+sp,col:(on?UP:DN)+'3d'}})}})}}}}}}
// breadth line under a chart: the bar's (or tonight's) Rising, its 10-day average, Uptrend and the upswing state
function leg(m,i){{if(!m.bl)return;const s=m.d[tf];if(!s||!s.br){{m.bl.textContent='';return}}
const L=s.br.length,last=i==null||i<0||i>=L-1||s.br[i]==null;if(last)i=L-1;
const r=s.br[i],a=s.ba[i],u=s.bu[i],w=m.d.sw;if(r==null||a==null){{m.bl.textContent='';return}}
const on=last&&w?w.on:s.bs[i]===1;
m.bl.innerHTML=(last?'':MD(s.t[i])+' · ')+'Breadth <b>'+r.toFixed(0)+'%</b> rising, avg '+a.toFixed(0)+'%'+(u==null?'':' · '+u.toFixed(0)+'% in uptrend')
+' · <span class="'+(on?'up':'dn')+'">'+(on?'▲ upswing':'▼ fading')+(last&&w?' since '+MD(w.since):'')+'</span>'}}
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
const runs=[];s.t.forEach((t,i)=>{{if(s.bs[i]==null)return;const on=s.bs[i]===1,r=runs[runs.length-1];
if(r&&r[2]===on&&r[3]===i-1){{r[1]=t;r[3]=i}}else runs.push([t,t,on,i])}});m.st.band.set(runs);
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
tip.innerHTML='<b>'+R.n+'</b> · '+d+'<br>'+v.toFixed(0)+'% rising (10 EMA over the 20), avg '+a.toFixed(0)+'%'
+(u==null?'':'<br>'+u.toFixed(0)+'% in your uptrend')+'<br><span class="'+(R.s[i]?'up':'dn')+'">'+(R.s[i]?'▲ upswing':'▼ fading')+'</span>';
c.children[i].classList.add('cur');tip.hidden=false;const h=hm.getBoundingClientRect();
tip.style.left=Math.max(0,Math.min(e.clientX-h.left+12,h.width-tip.offsetWidth))+'px';tip.style.top=(r.bottom-h.top+6)+'px'}}
hm.querySelectorAll('.hmc').forEach(c=>{{c.addEventListener('pointermove',show);c.addEventListener('pointerdown',show);
c.addEventListener('pointerleave',e=>{{if(e.pointerType==='mouse')off()}})}});
document.addEventListener('pointerdown',e=>{{if(!e.target.closest('.hmc'))off()}})}})();
const rows=[...document.querySelectorAll('#t tbody tr')];let fSet='setups',fSec=null;
const chip=document.getElementById('secf');
function apply(){{rows.forEach(r=>{{const st=r.dataset.setup;const okS=fSet==='all'||(fSet==='setups'?st!=='Uptrend':st===fSet);
r.style.display=okS&&(!fSec||r.dataset.sector===fSec)?'':'none'}});chip.hidden=!fSec;chip.textContent=(fSec||'')+'  ✕';
document.querySelectorAll('#s tbody tr').forEach(r=>r.classList.toggle('sel',r.dataset.sector===fSec))}}
document.querySelectorAll('.bar:not(.tf):not(.iv):not(.pk) button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar:not(.tf):not(.iv):not(.pk) button').forEach(x=>x.classList.remove('on'));b.classList.add('on');fSet=b.dataset.f;apply()}});
document.querySelectorAll('#s tbody tr').forEach(r=>r.onclick=()=>{{fSec=fSec===r.dataset.sector?null:r.dataset.sector;apply();document.getElementById('t').scrollIntoView({{behavior:'smooth'}})}});
chip.onclick=()=>{{fSec=null;apply()}};
function sortable(id){{const tb=document.querySelector('#'+id+' tbody');document.querySelectorAll('#'+id+' th').forEach((h,i)=>h.onclick=()=>{{const d=h.dataset.d=h.dataset.d==='1'?-1:1;
[...tb.rows].sort((a,b)=>{{const x=a.cells[i].dataset.v??a.cells[i].textContent,y=b.cells[i].dataset.v??b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);return (isNaN(nx)||isNaN(ny)?String(x).localeCompare(String(y)):nx-ny)*d}}).forEach(r=>tb.appendChild(r))}})}}
sortable('t');sortable('s');apply();
document.querySelectorAll('.bar.pk button').forEach(b=>b.onclick=()=>{{setOn('.bar.pk',b.dataset.pk,'pk');
document.querySelectorAll('.pkl').forEach(d=>d.hidden=d.dataset.pk!==b.dataset.pk);try{{localStorage.setItem('pk',b.dataset.pk)}}catch(e){{}}}});
try{{const k=localStorage.getItem('pk'),b=k&&document.querySelector('.bar.pk button[data-pk="'+k+'"]');if(b)b.click()}}catch(e){{}}
['pk-nu','pk-bo','pk-ai','ov-m'].forEach(id=>{{if(document.getElementById(id))sortable(id)}});
// ---- ticker chart pop-up (TradingView widget: 4H/D/W/M, indicators preloaded, more via its Indicators menu)
const cm=document.getElementById('cm');let cmSym=null,cmIv='D',tvLoading=null;
const tvSym=t=>t.replace(/-/g,'.');
function tvLib(){{return tvLoading||(tvLoading=new Promise((ok,no)=>{{const s=document.createElement('script');s.src='https://s3.tradingview.com/tv.js';s.onload=ok;s.onerror=no;document.head.appendChild(s)}}))}}
function tvDraw(){{document.getElementById('cmw').innerHTML='<div id="cmc"></div>';
const dark=matchMedia('(prefers-color-scheme: dark)').matches;
tvLib().then(()=>new TradingView.widget({{container_id:'cmc',autosize:true,symbol:tvSym(cmSym),interval:cmIv,timezone:'America/Chicago',
theme:dark?'dark':'light',style:'1',locale:'en',allow_symbol_change:true,hide_side_toolbar:false,withdateranges:true,details:true,
studies:['RSI@tv-basicstudies','MACD@tv-basicstudies','BB@tv-basicstudies']}}))
.catch(()=>{{document.getElementById('cmw').innerHTML='<div class="hint" style="padding:16px">Chart could not load. Use “Open on TradingView” above.</div>'}})}}
function openChart(t){{cmSym=t;document.getElementById('cmt').textContent=t;
document.getElementById('cml').href='https://www.tradingview.com/chart/?symbol='+encodeURIComponent(tvSym(t));
cm.hidden=false;document.body.style.overflow='hidden';draw()}}
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
(dataCache[sym]||(dataCache[sym]=fetch('data/'+encodeURIComponent(sym)+'.json').then(r=>{{if(!r.ok)throw 0;return r.json()}}))).then(D=>{{
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
<script>{paper_js}</script></body></html>"""

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
    secb = sector_breadth(frames, df, sectors)
    bh = {}
    try:
        bh = breadth_history(frames, sectors, sp500)
    except Exception as e:                 # extras; never block the scan
        print("  breadth history failed:", e)
    df["has_setup"] = df.setup.notna()
    df["setup"] = df.setup.fillna("Uptrend")
    picks = df[df.has_setup | df.core].sort_values(["has_setup", "score"], ascending=False).reset_index(drop=True)
    print(f"{int(df.core.sum())} of {len(df)} liquid stocks in uptrend; {int(picks.has_setup.sum())} setups ({(picks.setup == 'Momentum').sum()} momentum, {(picks.setup == 'Pullback').sum()} pullback)")

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
        lists, state = pick_lists(frames, sectors, subs, spy, prev, a.demo, step=live_at is None)
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
        ov = ovtlyr_plan(frames, sectors, etf_frames["SPY"], qqq, None if a.demo else next_earnings)
        ov["live_at"] = live_at
        if live_at is None:                # paper.py's OVTLYR account trades the next morning on closing prices only
            (out / f"ovtlyr_{asof}.json").write_text(json.dumps(ov, indent=1), encoding="utf-8")
        f = ov["funnel"]
        print(f"  market {'on' if ov['market']['ok'] else 'off'}, {sum(v['ok'] for v in ov['sectors'].values())} sectors pass, "
              f"{f['setups']} Plan M setups (of {f['signal']} buy signals), "
              + ", ".join(f"{k} {'set up' if e['ok'] else 'not set up'}" for k, e in ov["etf"].items()))
    except Exception as e:                 # never block the scan on it
        import traceback
        traceback.print_exc()
        print("  OVTLYR plan failed:", e)
    listed = [r["ticker"] for k in ("nu", "bo", "ai") for r in (lists or {}).get(k, {}).get("rows", [])]
    listed += [s["ticker"] for s in (ov or {}).get("setups", [])]
    chart_tks = list(dict.fromkeys(list(picks.ticker) + listed + list(SECTOR_ETF.values())))
    print(f"Building trend charts for {len(chart_tks)} tickers...")
    try:
        print(f"  wrote {write_stock_charts(chart_tks, out, a.demo, frames)} chart files")
    except Exception as e:                 # extras; never block the scan
        print("  stock charts failed:", e)
    html = render(picks, breadth, secb, df, asof, a.demo, charts, lists, earn, calls, live_at, ov, bh)
    (out / "latest.html").write_text(html, encoding="utf-8")
    (out / f"screener_{asof}.html").write_text(html, encoding="utf-8")
    picks.drop(columns=["opt"]).to_csv(out / f"screener_{asof}.csv", index=False)
    secb.round(1).to_csv(out / f"sectors_{asof}.csv", index=False)
    print(f"Done. Open {out / 'latest.html'}")


if __name__ == "__main__":
    main()
