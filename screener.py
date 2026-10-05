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
    # order blocks on the charts; research/ob_backtest.py tested all of these on 1,000 stocks over 10 years
    OB_TYPE="strong",        # classic, strong (best in the test), bos, fvg, volume or lux
    OB_ENTRY="top",          # box runs from the candle's far side to: "top" (whole candle, best), "body" or "mid" (50%)
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
    sectors = dict(zip(sp["Symbol"].str.replace(".", "-", regex=False), sp["GICS Sector"]))
    syms = set(sectors)
    for t in tables("https://en.wikipedia.org/wiki/Nasdaq-100"):
        col = next((c for c in ("Ticker", "Symbol") if c in t.columns), None)
        if col and len(t) > 50:
            t[col] = t[col].astype(str).str.replace(".", "-", regex=False)
            syms |= set(t[col])
            scol = next((c for c in t.columns if "Sector" in str(c) or "Industry" in str(c)), None)
            if scol:
                for tk, sec in zip(t[col], t[scol].astype(str)):
                    sectors.setdefault(tk, ICB_TO_GICS.get(sec, sec))
            break
    return sorted(syms), sectors


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
STOCK_BARS = {"4H": 300, "D": 260, "W": 156, "M": 180}   # ~5 months, 1 year, 3 years, 15 years


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


def write_stock_charts(tickers, out, demo=False):
    """One JSON per ticker (4H / D / W / M), loaded by the chart pop-up on click."""
    if demo:
        fr = demo_frames(n=len(tickers), days=2600)
        daily = dict(zip(tickers, fr.values()))
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
        cross=crossed, days_since_cross=days_since_cross,
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
        o, why = _pick_from_chain(tk, S, exp, dte)
        if o:
            return o, why
    return None, why


def _pick_from_chain(tk, S, exp, dte):
    T = dte / 365
    ch = tk.option_chain(exp).calls
    oi_known = ch.openInterest.fillna(0).gt(0).any()   # Yahoo often zeroes OI on weekends
    if oi_known:
        ch = ch[ch.openInterest.fillna(0) >= CFG["MIN_OI"]].copy()
    if ch.empty:
        return None, f"{exp}: no strikes with OI >= {CFG['MIN_OI']}"
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
                     "spr": o.spr, "oi": int(o.openInterest) if oi_known else None, "exp": exp, "dte": dte, "quote": quote})
    if not rows:
        return None, f"{exp}: {quote} quotes but none usable"
    return min(rows, key=lambda r: abs(r["delta"] - CFG["TARGET_DELTA"])), quote

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


def render(picks, breadth, secb, df, asof, demo, charts=None):
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
    cards = (f'<div class="card"><div class="lbl">In uptrend (EMA10 &gt; 20, price &gt; EMA50 &amp; 150)</div>'
             f'<div class="val {"up" if up_pct > 50 else "dn"}">{up_n} / {liq_n}</div>'
             f'<div class="sub">{up_pct:.0f}% of stocks averaging 1M+ shares/day</div></div>') + cards

    def bar(v, good=50):
        c = "var(--up)" if v >= good else "var(--dn)"
        return f'<div class="bar2"><i style="width:{max(v, 0):.0f}%;background:{c}"></i></div>'
    def delta(now, then):
        d = now - then
        return f'<span class="{"up" if d > 0 else "dn" if d < 0 else ""}">{d:+.0f}</span>'
    srows = []
    for _, s_ in secb.iterrows():
        srows.append(
            f'<tr data-sector="{s_.sector}"><td><b>{s_.sector}</b></td>'
            f'<td data-v="{s_.up_pct}"><b>{s_.uptrend}</b> / {s_.liquid} <span class="mut">({s_.up_pct:.0f}%)</span>{bar(s_.up_pct)}</td>'
            f'<td data-v="{s_.momentum}">{s_.momentum}</td><td data-v="{s_.pullback}">{s_.pullback}</td>'
            f'<td data-v="{s_.pct20}">{s_.pct20:.0f}% {delta(s_.pct20, s_.pct20_5d)}</td>'
            f'<td data-v="{s_.pct50}">{s_.pct50:.0f}% {delta(s_.pct50, s_.pct50_5d)}</td>'
            f'<td data-v="{s_.pct200}">{s_.pct200:.0f}% {delta(s_.pct200, s_.pct200_5d)}</td>'
            f'<td data-v="{s_.adv - s_.dec}">{s_.adv} / {s_.dec}</td>'
            f'<td data-v="{s_.nh - s_.nl}">{s_.nh} / {s_.nl}</td></tr>')
    sector_html = ('<h2>Sector breadth</h2><div class="hint">Click a sector to filter the stock list. '
                   '± is the change vs 5 trading days ago.</div><div class="wrap"><table id="s"><thead><tr>'
                   '<th>Sector</th><th>In uptrend</th><th>Momentum</th><th>Pullback</th><th>% &gt; 20d</th>'
                   '<th>% &gt; 50d</th><th>% &gt; 200d</th><th>Adv / Dec</th><th>52w Hi / Lo</th></tr></thead>'
                   f'<tbody>{"".join(srows)}</tbody></table></div>')

    order = ["S&P 500"] + [n for n in secb.sector if n != "S&P 500"]
    order += [n for n in SECTOR_ETF if n not in order]
    charts = {n: charts[n] for n in order if charts and n in charts}
    if charts:
        chart_html = ('<h2>Sector charts</h2><div class="hint">Sector SPDR ETFs with EMA 10 (orange), 20 (blue) and 50 (purple). '
                      'Daily shows ~6 months, weekly ~2 years, monthly ~10 years.</div>'
                      '<div class="bar tf"><button class="on" data-tf="D">Daily</button><button data-tf="W">Weekly</button>'
                      '<button data-tf="M">Monthly</button></div><div class="charts">'
                      + "".join(f'<div class="ch" data-sector="{n}"><div class="chh"><b>{n}</b> <span class="tk mut" data-tk="{c["etf"]}">{c["etf"]}</span>'
                                f'<span class="chg"></span></div><div class="cv"></div></div>' for n, c in charts.items())
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
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swing Screener {asof}</title><style>
:root{{--bg:#fff;--fg:#1b1b1f;--mut:#6b6b76;--card:#f4f4f7;--line:#e2e2e8;--up:#12803c;--dn:#c2271d;--acc:#2a5bd7}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111114;--fg:#ececf1;--mut:#9a9aa6;--card:#1b1b20;--line:#2c2c34;--up:#3ecf70;--dn:#ff6b61;--acc:#7aa2ff}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px -apple-system,system-ui,sans-serif}}
h1{{font-size:20px;margin:0 0 2px}} .meta{{color:var(--mut);margin-bottom:14px}}
.reg{{display:inline-block;padding:3px 10px;border-radius:99px;font-weight:600;margin-left:8px}}
.reg.good{{background:color-mix(in srgb,var(--up) 20%,transparent);color:var(--up)}}.reg.bad{{background:color-mix(in srgb,var(--dn) 20%,transparent);color:var(--dn)}}.reg.mid{{background:var(--card);color:var(--mut)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:18px}}
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
.charts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:10px;margin-top:10px}}
.ch{{background:var(--card);border-radius:10px;padding:8px 10px}}.chh{{font-size:13px;margin-bottom:4px}}.chg{{float:right;font-weight:600}}.cv{{height:240px}}.bar.tf{{margin-top:8px}}
.tk{{cursor:pointer;color:var(--acc);text-decoration:underline dotted;text-underline-offset:3px}}
#cm{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:50;display:flex;align-items:center;justify-content:center}}#cm[hidden]{{display:none}}
#cm .box{{background:var(--bg);border-radius:12px;width:min(1200px,96vw);height:min(820px,92vh);display:flex;flex-direction:column;overflow:hidden}}
#cm .top{{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--line);flex-wrap:wrap}}#cm .top b{{font-size:16px}}
#cm .top .sp{{flex:1}}#cm .top a{{color:var(--acc);font-size:12px}}#cm .x{{background:none;border:0;color:var(--fg);font-size:22px;cursor:pointer;padding:0 4px}}
#cmlg{{padding:4px 12px 0}}#cmlg .up,#cmlg .dn{{font-weight:600}}#cmw{{flex:1;min-height:0}}.trl{{position:absolute;inset:0 0 26px 0;pointer-events:none;z-index:2}}.trl i{{position:absolute;top:0;bottom:0;opacity:.13}}#cmw>div{{height:100%}}
@media(max-width:600px){{#cm .box{{width:100vw;height:100dvh;border-radius:0}}}}</style></head><body>
{banner}<h1>Swing Screener<span class="reg {rcls}">{reg}</span></h1>
<div class="meta">Data as of {asof} · {n_m} momentum · {n_p} pullback · stocks averaging 1M+ shares/day · S&amp;P 500 + Nasdaq 100</div>
<div class="cards">{cards}</div>
{sector_html}
{chart_html}
<h2>Stocks <span id="secf" class="chip" hidden></span></h2>
<div class="bar"><button class="on" data-f="setups">Setups</button><button data-f="Momentum">Momentum</button><button data-f="Pullback">Pullback</button><button data-f="all">All uptrend</button></div>
<div class="wrap"><table id="t"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<div class="note">Green bar = full stack (EMA10 &gt; 20 &gt; 50 &gt; {CFG["LONG_MA_TYPE"]}150 &gt; {CFG["LONG_MA_TYPE"]}200). Score = trend structure (70%) + setup quality (30 pts).
Uptrend = EMA10 &gt; EMA20, price &gt; EMA50 and price &gt; {CFG["LONG_MA_TYPE"]}150. Momentum requires an uptrend, RSI 55–80 and a 20-day breakout or within 3% of the 52w high; pullbacks require price &gt; EMA50, EMA20 &gt; EMA50, RSI ≤ 50, 3%+ off the 15-day high and back near/below the EMA20 (EMA10 may dip). Options shown for top {CFG["OPT_TOP_N"]} picks:
call nearest {CFG["TARGET_DELTA"]} delta, ~{CFG["TARGET_DTE"]} DTE, OI ≥ {CFG["MIN_OI"]}, spread ≤ {CFG["MAX_SPREAD_PCT"]:.0f}%. Greeks are Black-Scholes from Yahoo's IV (Yahoo IV can be unreliable; confirm in your broker). When Yahoo has no live bid/ask (after hours, weekends) the last trade is shown and IV is solved from it. Click any ticker for a 4H / daily / weekly / monthly chart: the Trend view shades uptrends green (EMA10 &gt; EMA20, price &gt; EMA50 and &gt; 150 MA) and downtrends red (all three reversed), with arrows where each trend starts; the Indicators view shows RSI, MACD and Bollinger Bands (the free chart allows about 3 studies at once; swap them from its Indicators menu).
Order blocks (Trend view, daily chart): blue boxes are bullish blocks, the last down candle before a rise of 2+ ATR within 3 bars; orange boxes are bearish blocks, the last up candle before a drop of 2+ ATR. A box ends where price first came back to it; bright boxes haven't been revisited yet. This was the best of 18 versions in a 10-year test on 1,000 stocks, but as support it did no better than random price zones, while bearish blocks held as resistance slightly better than random. Not financial advice.</div>
<div id="cm" hidden><div class="box"><div class="top"><b id="cmt"></b>
<div class="bar iv src"><button class="on" data-src="trend">Trend</button><button data-src="tv">Indicators</button></div>
<div class="bar iv tfb"><button data-iv="240">4H</button><button class="on" data-iv="D">Daily</button><button data-iv="W">Weekly</button><button data-iv="M">Monthly</button></div>
<div class="bar iv obb"><button class="on" id="obt" title="Show or hide order blocks">Order blocks</button></div>
<span class="sp"></span><a id="cml" target="_blank" rel="noopener">Open on TradingView ↗</a><button class="x" aria-label="Close">×</button></div>
<div id="cmlg" class="hint"></div><div id="cmw"><div id="cmc"></div></div></div></div>
<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
const CH={chart_json};
(function(){{const boxes=[...document.querySelectorAll('.ch')];if(!boxes.length)return;
if(!window.LightweightCharts){{document.getElementById('chfail').hidden=false;return}}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim();
const UP=V('--up'),DN=V('--dn');let tf='D';
const made=boxes.map(b=>{{const d=CH[b.dataset.sector];
const c=LightweightCharts.createChart(b.querySelector('.cv'),{{autoSize:true,localization:{{locale:'en-US'}},layout:{{background:{{color:'transparent'}},textColor:V('--mut'),fontSize:11}},
grid:{{vertLines:{{visible:false}},horzLines:{{color:V('--line')}}}},rightPriceScale:{{borderVisible:false}},timeScale:{{borderVisible:false}},handleScroll:false,handleScale:false}});
const k=c.addCandlestickSeries({{upColor:UP,downColor:DN,wickUpColor:UP,wickDownColor:DN,borderVisible:false}});
const vol=c.addHistogramSeries({{priceScaleId:'v',priceFormat:{{type:'volume'}},lastValueVisible:false,priceLineVisible:false}});
c.priceScale('v').applyOptions({{scaleMargins:{{top:0.82,bottom:0}}}});
const ln=[['e10','#e8a33d'],['e20',V('--acc')],['e50','#a259d9']].map(([key,col])=>[key,c.addLineSeries({{color:col,lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false}})]);
return {{b,d,c,k,vol,ln}}}});
function draw(){{made.forEach(m=>{{const s=m.d[tf];if(!s)return;
m.k.setData(s.t.map((t,i)=>({{time:t,open:s.o[i],high:s.h[i],low:s.l[i],close:s.c[i]}})));
m.vol.setData(s.t.map((t,i)=>({{time:t,value:s.v[i],color:(s.c[i]>=s.o[i]?UP:DN)+'55'}})));
m.ln.forEach(([key,ser])=>ser.setData(s.t.map((t,i)=>({{time:t,value:s[key][i]}}))));
m.c.timeScale().fitContent();
const n=s.c.length,p=(s.c[n-1]/s.c[n-2]-1)*100,e=m.b.querySelector('.chg');
e.textContent=s.c[n-1].toFixed(2)+'  '+(p>=0?'+':'')+p.toFixed(1)+'% '+({{D:'1d',W:'1w',M:'1m'}})[tf];e.className='chg '+(p>=0?'up':'dn')}})}}
document.querySelectorAll('.bar.tf button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar.tf button').forEach(x=>x.classList.remove('on'));b.classList.add('on');tf=b.dataset.tf;draw()}});
draw()}})();
const rows=[...document.querySelectorAll('#t tbody tr')];let fSet='setups',fSec=null;
const chip=document.getElementById('secf');
function apply(){{rows.forEach(r=>{{const st=r.dataset.setup;const okS=fSet==='all'||(fSet==='setups'?st!=='Uptrend':st===fSet);
r.style.display=okS&&(!fSec||r.dataset.sector===fSec)?'':'none'}});chip.hidden=!fSec;chip.textContent=(fSec||'')+'  ✕';
document.querySelectorAll('#s tbody tr').forEach(r=>r.classList.toggle('sel',r.dataset.sector===fSec))}}
document.querySelectorAll('.bar:not(.tf):not(.iv) button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.bar:not(.tf):not(.iv) button').forEach(x=>x.classList.remove('on'));b.classList.add('on');fSet=b.dataset.f;apply()}});
document.querySelectorAll('#s tbody tr').forEach(r=>r.onclick=()=>{{fSec=fSec===r.dataset.sector?null:r.dataset.sector;apply();document.getElementById('t').scrollIntoView({{behavior:'smooth'}})}});
chip.onclick=()=>{{fSec=null;apply()}};
function sortable(id){{const tb=document.querySelector('#'+id+' tbody');document.querySelectorAll('#'+id+' th').forEach((h,i)=>h.onclick=()=>{{const d=h.dataset.d=h.dataset.d==='1'?-1:1;
[...tb.rows].sort((a,b)=>{{const x=a.cells[i].dataset.v??a.cells[i].textContent,y=b.cells[i].dataset.v??b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);return (isNaN(nx)||isNaN(ny)?String(x).localeCompare(String(y)):nx-ny)*d}}).forEach(r=>tb.appendChild(r))}})}}
sortable('t');sortable('s');apply();
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
let cmSrc='trend',cmOB=true;const dataCache={{}};
function draw(){{cmSrc==='trend'?trendDraw():tvDraw();document.getElementById('cmlg').hidden=cmSrc!=='trend';document.querySelector('.obb').hidden=cmSrc!=='trend'||cmIv!=='D'}}
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
grid:{{vertLines:{{visible:false}},horzLines:{{color:V('--line')}}}},rightPriceScale:{{borderVisible:false}},timeScale:{{borderVisible:false,timeVisible:tf==='4H'}}}});
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
k.setMarkers(mk);if(cmOB&&tf==='D'&&s.ob)k.attachPrimitive(obPrim(s.ob));c.timeScale().fitContent();
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
cm.querySelector('.x').onclick=closeChart;cm.onclick=e=>{{if(e.target===cm)closeChart()}};
document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&!cm.hidden)closeChart()}});
</script></body></html>"""

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
    else:
        tickers, sectors = get_universe()
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
    print(f"  charts for {len(charts)} of {len(SECTOR_ETF)} sectors")

    out = Path(a.out); out.mkdir(exist_ok=True)
    chart_tks = list(picks.ticker) + list(SECTOR_ETF.values())
    print(f"Building trend charts for {len(chart_tks)} tickers...")
    try:
        print(f"  wrote {write_stock_charts(chart_tks, out, a.demo)} chart files")
    except Exception as e:                 # extras; never block the scan
        print("  stock charts failed:", e)
    html = render(picks, breadth, secb, df, asof, a.demo, charts)
    (out / "latest.html").write_text(html, encoding="utf-8")
    (out / f"screener_{asof}.html").write_text(html, encoding="utf-8")
    picks.drop(columns=["opt"]).to_csv(out / f"screener_{asof}.csv", index=False)
    secb.round(1).to_csv(out / f"sectors_{asof}.csv", index=False)
    print(f"Done. Open {out / 'latest.html'}")


if __name__ == "__main__":
    main()
