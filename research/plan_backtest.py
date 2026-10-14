#!/usr/bin/env python3
"""
Ten-year backtests of the four paper trading plans, for the page's Backtests tab.

  A  Your system               last night's setups on the strongest sector, strongest stock list, highest score first;
                               2 positions, each buy at most 30% of the account; sells on your exit (the 10 EMA under
                               the 20 and the price under the 50) or an 8% stop. Buys at the next open (about 10:00).
  C  Your system, after 2 PM   the same, but buys at the next day's close (the paper account buys at 3:00 PM New York).
  B  Claude's picks            the AI picks list (relative strength, hold 10, keep while in the top 20, max 3 per
                               sector), a tenth of the account each, also sold on your exit and not bought back while
                               it stays on the list.
  D  OVTLYR plan               Plan M with the page's stand-ins for OVTLYR's signals, else Plan ETF (TQQQ / SPXL on
                               QQQ's / SPY's signals), spare cash in T-bills (BIL, standing in for SGOV).

Your overbought rule applies to every plan: no buy with RSI over 70 or CCI over 100, or while the market's or the
stock's sector's breadth (Rising: the share of S&P 500 stocks with the 10 EMA over the 20) is over 75.

What a daily backtest can't copy from the paper accounts, and what it does instead:
  - Calls: there's no free history of option prices, so A and C buy shares (the paper accounts' fallback).
  - The 4-hour exit: Yahoo keeps about 2 years of intraday bars, so the exit is checked on daily closes.
  - OVTLYR's order block and earnings checks are left out (no earnings history; blocks would need every stock's).
Stocks: the S&P 500 as it was each day (rebuilt from Wikipedia's change log, so stocks that left the index count while
they were in it; ones that no longer trade on Yahoo are missing). Coins: today's ~100 largest, with the history each
has, so coins that died are missing and the results are flattered.

Runs on GitHub Actions ("Plan backtests" in the Actions tab), where Yahoo and Wikipedia work:
    python research/plan_backtest.py --market stocks --out history/plan_backtests.json
    python research/plan_backtest.py --market crypto --out crypto/history/plan_backtests.json
    python research/plan_backtest.py --demo --out /tmp/pb.json        # random walks, to test the code
"""
import argparse, datetime as dt, importlib.util, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import screener as S                      # the stock page's rules and settings

YEARS = 10
SLIP = 0.0005                             # every fill 0.05% worse, as in the paper accounts
CASH = 1000.0
STOP = 0.08                               # A / C share stop
A_SLOTS, A_CAP = 2, 0.30
D = dict(RISK=0.05, SIZE_ATR=2.0, STOP_ATR=0.5, EMERGENCY_ATR=2.0, MAX_DAYS=120, GAP=0.05, GAP_DAYS=3,
         LOSERS=3, PAUSE=7, MIN=25.0)
NAMES = {"A": "Your system", "C": "Your system, after 2 PM", "B": "Claude's picks", "D": "OVTLYR plan"}


def load_crypto_module():
    spec = importlib.util.spec_from_file_location("crypto_screener", ROOT / "crypto" / "screener.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- data
class Market:
    """Everything one market's plans need: wide price tables, members, sectors and settings."""

    def __init__(self, kind, frames, sector, member, bench, und, funds, cash_px=None, mod=S):
        self.kind, self.mod, self.cfg, self.ov = kind, mod, mod.CFG, mod.OV
        self.year = 365 if kind == "crypto" else 252
        idx = frames[bench].index
        start = idx[-1] - pd.DateOffset(years=YEARS)
        self.idx = idx
        self.t0 = int(np.searchsorted(idx, start))
        self.names = [t for t in frames if t not in set(funds)]
        self.P = {k: S.wide({t: frames[t] for t in self.names}, k, idx) for k in ("Open", "High", "Low", "Close", "Volume")}
        self.sector = sector
        self.member = member.reindex(index=idx, columns=self.names).fillna(False).to_numpy(bool)
        self.bench = self.names.index(bench)
        self.und = {f: self.names.index(u) for f, u in und.items() if u in self.names}
        fund_px = {}
        for f in und:                           # Plan ETF: the fund's own prices (or the coin itself for crypto)
            src = frames.get(f)
            if src is not None:
                fund_px[f] = {k: src[k].reindex(idx).to_numpy(float) for k in ("Open", "Close")}
        self.fund = fund_px
        self.cash_ret = (cash_px.reindex(idx).ffill().pct_change().fillna(0).to_numpy(float)
                         if cash_px is not None else np.zeros(len(idx)))


def feats(M):
    """dates x tickers numpy tables for every rule the plans use (the same formulas as screener.py)."""
    P, cfg, Y = M.P, M.cfg, M.year
    O, H, L, C, V = (P[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    alive = C.notna()
    e10, e20, e50 = (C.ewm(span=n, adjust=False).mean() for n in (10, 20, 50))
    m150 = C.ewm(span=150, adjust=False).mean() if cfg["LONG_MA_TYPE"] == "EMA" else C.rolling(150).mean()
    m200 = C.rolling(200).mean()
    r = S.rsi(C)
    pc = C.shift()
    tr = np.fmax(H - L, np.fmax((H - pc).abs(), (L - pc).abs()))
    a = tr.ewm(alpha=1 / 14, adjust=False).mean()
    tp = (H + L + C) / 3
    n = cfg["CCI_N"]
    sma = tp.rolling(n).mean()
    md = sum((tp.shift(k) - sma).abs() for k in range(n)) / n
    cc = (tp - sma) / (0.015 * md)
    hiY = C.rolling(Y, min_periods=200).max()
    prior20 = C.shift().rolling(20).max()
    core = (e10 > e20) & (C > e50) & (C > m150)
    ext = (C - e20) / a
    mom = core & (r >= 55) & (r <= 80) & (ext <= 3) & ((C > prior20) | (C >= 0.97 * hiY))
    x50150 = e50 > m150
    depth = (C.rolling(15).max() - C) / C.rolling(15).max() * 100
    pull = (C > e50) & (e20 > e50) & ((C > m150) | x50150) & (r <= 50) & ((C - e20) / e20 <= 0.02) & (depth >= 3)
    hot = (r > cfg["OB_RSI"]) | (cc > cfg["OB_CCI"])
    setup = (mom | pull) & ~hot & hiY.notna() & m150.notna()
    exit_ = (e10 < e20) & (C < e50)
    av = V.rolling(20).mean()
    liquid = (C >= cfg["MIN_PRICE"]) & (av >= cfg["MIN_AVG_VOL"]) & m200.notna()
    q = round(Y / 4)
    ret = lambda k: C / C.shift(k) - 1
    rs = 0.4 * ret(q) + 0.2 * ret(2 * q) + 0.2 * ret(3 * q) + 0.2 * ret(Y)
    cross = (e10 > e20) & ~(e10.shift() > e20.shift())
    age = S.days_since(cross)
    f = lambda x: x.where(alive).to_numpy(float) if x.dtypes.iloc[0] != bool else (x & alive).to_numpy(bool)
    F = dict(O=O.to_numpy(float), H=H.to_numpy(float), L=L.to_numpy(float), C=C.to_numpy(float),
             Cf=C.ffill().to_numpy(float), e10=f(e10), e20=f(e20), e50=f(e50), rsi=f(r), cci=f(cc), atr=f(a),
             core=f(core), setup=f(setup), exit=f(exit_), hot=f(hot), liquid=f(liquid), rs=f(rs), age=age.to_numpy(float))
    F["last"] = np.array([C[c].last_valid_index() for c in C.columns], dtype=object)
    F["lastpos"] = np.array([M.idx.get_loc(x) if x is not None else -1 for x in F["last"]])
    # breadth: Rising = the share of member stocks (all coins) with the 10 EMA over the 20, market and each sector
    bull = (e10 > e20).where(alive).to_numpy(float)
    mem = M.member & alive.to_numpy(bool)
    secs = np.array([M.sector.get(t) if isinstance(M.sector.get(t), str) else "" for t in M.names], dtype=object)
    # stocks with no known sector (most former S&P 500 members) count in the market's breadth only
    groups = {"_mkt": np.ones(len(M.names), bool), **{g: secs == g for g in sorted(set(secs) - {""})}}
    rise, avg = {}, {}
    for g, cols in groups.items():
        m = mem & cols[None, :]
        cnt = m.sum(1)
        x = pd.Series(np.where(cnt >= 5, np.nansum(np.where(m, bull, 0), 1) / np.maximum(cnt, 1) * 100, np.nan), index=M.idx)
        rise[g], avg[g] = x.to_numpy(), x.ewm(span=10, adjust=False).mean().to_numpy()
    F.update(secs=secs, groups=groups, rise=rise, ravg=avg)
    lim = cfg["OB_BREADTH"]
    F["mkt_hot"] = rise["_mkt"] > lim
    sr = np.column_stack([rise.get(s, np.full(len(M.idx), np.nan)) for s in secs])
    sa = np.column_stack([avg.get(s, np.full(len(M.idx), np.nan)) for s in secs])
    F["sec_rise"], F["sec_on"] = sr, np.round(sr, 1) > np.round(sa, 1)
    F["sec_hot"] = sr > lim
    ok = F["liquid"] & M.member
    F["ok"] = ok
    # strongest sector, strongest stock: 40% market, 40% sector, 20% the stock's RS rank inside its sector
    rsd = pd.DataFrame(np.where(ok, F["rs"], np.nan), index=M.idx)
    pct = np.full(rsd.shape, np.nan)
    for g, cols in groups.items():
        if g == "_mkt":
            continue
        j = np.flatnonzero(cols)
        pct[:, j] = rsd.iloc[:, j].rank(axis=1, pct=True, method="max").to_numpy() * 100
    F["strength"] = 0.4 * rise["_mkt"][:, None] + 0.4 * sr + 0.2 * pct
    F["ss_ok"] = ok & F["core"] & F["sec_on"] & ~F["sec_hot"] & ~F["hot"] & np.isfinite(F["strength"])
    F["rs_pct"] = rsd.rank(axis=1, pct=True).to_numpy()
    return F


# ---------------------------------------------------------------- the account
class Acct:
    def __init__(self, M, F):
        self.M, self.F, self.cash, self.pos, self.trades = M, F, CASH, {}, []
        self.eq = np.full(len(M.idx), np.nan)
        self.inv = np.full(len(M.idx), np.nan)
        self.earn_cash = False

    def value(self, t, at="C"):
        v = self.cash
        for j, p in self.pos.items():
            v += p["sh"] * self.mark(t, j, at)
        return v

    def mark(self, t, j, at="C"):
        if isinstance(j, str):
            fp = self.M.fund[j]
            x = fp["Open" if at == "O" else "Close"][t]
            if x != x:
                x = pd.Series(fp["Close"][:t + 1]).ffill().iloc[-1]
            return x
        x = self.F["O" if at == "O" else "C"][t, j]
        return x if x == x else self.F["Cf"][t, j]

    def buy(self, t, j, dollars, at, **kw):
        px = self.mark(t, j, at)
        dollars = min(dollars, self.cash)
        if not px == px or px <= 0 or dollars < 1:
            return False
        fill = px * (1 + SLIP)
        self.cash -= dollars
        self.pos[j] = dict(sh=dollars / fill, px=fill, t=t, at=at, cost=dollars, **kw)
        return True

    def sell(self, t, j, px=None, at="C", why=""):
        p = self.pos.pop(j)
        px = (px if px is not None else self.mark(t, j, at)) * (1 - SLIP)
        self.cash += p["sh"] * px
        name = j if isinstance(j, str) else self.M.names[j]
        self.trades.append(dict(t=name, buy=self.M.idx[p["t"]].strftime("%Y-%m-%d"), sell=self.M.idx[t].strftime("%Y-%m-%d"),
                                ret=px / p["px"] - 1, why=why))
        return px / p["px"] - 1

    def dead(self, t):
        """Stocks with no prices after today (left Yahoo): sold at their last close."""
        for j in [j for j in self.pos if not isinstance(j, str) and self.F["lastpos"][j] <= t and self.F["lastpos"][j] < len(self.M.idx) - 1]:
            self.sell(t, j, self.F["Cf"][t, j], why="no more prices")

    def close_day(self, t):
        if self.earn_cash:                          # spare cash in T-bills (OVTLYR's SGOV)
            self.cash *= 1 + self.M.cash_ret[t]
        assert self.cash > -0.01, f"cash went negative on {self.M.idx[t].date()}"
        v = self.value(t)
        self.eq[t] = v
        self.inv[t] = 1 - self.cash / v if v > 0 else 0


def stops(A, t, level_of):
    """Intraday stops: sell at the stop, or at the open if it gapped under it."""
    for j in list(A.pos):
        if isinstance(j, str):
            continue
        lv = level_of(A.pos[j])
        if lv is None:
            continue
        lo = A.F["L"][t, j]
        if lo == lo and lo <= lv:
            o = A.F["O"][t, j]
            A.sell(t, j, min(o, lv) if o == o else lv, why="stop")


# ---------------------------------------------------------------- A and C: your system
def run_system(M, F, when):
    A = Acct(M, F)
    pend = set()                                    # exits decided last night, sold at this open
    for t in range(M.t0, len(M.idx)):
        for j in list(pend):
            if j in A.pos:
                A.sell(t, j, at="O", why="your exit")
        pend.clear()
        night = t - 1

        def buys(at):
            if F["mkt_hot"][night]:
                return
            free = A_SLOTS - len(A.pos)
            if free <= 0:
                return
            c = np.flatnonzero(F["setup"][night] & F["ss_ok"][night])
            c = [j for j in c[np.argsort(-F["strength"][night, c], kind="stable")] if j not in A.pos]
            for j in c[:free]:
                A.buy(t, j, min(A_CAP * A.value(t, at), A.cash), at)
        if when == "open":
            buys("O")
        stops(A, t, lambda p: p["px"] * (1 - STOP) if not (p["at"] == "C" and p["t"] == t) else None)
        if when == "close":
            buys("C")
        A.dead(t)
        for j, p in A.pos.items():                  # your exit on tonight's close: sold at the next open
            if F["exit"][t, j] and not (p["at"] == "C" and p["t"] == t):
                pend.add(j)
        A.close_day(t)
    return A


# ---------------------------------------------------------------- B: Claude's picks
def run_ai(M, F):
    A = Acct(M, F)
    cfg = M.cfg
    names = np.array(M.names, dtype=object)
    held, outx, sells, adds = [], set(), [], []
    col = {t: j for j, t in enumerate(M.names)}
    for t in range(M.t0, len(M.idx)):
        for k in sells:
            j = col[k]
            if j in A.pos:
                A.sell(t, j, at="O", why="left the list or your exit")
        for k in adds:
            A.buy(t, col[k], A.value(t, "O") / cfg["AI_N"], "O")
        A.dead(t)
        ok = F["ok"][t] & np.isfinite(F["rs_pct"][t])
        row = pd.Series(F["rs_pct"][t, ok], index=names[ok])
        top = set(row.sort_values(ascending=False, kind="stable").index[:cfg["AI_KEEP"]])
        outx &= top                                 # sold on your exit: not bought back while it stays on the list
        sell = {k for k in held if F["exit"][t, col[k]]}
        outx |= sell
        skip = set(names[F["hot"][t] | F["sec_hot"][t]]) | outx
        kept, added, dropped = S.ai_step(held, row, M.sector, n=cfg["AI_N"], keep=cfg["AI_KEEP"], cap=cfg["AI_CAP"],
                                         allow_new=not F["mkt_hot"][t], sell=sell, skip=skip)
        held, sells, adds = kept + added, dropped, added
        A.close_day(t)
    return A


# ---------------------------------------------------------------- D: OVTLYR plan
def run_ov(M, F):
    A = Acct(M, F)
    A.earn_cash = True
    ov, b = M.ov, M.bench
    secs, rise, ravg = F["secs"], F["rise"], F["ravg"]
    R, C, e10, e20, e50, atr = F["rsi"], F["C"], F["e10"], F["e20"], F["e50"], F["atr"]
    lo, hi = ov["PRICE"]
    gap = np.zeros_like(C, bool)
    gap[1:] = F["O"][1:] / C[:-1] - 1 >= D["GAP"]
    sec_avg_rsi = {}
    for g, cols in F["groups"].items():
        if g == "_mkt":
            continue
        m = F["ok"] & cols[None, :]
        sec_avg_rsi[g] = np.where(m.sum(1) >= 5, np.nansum(np.where(m, R, 0), 1) / np.maximum(m.sum(1), 1), np.nan)

    def idx_ok(j, t):
        """Plan ETF's checks on an index (or coin): heat, signal, uptrend, value zone, CCI, market breadth."""
        c, x10, x20 = C[t, j], e10[t, j], e20[t, j]
        return (R[t, j] < ov["HEAT_MAX"] and x10 > x20 and c > e50[t, j] and x20 <= c <= x20 + ov["ZONE_ATR"] * atr[t, j]
                and not F["cci"][t, j] > M.cfg["OB_CCI"] and not F["mkt_hot"][t])

    pause_until, morning, etf_sell = -1, set(), set()
    for t in range(M.t0, len(M.idx)):
        n = t - 1
        # the morning: last night's exits, then new trades
        for j in list(morning) + list(etf_sell):
            if j in A.pos:
                A.sell(t, j, at="O", why="morning exit")
        morning, etf_sell = set(), set()
        mkt = (R[n, b] < ov["HEAT_MAX"] and R[n, b] > R[n - 1, b] and e10[n, b] > e20[n, b] and C[n, b] > e50[n, b]
               and rise["_mkt"][n] > ravg["_mkt"][n] and not F["mkt_hot"][n])
        took = False
        if mkt and C[n, b] >= e20[n, b] and t > pause_until:
            sec_ok = {}
            for g in sec_avg_rsi:
                ra = sec_avg_rsi[g]
                sec_ok[g] = (g not in ov["EXCLUDE"] and rise[g][n] > ravg[g][n] and ra[n] > R[n, b] and ra[n] < ov["HEAT_MAX"]
                             and ra[n] > ra[n - 1] and not rise[g][n] > M.cfg["OB_BREADTH"])
            cand = (F["ok"][n] & (C[n] >= lo) & (C[n] <= hi) & (F["age"][n] <= ov["SIGNAL_DAYS"] - 1) & (e10[n] > e20[n])
                    & (C[n] > e50[n]) & (C[n] > e10[n]) & (R[n] > R[n - 1]) & ~F["hot"][n])
            c = [j for j in np.flatnonzero(cand) if sec_ok.get(secs[j]) and j not in A.pos]
            c.sort(key=lambda j: (F["age"][n, j], -(F["rs"][n, j] if F["rs"][n, j] == F["rs"][n, j] else -9)))
            for j in c:
                if A.cash < D["MIN"]:
                    break
                o = A.mark(t, j, "O")
                want = A.value(t, "O") * D["RISK"] / (D["SIZE_ATR"] * atr[n, j]) * o
                if min(want, A.cash) >= D["MIN"]:
                    A.buy(t, j, want, "O", atr=atr[n, j], r0=R[n, j], kind="M")
                    took = True
        if not took and A.cash >= D["MIN"]:
            funds = [f for f, j in M.und.items() if f in M.fund and f not in A.pos and idx_ok(j, n)]
            cash = A.cash
            for f in funds:
                A.buy(t, f, cash / len(funds), "O", kind="ETF")
        # the day: the emergency exit, then the closing-price exits
        stops(A, t, lambda p: p["px"] - D["EMERGENCY_ATR"] * p["atr"] if p.get("kind") == "M" else None)
        A.dead(t)
        losers = 0
        for j in [j for j in A.pos if not isinstance(j, str)]:
            p, c = A.pos[j], C[t, j]
            if c != c:
                continue
            r0 = p["r0"]
            target = 63 if r0 < 50 else r0 + 10 if r0 < 75 else r0 + 5
            g = [k for k in range(max(p["t"], t - D["GAP_DAYS"]), t) if gap[k, j]]
            why = ("stop" if c < p["px"] - D["STOP_ATR"] * p["atr"] else "10/20 cross" if e10[t, j] < e20[t, j]
                   else "SPY under its 20 EMA" if C[t, b] < e20[t, b] else "RSI target" if R[t, j] >= target
                   else "gap and crap" if any(c < F["L"][k, j] for k in g) else "")
            if why:
                losers += A.sell(t, j, c, why=why) < 0
            elif (rise.get(secs[j], np.zeros(1))[t:t + 1] < ravg.get(secs[j], np.zeros(1))[t:t + 1]).any() \
                    or (M.idx[t] - M.idx[p["t"]]).days >= D["MAX_DAYS"]:
                morning.add(j)
        if losers >= D["LOSERS"]:
            pause_until = int(np.searchsorted(M.idx, M.idx[t] + pd.Timedelta(days=D["PAUSE"])))
        for f in [f for f in A.pos if isinstance(f, str)]:
            j = M.und[f]
            if e10[t, j] < e20[t, j] or C[t, j] > e20[t, j] + ov["HOT_ATR"] * atr[t, j]:
                etf_sell.add(f)
        A.close_day(t)
    return A


# ---------------------------------------------------------------- results
def summary(M, A, desc):
    idx = M.idx[M.t0:]
    eq = pd.Series(A.eq[M.t0:], index=idx).ffill()
    bc = pd.Series(M.P["Close"].iloc[M.t0:, M.bench].to_numpy(float), index=idx).ffill()
    bench = CASH * bc / bc.iloc[0]
    yrs = (idx[-1] - idx[0]).days / 365.25
    dd = lambda s: float((s / s.cummax() - 1).min())
    wk = eq.resample("W-FRI").last().dropna()
    bw = bench.resample("W-FRI").last().reindex(wk.index)
    curve = [[d.strftime("%Y-%m-%d"), round(float(v), 2), round(float(x), 2)] for d, v, x in zip(wk.index, wk, bw)]
    curve[-1][0] = idx[-1].strftime("%Y-%m-%d")
    years = {}
    for y in sorted(set(idx.year)):
        e, s = eq[eq.index.year == y], bench[bench.index.year == y]
        pe, ps = eq[eq.index.year < y], bench[bench.index.year < y]
        e0, s0 = (pe.iloc[-1] if len(pe) else CASH), (ps.iloc[-1] if len(ps) else CASH)
        years[str(y)] = [round((e.iloc[-1] / e0 - 1) * 100, 1), round((s.iloc[-1] / s0 - 1) * 100, 1)]
    tr = A.trades
    rets = np.array([x["ret"] for x in tr]) if tr else np.array([])
    return dict(
        name=desc[0], rules=desc[1], start=idx[0].strftime("%Y-%m-%d"), end=idx[-1].strftime("%Y-%m-%d"), years=round(yrs, 1),
        final=round(float(eq.iloc[-1]), 2), total=round((eq.iloc[-1] / CASH - 1) * 100, 1),
        cagr=round(((eq.iloc[-1] / CASH) ** (1 / yrs) - 1) * 100, 1), maxdd=round(dd(eq) * 100, 1),
        bench_final=round(float(bench.iloc[-1]), 2), bench_total=round((bench.iloc[-1] / CASH - 1) * 100, 1),
        bench_cagr=round(((bench.iloc[-1] / CASH) ** (1 / yrs) - 1) * 100, 1), bench_maxdd=round(dd(bench) * 100, 1),
        trades=len(tr), win=round(float((rets > 0).mean()) * 100) if len(rets) else None,
        avg_trade=round(float(rets.mean()) * 100, 1) if len(rets) else None,
        median_trade=round(float(np.median(rets)) * 100, 1) if len(rets) else None,
        invested=round(float(np.nanmean(A.inv[M.t0:])) * 100), curve=curve, by_year=years,
        last_trades=[dict(x, ret=round(x["ret"] * 100, 1)) for x in tr[-12:]])


def run_all(M):
    t0 = time.time()
    F = feats(M)
    print(f"  signals ready ({time.time() - t0:.0f}s)", flush=True)
    unit, bn = ("coin", "BTC") if M.kind == "crypto" else ("stock", "SPY")
    desc = {
        "A": (NAMES["A"], f"Last night's setups on the strongest sector, strongest {unit} list, highest score first; 2 at a time, "
                          f"each at most 30% of the account; sells on your exit (10 EMA under the 20 and price under the 50) or an 8% stop. "
                          f"Buys at the next open." + (" Shares, not calls: there's no free history of option prices." if unit == "stock" else "")),
        "C": (NAMES["C"], "The same rules as Your system, but it buys at the next day's close, standing in for after 2 PM."),
        "B": (NAMES["B"], f"AI picks list: top relative strength, hold 10, keep while in the top 20, max 3 per "
                          f"{'category' if unit == 'coin' else 'sector'}, a tenth of the account each; also sold on your exit."),
        "D": (NAMES["D"], ("Plan M on the page's stand-ins for OVTLYR's signals, else Plan ETF (" +
                           ("BTC / ETH on their own signals), spare cash as cash." if unit == "coin" else
                            "TQQQ / SPXL on QQQ's / SPY's signals), spare cash in T-bills (BIL for SGOV).") +
                           " Order block and earnings checks left out.")),
    }
    out = {}
    for k, fn in (("A", lambda: run_system(M, F, "open")), ("C", lambda: run_system(M, F, "close")),
                  ("B", lambda: run_ai(M, F)), ("D", lambda: run_ov(M, F))):
        A = fn()
        out[k] = summary(M, A, desc[k])
        s = out[k]
        print(f"  {k} {s['name']}: ${s['final']:,.0f} ({s['cagr']:+.1f}%/yr, worst drop {s['maxdd']:.0f}%, {s['trades']} trades, "
              f"in the market {s['invested']}%) vs {bn} ${s['bench_final']:,.0f} ({s['bench_cagr']:+.1f}%/yr) ({time.time() - t0:.0f}s)", flush=True)
    return dict(market=M.kind, bench=bn, asof=M.idx[-1].strftime("%Y-%m-%d"), built=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                universe=(f"{int(M.member[M.t0:].sum(1).mean())} S&P 500 stocks a day, as the index was each day" if unit == "stock"
                          else f"{len(M.names)} of today's largest coins, each from its first day on Yahoo"),
                plans=out)


# ---------------------------------------------------------------- loading
def stocks(demo=False, seed=5):
    import picks_backtest as PB
    start = (pd.Timestamp.today() - pd.DateOffset(years=YEARS + 2)).strftime("%Y-%m-%d")
    PB.START, PB.TEST_FROM, PB.OTHER = start, (pd.Timestamp.today() - pd.DateOffset(years=YEARS)).strftime("%Y-%m-%d"), ()
    extra = ["SPY", "QQQ", "TQQQ", "SPXL", "BIL"]
    if demo:
        frames, info, spans = PB.demo_data(n=260, days=3200, seed=seed)
        rng = np.random.default_rng(seed + 1)
        spy = frames["SPY"]
        for k, lev in (("QQQ", 1.1), ("TQQQ", 3.3), ("SPXL", 3.0)):
            r = spy.Close.pct_change().fillna(0) * lev + rng.normal(0, 0.002, len(spy))
            c = 100 * (1 + r).cumprod()
            frames[k] = pd.DataFrame({"Open": c.shift().fillna(c.iloc[0]), "High": c * 1.01, "Low": c * 0.99, "Close": c,
                                      "Volume": 5e6}, index=spy.index)
        frames["BIL"] = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": np.cumprod(np.full(len(spy), 1.0001)),
                                      "Volume": 1e6}, index=spy.index)
        now = set(spans)
    else:
        info, spans, now, former = PB.universe()
        tickers = sorted(info) + extra
        frames = PB.download(tickers)
        miss = [t for t in tickers if t not in frames and (t in now or t in extra)]
        if miss:
            time.sleep(30)
            frames.update(PB.download(miss, size=25))
        got = sum(t in frames for t in now)
        if got < 0.8 * len(now) or any(t not in frames for t in extra):
            sys.exit(f"Only {got} of {len(now)} S&P 500 members (or not every fund) downloaded; not running on partial data.")
        print(f"  {got} of {len(now)} members and {sum(t in frames for t in former)} of {len(former)} former members have prices", flush=True)
    idx = frames["SPY"].index
    stock_t = [t for t in frames if t not in ("QQQ", "TQQQ", "SPXL", "BIL")]
    member = pd.DataFrame(False, index=idx, columns=stock_t)
    for t in stock_t:
        for s0, s1 in spans.get(t, []):
            member.loc[(idx >= s0) & (idx < s1), t] = True
    member["SPY"] = False
    keep = {t: frames[t] for t in stock_t + ["QQQ"]}           # QQQ: Plan ETF's signals (not a member, never bought)
    member["QQQ"] = False
    sector = {t: info[t]["sector"] for t in info if isinstance(info[t].get("sector"), str)}
    funds = {"TQQQ": frames["TQQQ"], "SPXL": frames["SPXL"]}
    return Market("stocks", {**keep, **funds}, sector, member, "SPY", {"TQQQ": "QQQ", "SPXL": "SPY"}, ("TQQQ", "SPXL"),
                  cash_px=frames["BIL"]["Close"])


def crypto(demo=False):
    CS = load_crypto_module()
    tickers, sectors, _, _ = CS.get_universe()
    if demo:
        frames = CS.demo_frames(n=60, days=3000)
        frames = {t: d.assign(Volume=d.Volume * 10) for t, d in zip(tickers, frames.values())}   # dollars traded
        frames["BTC"], frames["ETH"] = frames.get("BTC", next(iter(frames.values()))), frames.get("ETH", next(iter(frames.values())))
    else:
        frames = CS.download(tickers, period="max")
        miss = [t for t in tickers if t not in frames]
        if len(miss) > 10:
            time.sleep(60)
            frames.update(CS.download(miss, size=10, period="max"))
        if "BTC" not in frames or len(frames) < 0.8 * len(tickers):
            sys.exit(f"Only {len(frames)} of {len(tickers)} coins downloaded; not running on partial data.")
    idx = frames["BTC"].index
    member = pd.DataFrame(True, index=idx, columns=list(frames))
    funds = {"BTC*": frames["BTC"], "ETH*": frames["ETH"]}       # Plan ETF holds the coin itself, on its own signals
    return Market("crypto", {**frames, **funds}, sectors, member, "BTC", {"BTC*": "BTC", "ETH*": "ETH"}, ("BTC*", "ETH*"), mod=CS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="stocks", choices=("stocks", "crypto"))
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    print(f"Prices ({a.market})...", flush=True)
    M = stocks(a.demo) if a.market == "stocks" else crypto(a.demo)
    print(f"  {len(M.names)} tickers, {M.idx[M.t0].date()} to {M.idx[-1].date()} ({time.time() - t0:.0f}s)", flush=True)
    res = run_all(M)
    res["demo"] = a.demo
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    print(f"Done in {time.time() - t0:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
