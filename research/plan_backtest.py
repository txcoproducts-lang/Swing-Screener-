#!/usr/bin/env python3
"""
Ten-year backtests of the four paper trading plans, for the page's Backtests tab.

  A  Your system               last night's setups on the strongest sector, strongest stock list, highest score first;
                               2 positions, each buy at most 30% of the account: a call by your rules when one fits
                               (nearest 0.65 delta at 0.50-0.80, else the highest delta down to 0.15), else shares;
                               sells on your exit (the 10 EMA under the 20 and the price under the 50), calls also at
                               -50% or 5 days before expiry, shares on an 8% stop. Buys at the next open (about 10:00).
  C  Your system, after 2 PM   the same, but buys at the next day's close (the paper account buys at 3:00 PM New York).
  B  Claude's picks            the AI picks list (relative strength, hold 10, keep while in the top 20, max 3 per
                               sector), a tenth of the account each (a call by your rules when one fits, else shares),
                               also sold on your exit (or a call's -50%) and not bought back while it stays on the list.
  D  OVTLYR plan               Plan M with the page's stand-ins for OVTLYR's signals (a call by your rules within the
                               plan's size and 30% of the account, else shares), else Plan ETF (TQQQ / SPXL on QQQ's /
                               SPY's signals), spare cash in T-bills (BIL, standing in for SGOV).
Stocks start with $5,000 a plan and coins with $1,000, as the paper accounts do (stocks restarted at $5,000 on 2026-10-15).

Your overbought rule applies to every plan: no buy while the market's or the stock's sector's breadth (Rising: the
share of S&P 500 stocks with the 10 EMA over the 20) is over 75. RSI and CCI no longer count (the user, 2026-10-15).

What a daily backtest can't copy from the paper accounts, and what it does instead:
  - Calls: there's no free history of option prices, so the plan lines use shares (the paper accounts' fallback). Each
    plan is also run with calls (saved as with_calls, shown on its card as a rough guide): each call is priced with Black-Scholes on the stock's own
    30-day volatility x 1.1 (at least 15%), 30 days out, strikes on the usual grid, bought 3% over and sold 3% under the
    model price, plus $0.65 a contract each way. Real quotes differ; read the call plans' results as a rough guide.
    Coins have no options, so the crypto plans buy coins.
  - The 4-hour exit: Yahoo keeps about 2 years of intraday bars, so the exit is checked on daily closes.
  - OVTLYR's order block and earnings checks are left out (no earnings history; blocks would need every stock's).
Stocks: the S&P 500 as it was each day (rebuilt from Wikipedia's change log, so stocks that left the index count while
they were in it; ones that no longer trade on Yahoo are missing). Coins: today's ~100 largest, with the history each
has, so coins that died are missing and the results are flattered.

Runs on GitHub Actions ("Plan backtests" in the Actions tab), where Yahoo and Wikipedia work:
    python research/plan_backtest.py --market stocks --out history/plan_backtests.json --breadth history/breadth_10y.json
    python research/plan_backtest.py --market crypto --out crypto/history/plan_backtests.json --breadth crypto/history/breadth_10y.json
    python research/plan_backtest.py --demo --out /tmp/pb.json        # random walks, to test the code
--breadth also saves the 10 years of market and sector breadth, so the nightly per-stock backtest (screener.py
backtest()) can check the same strongest-sector list and overbought breadth that Your system buys on.
"""
import argparse, datetime as dt, importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import screener as S                      # the stock page's rules and settings

YEARS = 10
SLIP = 0.0005                             # every fill 0.05% worse, as in the paper accounts
CASH = 5000.0                             # set per market in main(): stocks $5,000, coins $1,000 (the paper accounts)
START_CASH = dict(stocks=5000.0, crypto=1000.0)
OPT = dict(DTE=30, MID=0.65, DELTA=(0.50, 0.80), LO=0.15, STOP=0.50, EXIT_DTE=5, FEE=0.65, HALF=0.03, IV_X=1.1,
           IV_MIN=0.15, RATE=0.03, SCAN=15)        # the paper accounts' call rules, and how the model prices them
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
    setup = (mom | pull) & hiY.notna() & m150.notna()      # RSI / CCI overbought checks dropped by the user, 2026-10-15
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
             core=f(core), setup=f(setup), exit=f(exit_), liquid=f(liquid), rs=f(rs), age=age.to_numpy(float))
    vol = np.log(C).diff().rolling(30, min_periods=20).std() * np.sqrt(M.year)
    F["iv"] = (vol * OPT["IV_X"]).clip(OPT["IV_MIN"], 2.5).ffill().fillna(0.4).to_numpy(float)
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
    F["ss_ok"] = ok & F["core"] & F["sec_on"] & ~F["sec_hot"] & np.isfinite(F["strength"])
    F["rs_pct"] = rsd.rank(axis=1, pct=True).to_numpy()
    return F


# ---------------------------------------------------------------- calls
_erf = np.vectorize(math.erf)
N = lambda x: 0.5 * (1 + _erf(np.asarray(x, float) / math.sqrt(2)))


def bs(S, K, T, v):
    """Black-Scholes call price and delta (per share)."""
    K = np.asarray(K, float)
    if T <= 0:
        return np.maximum(S - K, 0.0), (S > K).astype(float)
    sq = v * math.sqrt(T)
    d1 = (np.log(S / K) + (OPT["RATE"] + v * v / 2) * T) / sq
    return S * N(d1) - K * math.exp(-OPT["RATE"] * T) * N(d1 - sq), N(d1)


def pick_call(S, v, budget):
    """The call paper.py's pick_call would take within budget, on modeled prices: of the calls DTE days out at 0.50-0.80
    delta that fit, the nearest 0.65; else the highest delta down to 0.15 that fits; else None (then shares)."""
    if not (S == S and S > 0 and v == v) or budget < 1:
        return None
    T = OPT["DTE"] / 365
    g = 0.5 if S < 25 else 1.0 if S < 100 else 2.5 if S < 250 else 5.0
    w = 2.5 * v * math.sqrt(T)
    K = np.arange(max(g, math.floor(S * math.exp(-w) / g) * g), S * math.exp(w) + g, g)
    px, d = bs(S, K, T, v)
    cost = px * (1 + OPT["HALF"]) * 100 + OPT["FEE"]
    ok = (d >= OPT["LO"]) & (d <= OPT["DELTA"][1]) & (cost <= budget) & (px >= 0.05)
    band = ok & (d >= OPT["DELTA"][0])
    if band.any():
        i = np.flatnonzero(band)[np.argmin(np.abs(d[band] - OPT["MID"]))]
    elif ok.any():
        i = np.flatnonzero(ok)[np.argmax(d[ok])]
    else:
        return None
    return dict(K=float(K[i]), ask=float(px[i] * (1 + OPT["HALF"])), delta=float(d[i]), cost=float(cost[i]), band=bool(band.any()))


# ---------------------------------------------------------------- the account
class Acct:
    def __init__(self, M, F, options=True):
        self.M, self.F, self.cash, self.pos, self.trades = M, F, CASH, {}, []
        self.options = options and M.kind == "stocks"   # coins have no options
        self.eq = np.full(len(M.idx), np.nan)
        self.inv = np.full(len(M.idx), np.nan)
        self.earn_cash = False

    def value(self, t, at="C"):
        v = self.cash
        for j, p in self.pos.items():
            v += self.worth(t, j, p, at=at)
        return v

    def worth(self, t, j, p, S=None, at="C", side=0):
        """What a position is worth: shares at the price; a call at the model's mid (side -1: the bid, after fees)."""
        S = self.mark(t, j, at) if S is None else S
        if p.get("kind") != "call":
            return p["sh"] * S
        T = (p["exp"] - self.M.idx[t]).days / 365
        v = self.F["iv"][t - 1 if at == "O" else t, j]
        mid = float(bs(S, p["K"], T, v)[0])
        if side < 0:
            return max(0.0, p["qty"] * (mid * (1 - OPT["HALF"]) * 100 - OPT["FEE"]))
        return p["qty"] * mid * 100

    def buy_call(self, t, j, c, budget, at, **kw):
        qty = int(min(budget, self.cash) // c["cost"])
        if qty < 1:
            return False
        cost = qty * c["cost"]
        self.cash -= cost
        self.pos[j] = dict(kind="call", qty=qty, K=c["K"], exp=self.M.idx[t] + pd.Timedelta(days=OPT["DTE"]), ask=c["ask"],
                           u=self.mark(t, j, at), t=t, at=at, cost=cost, **kw)
        return True

    def buy_any(self, t, j, budget, at, c=None, **kw):
        """A call by your rules when one fits (c, or picked here), else shares."""
        if self.options:
            c = c or pick_call(self.mark(t, j, at), self.F["iv"][t - 1 if at == "O" else t, j], min(budget, self.cash))
            if c and self.buy_call(t, j, c, budget, at, **kw):
                return True
        return self.buy(t, j, budget, at, **kw)

    def call_nets(self, t, at):
        """The paper accounts' call safety nets: sell 5 days before expiry (at the open), or at -50% (on the close)."""
        out = []
        for j in [j for j, p in self.pos.items() if p.get("kind") == "call"]:
            p = self.pos[j]
            if at == "O" and (p["exp"] - self.M.idx[t]).days <= OPT["EXIT_DTE"]:
                self.sell(t, j, at="O", why="5 days before expiry")
                out.append((j, "expiry"))
            elif at == "C" and not (p["at"] == "C" and p["t"] == t):
                lv = p["qty"] * p["ask"] * 100 * (1 - OPT["STOP"])      # -50% on the mid, checked every 30 minutes
                lo = self.F["L"][t, j]
                if self.worth(t, j, p) <= lv:
                    self.sell(t, j, at="C", why="call -50%")
                elif lo == lo and self.worth(t, j, p, S=lo) <= lv:
                    self.sell(t, j, at="C", why="call -50%", cval=lv)
                else:
                    continue
                out.append((j, "stop"))
        return out

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
        self.pos[j] = dict(kind="shares", sh=dollars / fill, px=fill, u=fill, t=t, at=at, cost=dollars, **kw)
        return True

    def sell(self, t, j, px=None, at="C", why="", cval=None):
        """Sell a position; px is the stock's price (default: the open or the close), a call goes at the model's bid."""
        p = self.pos.pop(j)
        S = px if px is not None else self.mark(t, j, at)
        if p.get("kind") != "call":
            got = p["sh"] * S * (1 - SLIP)
        elif cval is not None:                      # sold at a given mid value (the -50% stop during the day)
            got = max(0.0, cval * (1 - OPT["HALF"]) - p["qty"] * OPT["FEE"])
        else:
            got = self.worth(t, j, p, S=S, at=at, side=-1)
        self.cash += got
        ret = got / p["cost"] - 1
        name = j if isinstance(j, str) else self.M.names[j]
        self.trades.append(dict(t=name, kind=p.get("kind", "shares"), buy=self.M.idx[p["t"]].strftime("%Y-%m-%d"),
                                sell=self.M.idx[t].strftime("%Y-%m-%d"), ret=ret, why=why))
        return ret

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
def run_system(M, F, when, options=True):
    A = Acct(M, F, options)
    pend = set()                                    # exits decided last night, sold at this open
    for t in range(M.t0, len(M.idx)):
        sold = {j for j in pend if j in A.pos}
        for j in sold:
            A.sell(t, j, at="O", why="your exit")
        pend.clear()
        sold |= {j for j, _ in A.call_nets(t, "O")}
        night = t - 1

        def buys(at):
            """paper.py's A buy: per free slot, the first of the top 15 setups with a call at 0.50-0.80 delta within 30% of
            the account; else the first with a cheaper call down to 0.15; else shares of the top setup."""
            if F["mkt_hot"][night]:
                return
            c = np.flatnonzero(F["setup"][night] & F["ss_ok"][night])
            c = [j for j in c[np.argsort(-F["strength"][night, c], kind="stable")] if j not in sold]
            while len(A.pos) < A_SLOTS:
                c = [j for j in c if j not in A.pos]
                budget = min(A_CAP * A.value(t, at), A.cash)
                if not c or budget < 50:
                    return
                pick = low = None
                for j in c[:OPT["SCAN"]] if A.options else []:
                    k = pick_call(A.mark(t, j, at), F["iv"][night if at == "O" else t, j], budget)
                    if k and k["band"]:
                        pick = (j, k)
                        break
                    if k and low is None:
                        low = (j, k)
                j, k = pick or low or (c[0], None)
                if not (A.buy_call(t, j, k, budget, at) if k else A.buy(t, j, budget, at)):
                    return
        if when == "open":
            buys("O")
        stops(A, t, lambda p: p["px"] * (1 - STOP) if p["kind"] == "shares" and not (p["at"] == "C" and p["t"] == t) else None)
        if when == "close":
            buys("C")
        A.dead(t)
        A.call_nets(t, "C")
        for j, p in A.pos.items():                  # your exit on tonight's close: sold at the next open
            if F["exit"][t, j] and not (p["at"] == "C" and p["t"] == t):
                pend.add(j)
        A.close_day(t)
    return A


# ---------------------------------------------------------------- B: Claude's picks
def run_ai(M, F, options=True):
    A = Acct(M, F, options)
    cfg = M.cfg
    names = np.array(M.names, dtype=object)
    held, outx, sells, adds = [], set(), [], []
    col = {t: j for j, t in enumerate(M.names)}
    for t in range(M.t0, len(M.idx)):
        for k in sells:
            j = col[k]
            if j in A.pos:
                A.sell(t, j, at="O", why="left the list or your exit")
        for j, why in A.call_nets(t, "O"):          # a call 5 days before expiry: bought again in its place
            if names[j] in held and names[j] not in adds:
                adds = adds + [names[j]]
        for i, k in enumerate(adds):                # a tenth of the account each: a call when one fits, else shares
            A.buy_any(t, col[k], min(A.value(t, "O") / cfg["AI_N"], A.cash / (len(adds) - i)), "O")
        A.dead(t)
        stopped = {names[j] for j, _ in A.call_nets(t, "C")}   # a call at -50%: not bought back while on the list
        ok = F["ok"][t] & np.isfinite(F["rs_pct"][t])
        row = pd.Series(F["rs_pct"][t, ok], index=names[ok])
        top = set(row.sort_values(ascending=False, kind="stable").index[:cfg["AI_KEEP"]])
        outx &= top                                 # sold on your exit: not bought back while it stays on the list
        sell = {k for k in held if F["exit"][t, col[k]]} | stopped
        outx |= sell
        skip = set(names[F["sec_hot"][t]]) | outx
        kept, added, dropped = S.ai_step(held, row, M.sector, n=cfg["AI_N"], keep=cfg["AI_KEEP"], cap=cfg["AI_CAP"],
                                         allow_new=not F["mkt_hot"][t], sell=sell, skip=skip)
        held, sells, adds = kept + added, dropped, added
        A.close_day(t)
    return A


# ---------------------------------------------------------------- D: OVTLYR plan
def run_ov(M, F, options=True):
    A = Acct(M, F, options)
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
        """Plan ETF's checks on an index (or coin): heat, signal, uptrend, value zone, market breadth."""
        c, x10, x20 = C[t, j], e10[t, j], e20[t, j]
        return (R[t, j] < ov["HEAT_MAX"] and x10 > x20 and c > e50[t, j] and x20 <= c <= x20 + ov["ZONE_ATR"] * atr[t, j]
                and not F["mkt_hot"][t])

    pause_until, morning, etf_sell = -1, set(), set()
    for t in range(M.t0, len(M.idx)):
        n = t - 1
        # the morning: last night's exits, then new trades
        for j in list(morning) + list(etf_sell):
            if j in A.pos:
                A.sell(t, j, at="O", why="morning exit")
        A.call_nets(t, "O")
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
                    & (C[n] > e50[n]) & (C[n] > e10[n]) & (R[n] > R[n - 1]))
            c = [j for j in np.flatnonzero(cand) if sec_ok.get(secs[j]) and j not in A.pos]
            c.sort(key=lambda j: (F["age"][n, j], -(F["rs"][n, j] if F["rs"][n, j] == F["rs"][n, j] else -9)))
            for j in c:
                if A.cash < D["MIN"]:
                    break
                o = A.mark(t, j, "O")
                want = A.value(t, "O") * D["RISK"] / (D["SIZE_ATR"] * atr[n, j]) * o
                if min(want, A.cash) >= D["MIN"]:
                    # a call by your rules within the plan's size and 30% of the account, else shares (paper.py)
                    k = A.options and pick_call(o, F["iv"][n, j], min(want, A.cash, A_CAP * A.value(t, "O")))
                    if not (k and A.buy_call(t, j, k, min(want, A.cash, A_CAP * A.value(t, "O")), "O",
                                             atr=atr[n, j], r0=R[n, j], leg="M")):
                        A.buy(t, j, want, "O", atr=atr[n, j], r0=R[n, j], leg="M")
                    took = True
        if not took and A.cash >= D["MIN"]:
            funds = [f for f, j in M.und.items() if f in M.fund and f not in A.pos and idx_ok(j, n)]
            cash = A.cash
            for f in funds:
                A.buy(t, f, cash / len(funds), "O", leg="ETF")
        # the day: the emergency exit, then the closing-price exits
        stops(A, t, lambda p: p["u"] - D["EMERGENCY_ATR"] * p["atr"] if p.get("leg") == "M" else None)
        A.dead(t)
        losers = 0
        for j in [j for j in A.pos if not isinstance(j, str)]:
            p, c = A.pos[j], C[t, j]
            if c != c:
                continue
            r0 = p["r0"]
            target = 63 if r0 < 50 else r0 + 10 if r0 < 75 else r0 + 5
            g = [k for k in range(max(p["t"], t - D["GAP_DAYS"]), t) if gap[k, j]]
            why = ("stop" if c < p["u"] - D["STOP_ATR"] * p["atr"] else "10/20 cross" if e10[t, j] < e20[t, j]
                   else "SPY under its 20 EMA" if C[t, b] < e20[t, b] else "RSI target" if R[t, j] >= target
                   else "gap and crap" if any(c < F["L"][k, j] for k in g) else "")
            if why:
                losers += A.sell(t, j, c, why=why) < 0
            elif (rise.get(secs[j], np.zeros(1))[t:t + 1] < ravg.get(secs[j], np.zeros(1))[t:t + 1]).any() \
                    or (M.idx[t] - M.idx[p["t"]]).days >= D["MAX_DAYS"]:
                morning.add(j)
        losers += sum(1 for _ in A.call_nets(t, "C"))
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
        start_cash=CASH, calls=sum(1 for x in tr if x.get("kind") == "call"),
        trades=len(tr), win=round(float((rets > 0).mean()) * 100) if len(rets) else None,
        avg_trade=round(float(rets.mean()) * 100, 1) if len(rets) else None,
        median_trade=round(float(np.median(rets)) * 100, 1) if len(rets) else None,
        invested=round(float(np.nanmean(A.inv[M.t0:])) * 100), curve=curve, by_year=years,
        last_trades=[dict(x, ret=round(x["ret"] * 100, 1)) for x in tr[-12:]])


def breadth_json(M, F):
    """The 10 years of breadth these backtests used: each day's Rising and its 10-day EMA, the market and each sector."""
    mkt = "Crypto market" if M.kind == "crypto" else "S&P 500"
    r1 = lambda a: [None if x != x else round(float(x), 1) for x in a[M.t0:]]
    return dict(asof=M.idx[-1].strftime("%Y-%m-%d"), dates=[d.strftime("%Y-%m-%d") for d in M.idx[M.t0:]],
                groups={(mkt if g == "_mkt" else g): dict(rise=r1(F["rise"][g]), avg=r1(F["ravg"][g])) for g in F["rise"]})


def run_all(M):
    t0 = time.time()
    F = feats(M)
    print(f"  signals ready ({time.time() - t0:.0f}s)", flush=True)
    unit, bn = ("coin", "BTC") if M.kind == "crypto" else ("stock", "SPY")
    desc = {
        "A": (NAMES["A"], f"Last night's setups on the strongest sector, strongest {unit} list, highest score first; 2 at a time, "
                          f"each at most 30% of the account; sells on your exit (10 EMA under the 20 and price under the 50) or an 8% stop. "
                          + "Buys at the next open." + (" Tested with shares: there's no history of option prices to test the "
                          "paper account's calls on; the card also shows the calls on a pricing model." if unit == "stock" else "")),
        "C": (NAMES["C"], "The same rules as Your system, but it buys at the next day's close, standing in for after 2 PM."),
        "B": (NAMES["B"], f"AI picks list: top relative strength, hold 10, keep while in the top 20, max 3 per "
                          f"{'category' if unit == 'coin' else 'sector'}, a tenth of the account each"
                          + "; also sold on your exit." + (" Tested with shares (the paper account may buy calls)." if unit == "stock" else "")),
        "D": (NAMES["D"], ("Plan M on the page's stand-ins for OVTLYR's signals, else Plan ETF (" +
                           ("BTC / ETH on their own signals), spare cash as cash." if unit == "coin" else
                            "TQQQ / SPXL on QQQ's / SPY's signals), spare cash in T-bills (BIL for SGOV).") +
                           (" Plan M tested with shares (the paper account may buy calls)." if unit == "stock" else "")
                           + " Order block and earnings checks left out.")),
    }
    out = {}
    for k, fn in (("A", lambda o=True: run_system(M, F, "open", o)), ("C", lambda o=True: run_system(M, F, "close", o)),
                  ("B", lambda o=True: run_ai(M, F, o)), ("D", lambda o=True: run_ov(M, F, o))):
        A = fn()
        out[k] = summary(M, A, desc[k])
        s = out[k]
        print(f"  {k} {s['name']}: ${s['final']:,.0f} ({s['cagr']:+.1f}%/yr, worst drop {s['maxdd']:.0f}%, {s['trades']} trades, "
              f"in the market {s['invested']}%) vs {bn} ${s['bench_final']:,.0f} ({s['bench_cagr']:+.1f}%/yr) ({time.time() - t0:.0f}s)", flush=True)
        if s["calls"]:
            # Calls can't be backtested on real prices (no free option history), and modeled calls at 30% a trade with a
            # -50% stop swing from 20x to nearly zero. So the plan's line is the same rules with shares, as before, and the
            # modeled-calls result rides along for the card.
            sh = summary(M, fn(False), desc[k])
            sh["with_calls"] = {x: s[x] for x in ("final", "cagr", "maxdd", "trades", "calls", "win")}
            sh["with_calls"]["peak"] = round(max(c[1] for c in s["curve"]), 2)
            out[k] = sh
            print(f"    shown with shares: ${sh['final']:,.0f} ({sh['cagr']:+.1f}%/yr, worst drop {sh['maxdd']:.0f}%)", flush=True)
    M.breadth = breadth_json(M, F)
    return dict(market=M.kind, bench=bn, cash=CASH, asof=M.idx[-1].strftime("%Y-%m-%d"), built=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
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
    ap.add_argument("--breadth", help="also save the 10 years of breadth here, for the nightly per-stock backtest")
    a = ap.parse_args()
    t0 = time.time()
    print(f"Prices ({a.market})...", flush=True)
    global CASH
    CASH = START_CASH[a.market]
    M = stocks(a.demo) if a.market == "stocks" else crypto(a.demo)
    print(f"  {len(M.names)} tickers, {M.idx[M.t0].date()} to {M.idx[-1].date()} ({time.time() - t0:.0f}s)", flush=True)
    res = run_all(M)
    res["demo"] = a.demo
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    if a.breadth:
        Path(a.breadth).write_text(json.dumps(M.breadth, separators=(",", ":")), encoding="utf-8")
    print(f"Done in {time.time() - t0:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
