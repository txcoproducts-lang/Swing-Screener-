#!/usr/bin/env python3
"""
Why do Your system and Your system after 2 PM lag SPY, most of all from 2023 on? (the user's question, 2026-10-20)
Research only: runs research/plan_backtest.py's A and C (shares) as they are, breaks the trades down by year, then
reruns them with one piece changed at a time to see which piece costs the most. Nothing live changes.

    python research/system_diag.py --out research/system_diag.json [--demo]
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import plan_backtest as PBT


def cagr(eq, idx, t0):
    e = pd.Series(eq[t0:], index=idx[t0:]).ffill().dropna()
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return round(float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1) * 100, 1) if yrs > 0.2 else None


def maxdd(eq, t0):
    e = pd.Series(eq[t0:]).ffill()
    return round(float((e / e.cummax() - 1).min()) * 100, 1)


def yearly(eq, idx, t0):
    e = pd.Series(eq[t0:], index=idx[t0:]).ffill()
    last = e.groupby(e.index.year).last()
    prev = last.shift().fillna(e.iloc[0])
    return {str(y): round(float(v) * 100, 1) for y, v in (last / prev - 1).items()}


def run(M, F, when, **kw):
    """One A / C run with module settings or signal tables swapped for the run."""
    saved = {k: getattr(PBT, k) for k in ("STOP", "A_SLOTS", "A_CAP")}
    for k in saved:
        if k in kw:
            setattr(PBT, k, kw[k])
    F2 = dict(F, **kw.get("swap", {}))
    try:
        A = PBT.run_system(M, F2, when, False)
    finally:
        for k, v in saved.items():
            setattr(PBT, k, v)
    return A


def trade_stats(M, F, A):
    idx, col = M.idx, {t: j for j, t in enumerate(M.names)}
    rows = []
    for x in A.trades:
        b, s = idx.get_loc(pd.Timestamp(x["buy"])), idx.get_loc(pd.Timestamp(x["sell"]))
        j = col.get(x["t"])
        after = None
        if j is not None and x["why"] == "stop" and s + 20 < len(idx):      # where the stock was 20 days after a stop
            c0, c1 = F["Cf"][s, j], F["Cf"][s + 20, j]
            after = c1 / c0 - 1 if c0 == c0 and c1 == c1 else None
        spy = F["Cf"][s, M.bench] / F["Cf"][b, M.bench] - 1
        rows.append(dict(y=x["sell"][:4], ret=x["ret"], why=x["why"], days=s - b, after=after, spy=spy, t=x["t"],
                         sec=M.sector.get(x["t"], "")))
    df = pd.DataFrame(rows)
    out = {}
    for y, g in df.groupby("y"):
        w, l = g[g.ret > 0], g[g.ret <= 0]
        st = g[g.why == "stop"]
        out[y] = dict(n=len(g), win=round(len(w) / len(g) * 100), avg_win=round(w.ret.mean() * 100, 1) if len(w) else None,
                      avg_loss=round(l.ret.mean() * 100, 1) if len(l) else None, stops=len(st),
                      stops_pct=round(len(st) / len(g) * 100), med_days=float(g.days.median()),
                      stop_then_up=int((st.after > 0).sum()), stop_after_med=round(float(st.after.median()) * 100, 1) if st.after.notna().any() else None,
                      beat_spy=round(float((g.ret > g.spy).mean()) * 100), sum_ret=round(g.ret.sum() * 100, 1),
                      biggest_win=round(g.ret.max() * 100, 1), top_secs=g.sec.value_counts().head(3).to_dict())
    return out


def nights(M, F, A):
    """Per year: % of nights the market was over 75 (no buys), % with no buyable setup, % of days fully in cash."""
    idx = M.idx
    out = {}
    buy = F["buy"].any(1)
    for y in sorted(set(idx[M.t0:].year)):
        m = (idx.year == y) & (np.arange(len(idx)) >= M.t0)
        out[str(y)] = dict(mkt_hot=round(float(F["mkt_hot"][m].mean()) * 100), no_setup=round(float((~buy[m]).mean()) * 100),
                           setups_avg=round(float(F["buy"][m].sum(1).mean()), 1), invested=round(float(np.nanmean(A.inv[m])) * 100),
                           spy_over_e50=round(float((F["C"][m, M.bench] > F["e50"][m, M.bench]).mean()) * 100))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    PBT.CASH = PBT.START_CASH["stocks"]
    M = PBT.stocks(a.demo)
    F = PBT.feats(M)
    idx = M.idx
    t23 = int(np.searchsorted(idx, pd.Timestamp("2023-01-01")))
    bench = F["Cf"][:, M.bench]
    res = dict(asof=idx[-1].strftime("%Y-%m-%d"), demo=a.demo,
               spy=dict(all=cagr(bench, idx, M.t0), since23=cagr(bench, idx, t23), maxdd=maxdd(bench, M.t0), years=yearly(bench, idx, M.t0)), plans={})
    core_buy = F["setup"] & F["ok"] & F["core"]                     # any setup, not just the strongest-sector list
    no_hot = np.zeros_like(F["mkt_hot"])
    cool = F["setup"] & F["ok"] & F["core"] & F["sec_on"] & np.isfinite(F["strength"])   # the list without the sector 75 check
    up = F["ok"] & F["core"] & F["sec_on"] & ~F["sec_hot"] & np.isfinite(F["strength"])   # the list, uptrend only
    variants = [
        ("As it is", {}),
        ("No 8% stop (sell on your exit only)", dict(STOP=1.0)),
        ("15% stop instead of 8%", dict(STOP=0.15)),
        ("3 at a time, a third each (fully invested)", dict(A_SLOTS=3, A_CAP=0.34)),
        ("2 at a time, half each (fully invested)", dict(A_SLOTS=2, A_CAP=0.5)),
        ("Any setup, not just the strongest-sector list", dict(swap=dict(buy=core_buy))),
        ("Strongest list, any stock in your uptrend (no setup needed)", dict(swap=dict(buy=up))),
        ("Breadth over 75 doesn't block buys", dict(swap=dict(mkt_hot=no_hot))),
        # 2026-10-21, the user: "yes run test" on full investment + no 75 block together
        ("Half each + no market 75 block", dict(A_SLOTS=2, A_CAP=0.5, swap=dict(mkt_hot=no_hot))),
        ("A third each + no market 75 block", dict(A_SLOTS=3, A_CAP=0.34, swap=dict(mkt_hot=no_hot))),
        ("Half each + no 75 block at all (market or sector)", dict(A_SLOTS=2, A_CAP=0.5, swap=dict(mkt_hot=no_hot, buy=cool))),
        ("A third each + no 75 block at all (market or sector)", dict(A_SLOTS=3, A_CAP=0.34, swap=dict(mkt_hot=no_hot, buy=cool))),
    ]
    for k, when in (("A", "open"), ("C", "close")):
        rows = []
        for name, kw in variants:
            A = run(M, F, when, **kw)
            rows.append(dict(name=name, all=cagr(A.eq, idx, M.t0), since23=cagr(A.eq, idx, t23), trades=len(A.trades),
                             invested=round(float(np.nanmean(A.inv[M.t0:])) * 100), maxdd=maxdd(A.eq, M.t0),
                             final=round(float(pd.Series(A.eq).ffill().iloc[-1])), years=yearly(A.eq, idx, M.t0)))
            print(f"  {k} {name}: {rows[-1]} ({time.time() - t0:.0f}s)", flush=True)
            if not kw:
                base = A
        res["plans"][k] = dict(variants=rows, by_year=trade_stats(M, F, base), nights=nights(M, F, base))
    Path(a.out).write_text(json.dumps(res, separators=(",", ":"), default=float), encoding="utf-8")
    print(json.dumps(res["plans"]["A"]["by_year"], default=float)[:3000])
    print(json.dumps(res["plans"]["A"]["nights"]))
    print(f"Done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
