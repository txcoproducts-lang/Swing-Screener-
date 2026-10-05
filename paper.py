#!/usr/bin/env python3
"""Paper trading trial: two accounts start with $1,000 each on 2026-10-06 and trade for six months.

  A  "Your system": last night's screener setups (Momentum and Pullback) and your option rules
     (calls 15-30 days out, delta 0.50-0.80, open interest over 500), up to half the account a trade, or one
     contract with up to all the cash when every call that fits costs more. Shares when no call fits.
  B  "Claude's picks": my AI picks list (relative strength momentum, research/picks_backtest.py), as shares.

GitHub Actions runs this every 30 minutes on weekdays (.github/workflows/paper.yml). On a market day the
first run at or after 9:45 New York time sells and buys, later runs check stops and targets, and the first
run after 4 PM records the closing value. The accounts are saved on the paper-trading branch
(paper/A.json, paper/B.json), which the page reads. Every buy, sell and daily decision is logged with
its reason. An account that hits an error mid-run is left as it was, and the next run tries again.

  python paper.py --state DIR [--history DIR] [--dry-run] [--at "2026-10-06 10:05"] [--test-quotes]
"""
import argparse, copy, datetime as dt, json, math, sys, traceback
from pathlib import Path
import pandas as pd
import screener as SC

NY = "America/New_York"
P = dict(
    START="2026-10-06", MONTHS=6, CASH=1000.0,
    OPEN=dt.time(9, 45),          # the first run at or after this sells and buys
    CLOSE=dt.time(16, 0),         # the first run at or after this records the day's closing value
    STALE_MIN=20,                 # Yahoo's latest 1-minute bar must be this fresh to trade on it
    STALE_DAYS=5,                 # if a nightly run failed, trade on screener files up to this many days old
    SLIP=0.0005,                  # shares fill 0.05% worse than the last trade
    FEE=0.65,                     # per option contract, each way
    # A: your screener and option rules
    A_SLOTS=2,                    # positions at a time, each up to half the account (one call contract can take more)
    A_SCAN=15,                    # how far down the setups to look for a call that fits the budget
    A_TARGET=0.50, A_STOP=0.50,   # calls: sell at +50% (bid) or -50% (mid)
    A_EXIT_DTE=5,                 # calls: sell this many days before expiry
    A_SHARE_STOP=0.08,            # shares: sell on an 8% drop
    # B: my AI picks
    B_SLOTS=10,
)
NAMES = {"A": "Your system", "B": "Claude's picks"}
FILLS = ("Paper trades, no real money. Shares fill at Yahoo's latest 1-minute price, 0.05% worse, and fractional "
         "shares are allowed. Calls fill at the ask to buy and the bid to sell, plus $0.65 per contract each way. "
         "Yahoo's option quotes can lag by up to 15 minutes. Dividends are ignored.")


def rules(aid):
    lo, hi = SC.CFG["PK_DTE"]
    dlo, dhi = SC.CFG["PK_DELTA"]
    if aid == "A":
        return [
            "Uses your screener: last night's setups (Momentum and Pullback), in the stock table's order.",
            f"Holds {P['A_SLOTS']} positions at a time, each up to half the account (a call can take more, see below). "
            "Buys and sells at about 10:00 New York time, once the opening half hour's swings settle and option "
            "spreads narrow, then checks stops and targets every 30 minutes until the close.",
            f"Buys a call by your rules ({lo}-{hi} days out, delta {dlo:.2f}-{dhi:.2f}, open interest over "
            f"{SC.CFG['PK_OI_OVER']}, bid/ask spread under {SC.CFG['MAX_SPREAD_PCT']:.0f}%), the one nearest "
            f"{(dlo + dhi) / 2:.2f} delta, on the first of the top {P['A_SCAN']} setups that has one within half the "
            "account. If none does, it buys one contract that costs more, with up to all the cash. If no call fits "
            "even that, it buys shares of the top setup.",
            "Skips a setup that has dropped below its 50-day EMA by the time it buys.",
            f"Sells a call at +{P['A_TARGET']:.0%} (at the bid), at -{P['A_STOP']:.0%}, {P['A_EXIT_DTE']} days before "
            "expiry, or after a close below the 50-day EMA or 150-day average.",
            f"Sells shares if they drop {P['A_SHARE_STOP']:.0%} or after a close below the 50-day EMA or 150-day average.",
            "The exits are my defaults, since your screener doesn't set any. Tell me yours and I'll switch.",
        ]
    return [
        f"Copies my AI picks list: up to {P['B_SLOTS']} stocks, at most {SC.CFG['AI_CAP']} per sector, ranked by "
        "relative strength among liquid S&P 500 and Nasdaq-100 stocks (the IBD formula: 40% weight on the last "
        "3 months, 20% each on 6, 9 and 12).",
        "Trades at about 10:00 New York time: sells stocks that left the list the night before and buys the new "
        "ones, about a tenth of the account each. Empty spots stay in cash.",
        f"A stock stays while it ranks in the top {SC.CFG['AI_KEEP']}. No stop-loss: in my 2014-2026 test, also "
        "selling below the 50-day EMA cut the return from 17.4% to 9.1% a year.",
        "Shares, not options: the edge in my test came from holding leaders for weeks, which 15-30 day calls lose "
        "to time decay, and a $100 slot rarely covers one contract.",
        "In the test (S&P 500 as it was each day, 2014-2026) this made +19.4% a year against +14.5% for the average "
        "stock, with long stretches behind and a worst drop of -31%. The edge is not proven.",
    ]


# ------------------------------------------------------------------ helpers
def tstr(ts): return ts.strftime("%Y-%m-%d %H:%M")
def r2(x): return round(float(x), 2)
def r4(x): return round(float(x), 4)
def day_str(d): return f"{d:%b} {d.day}"
def plural(n, word): return f"{n:g} {word}{'' if n == 1 else 's'}"


def money(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def ema50_150(close):
    """Last close, its 50-day EMA and its 150-day average (the price half of your uptrend rule)."""
    c = close.dropna()
    return float(c.iloc[-1]), float(SC.ema(c, 50).iloc[-1]), float(c.rolling(150).mean().iloc[-1])


def opt_label(t, exp, strike):
    return f"{t} {day_str(dt.date.fromisoformat(exp))} ${strike:g} call"


# ------------------------------------------------------------------ market data (Yahoo, on GitHub Actions)
class Yahoo:
    def __init__(self):
        import yfinance as yf
        self.yf = yf
        self._exp, self._chains = {}, {}

    def prices(self, tickers):
        """{ticker: (last price, its time in New York)} from today's 1-minute bars."""
        tks = sorted(set(tickers))
        out = {}
        if not tks:
            return out
        df = self.yf.download(tks, period="1d", interval="1m", group_by="ticker", auto_adjust=False,
                              progress=False, threads=True)
        if df is None or df.empty:
            return out
        for t in tks:
            try:
                s = (df[t] if isinstance(df.columns, pd.MultiIndex) else df)["Close"].dropna()
            except KeyError:
                continue
            if len(s):
                ts = s.index[-1]
                ts = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY)
                out[t] = (float(s.iloc[-1]), ts)
        return out

    def daily(self, tickers, through, period="1y"):
        """{ticker: daily bars} up to and including the date `through`."""
        tks = sorted(set(tickers))
        if not tks:
            return {}
        fr = SC.yf_batch(tks, period=period, interval="1d")
        return {t: d[d.index.date <= through] for t, d in fr.items()}

    def expiries(self, t):
        if t not in self._exp:
            self._exp[t] = list(self.yf.Ticker(t).options)
        return self._exp[t]

    def calls(self, t, exp):
        if (t, exp) not in self._chains:
            self._chains[(t, exp)] = self.yf.Ticker(t).option_chain(exp).calls
        return self._chains[(t, exp)]

    def splits(self, t, since):
        s = self.yf.Ticker(t).splits
        if s is None or not len(s):
            return []
        idx = s.index.tz_localize(None) if s.index.tz is not None else s.index
        return [(i.date().isoformat(), float(v)) for i, v in zip(idx, s.values) if i.date().isoformat() > since and v > 0]


# ------------------------------------------------------------------ the run's context
class Day:
    """What a run knows: the time, the market, last night's screener files and the prices it has fetched."""
    def __init__(self, mkt, now, hist, test_quotes=False):
        self.mkt, self.now, self.hist, self.test_quotes = mkt, now, Path(hist), test_quotes
        self.today = now.date()
        self.prev_day = None
        self.px = {}

    def price(self, tickers):
        need = [t for t in set(tickers) if t not in self.px]
        if need:
            self.px.update(self.mkt.prices(need))
        return {t: self.px[t] for t in tickers if t in self.px}

    def fresh(self, t):
        q = self.px.get(t)
        return q is not None and q[1].date() == self.today and self.now - q[1] <= pd.Timedelta(minutes=P["STALE_MIN"])

    def recent(self, d):
        """Is a nightly file from date d usable today? (Last night's, or a few days old if a nightly run failed.)"""
        return d is not None and d < self.today and (self.today - d).days <= P["STALE_DAYS"]

    def source(self, d):
        return "last night's screener" if d == self.prev_day else f"the screener from {day_str(d)} (the last finished nightly run)"

    def screener(self):
        """The latest screener results from before today: (date, table), or (date or None, None) if too old."""
        files = sorted(f for f in self.hist.glob("screener_*.csv") if f.stem[9:] < self.today.isoformat())
        d = dt.date.fromisoformat(files[-1].stem[9:]) if files else None
        return (d, pd.read_csv(files[-1])) if self.recent(d) else (d, None)

    def ai(self):
        """My AI picks list as of its last nightly update, plus each pick's rank and reasons from that night's
        Top picks file."""
        f = self.hist / "ai_picks.json"
        st = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        info, tp = {}, self.hist / f"toppicks_{(st or {}).get('as_of')}.csv"
        if tp.exists():
            d = pd.read_csv(tp)
            for _, r in d[d.list == "ai"].iterrows():
                rk, why = r.get("ai_rank"), r.get("why")
                info[r.ticker] = dict(rank=int(rk) if rk is not None and rk == rk else None,
                                      why=why if isinstance(why, str) else "")
        return st, info


# ------------------------------------------------------------------ accounts and fills
def new_account(aid):
    end = (pd.Timestamp(P["START"]) + pd.DateOffset(months=P["MONTHS"])).date().isoformat()
    return dict(id=aid, name=NAMES[aid], start=P["START"], end=end, start_cash=P["CASH"], cash=P["CASH"],
                rules=rules(aid), fills=FILLS, positions=[], closed=[], log=[], equity=[], mark=None,
                days={}, next_id=1, updated=None, over=False)


def value(a):
    return a["cash"] + sum(p["last"]["value"] for p in a["positions"])


def note(a, now, text, kind="note"):
    a["log"].append(dict(t=tstr(now), kind=kind, text=text))


def open_pos(a, **pos):
    pos = dict(id=a["next_id"], **pos)
    a["next_id"] += 1
    a["positions"].append(pos)
    a["cash"] = r2(a["cash"] - pos["buy"]["cost"])
    return pos


def close_pos(a, pos, now, price, proceeds, why):
    a["positions"].remove(pos)
    a["cash"] = r2(a["cash"] + proceeds)
    pnl = proceeds - pos["buy"]["cost"]
    days = (now.date() - dt.date.fromisoformat(pos["buy"]["t"][:10])).days
    pos.pop("exit", None)
    pos.update(sell=dict(t=tstr(now), price=r4(price), proceeds=r2(proceeds), why=why),
               pnl=r2(pnl), pnl_pct=round(pnl / pos["buy"]["cost"] * 100, 2), days=days,
               last=dict(t=tstr(now), price=r4(price), value=r2(proceeds)))
    a["closed"].append(pos)
    res = f"{'+' if pnl >= 0 else '-'}{money(abs(pnl))} ({pos['pnl_pct']:+.1f}%) in {plural(days, 'day')}"
    if pos["kind"] == "call":
        what = f"{plural(pos['qty'], 'contract')} of the {pos['label']} at {money(price)}"
    else:
        what = f"{pos['qty']:g} shares of {pos['ticker']} at {money(price)}"
    note(a, now, f"Sold {what}, {money(proceeds)}. {why} Result: {res}.", "sell")


def buy_shares(a, now, t, price, budget, why, plan):
    fill = price * (1 + P["SLIP"])
    qty = math.floor(budget / fill * 10000) / 10000
    if qty <= 0:
        return None
    cost = r2(qty * fill)
    pos = open_pos(a, ticker=t, kind="shares", qty=qty, label=f"{qty:g} shares of {t}",
                   buy=dict(t=tstr(now), price=r4(fill), cost=cost, why=why), plan=plan,
                   last=dict(t=tstr(now), price=r4(price), value=r2(qty * price)))
    note(a, now, f"Bought {qty:g} shares of {t} at {money(fill)}, {money(cost)}. {why} Plan: {plan['text']}", "buy")
    return pos


def sell_shares(a, pos, now, price, why):
    fill = price * (1 - P["SLIP"])
    close_pos(a, pos, now, fill, pos["qty"] * fill, why)


def call_quote(day, pos):
    """Bid / ask / mid for a held call right now, or None if Yahoo has no quote for it."""
    o = pos["option"]
    try:
        ch = day.mkt.calls(pos["ticker"], o["exp"])
    except Exception as e:
        print(f"  no quote for the {pos['label']}: {e}")
        return None
    row = ch[ch.contractSymbol == o["symbol"]] if o.get("symbol") and "contractSymbol" in ch else ch.iloc[0:0]
    if row.empty:
        row = ch[(ch.strike - o["strike"]).abs() < 1e-6]
    if row.empty:
        return None
    r = row.iloc[0]
    num = lambda v: float(v) if v is not None and v == v else 0.0
    bid, ask, last = num(r.bid), num(r.ask), num(r.lastPrice)
    if day.test_quotes and (bid <= 0 or ask <= 0):
        bid = ask = last
    return dict(bid=bid, ask=ask, last=last, mid=(bid + ask) / 2 if bid > 0 and ask > 0 else last)


def mark_call(pos, now, q):
    pos["last"] = dict(t=tstr(now), price=r4(q["mid"]), value=r2(q["mid"] * 100 * pos["qty"]),
                       bid=r4(q["bid"]), ask=r4(q["ask"]))


def sell_call(a, pos, now, bid, why):
    close_pos(a, pos, now, bid, bid * 100 * pos["qty"] - P["FEE"] * pos["qty"], why)


def settle_call(a, pos, now, under):
    """A call still held at expiry is worth what it's in the money."""
    per = max(0.0, under - pos["option"]["strike"])
    close_pos(a, pos, now, per, per * 100 * pos["qty"],
              f"It expired with {pos['ticker']} at {money(under)}, {'in' if per > 0 else 'out of'} the money.")


# ------------------------------------------------------------------ A: your screener and option rules
def setup_why(r, n, src="last night's screener"):
    """Plain-words reason a screener row is a setup."""
    if r.setup == "Momentum":
        b = r.get("brk20")
        brk = bool(b) if b is not None and b == b else r.from_hi < -3
        where = " and ".join((["closed above its 20-day high"] if brk else [])
                             + (["is at its 52-week high"] if r.from_hi >= -0.5 else
                                [f"is within {abs(r.from_hi):.1f}% of its 52-week high"] if r.from_hi >= -3 else []))
        return (f"#{n} setup in {src}, a Momentum setup (score {r.score:g}): it {where}, RSI {r.rsi:.0f}, "
                f"volume {r.relvol:.1f}x its 20-day average. It's in your uptrend: EMA10 above EMA20, price above the "
                "50-day EMA and the 150-day average.")
    return (f"#{n} setup in {src}, a Pullback setup (score {r.score:g}): RSI {r.rsi:.0f} after a dip, "
            f"{r.vs20:+.1f}% from its 20-day EMA and {r.vs50:+.1f}% from its 50-day EMA, volume {r.relvol:.1f}x its "
            "20-day average. The trend under it holds: price above the 50-day EMA, 20-day EMA above the 50-day.")


def fitting_calls(day, t, S):
    """Calls that fit your rules right now, with live quotes (a tight bid/ask)."""
    lo, hi = SC.CFG["PK_DTE"]
    dlo, dhi = SC.CFG["PK_DELTA"]
    out = []
    for e in day.mkt.expiries(t):
        dte = (dt.date.fromisoformat(e) - day.today).days
        if not lo <= dte <= hi:
            continue
        rows, _ = SC.chain_rows(day.mkt.calls(t, e), S, e, dte, SC.CFG["PK_OI_OVER"] + 1)
        for r in rows:
            if r["oi"] is None or not dlo <= r["delta"] <= dhi:
                continue
            if r["quote"] != "live":
                if not (day.test_quotes and r["last"] > 0):
                    continue
                r = dict(r, bid=r["last"], ask=r["last"])
            out.append(r)
    return out


def a_exits(a, day, trend):
    """Stops, targets and time exits; with trend=True (the morning run) also last night's close against the
    50-day EMA and 150-day average."""
    now = day.now
    if not a["positions"]:
        return
    px = day.price([p["ticker"] for p in a["positions"]])
    if trend:
        bars = day.mkt.daily([p["ticker"] for p in a["positions"]], day.prev_day)
        for p in a["positions"]:
            d = bars.get(p["ticker"])
            if d is None or len(d) < 150:
                continue
            c, e50, m150 = ema50_150(d["Close"])
            if c >= e50 and c >= m150:
                continue
            below = " and ".join(([f"its 50-day EMA ({money(e50)})"] if c < e50 else [])
                                 + ([f"its 150-day average ({money(m150)})"] if c < m150 else []))
            p["exit"] = (f"{p['ticker']} closed at {money(c)} on {day_str(d.index[-1])}, below {below}, so it's out of "
                         "your uptrend.")
    for p in list(a["positions"]):
        t = p["ticker"]
        if p["kind"] == "shares":
            if not day.fresh(t):
                continue
            price = px[t][0]
            p["last"] = dict(t=tstr(now), price=r4(price), value=r2(p["qty"] * price))
            if p.get("exit"):
                sell_shares(a, p, now, price, p["exit"])
            elif price <= p["plan"]["stop"]:
                sell_shares(a, p, now, price, f"It fell to {money(price)}, through the {P['A_SHARE_STOP']:.0%} stop "
                                              f"at {money(p['plan']['stop'])}.")
            continue
        exp = dt.date.fromisoformat(p["option"]["exp"])
        if day.today >= exp:
            if day.fresh(t):
                settle_call(a, p, now, px[t][0])
            continue
        q = call_quote(day, p)
        if q is None:
            continue
        mark_call(p, now, q)
        if q["bid"] <= 0:
            continue
        left = (exp - day.today).days
        if p.get("exit"):
            sell_call(a, p, now, q["bid"], p["exit"])
        elif q["bid"] >= p["plan"]["target"]:
            sell_call(a, p, now, q["bid"], f"The bid reached {money(q['bid'])}, past the +{P['A_TARGET']:.0%} target "
                                           f"({money(p['plan']['target'])}).")
        elif q["mid"] <= p["plan"]["stop"]:
            sell_call(a, p, now, q["bid"], f"It fell to {money(q['mid'])} (mid), through the -{P['A_STOP']:.0%} stop "
                                           f"({money(p['plan']['stop'])}).")
        elif left <= P["A_EXIT_DTE"]:
            sell_call(a, p, now, q["bid"], f"{plural(left, 'day')} left before expiry, and time decay speeds up in "
                                           "the last week.")


def a_buys(a, day):
    now = day.now
    if len(a["positions"]) >= P["A_SLOTS"]:
        note(a, now, f"No new buy: both slots are taken ({'; '.join(p['label'] for p in a['positions'])}).", "day")
        return
    sd, scr = day.screener()
    if scr is None:
        note(a, now, "No new buy: the screener hasn't finished a nightly run in the last few days"
                     + (f" (the latest is from {day_str(sd)})." if sd else "."), "day")
        return
    src = day.source(sd)
    setups = scr[scr.has_setup.astype(bool)].reset_index(drop=True)
    if setups.empty:
        note(a, now, f"No new buy: {src} found no setups.", "day")
        return
    sold_today = {p["ticker"] for p in a["closed"] if p["sell"]["t"][:10] == day.today.isoformat()}
    scan = [(i + 1, r) for i, r in setups.head(P["A_SCAN"]).iterrows()]
    px = day.price([r.ticker for _, r in scan])
    mid = sum(SC.CFG["PK_DELTA"]) / 2
    cost = lambda f: f["ask"] * 100 + P["FEE"]
    best = lambda fs: min(fs, key=lambda f: (abs(f["delta"] - mid), -f["oi"]))
    while len(a["positions"]) < P["A_SLOTS"]:
        budget = min(a["cash"], value(a) / P["A_SLOTS"])
        if budget < 50:
            note(a, now, f"No new buy: only {money(a['cash'])} in cash.", "day")
            return
        cash = a["cash"]                       # one contract can use all of it when no call fits the budget
        within = "half the account" if budget < cash else "the cash on hand"
        held = {p["ticker"] for p in a["positions"]}
        valid, skipped, cheapest, looked, failed = [], [], None, 0, 0
        pick = big = None
        for n, r in scan:
            t = r.ticker
            if t in held or t in sold_today:
                continue
            if not day.fresh(t):
                skipped.append(f"{t} had no live price")
                continue
            S = px[t][0]
            e50 = r.close / (1 + r.vs50 / 100)
            if S <= e50:
                skipped.append(f"{t} was at {money(S)}, below its 50-day EMA ({money(e50)})")
                continue
            valid.append((n, r, S))
            looked += 1
            try:
                fits = fitting_calls(day, t, S)
            except Exception as e:
                failed += 1
                print(f"  option lookup failed for {t}: {e}")
                continue
            ok = [f for f in fits if cost(f) <= budget]
            if ok:
                pick = (n, r, S, best(ok), len(ok), False)
                break
            over = [f for f in fits if cost(f) <= cash]
            if over and big is None:
                big = (n, r, S, best(over), len(over), True)
            if fits and not over:
                c = min(fits, key=cost)
                if cheapest is None or cost(c) < cheapest[1]:
                    cheapest = (f"{opt_label(t, c['exp'], c['strike'])} at {money(cost(c))}", cost(c))
        pick = pick or big
        if pick:
            n, r, S, f, n_ok, one = pick
            t, entry = r.ticker, float(f["ask"])
            qty = 1 if one else int(budget // cost(f))
            tot = r2(qty * cost(f))
            label = opt_label(t, f["exp"], f["strike"])
            exp = dt.date.fromisoformat(f["exp"])
            exit_by = exp - dt.timedelta(days=P["A_EXIT_DTE"])
            while exit_by.weekday() >= 5:              # the first market day inside the last week
                exit_by += dt.timedelta(days=1)
            plan = dict(target=r4(entry * (1 + P["A_TARGET"])), stop=r4(entry * (1 - P["A_STOP"])), exit_by=exit_by.isoformat())
            plan["text"] = (f"sell at +{P['A_TARGET']:.0%} (a bid of {money(plan['target'])}), at -{P['A_STOP']:.0%} "
                            f"({money(plan['stop'])}), on {day_str(exit_by)} at the latest ({plural((exp - exit_by).days, 'day')} before "
                            f"expiry), or after {t} closes below its 50-day EMA or 150-day average.")
            why = (f"{setup_why(r, n, src)} Why this call: delta {f['delta']:.2f}, {f['dte']} days to expiry, open interest "
                   f"{f['oi']:,}, IV {f['iv']:.0f}%, bid {money(f['bid'])} / ask {money(f['ask'])}. "
                   + (f"None of the top {P['A_SCAN']} setups had a call that fits your rules for {money(budget)} or less "
                      f"({within}), so it buys one contract, which can use up to all {money(cash)} in cash. "
                      if one else "")
                   + (f"It's the only call{f' on {t}' if one else ''} that fits your rules and "
                      if n_ok == 1 else
                      f"It's the nearest to {mid:.2f} delta of the {n_ok} calls{f' on {t}' if one else ''} that fit your "
                      "rules and ")
                   + ("the cash." if one else f"the {money(budget)} budget ({within})."))
            open_pos(a, ticker=t, kind="call", qty=qty, label=label,
                     option=dict(symbol=f.get("symbol"), exp=f["exp"], strike=float(f["strike"])),
                     buy=dict(t=tstr(now), price=r4(entry), cost=tot, why=why, under=r4(S),
                              delta=round(float(f["delta"]), 3), iv=round(float(f["iv"]), 1), oi=int(f["oi"]), dte=int(f["dte"])),
                     plan=plan, last=dict(t=tstr(now), price=r4((f["bid"] + f["ask"]) / 2),
                                          value=r2((f["bid"] + f["ask"]) / 2 * 100 * qty), bid=r4(f["bid"]), ask=r4(f["ask"])))
            note(a, now, f"Bought {plural(qty, 'contract')} of the {label} at {money(entry)} (the ask), {money(tot)} with "
                         f"the fee, with {t} at {money(S)}. {why} Plan: {plan['text']}", "buy")
            continue
        if not valid:
            note(a, now, "No new buy: none of the top setups passed the checks at buying time"
                         + (f" ({'; '.join(skipped[:5])})." if skipped else "."), "day")
            return
        n, r, S = valid[0]
        t = r.ticker
        if failed == looked:
            reason = "Yahoo's option quotes couldn't be loaded this morning."
        elif cheapest:
            reason = (f"none of the top {P['A_SCAN']} setups had a call that fits your rules for {money(cash)} or less "
                      f"(all the cash). The cheapest that fits was the {cheapest[0]}.")
        else:
            reason = (f"none of the top {P['A_SCAN']} setups had a call that fits your rules this morning (15-30 days out, "
                      "delta 0.50-0.80, open interest over 500, a tight bid/ask).")
        stop = r4(S * (1 - P["A_SHARE_STOP"]))
        plan = dict(stop=stop, text=f"sell if it drops {P['A_SHARE_STOP']:.0%} (to {money(stop)}) or after {t} closes below "
                                    "its 50-day EMA or 150-day average.")
        if buy_shares(a, now, t, S, budget, f"{setup_why(r, n, src)} Why shares, not a call: {reason}", plan) is None:
            return


# ------------------------------------------------------------------ B: my AI picks
def b_trade(a, day, quiet=False):
    """Make the account match last night's AI picks list. quiet=True (later runs) only retries what the
    morning run couldn't do, without logging a no-trade note."""
    now = day.now
    st, info = day.ai()
    as_of = dt.date.fromisoformat(st["as_of"]) if st and st.get("as_of") else None
    if not day.recent(as_of):
        if not quiet:
            note(a, now, "No trades: my AI picks list hasn't been updated in the last few days"
                         + (f" (the latest is from {day_str(as_of)})." if as_of else "."), "day")
        return
    if as_of != day.prev_day and not quiet:
        note(a, now, f"Last night's update of my AI picks list didn't finish, so I'm trading the list from {day_str(as_of)}.", "note")
    picks = [p["ticker"] for p in st["picks"]]
    added = {p["ticker"]: p.get("added") for p in st["picks"]}
    held = {p["ticker"]: p for p in a["positions"]}
    px = day.price(list(held) + picks)
    gone = {c["ticker"]: c for c in st.get("closed", []) if c.get("dropped") == st["as_of"]}
    acted, waiting = 0, []
    for t, p in held.items():
        if t in picks:
            continue
        if not day.fresh(t):
            waiting.append(f"sell {t}")
            continue
        g = gone.get(t)
        sell_shares(a, p, now, px[t][0], f"It left my AI picks list last night: it {g['why']}." if g and g.get("why")
                    else "It's no longer on my AI picks list.")
        acted += 1
    have = {p["ticker"] for p in a["positions"]}
    new = [t for t in picks if t not in have]
    for i, t in enumerate(new):
        if not day.fresh(t):
            waiting.append(f"buy {t}")
            continue
        budget = min(value(a) / P["B_SLOTS"], a["cash"] / (len(new) - i))
        if budget < 5:
            continue
        inf = info.get(t, {})
        rank = f"ranked #{inf['rank']}" if inf.get("rank") else f"in the top {SC.CFG['AI_KEEP']}"
        since = ("added last night" if added.get(t) == day.prev_day.isoformat() else
                 f"on the list since {day_str(dt.date.fromisoformat(added[t]))}" if added.get(t) else "on the list")
        why = (f"On my AI picks list ({since}), {rank} by relative strength among liquid S&P 500 and Nasdaq-100 stocks"
               + (f": {inf['why']}." if inf.get("why") else ".")
               + " Why shares, not a call: my method's edge came from holding leaders for weeks, which 15-30 day calls "
               f"lose to time decay, and about ${budget:,.0f} a stock rarely covers one contract.")
        plan = dict(text=f"hold while it ranks in the top {SC.CFG['AI_KEEP']} (checked each night) and sell the morning "
                         "after it drops out.")
        if buy_shares(a, now, t, px[t][0], budget, why, plan):
            acted += 1
    if quiet:
        return
    if waiting:
        note(a, now, f"Waiting for a live price to {', '.join(waiting)}; trying again every 30 minutes.", "note")
    if not acted and not waiting:
        hold = sorted(p["ticker"] for p in a["positions"])
        note(a, now, f"No trades: my list didn't change{' last night' if as_of == day.prev_day else ''}, so I'm holding "
                     f"{plural(len(hold), 'stock')}"
                     + (f" ({', '.join(hold)})." if hold else "."), "day")


def b_marks(a, day):
    px = day.price([p["ticker"] for p in a["positions"]])
    for p in a["positions"]:
        if day.fresh(p["ticker"]):
            price = px[p["ticker"]][0]
            p["last"] = dict(t=tstr(day.now), price=r4(price), value=r2(p["qty"] * price))


# ------------------------------------------------------------------ the run
def splits(a, day):
    for p in a["positions"]:
        if p["kind"] != "shares":
            continue
        try:
            got = day.mkt.splits(p["ticker"], p.get("split_checked") or p["buy"]["t"][:10])
        except Exception as e:
            print(f"  split check failed for {p['ticker']}: {e}")
            continue
        for d, ratio in got:
            p["qty"] = r4(p["qty"] * ratio)
            p["buy"]["price"] = r4(p["buy"]["price"] / ratio)
            if "stop" in p["plan"]:
                p["plan"]["stop"] = r4(p["plan"]["stop"] / ratio)
            p["label"] = f"{p['qty']:g} shares of {p['ticker']}"
            note(a, day.now, f"{p['ticker']} split {ratio:g}-for-1 on {d}: the account now holds {p['qty']:g} shares.", "note")
        p["split_checked"] = day.today.isoformat()


def close_day(a, day, spy_close):
    """Value everything at today's close and add the day to the chart."""
    held = [p["ticker"] for p in a["positions"] if p["kind"] == "shares"]
    bars = day.mkt.daily(held, day.today, period="5d") if held else {}
    for p in a["positions"]:
        if p["kind"] == "shares":
            d = bars.get(p["ticker"])
            if d is not None and len(d) and d.index[-1].date() == day.today:
                c = float(d["Close"].iloc[-1])
                p["last"] = dict(t=f"{day.today} 16:00", price=r4(c), value=r2(p["qty"] * c))
        else:
            q = call_quote(day, p)
            if q:
                mark_call(p, day.now, q)
    v = r2(value(a))
    prev = a["equity"][-1]["v"] if a["equity"] else a["start_cash"]
    a["equity"].append(dict(d=day.today.isoformat(), v=v, spy=r2(spy_close)))
    spy0 = a["equity"][0]["spy"]
    note(a, day.now, f"Closed the day at {money(v)}: {(v / prev - 1) * 100:+.2f}% today, "
                     f"{(v / a['start_cash'] - 1) * 100:+.2f}% since the start (SPY {(spy_close / spy0 - 1) * 100:+.2f}%). "
                     f"Cash {money(a['cash'])}, {plural(len(a['positions']), 'position')} open.", "close")


def end_trial(a, day):
    why = f"The six-month trial ended on {day_str(dt.date.fromisoformat(a['end']))}, so everything is sold."
    px = day.price([p["ticker"] for p in a["positions"]])
    for p in list(a["positions"]):
        if p["kind"] == "shares":
            if day.fresh(p["ticker"]):
                sell_shares(a, p, day.now, px[p["ticker"]][0], why)
        else:
            q = call_quote(day, p)
            if q and q["bid"] > 0:
                sell_call(a, p, day.now, q["bid"], why)


def start(a, day, spy_daily):
    """The first run of the trial: $1,000 at the previous close, so SPY is measured from the same point."""
    if a["equity"]:
        return
    prev = spy_daily[spy_daily.index.date == day.prev_day]
    a["equity"].append(dict(d=day.prev_day.isoformat(), v=a["start_cash"], spy=r2(prev["Close"].iloc[-1])))
    end = dt.date.fromisoformat(a["end"])
    note(a, day.now, f"Trial started with {money(a['start_cash'])}. It runs to {day_str(end)}, {end.year}.", "day")


def step(a, day, spy_daily):
    """One account's part of a run. Returns what it did in a few words, or None when only prices moved."""
    now, today = day.now, day.today.isoformat()
    steps = a["days"].get(today, [])
    if a.get("over") or now.time() < P["OPEN"]:
        return None
    if now.time() >= P["CLOSE"]:
        if "close" in steps or spy_daily.index[-1].date() != day.today:
            return None
        start(a, day, spy_daily)
        close_day(a, day, float(spy_daily["Close"].iloc[-1]))
        a["days"][today] = steps + ["close"]
        if today >= a["end"] and not a["positions"]:
            a["over"] = True
            note(a, now, f"Trial over. Final value {money(value(a))}, {(value(a) / a['start_cash'] - 1) * 100:+.1f}% "
                         "since the start.", "day")
        return "closed the day"
    if not day.fresh("SPY"):
        return None
    n0 = len(a["log"])
    first = "morning" not in steps
    if first:
        start(a, day, spy_daily)
    if today >= a["end"]:
        end_trial(a, day)
    elif a["id"] == "A":
        if first:
            splits(a, day)
        a_exits(a, day, trend=first)
        if first:
            a_buys(a, day)
    else:
        if first:
            splits(a, day)
        b_trade(a, day, quiet=not first)
        b_marks(a, day)
    if first:
        a["days"][today] = steps + ["morning"]
    trades = sum(e["kind"] in ("buy", "sell") for e in a["log"][n0:])
    if first:
        return f"morning, {plural(trades, 'trade')}"
    return plural(trades, "trade") if trades else None


def load(state_dir, aid):
    f = Path(state_dir) / f"{aid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else new_account(aid)


def save(state_dir, accts):
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    for aid, a in accts.items():
        (Path(state_dir) / f"{aid}.json").write_text(json.dumps(a, separators=(",", ":")), encoding="utf-8")


def run(state_dir, mkt, now, hist, dry=False, test_quotes=False):
    """One scheduled run. Returns (what each account did, the accounts, accounts that hit an error),
    or None when there's nothing to do (before the trial, or the market hasn't traded today)."""
    accts = {aid: load(state_dir, aid) for aid in "AB"}
    if now.date().isoformat() < P["START"]:
        return None
    day = Day(mkt, now, hist, test_quotes)
    spy = day.price(["SPY"]).get("SPY")
    if spy is None or spy[1].date() != day.today:
        return None                                      # weekend, holiday or before the open
    spy_daily = mkt.daily(["SPY"], day.today, period="10d").get("SPY")
    if spy_daily is None or not len(spy_daily) or spy_daily.index[0].date() >= day.today:
        return None
    day.prev_day = max(d for d in spy_daily.index.date if d < day.today)
    did, errors = {}, []
    for aid in list(accts):
        keep = copy.deepcopy(accts[aid])
        try:
            r = step(accts[aid], day, spy_daily)
        except Exception:
            traceback.print_exc()
            accts[aid] = keep                            # undo the half-done run; the next run tries again
            errors.append(aid)
            continue
        if r:
            did[aid] = r
    for a in accts.values():
        a["mark"] = dict(t=tstr(now), v=r2(value(a)), spy=r2(spy[0]))
        a["updated"] = tstr(now)
        a["rules"], a["fills"] = rules(a["id"]), FILLS
    if not dry:
        save(state_dir, accts)
    return did, accts, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="folder with A.json and B.json (created if missing)")
    ap.add_argument("--history", default=str(Path(__file__).resolve().parent / "history"))
    ap.add_argument("--dry-run", action="store_true", help="print what would happen, save nothing")
    ap.add_argument("--at", help='pretend it is this New York time, e.g. "2026-10-06 10:05" (prices are still the latest)')
    ap.add_argument("--test-quotes", action="store_true", help="dry runs after hours: use last trades as option quotes")
    ap.add_argument("--message", help="write a commit message to this file when something worth a commit happened")
    ap.add_argument("--start", help="dry runs: pretend the trial starts on this date (to test on a day before the start)")
    a = ap.parse_args()
    if (a.test_quotes or a.start) and not a.dry_run:
        sys.exit("--test-quotes and --start are only for dry runs")
    if a.start:
        P["START"] = a.start
    now = pd.Timestamp(a.at, tz=NY) if a.at else pd.Timestamp.now(tz=NY)
    res = run(a.state, Yahoo(), now, a.history, a.dry_run, a.test_quotes)
    if res is None:
        print(f"{tstr(now)} New York: nothing to do (before the trial, or the market hasn't traded today).")
        return
    did, accts, errors = res
    for acct in accts.values():
        for e in acct["log"]:
            if e["t"] == tstr(now):
                print(f"[{acct['id']}] {e['kind']}: {e['text']}")
        print(f"[{acct['id']}] value {money(value(acct))}, cash {money(acct['cash'])}, "
              f"{plural(len(acct['positions']), 'position')}" + (" (dry run, not saved)" if a.dry_run else ""))
    msg = (f"Paper trading {tstr(now)} New York: " + "; ".join(f"{k} {v}" for k, v in did.items())) if did else None
    print(msg or "Only prices moved.")
    if msg and a.message:
        Path(a.message).write_text(msg + "\n", encoding="utf-8")
    if errors:
        sys.exit(f"Account {', '.join(errors)} hit an error and was left as it was; the next run tries again.")


if __name__ == "__main__":
    main()
