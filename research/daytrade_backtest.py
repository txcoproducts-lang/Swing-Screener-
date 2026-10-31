#!/usr/bin/env python3
"""
Day-trade backtest: your rules on 5-minute and 10-minute charts, every position sold by the close.

Each morning the stock list comes from last night's daily charts, the way you pick stocks:
  1. the market first: SPY in your uptrend (EMA10 > EMA20, price > EMA50 and the 150 line) and the S&P 500's breadth
     not over 75; otherwise no trades that day,
  2. then the strongest sector, strongest stock list (the page's score: 40% market breadth, 40% sector breadth, 20% the
     stock's strength in its sector; the sector in an upswing and not over 75, the stock in an uptrend), top 10.
Then the intraday chart decides when to buy and sell. Versions tested (each on 5-minute and 10-minute bars):
  open      buy the list at the open, sell at the close (no intraday timing; the yardstick)
  up        buy when the chart is in your uptrend without the 150 line (EMA10 > EMA20, price > EMA50)
  full      buy when the chart is in your full uptrend (adds price > the 150 line)
  full_spy  full, and SPY's own 5 / 10-minute chart is in the full uptrend at that moment too
  pull      full_spy, but buy only a pullback: the bar dips to the 20 EMA and closes back above it
  quick     full_spy, but sell as soon as EMA10 crosses under EMA20 (not waiting for the price to lose the 50 too)
  any_mkt   full_spy on any liquid S&P 500 / Nasdaq 100 stock, with last night's market check but no sector check
  any       full_spy on any liquid stock, skipping the daily market and sector checks
Sells: your exit on the same chart (a bar closes with EMA10 < EMA20 and price < EMA50; "quick" uses EMA10 < EMA20 alone),
or at the close. Signals are read at a bar's close and filled at the next bar's open, 0.05% worse (as the paper
accounts fill). No new buys after 3:30 PM New York. Today's signals only: a chart already up at the open is bought at
the second bar's open (9:35 on 5-minute, 9:40 on 10-minute), never the night before.

Account: $5,000 in shares, at most 3 positions at once, each 30% of the account's value at the open (Claude's default,
the paper accounts' 30% cap). Each version is also run under the pattern day trader rule (an account under $25,000 may
make only 3 day trades in any 5 trading days).

Limits: Yahoo keeps only about 60 days of 5-minute bars. With --store, every run adds its bars to the ones saved by
earlier runs (the workflow keeps them on the daytrade-backtest branch), so the test grows by a week each Saturday.
The first 5 days warm up the 150-bar line on the 10-minute chart; 10-minute bars are built from the 5-minute ones. Shares only (no intraday option prices).
Today's index members, so no survivorship correction (it matters little over 60 days).

Runs on GitHub Actions ("Day-trade backtest" in the Actions tab), where Yahoo and Wikipedia work:
    python research/daytrade_backtest.py --out daytrade_results
    python research/daytrade_backtest.py --demo --out /tmp/dt    # random walks, to test the code
"""
import argparse, json, sys, time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import screener as S                      # the stock page's rules and settings
import plan_backtest as PB                # the same daily list the paper plans' backtests use

CASH = 5000.0
SLIP = 0.0005
SLOTS, SIZE = 3, 0.30
LIST_N = 10
WARM_DAYS = 5
LAST_BUY = 15 * 60 + 30                   # minutes after midnight, New York
PDT = (3, 5)                              # at most 3 day trades in any 5 trading days under $25,000
VERSIONS = {
    "open": "Buy the list at the open, sell at the close",
    "up": "Uptrend on the chart (EMA10 > EMA20, price > EMA50)",
    "full": "Full uptrend on the chart (also over the 150 line)",
    "full_spy": "Full uptrend, and SPY's chart is in the full uptrend too",
    "pull": "Full uptrend + SPY up, buy a pullback to the 20 EMA",
    "quick": "Full uptrend + SPY up, sell when EMA10 crosses under EMA20",
    "any_mkt": "Full uptrend + SPY up, any liquid stock (market check, no sector check)",
    "any": "Full uptrend + SPY up, any liquid stock (no daily checks)",
}


# ---------------------------------------------------------------- data
def daily_list(frames, sectors, sp500):
    """For each day: the market gate and the stocks on the strongest sector, strongest stock list, best first."""
    names = sorted(frames)
    idx = frames["SPY"].index
    M = SimpleNamespace(P={k: S.wide(frames, k, idx)[names] for k in ("Open", "High", "Low", "Close", "Volume")},
                        cfg=S.CFG, year=252, idx=idx, names=names, sector=sectors,
                        member=np.array([[t in sp500 for t in names]] * len(idx)))
    F = PB.feats(M)
    j = names.index("SPY")
    gate = F["core"][:, j] & ~F["mkt_hot"]
    out, liquid = {}, {}
    for k, d in enumerate(idx):
        ok = F["ss_ok"][k]
        sc = np.where(ok, F["strength"][k], -np.inf)
        order = [names[i] for i in np.argsort(-sc) if ok[i]][:LIST_N]
        out[d.normalize()] = (bool(gate[k]), order)
        rs = np.where(F["liquid"][k] & np.isfinite(F["rs"][k]), F["rs"][k], -np.inf)
        liquid[d.normalize()] = [names[i] for i in np.argsort(-rs) if np.isfinite(rs[i])]
    return out, liquid


def session(d):
    if d.index.tz is not None:
        d = d.tz_convert("America/New_York").tz_localize(None)
    m = d.index.hour * 60 + d.index.minute
    return d[(m >= 9 * 60 + 30) & (m < 16 * 60)]


def to_10m(d):
    g = d.resample("10min")
    b = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(), "Close": g.Close.last(),
                      "Volume": g.Volume.sum()})
    return b.dropna(subset=["Close"])


def download_intraday(tickers):
    frames = {}
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        print(f"  5-minute bars {i + 1}-{i + len(chunk)} of {len(tickers)}", flush=True)
        frames.update(S.yf_batch(chunk, size=50, period="60d", interval="5m"))
        time.sleep(1)
    miss = [t for t in tickers if t not in frames]
    if miss:
        time.sleep(30)
        frames.update(S.yf_batch(miss, size=25, period="60d", interval="5m"))
    return {t: session(d) for t, d in frames.items() if len(d)}


def load_store(d):
    """The 5-minute bars saved by earlier runs: one gzipped pickle per month, {ticker: Open / Low / Close}."""
    out = {}
    for f in sorted(Path(d).glob("bars_*.pkl.gz")):
        for t, x in pd.read_pickle(f).items():
            out.setdefault(t, []).append(x)
    return {t: pd.concat(v) for t, v in out.items()}


def merge_store(d, new):
    """Adds this run's bars to the saved ones (this run wins where they overlap), saves them back, returns them all."""
    old = load_store(d)
    keep = ["Open", "High", "Low", "Close", "Volume"]
    allb = {}
    for t in set(old) | set(new):
        parts = [x for x in (old.get(t), new.get(t)) if x is not None]
        x = pd.concat(parts)
        x = x[~x.index.duplicated(keep="last")].sort_index()
        allb[t] = x.reindex(columns=keep)
    Path(d).mkdir(parents=True, exist_ok=True)
    months = sorted({m for x in allb.values() for m in x.index.to_period("M").unique()})
    for m in months:
        part = {t: x[x.index.to_period("M") == m][["Open", "Low", "Close"]].astype("float32") for t, x in allb.items()}
        pd.to_pickle({t: x for t, x in part.items() if len(x)}, Path(d) / f"bars_{m}.pkl.gz")
    # signals only need Open, Low and Close; High / Volume are kept for this run's bars only
    for t, x in allb.items():
        x["High"] = x["High"].fillna(x[["Open", "Close"]].max(axis=1))
        x["Volume"] = x["Volume"].fillna(0)
    print(f"  bars saved: {len(allb)} tickers, {months[0]} to {months[-1]}", flush=True)
    return {t: x.astype(float) for t, x in allb.items()}


def demo():
    """Driftless random walks: no version should make money here beyond luck, after costs it should lose a little."""
    rng = np.random.default_rng(3)
    days = pd.bdate_range(end="2026-10-30", periods=560)
    names = ["SPY"] + [f"DEMO{k:02d}" for k in range(60)]
    daily, intra = {}, {}
    bars = pd.timedelta_range("09:30:00", "15:55:00", freq="5min")
    last = days[-60:]
    for t in names:
        r = rng.normal(0, 0.015, len(days))
        c = 100 * np.cumprod(1 + r)
        daily[t] = pd.DataFrame({"Open": c / (1 + r), "High": c * 1.01, "Low": c * 0.99, "Close": c,
                                 "Volume": 3e6}, index=days)
        idx = pd.DatetimeIndex([d + b for d in last for b in bars])
        rr = rng.normal(0, 0.0015, len(idx))
        cc = 100 * np.cumprod(1 + rr)
        intra[t] = pd.DataFrame({"Open": cc / (1 + rr), "High": cc * 1.001, "Low": cc * 0.999, "Close": cc,
                                 "Volume": 1e5}, index=idx)
    sectors = {t: f"Sector {i % 5}" for i, t in enumerate(names)}
    return daily, intra, sectors, set(names) - {"SPY"}


# ---------------------------------------------------------------- signals
def signals(d):
    c = d.Close
    e10, e20, e50 = S.ema(c, 10), S.ema(c, 20), S.ema(c, 50)
    m150 = S.ema(c, 150) if S.CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()
    up = (e10 > e20) & (c > e50)
    full = up & (c > m150)
    return pd.DataFrame(dict(O=d.Open, C=c, up=up, full=full, pull=full & (d.Low <= e20) & (c > e20),
                             out=(e10 < e20) & (c < e50), quick=e10 < e20), index=d.index)


# ---------------------------------------------------------------- simulation
def simulate(sig, spy, lists, liquid, version, pdt=False):
    """One account through every day. sig: ticker -> signal frame; spy: SPY's signal frame (sets the bar clock)."""
    days = sorted(set(spy.index.normalize()))[WARM_DAYS:]
    dl = sorted(lists)
    cash, eq, trades, made = CASH, [], [], []
    for day in days:
        prior = [d for d in dl if d < day]
        if not prior:
            continue
        gate, names = lists[prior[-1]]
        if version in ("any", "any_mkt"):
            gate, names = gate or version == "any", liquid[prior[-1]]
        bars = spy.index[spy.index.normalize() == day]
        start_val, held = cash, {}
        size = start_val * SIZE
        rows = {t: {k: v.to_numpy() for k, v in sig[t].reindex(bars).items()} for t in names if t in sig} if gate else {}
        spy_up = spy.full.reindex(bars).to_numpy()
        ek = {"quick": "quick", "open": None}.get(version, "out")
        bk = version if version in ("up", "full", "pull") else "full"
        recent = sum(made[-(PDT[1] - 1):]) if PDT[1] > 1 else 0
        today = 0
        for i, b in enumerate(bars):
            m = b.hour * 60 + b.minute
            last = i == len(bars) - 1
            # sells: last bar's exit signal, filled at this bar's open
            for t in list(held):
                r = rows[t]
                px = r["O"][i]
                if ek and i > 0 and px == px and r[ek][i - 1] == True:
                    sh, cost, tin = held.pop(t)
                    cash += sh * px * (1 - SLIP)
                    trades.append(dict(t=t, day=str(day.date()), buy=str(tin.time())[:5], sell=str(b.time())[:5],
                                       ret=px * (1 - SLIP) * sh / cost - 1))
                    today += 1
            # buys
            if (len(held) < SLOTS and m <= LAST_BUY and not last
                    and not (pdt and recent + today >= PDT[0])):
                for t in names:
                    if t in held or t not in rows or len(held) >= SLOTS or (pdt and recent + today >= PDT[0]):
                        continue
                    r = rows[t]
                    px = r["O"][i]
                    if px != px:
                        continue
                    if version == "open":
                        go = i == 0
                    else:
                        go = i > 0 and r[bk][i - 1] == True
                        if version in ("full_spy", "pull", "quick", "any", "any_mkt"):
                            go = go and spy_up[i - 1] == True
                    spend = min(size, cash)
                    if go and spend > 50:
                        p = px * (1 + SLIP)
                        sh = spend / p
                        cash -= spend
                        held[t] = (sh, spend, b)
            # the close: sell what's left at this bar's close
            if last:
                for t in list(held):
                    r = rows[t]
                    px = r["C"][i]
                    if px != px:
                        px = sig[t].C[:b].dropna().iloc[-1]
                    sh, cost, tin = held.pop(t)
                    cash += sh * px * (1 - SLIP)
                    trades.append(dict(t=t, day=str(day.date()), buy=str(tin.time())[:5], sell="close",
                                       ret=px * (1 - SLIP) * sh / cost - 1))
                    today += 1
        made.append(today)
        eq.append((day, cash))
    return pd.Series(dict(eq)), trades


def stats(eq, trades, spy_daily):
    rets = np.array([x["ret"] for x in trades]) if trades else np.array([0.0])
    dd = float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0
    days = len(eq)
    traded = len({x["day"] for x in trades})
    win = rets[rets > 0]
    loss = rets[rets <= 0]
    s = spy_daily.reindex(eq.index, method="ffill")
    return dict(final=round(float(eq.iloc[-1]), 2), total=round((eq.iloc[-1] / CASH - 1) * 100, 1),
                maxdd=round(dd * 100, 1), days=days, days_traded=traded, trades=len(trades),
                per_week=round(len(trades) / max(days, 1) * 5, 1),
                win=round(float((rets > 0).mean()) * 100) if trades else None,
                avg=round(float(rets.mean()) * 100, 2) if trades else None,
                avg_win=round(float(win.mean()) * 100, 2) if len(win) else None,
                avg_loss=round(float(loss.mean()) * 100, 2) if len(loss) and trades else None,
                spy=round((s.iloc[-1] / s.iloc[0] - 1) * 100, 1) if len(s) > 1 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--store", help="folder of 5-minute bars saved by earlier runs; this run's bars are added to it")
    a = ap.parse_args()
    t0 = time.time()
    if a.demo:
        daily, intra, sectors, sp500 = demo()
    else:
        syms, sectors, _, sp500 = S.get_universe()
        tickers = sorted(set(syms) | {"SPY"})
        print(f"Daily prices for {len(tickers)} tickers...", flush=True)
        daily = S.download_with_retry(tickers)
        if "SPY" not in daily or len(daily) < 0.8 * len(tickers):
            sys.exit(f"Only {len(daily)} of {len(tickers)} tickers downloaded; not running on partial data.")
        print("5-minute prices...", flush=True)
        intra = download_intraday(sorted(daily))
        if "SPY" not in intra or len(intra) < 0.8 * len(daily):
            sys.exit(f"Only {len(intra)} of {len(daily)} tickers have 5-minute bars; not running on partial data.")
    if a.store:
        intra = merge_store(a.store, intra)
    lists, liquid = daily_list(daily, sectors, sp500)
    spy_close = daily["SPY"].Close
    res = dict(versions=VERSIONS, demo=a.demo, bars={}, trades={})
    for label, conv in (("5m", lambda d: d), ("10m", to_10m)):
        sig = {t: signals(conv(d)) for t, d in intra.items() if len(d) > 200}
        spy = sig["SPY"]
        res["bars"][label] = {}
        for v in VERSIONS:
            row = {}
            for pdt in (False, True):
                eq, tr = simulate(sig, spy, lists, liquid, v, pdt)
                row["pdt" if pdt else "free"] = stats(eq, tr, spy_close)
                if not pdt:
                    res["trades"][f"{label}_{v}"] = [dict(x, ret=round(x["ret"] * 100, 2)) for x in tr]
                    row["curve"] = [[d.strftime("%Y-%m-%d"), round(float(x), 2)] for d, x in eq.items()]
            res["bars"][label][v] = row
            print(f"  {label} {v:9s} {row['free']}", flush=True)
    days = sorted(set(intra["SPY"].index.normalize()))
    res["from"], res["to"] = str(days[WARM_DAYS].date()), str(days[-1].date())
    res["gate_days"] = sum(1 for d in days[WARM_DAYS:] if lists.get(max((x for x in lists if x < d), default=d), (False,))[0])
    res["n_days"] = len(days) - WARM_DAYS
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    (out / "summary.md").write_text(report(res), encoding="utf-8")
    print(report(res))
    print(f"Done in {time.time() - t0:.0f}s")


def report(res):
    L = [f"# Day-trade backtest, {res['from']} to {res['to']} ({res['n_days']} trading days)", "",
         f"Market check passed on {res['gate_days']} of {res['n_days']} days (no trades on the other days, except 'any').",
         "$5,000, shares, up to 3 at a time at 30% each, flat by the close, 0.05% slippage each way.", ""]
    for mode, title in (("free", "No day-trade limit"), ("pdt", "Under the $25,000 rule (3 day trades per 5 days)")):
        L += [f"## {title}", "", "| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for v, name in res["versions"].items():
            for b in ("5m", "10m"):
                s = res["bars"][b][v][mode]
                L.append(f"| {name} | {b} | {s['final']:,.0f} | {s['total']:+.1f}% | {s['maxdd']:.1f}% | {s['trades']} | "
                         f"{s['win'] if s['win'] is not None else '-'} | {s['avg'] if s['avg'] is not None else '-'}% | "
                         f"{s['avg_win'] if s['avg_win'] is not None else '-'}% | {s['avg_loss'] if s['avg_loss'] is not None else '-'}% |")
        s = res["bars"]["5m"]["open"]["free"]
        L += ["", f"SPY held over the same days: {s['spy']:+.1f}%", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
