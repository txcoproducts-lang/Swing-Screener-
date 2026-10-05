#!/usr/bin/env python3
"""
Backtest for the three pick lists at the top of the page:

  New uptrends    stocks that turned into an uptrend (your rule) on the latest day
  Breakout watch  stocks showing the strongest signs of a coming breakout
  AI picks        Claude's own list: a multi-factor model with fixed buy and sell rules

Universe: the S&P 500 as it was on each day. Members are rebuilt from Wikipedia's list of
changes, so a stock only counts while it was in the index, which removes most of the
"today's winners" bias. The screener's liquidity filter applies (price >= $10, 20-day average
volume >= 1M shares). Today's S&P 400 and S&P 600 members are a second check; that one does
have survivorship bias.

Every rule is chosen on 2014-2021 data and then checked on 2022-2026 data it never saw.
Entries are at the next day's open (the page updates after the close), and returns are
measured against the average liquid stock over the same days.

Runs on GitHub Actions (the "Pick lists backtest" workflow), where Yahoo and Wikipedia work:
    python research/picks_backtest.py --out picks_results
    python research/picks_backtest.py --demo --out /tmp/pk    # random walks: no list should show an edge
"""
import argparse, io, json, re, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import screener as S                      # the same signal code the page runs
from ob_backtest import clean

START = "2013-06-01"                      # the first year only warms up the 12-month signals
TEST_FROM = "2014-10-01"
SPLIT = "2022-01-01"                      # rules are chosen before this date, checked after it
HORIZONS = (5, 10, 20)
TOP = 10
COST = 0.001                              # 0.10% per buy and per sell
TIE = 0.0001                              # 20-day returns this close (0.01%) count as the same when choosing a list
SP500, OTHER = "List_of_S%26P_500_companies", (("S&P 400", "List_of_S%26P_400_companies"),
                                               ("S&P 600", "List_of_S%26P_600_companies"))


# ---------------------------------------------------------------- universe and data
def wiki(page):
    import requests
    html = requests.get(f"https://en.wikipedia.org/wiki/{page}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    tabs = pd.read_html(io.StringIO(html))
    for t in tabs:
        t.columns = [" ".join(dict.fromkeys(str(x) for x in (c if isinstance(c, tuple) else (c,)))).strip() for c in t.columns]
    return tabs


def col(t, *words):
    return next((c for c in t.columns if all(w in c.lower() for w in words)), None)


def sym(s):
    s = re.sub(r"\[.*?\]", "", str(s)).strip().upper().replace(".", "-")
    return s if re.fullmatch(r"[A-Z][A-Z0-9\-]{0,6}", s) else None


def members(tabs):
    for t in tabs:
        s = col(t, "symbol") or col(t, "ticker")
        if s and len(t) > 300:
            return t, s
    raise RuntimeError("no constituents table found")


def sp500_spans(tabs):
    """When each stock was in the S&P 500: today's list ('Date added') plus the change log,
    walked back from today (before an addition a stock was out, before a removal it was in)."""
    t, s = members(tabs)
    now, ev = set(), set()
    added = col(t, "date added")
    for _, r in t.iterrows():
        k = sym(r[s])
        if not k:
            continue
        now.add(k)
        d = pd.to_datetime(str(r[added])[:10], errors="coerce") if added else pd.NaT
        if pd.notna(d):
            ev.add((d, k, 1))
    log = next((x for x in tabs if col(x, "added", "ticker") and col(x, "removed", "ticker")), None)
    n_log = 0
    if log is not None:
        dc, ac, rc = col(log, "date"), col(log, "added", "ticker"), col(log, "removed", "ticker")
        for _, r in log.iterrows():
            d = pd.to_datetime(r[dc], errors="coerce")
            if pd.isna(d):
                continue
            for k, e in ((sym(r[ac]), 1), (sym(r[rc]), -1)):
                if k:
                    ev.add((d, k, e))
                    n_log += 1
    by = {}
    for d, k, e in ev:
        by.setdefault(k, []).append((d, e))
    spans = {}
    for k in set(by) | now:
        inside, end, out = k in now, pd.Timestamp.max, []
        for d, e in sorted(by.get(k, []), reverse=True):
            if e > 0 and inside:
                out.append((d, end))
                inside = False
            elif e < 0 and not inside:
                end, inside = d, True
        if inside:
            out.append((pd.Timestamp.min, end))
        spans[k] = out
    return spans, now, n_log


def universe():
    tabs = wiki(SP500)
    t, s = members(tabs)
    info = {}
    for _, r in t.iterrows():
        k = sym(r[s])
        if k:
            info[k] = dict(sector=r.get(col(t, "gics sector")), sub=r.get(col(t, "sub-industry")), other=set())
    spans, now, n_log = sp500_spans(tabs)
    print(f"  S&P 500: {len(now)} members today, {n_log} entries in the change log", flush=True)
    for name, page in OTHER:
        try:
            tt, ss = members(wiki(page))
        except Exception as e:
            print(f"  could not read the {name} list: {e}")
            continue
        n = 0
        for _, r in tt.iterrows():
            k = sym(r[ss])
            if not k:
                continue
            d = info.setdefault(k, dict(sector=None, sub=None, other=set()))
            d["other"].add(name)
            d["sector"] = d["sector"] or r.get(col(tt, "gics sector"))
            d["sub"] = d["sub"] or r.get(col(tt, "sub-industry"))
            n += 1
        print(f"  {name}: {n} members today", flush=True)
    first = pd.Timestamp(TEST_FROM)
    former = [k for k, sp in spans.items() if k not in now and any(b > first for _, b in sp)]
    for k in former:
        info.setdefault(k, dict(sector=None, sub=None, other=set()))
    print(f"  former S&P 500 members since {TEST_FROM[:4]}: {len(former)}", flush=True)
    return info, spans, now, former


def download(tickers, size=100):
    import yfinance as yf
    frames = {}
    for i in range(0, len(tickers), size):
        chunk = tickers[i:i + size]
        print(f"  downloading {i + 1}-{i + len(chunk)} of {len(tickers)}", flush=True)
        try:
            df = yf.download(chunk, start=START, interval="1d", auto_adjust=True,
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
                if len(d) >= 260:
                    frames[t] = d
        time.sleep(1)
    return frames


def demo_data(n=300, days=3450, seed=5):
    """Driftless random walks (every stock's expected return is exactly 0): no list should beat the
    average stock here, so a clear edge would mean the code peeks at the future."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-10-02", periods=days)
    frames = {}
    for k in range(n):
        sd = rng.uniform(0.01, 0.03)
        g, r = rng.normal(0, 0.004, days), rng.normal(0, sd, days)
        c = rng.uniform(30, 300) * np.cumprod((1 + g) * (1 + r))
        o = c / (1 + r)
        hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, sd / 3, days)))
        lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, sd / 3, days)))
        v = rng.lognormal(np.log(2.5e6), 0.4, days) * np.where(rng.random(days) < 0.03, 4, 1)
        frames[f"DEMO{k:03d}"] = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": c, "Volume": v}, index=idx)
    frames["SPY"] = frames.pop("DEMO000")
    secs = [f"Sector {i}" for i in range(11)]
    info = {t: dict(sector=secs[i % 11], sub=f"Industry {i % 37}", other={"S&P 400"} if i % 4 == 0 else set())
            for i, t in enumerate(frames) if t != "SPY"}
    spans = {t: [(pd.Timestamp.min, pd.Timestamp.max)] for i, t in enumerate(info) if i % 4}
    return frames, info, spans


# ---------------------------------------------------------------- statistics
def boot(daily, block=60):
    """95% range of the average of a daily series of overlapping 20-day returns: the spread of averages
    over separate 60-day blocks (checked on random data to be wrong about 5% of the time, as it should)."""
    x = pd.Series(daily).dropna().to_numpy(float)
    m = len(x) // block
    if m < 8:
        return (np.nan, np.nan)
    se = x[:m * block].reshape(m, block).mean(1).std(ddof=1) / np.sqrt(m)
    t = 1.96 + 2.4 / (m - 1)                  # t distribution, 97.5%
    return (x.mean() - t * se, x.mean() + t * se)


def nw(x, lag=10):
    """95% range of the average of daily returns (Newey-West), for the managed list's daily edge."""
    x = pd.Series(x).dropna().to_numpy(float)
    n = len(x)
    if n < 60:
        return (np.nan, np.nan)
    e = x - x.mean()
    v = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        v += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    se = np.sqrt(max(v, 0) / n)
    return (x.mean() - 1.96 * se, x.mean() + 1.96 * se)


def top_k(score, cand, k=TOP):
    """Each day's k best-scoring candidates (all of them if there are fewer)."""
    s = score.where(cand).to_numpy(float)
    s = np.where(np.isnan(s), -np.inf, s)
    kk = min(k, s.shape[1])
    part = np.argpartition(-s, kk - 1, axis=1)[:, :kk]
    sel = np.zeros(s.shape, bool)
    np.put_along_axis(sel, part, True, axis=1)
    return pd.DataFrame(sel & np.isfinite(s), index=score.index, columns=score.columns)


class Book:
    """Forward returns and benchmarks for one universe."""

    def __init__(self, P, F, elig):
        O, C = P["Open"], P["Close"]
        entry = O.shift(-1)
        self.elig = elig
        self.fr = {h: C.shift(-h) / entry - 1 for h in HORIZONS}
        self.bench = {h: self.fr[h].where(elig).mean(axis=1) for h in HORIZONS}
        self.ex = {h: self.fr[h].sub(self.bench[h], axis=0) for h in HORIZONS}
        nxt = C.iloc[::-1].rolling(10, min_periods=10).max().iloc[::-1].shift(-1)
        self.bo = (nxt > F["piv"]).where(nxt.notna())      # closes above today's 50-day high within 10 days

    def stats(self, sel, dates):
        m = (sel & self.elig).loc[dates]
        n = m.sum(axis=1)
        out = dict(days=int((n > 0).sum()), per_day=float(n[n > 0].mean()) if (n > 0).any() else 0.0)
        for h in HORIZONS:
            e = self.ex[h].loc[dates].where(m)
            daily = e.mean(axis=1).dropna()
            out[f"ex{h}"] = float(daily.mean()) if len(daily) else np.nan
            out[f"ret{h}"] = float(self.fr[h].loc[dates].where(m).mean(axis=1).dropna().mean()) if len(daily) else np.nan
            cnt = e.notna().to_numpy().sum()
            out[f"hit{h}"] = float((e > 0).to_numpy().sum() / cnt) if cnt else np.nan
            if h == 20:
                out["ci20"] = boot(daily)
        b = self.bo.loc[dates].where(m).to_numpy(float)
        out["bo10"] = float(np.nanmean(b)) if np.isfinite(b).any() else np.nan
        return out


def perf(r):
    r = r.dropna()
    if len(r) < 60:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    return dict(cagr=float(eq.iloc[-1] ** (1 / yrs) - 1), vol=float(r.std() * np.sqrt(252)),
                sharpe=float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else np.nan,
                maxdd=float((eq / eq.cummax() - 1).min()))


def manage(score, elig, sector, oo, n=10, keep=30, cap=3, sell=None, allow=None):
    """Run the AI picks list day by day with the same step the page uses (screener.ai_step).
    Decisions at the close trade at the next open. Returns daily returns and the trade log."""
    cols = np.array(score.columns)
    sc = score.where(elig)
    sc[sc.index < TEST_FROM] = np.nan
    ooa = oo.to_numpy(float)
    held, entry, trades, rets = [], {}, [], []
    for t in range(len(sc)):
        row = sc.iloc[t].dropna()
        kept, added, dropped = S.ai_step(held, row, sector, n=n, keep=keep, cap=cap,
                                         allow_new=True if allow is None else bool(allow.iloc[t]),
                                         sell=set() if sell is None else set(cols[sell.iloc[t].to_numpy(bool)]))
        for k in dropped:
            trades.append((entry.pop(k), t, k))
        for k in added:
            entry[k] = t
        held = kept + added
        j = [score.columns.get_loc(k) for k in held]
        g = np.nan_to_num(ooa[t, j]).sum() / n if j else 0.0
        rets.append(g - COST * (len(added) + len(dropped)) / n)
    for k, t0 in entry.items():
        trades.append((t0, None, k))
    return pd.Series(rets, index=score.index), trades


def trade_stats(trades, O, dates):
    """Per-pick results: buy at the open after the pick, sell at the open after it drops off."""
    Oa, idx, rows = O.to_numpy(float), O.index, []
    for t0, t1, k in trades:
        j = O.columns.get_loc(k)
        if t0 + 1 >= len(idx) or not dates[t0]:
            continue
        e = t1 + 1 if t1 is not None and t1 + 1 < len(idx) else len(idx) - 1
        rows.append((Oa[e, j] / Oa[t0 + 1, j] - 1, e - t0 - 1))
    if not rows:
        return {}
    r = np.array(rows)
    return dict(trades=len(r), avg=float(np.nanmean(r[:, 0])), win=float(np.nanmean(r[:, 0] > 0)),
                days=float(np.median(r[:, 1])))


# ---------------------------------------------------------------- signal report card
FACTORS = {   # name: (description, sign) for the factor report card
    "mom": ("12-month momentum, skip last month", 1), "mom_va": ("momentum / volatility", 1),
    "mom6": ("6-month momentum, skip last month", 1), "rs": ("IBD-style relative strength", 1),
    "hi52": ("closeness to the 52-week high", 1), "ind": ("industry strength (6 months)", 1),
    "sec_up": ("share of the sector in an uptrend", 1), "smooth": ("steady climb (frog in the pan)", 1),
    "pgap": ("recent power gap that held", 1), "accum": ("up-day vs down-day volume", 1),
    "vol": ("low volatility", -1), "r5": ("1-week pullback", -1), "r21": ("1-month pullback", -1),
    "up": ("in an uptrend (your rule)", 1), "template": ("Minervini trend template", 1),
    "ext": ("not stretched above EMA20", -1), "dry": ("volume drying up", -1), "vcp": ("ranges shrinking", -1),
}


# ---------------------------------------------------------------- report
def num(x):
    return -9.0 if x is None or x != x else x


def pct(x, d=2, sign=True):
    return "n/a" if x is None or x != x else f"{x * 100:{'+' if sign else ''}.{d}f}%"


def ci(c):
    return "n/a" if c is None or c[0] != c[0] else f"{c[0] * 100:+.2f} to {c[1] * 100:+.2f}"


def list_table(rows, names):
    out = ["| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for key, per, s in rows:
        out.append(f"| {names[key]} | {per} | {s['days']} | {s['per_day']:.1f} | {pct(s['ex5'])} | {pct(s['ex10'])} | "
                   f"{pct(s['ex20'])} ({ci(s['ci20'])}) | {pct(s['hit20'], 0, False)} | {pct(s['ret20'])} | {pct(s['bo10'], 0, False)} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default="picks_results")
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("Universe and prices...", flush=True)
    if a.demo:
        frames, info, spans = demo_data(seed=a.seed)
        now, former = set(spans), []
    else:
        info, spans, now, former = universe()
        tickers = sorted(info) + ["SPY"]
        frames = download(tickers)
        miss = [t for t in tickers if t not in frames and (t in now or info.get(t, {}).get("other"))]
        if miss:
            print(f"  retrying {len(miss)} current members in smaller batches...", flush=True)
            time.sleep(30)
            frames.update(download(miss, size=25))
        cur = [t for t in tickers if t in now or info.get(t, {}).get("other")]
        got = sum(t in frames for t in cur)
        if got < 0.8 * len(cur):
            sys.exit(f"Only {got} of {len(cur)} current index members downloaded; not running on partial data.")
        print(f"  {got} of {len(cur)} current members and {sum(t in frames for t in former)} of {len(former)} "
              f"former S&P 500 members have prices", flush=True)
    if "SPY" not in frames:
        sys.exit("No SPY data.")

    idx = frames["SPY"].index
    idx = idx[idx >= START] if not a.demo else idx
    P = {k: S.wide(frames, k, idx) for k in ("Open", "High", "Low", "Close", "Volume")}
    cols = P["Close"].columns
    sector = {t: info[t]["sector"] for t in cols if t in info and isinstance(info[t]["sector"], str)}
    sub = {t: info[t]["sub"] for t in cols if t in info and isinstance(info[t]["sub"], str)}
    print(f"Signals for {len(cols)} tickers x {len(idx)} days...", flush=True)
    F = S.pick_features(P, sector, sub)

    m500 = np.zeros((len(idx), len(cols)), bool)
    for j, k in enumerate(cols):
        for s0, s1 in spans.get(k, []):
            m500[:, j] |= (idx >= s0) & (idx < s1)
    other = np.array([bool(info.get(k, {}).get("other")) for k in cols])
    stock = np.array([k != "SPY" for k in cols])
    U = {"sp500": F["liquid"] & pd.DataFrame(m500 & stock, index=idx, columns=cols),
         "midsmall": F["liquid"] & pd.DataFrame(~m500 & other & stock, index=idx, columns=cols)}
    names_u = {"sp500": "S&P 500 as it was each day", "midsmall": "S&P 400 + 600 (today's members)"}
    for u, m in U.items():
        print(f"  {names_u[u]}: {m.sum(axis=1).loc[TEST_FROM:].mean():.0f} liquid stocks a day on average", flush=True)

    valid = (idx >= TEST_FROM) & (idx <= idx[-22])
    PIS, POS, PALL = "2014-2021 (chosen here)", "2022-2026 (unseen)", "2014-2026 (all)"
    per = {PIS: valid & (idx < SPLIT), POS: valid & (idx >= SPLIT), PALL: valid}
    spy_c = P["Close"]["SPY"]
    mkt_up = spy_c > spy_c.rolling(200).mean()
    oo = P["Open"].shift(-2) / P["Open"].shift(-1) - 1           # open to open: decided at the close, traded next open

    res = dict(meta=dict(demo=a.demo, tickers=len(cols), start=str(idx[0].date()), end=str(idx[-1].date()),
                         split=SPLIT, universes={u: float(m.sum(axis=1).loc[TEST_FROM:].mean()) for u, m in U.items()}))
    md = [f"# Pick lists backtest{' (DEMO: random walks)' if a.demo else ''}", "",
          f"Data {idx[0].date()} to {idx[-1].date()}, {len(cols)} tickers. Signals from {TEST_FROM[:7]}; "
          f"every choice was made on {TEST_FROM[:4]}-2021 S&P 500 data and then checked on 2022-{idx[-1].year}. "
          "Entry at the next open; returns are compared with the average liquid stock in the same universe over the same days.", ""]
    chosen, top_md, body = {}, [], []

    for u in U:
        ok = U[u]
        B = Book(P, F, ok)
        main_u = u == "sp500"                                    # choices are made here; the other universe only checks them
        print(f"== {names_u[u]} ==", flush=True)
        body += [f"## {names_u[u]}", f"About {res['meta']['universes'][u]:.0f} liquid stocks a day.", ""]
        R = res[u] = {}

        # ---- factor report card
        rows = ["| Signal | Period | Top 10% vs avg stock, 20 days (95% range) | Bottom 10% | Rank correlation |", "|---|---|---|---|---|"]
        R["factors"] = {}
        y = B.ex[20]
        for f, (desc, sgn) in FACTORS.items():
            x = F[f].astype(float) * sgn
            q = (x.where(ok) * 0.8 + 0.1) if F[f].dtypes.iloc[0] == bool else x.where(ok).rank(axis=1, pct=True)   # yes/no: 0.9 vs 0.1
            ra, rb = x.where(ok & y.notna()).rank(axis=1), y.where(ok & x.notna()).rank(axis=1)
            ra, rb = ra.sub(ra.mean(axis=1), axis=0), rb.sub(rb.mean(axis=1), axis=0)
            icd = (ra * rb).sum(axis=1) / np.sqrt((ra ** 2).sum(axis=1) * (rb ** 2).sum(axis=1))
            R["factors"][f] = {}
            for pname, d in per.items():
                top_ = y.loc[d].where(q.loc[d] >= 0.9).mean(axis=1)
                bot_ = y.loc[d].where(q.loc[d] <= 0.1).mean(axis=1)
                s = dict(top=float(top_.mean()), top_ci=boot(top_), bot=float(bot_.mean()), ic=float(icd.loc[d].mean()))
                R["factors"][f][pname] = s
                rows.append(f"| {desc} | {pname} | {pct(s['top'])} ({ci(s['top_ci'])}) | {pct(s['bot'])} | {s['ic']:+.3f} |")
        body += ["### Signal report card", "Each signal on its own: the best 10% of stocks by that signal each day, "
                 "and the worst 10%, against the average stock over the next 20 trading days.", ""] + rows + [""]
        print(f"  factors done ({time.time() - t0:.0f}s)", flush=True)

        # ---- AI score: daily top 10, best 10%, and the managed list
        A = S.ai_scores(F, ok)
        res_ai = R["ai"] = {}
        names = {k: v[0] for k, v in A.items()}
        rows, dec = [], []
        for k, (desc, sc) in A.items():
            sel, sel10 = top_k(sc, ok), sc.where(ok).rank(axis=1, pct=True) > 0.9
            for pname, d in per.items():
                rows.append((k, pname, B.stats(sel, d)))
                dec.append((k, pname, B.stats(sel10, d)))
        body += ["### AI score: the 10 best stocks each day", "", list_table(rows, names), "",
                 "### AI score: the best 10% each day (30-40 stocks, so much less noise; the score is chosen here)", "",
                 list_table(dec, names), ""]
        res_ai["daily"], res_ai["decile"] = rows, dec
        if main_u:
            chosen["ai_score"] = max(A, key=lambda k: num(next(s for k2, p_, s in dec if k2 == k and p_ == PIS)["ex20"]))
        best = chosen["ai_score"]

        ew = oo.where(ok).mean(axis=1)
        spy = oo["SPY"]
        bench_rows = {pname: dict(ew=perf(ew[d]), spy=perf(spy[d])) for pname, d in per.items()}
        res_ai["bench"] = bench_rows

        def run(sc, **kw):
            r, trades = manage(sc, ok, sector, oo, **kw)
            row = {}
            for pname, d in per.items():
                xs = (r[d] - ew[d]).dropna()
                lo, hi = nw(xs)
                row[pname] = dict(perf(r[d]), **trade_stats(trades, P["Open"], d),
                                  vs_ew=float(xs.mean() * 252), vs_ew_ci=(lo * 252, hi * 252))
            return r, row

        sims = {}
        for k, (desc, sc) in A.items():
            sims[k] = run(sc)
            print(f"  managed {k} ({time.time() - t0:.0f}s)", flush=True)
        rules = {
            "base": ("Hold 10, keep while in the top 30, max 3 per sector", {}),
            "keep20": ("Keep only while in the top 20", dict(keep=20)),
            "keep50": ("Keep while in the top 50", dict(keep=50)),
            "trend": ("Also sell on a close below EMA50", dict(sell=F["close"] < F["e50"])),
            "market": ("No new picks while SPY is below its 200-day average", dict(allow=mkt_up)),
            "trend_market": ("Both of the above", dict(sell=F["close"] < F["e50"], allow=mkt_up)),
        }
        rsims = {"base": sims[best]}
        for rk, (desc, kw) in rules.items():
            if rk != "base":
                rsims[rk] = run(A[best][1], **kw)
                print(f"  rule {rk} ({time.time() - t0:.0f}s)", flush=True)
        if main_u:
            chosen["ai_rule"] = max(rsims, key=lambda k: num(rsims[k][1][PIS].get("sharpe")))
        best_rule = chosen["ai_rule"]
        res_ai.update(score=best, rule=best_rule, scores={k: v[1] for k, v in sims.items()},
                      rules={k: v[1] for k, v in rsims.items()})

        def ptable(items, label_of):
            rows = ["| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |",
                    "|---|---|---|---|---|---|---|---|---|---|"]
            for k, row in items:
                for pname in per:
                    s = row[pname]
                    rows.append(f"| {label_of(k)} | {pname} | {pct(s.get('cagr'), 1)} | {pct(s.get('vs_ew'), 1)} ({ci(s.get('vs_ew_ci'))}) | "
                                f"{s.get('sharpe', float('nan')):.2f} | {pct(s.get('maxdd'), 0)} | {s.get('trades', 0)} | "
                                f"{pct(s.get('avg'), 1)} | {pct(s.get('win'), 0, False)} | {s.get('days', float('nan')):.0f} |")
            for pname in per:
                for bk, bl in (("ew", "Average liquid stock (equal weight)"), ("spy", "SPY")):
                    s = bench_rows[pname][bk]
                    rows.append(f"| *{bl}* | {pname} | {pct(s.get('cagr'), 1)} | | {s.get('sharpe', float('nan')):.2f} | "
                                f"{pct(s.get('maxdd'), 0)} | | | | |")
            return "\n".join(rows)

        body += ["### AI picks as a managed list (10 stocks, entries and exits at the next open, 0.10% cost each way)", "",
                 "Score versions, all with the same rules (hold 10, keep while in the top 30, max 3 per sector):", "",
                 ptable([(k, v[1]) for k, v in sims.items()], lambda k: names[k]), "",
                 f"Score chosen on the best 10% in 2014-2021 (S&P 500): **{names[best]}**. "
                 "Rule versions for it (chosen on the 2014-2021 Sharpe ratio):", "",
                 ptable([(k, v[1]) for k, v in rsims.items()], lambda k: rules[k][0]), "",
                 f"Chosen rule: **{rules[best_rule][0]}**.", ""]
        r_final, ai_final = rsims[best_rule]
        yr = pd.DataFrame({"AI picks": r_final, "Average stock": ew, "SPY": spy})[valid].dropna()
        yrs = (1 + yr).groupby(yr.index.year).prod() - 1
        body += ["Year by year (chosen version):", "", "| Year | AI picks | Average stock | SPY |", "|---|---|---|---|"]
        body += [f"| {y_} | {pct(r_['AI picks'], 1)} | {pct(r_['Average stock'], 1)} | {pct(r_['SPY'], 1)} |" for y_, r_ in yrs.iterrows()]
        body += [""]
        res_ai["years"] = {int(y_): {k: float(v) for k, v in r_.items()} for y_, r_ in yrs.iterrows()}

        # ---- new uptrends
        NU = S.new_up_lists(F, ok, A[best][1])
        rows = []
        for k, (desc, cand, sc) in NU.items():
            sel = cand if sc is None else top_k(sc, cand, 5)
            for pname, d in per.items():
                rows.append((k, pname, B.stats(sel, d)))
        names_nu = {k: v[0] for k, v in NU.items()}
        old = F["up"] & ~F["new_up"] & ok
        for pname, d in per.items():
            rows.append(("old", pname, B.stats(old, d)))
        names_nu["old"] = "Baseline: stocks already in an uptrend"
        get = lambda rows_, k, p_: next(s for k2, q_, s in rows_ if k2 == k and q_ == p_)
        if main_u:   # an order is only worth using if its top 5 beat the whole list by more than noise (0.10%) in 2014-2021
            rk = max((k for k in NU if k != "all"), key=lambda k: num(get(rows, k, PIS)["ex20"]))
            chosen["new_up"] = rk if num(get(rows, rk, PIS)["ex20"]) > num(get(rows, "all", PIS)["ex20"]) + 0.001 else "all"
        R["new_up"] = dict(rows=rows, best=chosen["new_up"])
        body += ["### New uptrends (each ordering's top 5 a day, against the whole list)", "", list_table(rows, names_nu), "",
                 f"Chosen: **{names_nu[chosen['new_up']]}** (an ordering had to beat the whole list by 0.10% in 2014-2021).", ""]
        print(f"  new uptrends done ({time.time() - t0:.0f}s)", flush=True)

        # ---- breakout watch
        BL = S.breakout_lists(F, ok)
        rows = []
        for k, (desc, cand, sc) in BL.items():
            sel = cand if sc is None else top_k(sc, cand)
            for pname, d in per.items():
                rows.append((k, pname, B.stats(sel, d)))
        for pname, d in per.items():
            rows.append(("everyone", pname, B.stats(ok, d)))
        names_bl = {k: v[0] for k, v in BL.items()}
        names_bl["everyone"] = "Baseline: every liquid stock"
        tied = []
        if main_u:
            base_bo = get(rows, "everyone", PIS)["bo10"]
            ok_bl = [k for k in BL if k != "all" and get(rows, k, PIS)["bo10"] >= 1.5 * base_bo] or [k for k in BL if k != "all"]
            ex = lambda k: num(get(rows, k, PIS)["ex20"])
            tied = [k for k in ok_bl if ex(k) >= max(map(ex, ok_bl)) - TIE]      # a tie goes to the list that breaks out more
            chosen["breakout"] = max(tied, key=lambda k: num(get(rows, k, PIS)["bo10"]))
        R["breakout"] = dict(rows=rows, best=chosen["breakout"])
        tie_md = (" Tied on return with " + ", ".join(f"**{names_bl[k]}**" for k in tied if k != chosen["breakout"])
                  + "; it broke out more often." if len(tied) > 1 else "")
        body += ["### Breakout watch (top 10 a day)", "", list_table(rows, names_bl), "",
                 f"Chosen: **{names_bl[chosen['breakout']]}** (best 2014-2021 return among lists that broke out at least "
                 f"1.5x as often as the average stock; returns within {TIE * 100:.2f}% count as a tie, and a tie goes to "
                 f"the list that broke out more often).{tie_md}", ""]
        print(f"  breakouts done ({time.time() - t0:.0f}s)", flush=True)

        # ---- the chosen lists, side by side
        top_md += [f"### {names_u[u]}", "", "| List | Version | Period | vs avg stock | Notes |", "|---|---|---|---|---|"]
        for pname in per:
            s = get(R["new_up"]["rows"], chosen["new_up"], pname)
            top_md.append(f"| New uptrends | {names_nu[chosen['new_up']]} | {pname} | {pct(s['ex20'])} over 20 days ({ci(s['ci20'])}) | "
                          f"{s['per_day']:.1f} a day, {pct(s['hit20'], 0, False)} beat the average stock |")
        for pname in per:
            s, b0 = get(R["breakout"]["rows"], chosen["breakout"], pname), get(R["breakout"]["rows"], "everyone", pname)
            top_md.append(f"| Breakout watch | {names_bl[chosen['breakout']]} | {pname} | {pct(s['ex20'])} over 20 days ({ci(s['ci20'])}) | "
                          f"broke out within 10 days {pct(s['bo10'], 0, False)} of the time vs {pct(b0['bo10'], 0, False)} for all stocks |")
        for pname in per:
            s, bw = ai_final[pname], bench_rows[pname]
            top_md.append(f"| AI picks | {names[best]}, {rules[best_rule][0].lower()} | {pname} | {pct(s.get('vs_ew'), 1)} a year ({ci(s.get('vs_ew_ci'))}) | "
                          f"{pct(s.get('cagr'), 1)}/yr vs {pct(bw['ew'].get('cagr'), 1)} average stock and {pct(bw['spy'].get('cagr'), 1)} SPY; "
                          f"worst drop {pct(s.get('maxdd'), 0)}; {s.get('trades', 0)} picks, median hold {s.get('days', float('nan')):.0f} days |")
        top_md += [""]
        R["final"] = dict(new_up={p_: get(R["new_up"]["rows"], chosen["new_up"], p_) for p_ in per},
                          breakout={p_: get(R["breakout"]["rows"], chosen["breakout"], p_) for p_ in per},
                          breakout_base={p_: get(R["breakout"]["rows"], "everyone", p_) for p_ in per},
                          ai=ai_final, bench=bench_rows)

    res["chosen"] = chosen
    live = dict(new_up=S.CFG["NEW_UP"], breakout=S.CFG["BREAKOUT"], ai_score=S.CFG["AI_SCORE"],
                ai_rule={20: "keep20", 30: "base", 50: "keep50"}.get(S.CFG["AI_KEEP"]) if not (S.CFG["AI_TREND_EXIT"] or S.CFG["AI_MARKET_FILTER"])
                else "trend_market" if S.CFG["AI_TREND_EXIT"] and S.CFG["AI_MARKET_FILTER"] else "trend" if S.CFG["AI_TREND_EXIT"] else "market")
    same = all(live[k] == chosen[k] for k in chosen)
    print("Chosen:", chosen, "| the page uses:", live, "(same)" if same else "(DIFFERENT: update CFG in screener.py)", flush=True)
    md += ["## The chosen lists", "",
           f"Chosen: {chosen}. The page (CFG in screener.py) uses: {live}{'' if same else ' **(different!)**'}.", ""] + top_md + body
    md += ["## Caveats", "",
           "- S&P 500 membership is rebuilt from Wikipedia's change log. Stocks that left the index and no longer trade "
           "(most were bought out) have no Yahoo data, so they are missing from the days they were members.",
           "- The S&P 400 + 600 check uses today's members for all years, so it favors stocks that did well.",
           "- Returns include dividends (Yahoo's adjusted prices). The AI picks list pays 0.10% per buy and per sell; "
           "the daily lists have no costs.", ""]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(res, default=lambda o: None if o != o else str(o), indent=1), encoding="utf-8")
    print(f"Done in {time.time() - t0:.0f}s -> {out / 'summary.md'}")


if __name__ == "__main__":
    main()
