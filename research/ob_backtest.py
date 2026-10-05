#!/usr/bin/env python3
"""
Order block backtest: which way of finding order blocks works best?

An order block is the last opposite-colored candle before a strong move. Traders caught
on the wrong side of that move often get out when price comes back to it, so the zone
tends to act as support (bullish block) or resistance (bearish block). This script tests
several common definitions on 1,000 US stocks (S&P 500, S&P 400 and some S&P 600) over
10 years of daily bars, and the same stocks on weekly bars, against random zones.

Trade rule, the same for every variant: wait for the first return to the zone, buy at the
entry level (sell short for bearish blocks), stop 0.1 ATR beyond the far side of the zone
(at least 0.25 ATR away), target 2x the risk, exit after 20 bars if neither is hit.
Inside a bar we assume the extreme nearer the open came first (TradingView's rule), and
orders that gap are filled at the open.

Runs on GitHub Actions (the "Order block backtest" workflow) because Yahoo and Wikipedia
are only reachable there:
    python research/ob_backtest.py --stocks 1000 --out ob_results
    python research/ob_backtest.py --demo --out /tmp/ob     # random-walk data: no variant should show an edge
"""
import argparse, functools, io, json, sys, time, zlib
from pathlib import Path
import numpy as np
import pandas as pd

ATR_N = 14
RANDOM_SHARE = 0.10              # the baseline samples 10% of all candles
EXPIRY = {"D": 250, "W": 100}    # the zone must be revisited within this many bars
HOLD = 20                        # time exit after 20 bars
STOP_BUF, MIN_RISK = 0.10, 0.25  # in ATRs
TARGETS = (1, 2, 3)              # results are kept for 1R, 2R and 3R targets; 2R is the headline

VARIANTS = {
    "classic": "Classic: last opposite candle before a move of 1 ATR or more within 3 bars",
    "strong": "Strong move: same, but the move must be 2 ATR or more",
    "bos": "Break of structure: classic, and the move also closes past the last swing high/low",
    "fvg": "Break of structure + fair value gap: the move also leaves a price gap (strict ICT)",
    "volume": "Volume surge: classic, and the move comes on 1.5x the 20-day average volume",
    "lux": "LuxAlgo style: the biggest volume of 11 bars at a swing low/high",
    "random": "Baseline: a random candle that price later moved 1 ATR away from",
}
STYLES = {"top": "near edge (full wick range)", "body": "candle body", "mid": "50% of the candle"}
COLS = ["month", "trend", "r1", "r2", "r3", "held", "scratch", "age", "big", "stock"]
GROUPS = (("S&P 500", "List_of_S%26P_500_companies"), ("S&P 400", "List_of_S%26P_400_companies"),
          ("S&P 600", "List_of_S%26P_600_companies"))


# ---------------------------------------------------------------- universe and data
def wiki_symbols(page):
    import requests
    html = requests.get(f"https://en.wikipedia.org/wiki/{page}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    for t in pd.read_html(io.StringIO(html)):
        col = next((c for c in t.columns if any(w in str(c).lower() for w in ("symbol", "ticker"))), None)
        if col is not None and len(t) > 300:
            return [s.strip().replace(".", "-") for s in t[col].astype(str) if s.strip() and s != "nan"]
    return []


def universe(seed=1):
    """S&P 500 first, then S&P 400, then the S&P 600 in random order to fill up."""
    order, seen = [], set()
    for name, page in GROUPS:
        try:
            syms = wiki_symbols(page)
        except Exception as e:
            print(f"  could not read the {name} list: {e}")
            syms = []
        print(f"  {name}: {len(syms)} tickers", flush=True)
        if name == "S&P 600":
            syms = list(np.random.default_rng(seed).permutation(syms))
        for s in syms:
            if s not in seen:
                seen.add(s)
                order.append((s, name))
    return order


def download(tickers, size=100):
    import yfinance as yf
    frames = {}
    for i in range(0, len(tickers), size):
        chunk = tickers[i:i + size]
        print(f"  downloading {i + 1}-{i + len(chunk)} of {len(tickers)}", flush=True)
        try:
            df = yf.download(chunk, period="10y", interval="1d", auto_adjust=True,
                             group_by="ticker", threads=True, progress=False)
        except Exception as e:
            print("  batch failed:", e)
            continue
        if df.empty:
            continue
        top = set(df.columns.get_level_values(0))
        for t in chunk:
            if t in top:
                d = clean(df[t])
                if len(d) >= 500:
                    frames[t] = d
        time.sleep(1)
    return frames


def clean(d):
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float).dropna(subset=["Open", "High", "Low", "Close"])
    d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1)].copy()
    d["High"] = d[["Open", "High", "Low", "Close"]].max(axis=1)     # Yahoo's adjusted opens can sit outside the range
    d["Low"] = d[["Open", "High", "Low", "Close"]].min(axis=1)
    d["Volume"] = d["Volume"].fillna(0)
    return d


def demo_frames(n=100, days=2520, seed=3):
    """Driftless random walks (390 one-minute steps a day) with real candles: every variant
    should come out near 0R here, so anything clearly above 0 would mean a bug that peeks ahead."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-10-02", periods=days)
    frames = {}
    for k in range(n):
        path = np.cumsum(rng.normal(0, 20 / np.sqrt(390), (days, 390)), axis=1)
        c = 5000 + np.cumsum(path[:, -1] + rng.normal(0, 5, days))
        o = c - path[:, -1]
        frames[f"DEMO{k:02d}"] = pd.DataFrame({
            "Open": o, "High": o + np.maximum(path.max(1), 0), "Low": o + np.minimum(path.min(1), 0), "Close": c,
            "Volume": rng.lognormal(14, 0.5, days)}, index=idx)
    return frames


def weekly(d):
    g = d.groupby(d.index.to_period("W"))
    w = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(),
                      "Close": g.Close.last(), "Volume": g.Volume.sum()})
    w.index = [grp.index[0] for _, grp in g]
    return w


# ---------------------------------------------------------------- building blocks
def fwd(a, k):
    """a[i + k] lined up with bar i (NaN past the end)."""
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[:len(a) - k] = a[k:]
    return out


def atr(H, L, C, n=ATR_N):
    pc = np.concatenate([[np.nan], C[:-1]])
    tr = np.fmax(H - L, np.fmax(np.abs(H - pc), np.abs(L - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def trend(C):
    """Your rule: up = EMA10 > EMA20, close > EMA50 and close > 150 MA (1); down is the mirror (-1)."""
    s = pd.Series(C)
    e10, e20, e50 = (s.ewm(span=k, adjust=False).mean() for k in (10, 20, 50))
    m150 = s.rolling(150).mean()
    up = (e10 > e20) & (s > e50) & (s > m150)
    dn = (e10 < e20) & (s < e50) & (s < m150)
    return (up.astype(int) - dn.astype(int)).to_numpy()


def swing_high_asof(H, p=3):
    """Level of the latest swing high (highest of 7 bars) that was already confirmed at each bar."""
    n = len(H)
    pad = np.concatenate([np.full(p, -np.inf), H, np.full(p, -np.inf)])
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * p + 1).max(axis=1)
    ks = np.flatnonzero(H >= win)
    conf = ks + p
    keep = conf < n
    lvl = np.full(n, np.nan)
    lvl[conf[keep]] = H[ks[keep]]
    return pd.Series(lvl).ffill().to_numpy()


def lux_masks(H, L, V, p=5):
    """LuxAlgo Order Block Detector: a volume pivot (highest volume of 2p+1 bars) while the
    structure state says bullish (a low that the next p bars stay above) or bearish."""
    n = len(V)
    pad = np.concatenate([np.full(p, -np.inf), V, np.full(p, -np.inf)])
    vwin = np.lib.stride_tricks.sliding_window_view(pad, 2 * p + 1).max(axis=1)
    piv = (V >= vwin) & (V > 0)
    piv[max(0, n - p):] = False
    hn = functools.reduce(np.fmax, [fwd(H, k) for k in range(1, p + 1)])
    ln = functools.reduce(np.fmin, [fwd(L, k) for k in range(1, p + 1)])
    c_hi, c_lo = H > hn, L < ln
    state = np.zeros(n, np.int8)
    s = 0
    for i in range(n):
        if c_hi[i]:
            s = 0
        elif c_lo[i]:
            s = 1
        state[i] = s
    return piv & (state == 1), piv & (state == 0)


def detect(o, h, l, c, v, A, avgv, sh, kind, rng, lux):
    """Bullish zones as (origin bar, activation bar). Bearish zones use the same code on the
    mirrored series (prices times -1), so 'down candle' becomes 'up candle' and so on."""
    n = len(c)
    if kind == "lux":
        ii = np.flatnonzero(lux)
        return ii, ii + 5
    if kind == "random":
        ii = np.flatnonzero(rng.random(n) < RANDOM_SHARE)
        keep, acts = [], []
        for i in ii:
            hit = np.flatnonzero(c[i + 1:i + 61] >= h[i] + A[i])
            if hit.size:
                keep.append(i)
                acts.append(i + 1 + hit[0])
        return np.array(keep, int), np.array(acts, int)
    base = (c < o) & (fwd(c, 1) > fwd(o, 1))              # down candle, next one closes up
    k = 2.0 if kind == "strong" else 1.0
    best = np.fmax.accumulate(np.vstack([fwd(c, 1), fwd(c, 2), fwd(c, 3)]), axis=0)   # best close by bar i+1, i+2, i+3
    cond = best >= h + k * A
    if kind in ("bos", "fvg"):
        cond &= best > sh
    if kind == "fvg":
        g1 = fwd(l, 2) > h                                  # gap between bar i and bar i+2
        g2 = g1 | (fwd(l, 3) > fwd(h, 1))                   # or between bar i+1 and bar i+3
        cond &= np.vstack([np.zeros(n, bool), g1, g2])
    if kind == "volume":
        vmax = np.fmax.accumulate(np.vstack([fwd(v, 1), fwd(v, 2), fwd(v, 3)]), axis=0)
        cond &= vmax >= 1.5 * avgv
    cond &= base
    first = np.where(cond.any(axis=0), cond.argmax(axis=0), -1)
    ii = np.flatnonzero(first >= 0)
    return ii, ii + first[ii] + 1


def exit_price(o, h, l, c, t, e, p, fill, stop, tgt):
    """Where one trade ends. Inside a bar we follow TradingView's rule: the extreme nearer the
    open comes first. Orders that gap are filled at the open."""
    hf = (h[t] - o[t]) < (o[t] - l[t])
    if o[t] <= p:                                   # opened below the entry: filled at the open
        first, second = (("t", "s") if hf else ("s", "t"))
    else:                                           # traded down into the entry during the bar
        first, second = ("s", "close") if hf else ("s", "t")
    for step in (first, second):
        if step == "s" and l[t] <= stop:
            return stop
        if step == "t" and h[t] >= tgt:
            return tgt
        if step == "close" and c[t] >= tgt:
            return tgt
    os_, hs, ls = o[t + 1:e], h[t + 1:e], l[t + 1:e]
    gs, gt = os_ <= stop, os_ >= tgt
    hit_s, hit_t = ls <= stop, hs >= tgt
    hf = (hs - os_) < (os_ - ls)
    out = np.where(gs, -1, np.where(gt, 1, np.where(hf, np.where(hit_t, 1, np.where(hit_s, -1, 0)),
                                                    np.where(hit_s, -1, np.where(hit_t, 1, 0)))))
    nz = np.flatnonzero(out)
    if not nz.size:
        return c[e - 1]                             # time exit at the close
    f = nz[0]
    if gs[f] or gt[f]:
        return os_[f]
    return tgt if out[f] == 1 else stop


def simulate(ii, aa, P, D, o, h, l, c, A, tside, months, expiry, tag):
    """First return to each zone -> one trade. Returns (zones that became active, trade rows)."""
    n = len(c)
    rows, active = [], 0
    for i, a, p, dz in zip(ii, aa, P, D):
        if a + 1 >= n or not c[a] > p:
            continue
        active += 1
        hit = np.flatnonzero(l[a + 1:a + 1 + expiry] <= p)
        if not hit.size:
            continue
        t = a + 1 + hit[0]
        stop = min(dz - STOP_BUF * A[i], p - MIN_RISK * A[i])
        r = p - stop
        fill = min(p, o[t])                         # a gap down fills the buy at the open
        scratch = 0.0
        if fill <= stop:
            scratch, res = 1.0, [0.0, 0.0, 0.0]     # gapped through the whole zone: in and out at the open
        else:
            e = min(n, t + 1 + HOLD)
            res = [(exit_price(o, h, l, c, t, e, p, fill, stop, p + k * r) - fill) / r for k in TARGETS]
        held = 0.0 if (c[t:t + 11] < dz).any() else 1.0    # no close through the far side within 10 bars
        rows.append((months[t], tside[t - 1], *res, held, scratch, t - a, *tag))
    return active, rows


def run_frame(d, tf, seed, tag):
    O, H, L, C, V = (d[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    A = atr(H, L, C)
    avgv = pd.Series(V).rolling(20).mean().to_numpy()
    tr = trend(C)
    months = np.asarray(d.index.year * 12 + d.index.month - 1)
    lux_bull, lux_bear = lux_masks(H, L, V)
    out = {}
    for side, sgn in (("bull", 1), ("bear", -1)):
        o, h, l, c = (O, H, L, C) if sgn == 1 else (-O, -L, -H, -C)
        sh = swing_high_asof(h)
        rng = np.random.default_rng(seed + (0 if sgn == 1 else 1))
        for kind in VARIANTS:
            ii, aa = detect(o, h, l, c, V, A, avgv, sh, kind, rng, lux_bull if sgn == 1 else lux_bear)
            for style in STYLES:
                P = h[ii] if style == "top" else np.maximum(o[ii], c[ii]) if style == "body" else (h[ii] + l[ii]) / 2
                out[(tf, side, kind, style)] = simulate(ii, aa, P, l[ii], o, h, l, c, A, tr * sgn, months,
                                                        EXPIRY[tf], tag)
    return out


# ---------------------------------------------------------------- statistics
def summarize(X, zones=None):
    if X is None or len(X) == 0:
        return dict(n=0)
    r2 = X[:, 3].astype(float)
    n, mean = len(r2), float(r2.mean())
    se = 0.0
    for col in (0, 9):          # trades in the same month, or in the same stock, move together: use the wider error
        _, inv = np.unique(X[:, col], return_inverse=True)
        se = max(se, float(np.sqrt((np.bincount(inv, weights=r2 - mean) ** 2).sum()) / n))
    pos, neg = r2[r2 > 0].sum(), -r2[r2 < 0].sum()
    s = dict(n=n, avg_r=mean, ci=1.96 * se, win=float((r2 > 0).mean()), r1=float(X[:, 2].mean()),
             r3=float(X[:, 4].mean()), held=float(X[:, 5].mean()), pf=float(pos / neg) if neg else None,
             days=float(np.median(X[:, 7])))
    if zones:
        s["zones"], s["fill"] = zones, n / zones
    return s


def edge(Xv, Xb, reps=2000, seed=0):
    """Variant minus random zones. The 95% range comes from resampling whole months and, separately,
    whole stocks, keeping the wider one, so one crash month or one wild stock can't fake an edge."""
    if not len(Xv) or not len(Xb):
        return None
    lo, hi = np.inf, -np.inf
    for col in (0, 9):
        gv, gb = Xv[:, col].astype(int), Xb[:, col].astype(int)
        keys = np.union1d(gv, gb)
        iv, ib, M = np.searchsorted(keys, gv), np.searchsorted(keys, gb), len(keys)
        sv, nv = np.bincount(iv, Xv[:, 3].astype(float), M), np.bincount(iv, minlength=M).astype(float)
        sb, nb = np.bincount(ib, Xb[:, 3].astype(float), M), np.bincount(ib, minlength=M).astype(float)
        W = np.random.default_rng(seed).multinomial(M, np.full(M, 1 / M), size=reps).astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            d = (W @ sv) / (W @ nv) - (W @ sb) / (W @ nb)
        a, b = np.nanpercentile(d, [2.5, 97.5])
        lo, hi = min(lo, a), max(hi, b)
    diff = Xv[:, 3].astype(float).mean() - Xb[:, 3].astype(float).mean()
    return dict(edge=float(diff), lo=float(lo), hi=float(hi))


def fmt(s):
    if not s or not s.get("n"):
        return "no trades"
    return f"{s['avg_r']:+.3f}R ±{s['ci']:.3f} · {s['win'] * 100:.0f}% win · {s['n']:,}"


def fmt_edge(e):
    return "n/a" if not e else f"{e['edge']:+.3f}R ({e['lo']:+.3f} to {e['hi']:+.3f})"


def name(kind):
    return VARIANTS[kind].split(":")[0]


def report(results, meta):
    res = {k: summarize(v["X"], v["zones"]) for k, v in results.items()}
    X = lambda *k: results[k]["X"] if k in results else np.zeros((0, len(COLS)))
    L = ["# Order block backtest", "",
         f"{meta['stocks']:,} stocks ({meta['groups']}), daily bars {meta['start']} to {meta['end']}, "
         f"plus the same stocks on weekly bars. Run {meta['run']}.", "",
         "Each order block gives one trade: the first time price comes back to the zone, buy at the entry level "
         "(short for bearish blocks), stop 0.1 ATR past the far side of the zone (at least 0.25 ATR away), "
         "target 2x the risk, exit after 20 bars otherwise. Results are the average per trade in R "
         "(1R = the amount risked), with a 95% range, the share of winning trades and the number of trades. "
         "\"Edge\" is the result minus random zones built and traded the same way.", ""]
    # winner on daily bars: best average of the bullish and bearish result, with enough trades on both sides
    rank = []
    for kind in VARIANTS:
        if kind == "random":
            continue
        for style in STYLES:
            b, s_ = res.get(("D", "bull", kind, style), {}), res.get(("D", "bear", kind, style), {})
            if b.get("n", 0) >= 500 and s_.get("n", 0) >= 500:
                eb = edge(X("D", "bull", kind, style), X("D", "bull", "random", style))
                es = edge(X("D", "bear", kind, style), X("D", "bear", "random", style))
                rank.append(dict(kind=kind, style=style, score=(b["avg_r"] + s_["avg_r"]) / 2,
                                 bull=b, bear=s_, edge_bull=eb, edge_bear=es))
    rank.sort(key=lambda r: -r["score"])
    meta["ranking"] = [{k: v for k, v in r.items()} for r in rank]
    if rank:
        w = rank[0]
        win = (w["kind"], w["style"])
        L += ["## Best variation (daily bars)", "",
              f"**{VARIANTS[win[0]]}**, entering at the **{STYLES[win[1]]}**.", "",
              f"- Bullish blocks (buy at support): {fmt(w['bull'])}; edge {fmt_edge(w['edge_bull'])}",
              f"- Bearish blocks (short at resistance): {fmt(w['bear'])}; edge {fmt_edge(w['edge_bear'])}", "",
              "## Ranking (daily bars, best average of bullish and bearish first)", "",
              "| # | Definition | Enter at | Bullish | Bearish | Edge bullish | Edge bearish |",
              "|---|---|---|---|---|---|---|"]
        for j, r in enumerate(rank, 1):
            L.append(f"| {j} | {name(r['kind'])} | {STYLES[r['style']]} | {r['bull']['avg_r']:+.3f}R "
                     f"({r['bull']['n']:,}) | {r['bear']['avg_r']:+.3f}R ({r['bear']['n']:,}) | "
                     f"{fmt_edge(r['edge_bull'])} | {fmt_edge(r['edge_bear'])} |")
        rb, rs = res.get(("D", "bull", "random", win[1]), {}), res.get(("D", "bear", "random", win[1]), {})
        L += [f"| | Random zones | {STYLES[win[1]]} | {rb.get('avg_r', 0):+.3f}R ({rb.get('n', 0):,}) | "
              f"{rs.get('avg_r', 0):+.3f}R ({rs.get('n', 0):,}) | | |", ""]
        L += ["## Detail for the best variation (daily bars)", "",
              "| Slice | Bullish | Bearish |", "|---|---|---|"]
        for label, f in meta["slices"]:
            cells = []
            for side in ("bull", "bear"):
                v = X("D", side, *win)
                cells.append(fmt(summarize(v[f(v)]) if len(v) else None))
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        cells = []
        for side in ("bull", "bear"):
            s_ = res[("D", side) + win]
            cells.append(f"{s_['r1']:+.3f} / {s_['avg_r']:+.3f} / {s_['r3']:+.3f}")
        L.append("| Target 1R / 2R / 3R | " + " | ".join(cells) + " |")
        cells = []
        for side in ("bull", "bear"):
            s_ = res[("D", side) + win]
            cells.append(f"{s_['held'] * 100:.0f}% held, {s_['fill'] * 100:.0f}% of zones revisited")
        L.append("| Zone held (no close through it in 10 bars) | " + " | ".join(cells) + " |")
        cells = []
        for side in ("bull", "bear"):
            s_ = res.get(("W", side) + win, {})
            cells.append(fmt(s_) + "; edge " + fmt_edge(edge(X("W", side, *win), X("W", side, "random", win[1]))))
        L += ["| Weekly bars, same rules | " + " | ".join(cells) + " |", ""]
    for tf, tfname in (("D", "Daily"), ("W", "Weekly")):
        for side, sname in (("bull", "bullish blocks, buy the first pullback into the zone"),
                            ("bear", "bearish blocks, short the first rally into the zone")):
            L += [f"## {tfname} bars, {sname}", "", "| Definition | " + " | ".join(
                f"Enter at {v}" for v in STYLES.values()) + " |", "|---|" + "---|" * len(STYLES)]
            for kind in VARIANTS:
                L.append(f"| {name(kind)} | " + " | ".join(fmt(res.get((tf, side, kind, st))) for st in STYLES) + " |")
            L.append("")
    L += ["## Definitions", ""] + [f"- **{name(k)}**: {v.split(':', 1)[1].strip()}" for k, v in VARIANTS.items()]
    L += ["", "Entry levels for a bullish block (mirror for bearish): near edge = the candle's high, "
          "body = the top of the candle's body, 50% = halfway between high and low. The stop is always "
          "below the candle's low.", "",
          "Notes: today's index members are used for the whole 10 years, so stocks that were dropped or went "
          "bust are missing (this flatters long trades; the random zones have the same bias). "
          "No commissions; orders that gap are filled at the open. Inside a bar, the extreme nearer the open "
          "is assumed to come first (TradingView's rule)."]
    return "\n".join(L) + "\n", res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=1000)
    ap.add_argument("--out", default="ob_results")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if args.demo:
        frames = demo_frames()
        group = {t: "demo" for t in frames}
    else:
        print("Reading index lists...", flush=True)
        order = universe()
        want = [t for t, _ in order][:args.stocks + 80]          # a few spare in case some fail to download
        frames = download(want)
        missing = [t for t in want if t not in frames]
        if missing:
            print(f"  retrying {len(missing)} missing tickers in 30s...", flush=True)
            time.sleep(30)
            frames.update(download(missing, size=25))
        group = dict(order)
        keep = [t for t in want if t in frames][:args.stocks]
        frames = {t: frames[t] for t in keep}
        if len(frames) < 0.8 * args.stocks:
            sys.exit(f"Only {len(frames)} of {args.stocks} stocks downloaded; not enough for a fair test.")
    print(f"{len(frames)} stocks, {sum(len(d) for d in frames.values()):,} daily bars", flush=True)

    acc = {}
    for k, (t, d) in enumerate(frames.items(), 1):
        tag = (1.0 if group.get(t) == "S&P 500" else 0.0, float(k))
        seed = zlib.crc32(t.encode())
        for tf, frame in (("D", d), ("W", weekly(d))):
            for key, (zones, rows) in run_frame(frame, tf, seed, tag).items():
                a = acc.setdefault(key, {"zones": 0, "parts": []})
                a["zones"] += zones
                if rows:
                    a["parts"].append(np.asarray(rows, dtype=np.float32))
        if k % 50 == 0 or k == len(frames):
            print(f"  tested {k} of {len(frames)} ({time.time() - t0:.0f}s)", flush=True)
    results = {k: {"zones": v["zones"], "X": np.concatenate(v["parts"]) if v["parts"] else np.zeros((0, len(COLS)))}
               for k, v in acc.items()}

    start = min(d.index[0] for d in frames.values())
    end = max(d.index[-1] for d in frames.values())
    mid = start + (end - start) / 2
    mid_m = mid.year * 12 + mid.month - 1
    counts = pd.Series([group.get(t, "?") for t in frames]).value_counts()
    meta = dict(stocks=len(frames), groups=", ".join(f"{g}: {n}" for g, n in counts.items()),
                start=start.date().isoformat(), end=end.date().isoformat(),
                run=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
                slices=[("All trades", lambda X: np.ones(len(X), bool)),
                        ("With your trend (uptrend for longs, downtrend for shorts)", lambda X: X[:, 1] == 1),
                        ("No clear trend", lambda X: X[:, 1] == 0),
                        ("Against the trend", lambda X: X[:, 1] == -1),
                        (f"First half ({start.date()} to {mid.date()})", lambda X: X[:, 0] < mid_m),
                        (f"Second half ({mid.date()} to {end.date()})", lambda X: X[:, 0] >= mid_m),
                        ("S&P 500 stocks only", lambda X: X[:, 8] == 1),
                        ("Zone revisited within 21 bars", lambda X: X[:, 7] <= 21),
                        ("Zone revisited after 21 bars", lambda X: X[:, 7] > 21)])
    text, stats = report(results, meta)
    (out / "summary.md").write_text(text, encoding="utf-8")
    meta.pop("slices")
    (out / "results.json").write_text(json.dumps(
        {"meta": meta, "stats": {"|".join(k): v for k, v in stats.items()}}, indent=1), encoding="utf-8")
    print(text)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
