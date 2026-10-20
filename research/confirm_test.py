#!/usr/bin/env python3
"""
The 2-day confirm test (the user's ask, 2026-10-20): "like OVTLYR has the 5 day confirm, add a 2 day confirm to my rules
and redo all tests; don't change anything until I see the results". Nothing live changes: this only reruns the tests
both ways and saves the numbers next to each other.

  today      buy at the next open after one close with a setup (as now)
  confirm    the setup has to hold on two closes in a row, then buy at the next open (one day later than today)

Exits, stops, sizing and everything else stay as they are. The OVTLYR plan is left out on purpose: it follows OVTLYR's
own rules (its "5 days" is a window: the 10/20 cross stays a valid signal for 5 market days).

Tests rerun, stocks and coins:
  A  Your system, C  Your system after 2 PM, B  Claude's picks (a new pick is bought after two nights on the list),
     the same whole-account backtests as the Backtests tab (research/plan_backtest.py), stocks also with modeled calls;
  the 10-year per-stock "your rules vs holding it" backtest (screener.py backtest()), on every current S&P 500 stock
  or every coin, with the same breadth the plans use.

    python research/confirm_test.py --market stocks --out research/confirm_stocks.json
    python research/confirm_test.py --market crypto --out research/confirm_crypto.json
    python research/confirm_test.py --market stocks --demo --out /tmp/c.json      # random walks, to test the code
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
import plan_backtest as PBT

CONFIRM = 2


def plans(M, F):
    unit = "coin" if M.kind == "crypto" else "stock"
    desc = {k: (PBT.NAMES[k], "") for k in "ACB"}
    runs = {"A": lambda o, c: PBT.run_system(M, F, "open", o, c), "C": lambda o, c: PBT.run_system(M, F, "close", o, c),
            "B": lambda o, c: PBT.run_ai(M, F, o, c)}
    out = {}
    for k, fn in runs.items():
        out[k] = {}
        for tag, c in (("today", 1), ("confirm", CONFIRM)):
            s = PBT.summary(M, fn(False, c), desc[k])
            if unit == "stock":
                w = PBT.summary(M, fn(True, c), desc[k])
                s["with_calls"] = {x: w[x] for x in ("final", "cagr", "maxdd", "trades", "calls", "win", "avg_trade")}
                s["with_calls"]["curve"] = [[d, v] for d, v, _ in w["curve"]]
            out[k][tag] = s
            print(f"  {k} {tag}: ${s['final']:,.0f} ({s['cagr']:+.1f}%/yr, worst drop {s['maxdd']:.0f}%, {s['trades']} trades, "
                  f"win {s['win']}%)" + (f"; calls ${s['with_calls']['final']:,.0f}" if "with_calls" in s else ""), flush=True)
    return out


def per_stock(M, F):
    mod = M.mod
    bj = PBT.breadth_json(M, F)
    idx = pd.DatetimeIndex(bj["dates"])
    br = {g: pd.DataFrame(dict(rise=v["rise"], avg=v["avg"]), index=idx, dtype=float) for g, v in bj["groups"].items()}
    bench = M.P["Close"].iloc[:, M.bench].dropna()
    if M.kind == "crypto":
        names = [t for t in M.names]
    else:
        names = [t for t in M.names if isinstance(M.sector.get(t), str) and M.member[-1, M.names.index(t)]]
    rows, res = [], {1: [], CONFIRM: []}
    for t in names:
        j = M.names.index(t)
        d = pd.DataFrame({k: M.P[k].iloc[:, j] for k in ("Open", "High", "Low", "Close", "Volume")}).dropna(subset=["Close"])
        r = {}
        for c in (1, CONFIRM):
            mod.BT["CONFIRM"] = c
            try:
                r[c] = mod.backtest(d, bench, br=br, group=M.sector.get(t))
            except Exception as e:
                print("  backtest failed", t, e)
                r[c] = None
        mod.BT["CONFIRM"] = 1
        if not (r[1] and r[CONFIRM]):
            continue
        for c in r:
            res[c].append(r[c])
        a, b = r[1], r[CONFIRM]
        rows.append([t, a["rules"], b["rules"], a["hold"], a["n"], b["n"], a["win"], b["win"], a["inmkt"], b["inmkt"]])

    def stats(L):
        g = lambda k: np.array([x[k] for x in L if x.get(k) is not None], float)
        rules, hold = g("rules"), g("hold")
        return dict(stocks=len(L), beat_hold=int((rules > hold).sum()), median_rules=round(float(np.median(rules)), 1),
                    mean_rules=round(float(np.mean(rules)), 1), median_hold=round(float(np.median(hold)), 1),
                    median_trades=float(np.median(g("n"))), trades=int(g("n").sum()), median_win=float(np.median(g("win"))),
                    median_inmkt=float(np.median(g("inmkt"))), made_money=int((rules > 0).sum()))
    out = dict(today=stats(res[1]), confirm=stats(res[CONFIRM]), rows=rows,
               cols=["ticker", "rules_today", "rules_confirm", "hold", "trades_today", "trades_confirm", "win_today",
                     "win_confirm", "inmkt_today", "inmkt_confirm"])
    better = sum(1 for x in rows if x[2] > x[1])
    out["confirm_better"], out["confirm_worse"] = better, sum(1 for x in rows if x[2] < x[1])
    print(f"  per-{'coin' if M.kind == 'crypto' else 'stock'}: {len(rows)} names; today {out['today']}; confirm {out['confirm']}; "
          f"confirm better on {better}, worse on {out['confirm_worse']}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="stocks", choices=("stocks", "crypto"))
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    PBT.CASH = PBT.START_CASH[a.market]
    M = PBT.stocks(a.demo) if a.market == "stocks" else PBT.crypto(a.demo)
    print(f"  {len(M.names)} tickers, {M.idx[M.t0].date()} to {M.idx[-1].date()} ({time.time() - t0:.0f}s)", flush=True)
    F = PBT.feats(M)
    res = dict(market=a.market, demo=a.demo, confirm=CONFIRM, cash=PBT.CASH, bench="BTC" if a.market == "crypto" else "SPY",
               asof=M.idx[-1].strftime("%Y-%m-%d"), plans=plans(M, F), per_stock=per_stock(M, F))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    print(f"Done in {time.time() - t0:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
