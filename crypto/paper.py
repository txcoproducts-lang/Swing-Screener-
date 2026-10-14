#!/usr/bin/env python3
"""Crypto paper trading: the stock trial's four accounts (../paper.py), on coins. Each starts with $1,000 and trades
until 2027-04-06, when the stock trial ends too.

  A  "Your system": last night's crypto screener setups (Momentum and Pullback). The stock version buys calls by
     your option rules; coins have no options, so it buys the coin, at most 30% of the account a trade (your cap).
  C  "Your system, after 2 PM": the same rules as A, but it only buys after 2:00 PM Central (3:00 PM New York).
  B  "Claude's picks": my AI picks list for coins (relative strength momentum), about a tenth of the account each.
  D  "OVTLYR plan": OVTLYR's Plan M on coins, Plan ETF on Bitcoin / Ether themselves (there are no 3x crypto funds),
     and spare cash as cash (Plan #SICADFU's SGOV is a Treasury fund, not a coin), on the plan crypto/screener.py
     builds each night (crypto/history/ovtlyr_<date>.json).

Coins trade every day, so this runs every day, weekends too, on the stock accounts' clock: GitHub Actions runs it
every 30 minutes (.github/workflows/crypto-paper.yml); the first run at or after 10:00 New York time sells and buys
(C only sells), later runs check stops and the 4-hour exit, C buys at the first run at or after 3:00 PM, D checks its closing-price exits
at the first run at or after 3:30 PM, and the first run after 4 PM records the day's value. "Last night's screener"
is the run after the previous day's bar closed at midnight UTC. The accounts are saved on the crypto-paper branch
(paper/A.json to D.json), which the crypto page reads. Every buy, sell and daily decision is logged with its reason.
An account that hits an error mid-run is left as it was, and the next run tries again.

  python crypto/paper.py --state DIR [--history DIR] [--dry-run] [--at "2026-10-13 10:05"]
"""
import argparse, copy, datetime as dt, json, math, sys, traceback
from pathlib import Path
import pandas as pd
import screener as SC            # crypto/screener.py (this folder comes first on the path)

NY = "America/New_York"
BENCH = SC.BENCH                 # Bitcoin: the benchmark each account is measured against, where the stocks use SPY
P = dict(
    START="2026-10-13", END="2027-04-06", CASH=1000.0,   # ends with the stock trial
    OPEN=dt.time(10, 0),          # the first run at or after this sells and buys (the stock accounts' clock)
    CLOSE=dt.time(16, 0),         # the first run at or after this records the day's value
    STALE_MIN=20,                 # Yahoo's latest 1-minute bar must be this fresh to trade on it
    STALE_DAYS=5,                 # if a nightly run failed, trade on screener files up to this many days old
    SLIP=0.0005,                  # coins fill 0.05% worse than the last trade
    # A: your screener rules
    A_SLOTS=2,                    # positions at a time
    A_CAP=0.30,                   # each buy: at most this share of the account's value (your rule, from 2026-10-09)
    A_SCAN=15,                    # how far down the setups to look for one that passes the checks at buying time
    A_STOP=0.08,                  # sell on an 8% drop (the stock accounts' stop for shares)
    A_4H_FROM="2026-10-14",       # your exit from this day: the 4-hour EMA10 under the EMA20 and the price under the 4-hour EMA50
    # C: A's rules, buying only in the afternoon
    C_BUY=dt.time(15, 0),         # 2:00 PM Central: the first run at or after this buys
    # B: my AI picks
    B_SLOTS=10,
    # D: OVTLYR's trading plans, on the plan crypto/screener.py builds each night
    D_RISK=0.05, D_SIZE_ATR=2.0,  # Plan M size: coins = account x 5% / (2 x ATR), as in the deck
    D_STOP_ATR=0.5,               # Plan M stop loss: a close half an ATR under the entry
    D_EMERGENCY_ATR=2.0,          # Plan M emergency exit: any price 2 ATR under the entry
    D_MAX_DAYS=120,               # Plan M: out after 120 calendar days
    D_GAP=0.05, D_GAP_DAYS=3,     # gap & crap: a 5%+ gap up, then a close under that day's low within 3 days
    D_LATE=dt.time(15, 30),       # the first run at or after this decides Plan M's closing-price exits
    D_LOSERS=3, D_PAUSE=7,        # 3 losing trades in a day: no new trades for 7 days
    D_MIN=25.0,                   # smallest trade, in dollars
)
IDS = "ABCD"
NAMES = {"A": "Your system", "B": "Claude's picks", "C": "Your system, after 2 PM", "D": "OVTLYR plan"}
FILLS = ("Paper trades, no real money. Coins fill at Yahoo's latest 1-minute price, 0.05% worse, and fractions of a coin "
         "are allowed. No exchange fee is charged; real exchanges charge about 0.1% to 0.6% a trade.")


def rules(aid):
    if aid == "D":
        return d_rules()
    if aid in ("A", "C"):
        when = ("Buys and sells at about 10:00 New York time, every day (coins trade on weekends too), then checks its "
                "exits every 30 minutes until 5:45 PM New York time." if aid == "A" else
                "Buys only after 2:00 PM Central (3:00 PM New York), at the first check after that, using the same "
                "setups as Your system. Sells on the same signals, checked every 30 minutes from 10:00 AM to 5:45 PM New "
                "York time.")
        return [
            "Uses your screener on coins: last night's setups (Momentum and Pullback), in the coin table's order. "
            "Last night = the screener run after the day's bar closed at midnight UTC (7 PM Central in winter, 8 PM in summer).",
            f"Holds {P['A_SLOTS']} positions at a time, and never spends more than {P['A_CAP']:.0%} of the account "
            "on one buy. " + when,
            "Buys the coin itself. The stock version buys a call by your option rules (15-30 days out, delta 0.50-0.80, "
            "open interest over 500); coins have no options a normal brokerage account can buy, so it does what the stock "
            "version does when no call fits: buys the top setup outright.",
            f"Takes the first of the top {P['A_SCAN']} setups that passes the checks when it buys, and skips a setup that "
            "has dropped below its 50-day EMA by then.",
            f"Your overbought rule: it doesn't buy anything with RSI over {SC.CFG['OB_RSI']} or CCI over "
            f"{SC.CFG['OB_CCI']} (checked on the live price when it buys), or while the market's breadth or the coin's "
            f"category's is over the {SC.CFG['OB_BREADTH']} line (the share of its coins with the 10 EMA over the 20, last night).",
            "Your exit (from Oct 14): it enters on the daily chart and sells on the 4-hour chart, once a 4-hour bar "
            "closes with the 10 EMA under the 20 EMA and the price under the 50 EMA, both at once. The bars are the "
            "Trend view's 4H bars (4 hours each from midnight UTC) and only bars that close after the buy count. It "
            "sells at the next check after the bar closes; bars that close overnight sell at about 10:00 New York time.",
            f"Safety net, my default: it also sells if the coin drops {P['A_STOP']:.0%}.",
        ]
    return [
        f"Copies my AI picks list for coins: up to {P['B_SLOTS']} coins, at most {SC.CFG['AI_CAP']} per category, ranked by "
        "relative strength among liquid coins (the IBD formula: 40% weight on the last 3 months, 20% each on 6, 9 and 12).",
        "Trades at about 10:00 New York time, every day: sells coins that left the list the night before and buys the new "
        "ones, about a tenth of the account each. Empty spots stay in cash.",
        f"Your overbought rule: it doesn't buy anything with RSI over {SC.CFG['OB_RSI']} or CCI over "
        f"{SC.CFG['OB_CCI']} (checked on the live price when it buys), or while the market's breadth or the coin's "
        f"category's is over the {SC.CFG['OB_BREADTH']} line (the share of its coins with the 10 EMA over the 20, last night).",
        "A pick it skipped for being overbought is bought later, once it isn't, while it's still on the list.",
        f"A coin stays while it ranks in the top {SC.CFG['AI_KEEP']}. No stop-loss, as in the stock version.",
        "The stock version of this list was tested on S&P 500 stocks (2014-2026); it has not been tested on coins, which "
        "swing much harder.",
    ]


def d_rules():
    ov = SC.OV
    return [
        "Trades OVTLYR's plans from the deck you shared, on the OVTLYR plan section of the crypto page, rebuilt from the "
        "screener's data each night. OVTLYR's heatmap and buy/sell signals are private, so it uses stand-ins: "
        "heatmap = 14-day RSI; buy signal = the 10-day EMA crossing above the 20-day; sell signal = the 10 under the 20; "
        "breadth = the share of coins with the 10 above the 20, against its 10-day average. Bitcoin stands in for SPY "
        "and coin categories for sectors.",
        "Plan M (coins), at about 10:00 New York time, when all the market checks passed last night: buys coins with a "
        f"buy signal in the last {ov['SIGNAL_DAYS']} days, the 10/20/50 uptrend, the price over the 10 EMA, a rising "
        f"RSI, {SC.fusd(SC.CFG['MIN_AVG_VOL'])}+ traded a day, a passing category and no order block within "
        f"{ov['OB_GAP']:.0%}. No price range or earnings check (they're for stock options and earnings). No new Plan M "
        "trades while Bitcoin's last close is under its 20 EMA, one of the plan's exits.",
        f"Plan M size, the deck's formula: {P['D_RISK']:.0%} of the account at risk over a {P['D_SIZE_ATR']:g} ATR move, "
        "as far as the cash goes. The coin itself, not the deck's 80-delta calls: coins have no options.",
        f"Plan M exits, decided on the live price at about 3:30 PM New York time: a price {P['D_STOP_ATR']:g} ATR under "
        "the entry (the stop loss), the 10 EMA under the 20 (the 10/20 bearish cross, also the sell signal here), Bitcoin "
        "under its 20 EMA, RSI at the heatmap target (entry RSI under 50: 63; 50-75: +10; 75 and up: +5), a gap and crap "
        "(a 5%+ gap up, then a close under that day's low within 3 days), or reaching an untouched order block above the "
        "entry. One that only shows at the day's close (midnight UTC) sells at 10:00 the next morning.",
        f"Also sells a Plan M coin at once if it falls {P['D_EMERGENCY_ATR']:g} ATR under the entry (the emergency exit, "
        "checked every 30 minutes), and at about 10:00 New York time the morning after its category's breadth turns "
        f"bearish, or after {P['D_MAX_DAYS']} days.",
        "Plan ETF, with cash left and no Plan M trade to take: there are no 3x crypto funds like TQQQ or SPXL, so it buys "
        "Bitcoin or Ether itself on its own signals (half each if both qualify): heatmap under "
        f"{ov['HEAT_MAX']}, a buy signal, the uptrend, the price in the value zone (the 20 EMA to {ov['ZONE_ATR']:g} ATR "
        f"above it) and no order block {ov['ETF_OB_AGE']}+ days old within {ov['OB_GAP']:.0%}. Sells at about 10:00 the "
        "morning after its 10/20 bearish cross, a close more than "
        f"{ov['HOT_ATR']:g} ATR above its 20 EMA, or reaching a {ov['ETF_OB_AGE']}+ day old order block.",
        f"Your overbought rule, on top of the plan: no Plan M coin with RSI over {SC.CFG['OB_RSI']} or CCI over "
        f"{SC.CFG['OB_CCI']} (checked on the live price when it buys), no Plan ETF buy while that coin is, and nothing "
        f"while the market's breadth or the coin's category's is over the {SC.CFG['OB_BREADTH']} line.",
        "Plan #SICADFU: the stock version parks spare cash in SGOV, a Treasury bill fund; that isn't a coin, so here spare "
        "cash simply waits as cash.",
        f"After {P['D_LOSERS']} losing trades in one day, no new trades for {P['D_PAUSE']} days (it keeps the ones it has).",
    ]


# ------------------------------------------------------------------ helpers
def tstr(ts): return ts.strftime("%Y-%m-%d %H:%M")
def r2(x): return round(float(x), 2)
def rq(x): return round(float(x), 8)                 # coin amounts: fractions of a coin
def day_str(d): return f"{d:%b} {d.day}"
def plural(n, word): return f"{n:g} {word}{'' if n == 1 else 's'}"


def money(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def usd(x):
    """A coin's price: $64,321.50, $0.2134, $0.00001234."""
    return f"${SC.fp(x)}"


def qty_str(q):
    return f"{q:,.8f}".rstrip("0").rstrip(".") if q < 1000 else f"{q:,.0f}" if q >= 100000 else f"{q:,.2f}"


def exit_4h(hourly, since, now):
    """Your exit: the first 4-hour bar (from midnight UTC, as the Trend view draws them) closed after `since` (and by
    `now`) with EMA10 < EMA20 and close < EMA50, as (bar close time, close, e10, e20, e50), or None. Times are UTC,
    without a time zone."""
    h = hourly.dropna(subset=["Close"])
    h = h.tz_convert("UTC").tz_localize(None) if h.index.tz is not None else h
    b = SC.to_4h(h[h.index < now])
    if b.empty:
        return None
    ends = pd.DatetimeIndex(b.index) + pd.Timedelta(hours=4)
    b, ends = b[ends <= now], ends[ends <= now]
    if len(b) < 60:
        return None
    c = b["Close"]
    e10, e20, e50 = SC.ema(c, 10), SC.ema(c, 20), SC.ema(c, 50)
    print(f"  4-hour bar closed {ends[-1]:%Y-%m-%d %H:%M}: close {c.iloc[-1]:.4g}, EMA10 {e10.iloc[-1]:.4g}, "
          f"EMA20 {e20.iloc[-1]:.4g}, EMA50 {e50.iloc[-1]:.4g}")
    for i in range(len(b)):
        if ends[i] > since and e10.iloc[i] < e20.iloc[i] and c.iloc[i] < e50.iloc[i]:
            return ends[i], float(c.iloc[i]), float(e10.iloc[i]), float(e20.iloc[i]), float(e50.iloc[i])
    return None


def plan_text(t, plan):
    return (f"sell after a 4-hour bar on {t} closes with the 10 EMA under the 20 and the price under the 50 EMA (your "
            f"exit), or if it drops {P['A_STOP']:.0%} (to {usd(plan['stop'])}).")


# ------------------------------------------------------------------ market data (Yahoo, on GitHub Actions)
class Yahoo:
    def __init__(self, hist):
        import yfinance as yf
        self.yf = yf
        f = Path(hist) / "yahoo_names.json"            # which Yahoo name each coin trades under (the nightly saves it)
        if f.exists():
            SC.YF.update(json.loads(f.read_text(encoding="utf-8")))

    def _minute(self, tickers):
        tks = sorted(set(tickers))
        if not tks:
            return {}
        names = {SC.yahoo_names(t)[0]: t for t in tks}
        df = self.yf.download(list(names), period="1d", interval="1m", group_by="ticker", auto_adjust=False,
                              progress=False, threads=True)
        out = {}
        if df is None or df.empty:
            return out
        for n, t in names.items():
            try:
                f = (df[n] if isinstance(df.columns, pd.MultiIndex) else df).dropna(subset=["Close"])
            except KeyError:
                continue
            if len(f):
                out[t] = f
        return out

    def prices(self, tickers):
        """{coin: (last price, its time in New York)} from today's 1-minute bars."""
        out = {}
        for t, f in self._minute(tickers).items():
            ts = f.index[-1]
            ts = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY)
            out[t] = (float(f["Close"].iloc[-1]), ts)
        return out

    def daily(self, tickers, through, period="1y"):
        """{coin: daily bars} up to and including the date `through` (UTC days)."""
        tks = sorted(set(tickers))
        if not tks:
            return {}
        fr = SC.yf_batch(tks, period=period, interval="1d")
        out = {}
        for t, d in fr.items():
            if d.index.tz is not None:
                d = d.tz_convert("UTC").tz_localize(None)
            out[t] = d[d.index.date <= through]
        return out

    def hourly(self, tickers, today):
        """{coin: hourly bars over the last year}, for the 4-hour exit (the Trend view's 4H bars are built from these)."""
        tks = sorted(set(tickers))
        if not tks:
            return {}
        return SC.yf_batch(tks, start=(today - dt.timedelta(days=365)).isoformat(), interval="60m")

    def session(self, tickers, today):
        """{coin: (open, high, low)} of today's daily bar so far (the UTC day), from 1-minute bars."""
        out = {}
        for t, f in self._minute(tickers).items():
            ts = f.index.tz_convert("UTC") if f.index.tz is not None else f.index
            f = f[ts.date == today]
            if len(f):
                out[t] = (float(f["Open"].iloc[0]), float(f["High"].max()), float(f["Low"].min()))
        return out


# ------------------------------------------------------------------ the run's context
class Day:
    """What a run knows: the time, the market, last night's screener files and the prices it has fetched."""
    def __init__(self, mkt, now, hist):
        self.mkt, self.now, self.hist = mkt, now, Path(hist)
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

    def ovtlyr(self):
        """The latest OVTLYR plan from before today: (date, plan), or (date or None, None) if too old."""
        files = sorted(f for f in self.hist.glob("ovtlyr_*.json") if f.stem[7:] < self.today.isoformat())
        d = dt.date.fromisoformat(files[-1].stem[7:]) if files else None
        return (d, json.loads(files[-1].read_text(encoding="utf-8"))) if self.recent(d) else (d, None)

    def breadth(self):
        """Last night's breadth from the screener (the page's Rising: the share of each group's coins with the 10 EMA
        over the 20): {"Crypto market" or a category: %}, or {} when the file is missing or too old."""
        files = sorted(f for f in self.hist.glob("breadth_*.csv") if f.stem[8:] < self.today.isoformat())
        d = dt.date.fromisoformat(files[-1].stem[8:]) if files else None
        if not self.recent(d):
            return {}
        return {r.group: float(r.rise) for r in pd.read_csv(files[-1]).itertuples() if r.rise == r.rise}

    def ai(self):
        """My AI picks list as of its last nightly update, plus each pick's rank and reasons from that night's
        Top picks file."""
        f = self.hist / "ai_picks.json"
        st = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        info, tp = {}, self.hist / f"toppicks_{(st or {}).get('as_of')}.csv"
        if tp.exists():
            d = pd.read_csv(tp)
            for _, r in d[d.list == "ai"].iterrows():
                rk, why, sec = r.get("ai_rank"), r.get("why"), r.get("sector")
                info[r.ticker] = dict(rank=int(rk) if rk is not None and rk == rk else None,
                                      why=why if isinstance(why, str) else "", sector=sec if isinstance(sec, str) else "")
        return st, info


# ------------------------------------------------------------------ accounts and fills
def new_account(aid):
    return dict(id=aid, name=NAMES[aid], start=P["START"], end=P["END"], start_cash=P["CASH"], cash=P["CASH"],
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
    pos.update(sell=dict(t=tstr(now), price=SC.rp(price), proceeds=r2(proceeds), why=why),
               pnl=r2(pnl), pnl_pct=round(pnl / pos["buy"]["cost"] * 100, 2), days=days,
               last=dict(t=tstr(now), price=SC.rp(price), value=r2(proceeds)))
    a["closed"].append(pos)
    res = f"{'+' if pnl >= 0 else '-'}{money(abs(pnl))} ({pos['pnl_pct']:+.1f}%) in {plural(days, 'day')}"
    note(a, now, f"Sold {qty_str(pos['qty'])} {pos['ticker']} at {usd(price)}, {money(proceeds)}. {why} Result: {res}.", "sell")


def buy_coin(a, now, t, price, budget, why, plan):
    fill = price * (1 + P["SLIP"])
    qty = math.floor(budget / fill * 1e8) / 1e8
    if qty <= 0:
        return None
    cost = r2(qty * fill)
    pos = open_pos(a, ticker=t, kind="coin", qty=qty, label=f"{qty_str(qty)} {t}",
                   buy=dict(t=tstr(now), price=SC.rp(fill), cost=cost, why=why), plan=plan,
                   last=dict(t=tstr(now), price=SC.rp(price), value=r2(qty * price)))
    note(a, now, f"Bought {qty_str(qty)} {t} at {usd(fill)}, {money(cost)}. {why} Plan: {plan['text']}", "buy")
    return pos


def sell_coin(a, pos, now, price, why):
    fill = price * (1 - P["SLIP"])
    close_pos(a, pos, now, fill, pos["qty"] * fill, why)


def mark(pos, now, price):
    pos["last"] = dict(t=tstr(now), price=SC.rp(price), value=r2(pos["qty"] * price))


# ------------------------------------------------------------------ A and C: your screener rules
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


def market_hot(day):
    """Your overbought rule for the whole market: last night's crypto market breadth over the 75 line. The reason, or ""."""
    return SC.breadth_hot(None, day.breadth())


def with_today(d, sess, price, today):
    """Daily bars through yesterday plus today's bar so far (the live price as its close)."""
    o, h, l = sess
    ts = pd.Timestamp(today) if d.index.tz is None else pd.Timestamp(today).tz_localize(d.index.tz)
    row = pd.DataFrame({"Open": [o], "High": [max(h, price)], "Low": [min(l, price)], "Close": [price], "Volume": [0.0]},
                       index=pd.DatetimeIndex([ts]))
    return pd.concat([d[["Open", "High", "Low", "Close", "Volume"]], row])


def hot_now(day, items):
    """Your overbought rule at buying time: {coin: why} for each (coin, category) in items that is overbought now:
    RSI over 70 or CCI over 100 on its daily bars plus today's trading so far, or last night's breadth for its category
    over the 75 line (the market's is market_hot). Without today's bars it goes by last night's close; a coin whose
    daily bars don't load is judged on its category alone."""
    tks = sorted({t for t, _ in items})
    if not tks:
        return {}
    br = day.breadth()
    bars = day.mkt.daily(tks, day.prev_day)
    try:
        sess = day.mkt.session(tks, day.today)
    except Exception as e:                       # then it goes by last night's close
        print(f"  today's bars didn't load for the overbought check: {e}")
        sess = {}
    px = day.price(tks)
    out = {}
    for t, sec in items:
        why = []
        d = bars.get(t)
        if d is not None and len(d) > 3 * SC.CFG["CCI_N"]:
            if t in sess and day.fresh(t):
                try:
                    d = with_today(d, sess[t], px[t][0], day.today)
                except Exception as e:
                    print(f"  today's bar failed for {t}, so it goes by last night's close: {e}")
            why = SC.hot(float(SC.rsi(d["Close"]).iloc[-1]), float(SC.cci(d.tail(3 * SC.CFG["CCI_N"])).iloc[-1]))
        if isinstance(sec, str) and sec and SC.breadth_hot(sec, br):
            why.append(SC.breadth_hot(sec, br))
        if why:
            out[t] = " and ".join(why)
    return out


def passed_over(passed, n):
    """The buy note's line for higher setups (rank under n) your overbought rule left out, or ""."""
    left = [s for m, s in passed if m < n]
    more = f" and {len(left) - 5} more" if len(left) > 5 else ""
    return f" Passed over as overbought (your rule): {', '.join(left[:5])}{more}." if left else ""


def new_exits(a, day):
    """Your 4-hour exit replaced my daily trend-break exit on Oct 14, mid-trial: rewrite the plans of coins bought
    before then, once, and say so in the log."""
    old = [p for p in a["positions"] if not p["plan"].get("x4h")]
    for p in old:
        p["plan"]["text"] = plan_text(p["ticker"], p["plan"])
        p["plan"]["x4h"] = True
    if old:
        note(a, day.now, "Exit rule changed (your rule, from Oct 14): " + ", ".join(p["label"] for p in old)
             + (" now sell" if len(old) > 1 else " now sells") + " once a 4-hour bar closes with the 10 EMA under the 20 "
             "and the price under the 50 EMA, instead of on a daily close below the 50-day EMA or 150-day average. "
             f"The {P['A_STOP']:.0%} stop stays.")


def a_exits(a, day):
    """Your 4-hour exit and the stop, on every run."""
    now = day.now
    if not a["positions"]:
        return
    new_exits(a, day)
    px = day.price([p["ticker"] for p in a["positions"]])
    hourly = day.mkt.hourly([p["ticker"] for p in a["positions"]], day.today)
    utc = now.tz_convert("UTC").tz_localize(None)
    for p in a["positions"]:
        h = hourly.get(p["ticker"])
        if p.get("exit") or h is None:
            continue
        print(f"  {p['ticker']}, your 4-hour exit:")
        bought = pd.Timestamp(p["buy"]["t"], tz=NY).tz_convert("UTC").tz_localize(None)
        x = exit_4h(h, max(bought, pd.Timestamp(P["A_4H_FROM"], tz=NY).tz_convert("UTC").tz_localize(None)), utc)
        if x:
            end, c, e10, e20, e50 = x
            end_ny = end.tz_localize("UTC").tz_convert(NY)
            p["exit"] = (f"Your exit: the 4-hour bar that closed {day_str(end_ny)} at {end_ny:%-I:%M %p} New York time closed "
                         f"at {usd(c)}, under its 50 EMA ({usd(e50)}), with the 10 EMA ({usd(e10)}) under the 20 ({usd(e20)}).")
    for p in list(a["positions"]):
        t = p["ticker"]
        if not day.fresh(t):
            continue
        price = px[t][0]
        mark(p, now, price)
        if p.get("exit"):
            sell_coin(a, p, now, price, p["exit"])
        elif price <= p["plan"]["stop"]:
            sell_coin(a, p, now, price, f"It fell to {usd(price)}, through the {P['A_STOP']:.0%} stop at {usd(p['plan']['stop'])}.")


def a_buys(a, day):
    now = day.now
    if len(a["positions"]) >= P["A_SLOTS"]:
        note(a, now, f"No new buy: both slots are taken ({'; '.join(p['label'] for p in a['positions'])}).", "day")
        return
    mh = market_hot(day)
    if mh:
        note(a, now, f"No new buy: the market is overbought ({mh}, last night). Your rule: nothing gets bought then.", "day")
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
    hot = hot_now(day, [(r.ticker, r.get("sector")) for _, r in scan if r.ticker not in sold_today and day.fresh(r.ticker)])
    while len(a["positions"]) < P["A_SLOTS"]:
        budget = min(a["cash"], value(a) * P["A_CAP"])
        if budget < 50:
            note(a, now, f"No new buy: only {money(a['cash'])} in cash.", "day")
            return
        within = f"{P['A_CAP']:.0%} of the account" if budget < a["cash"] else "the cash on hand"
        held = {p["ticker"] for p in a["positions"]}
        skipped, passed, pick = [], [], None
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
                skipped.append(f"{t} was at {usd(S)}, below its 50-day EMA ({usd(e50)})")
                continue
            if t in hot:
                skipped.append(f"{t} was overbought: {hot[t]}")
                passed.append((n, f"#{n} {t} ({hot[t]})"))
                continue
            pick = (n, r, S)
            break
        if not pick:
            note(a, now, "No new buy: none of the top setups passed the checks at buying time"
                         + (f" ({'; '.join(skipped[:5])})." if skipped else "."), "day")
            return
        n, r, S = pick
        t = r.ticker
        stop = SC.rp(S * (1 - P["A_STOP"]))
        plan = dict(stop=stop, x4h=True)
        plan["text"] = plan_text(t, plan)
        why = (f"{setup_why(r, n, src)} {money(budget)} ({within}). The coin itself: there are no options to buy on it."
               + passed_over(passed, n))
        if buy_coin(a, now, t, S, budget, why, plan) is None:
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
        sell_coin(a, p, now, px[t][0], f"It left my AI picks list last night: it {g['why']}." if g and g.get("why")
                  else "It's no longer on my AI picks list.")
        acted += 1
    have = {p["ticker"] for p in a["positions"]}
    new = [t for t in picks if t not in have]
    mh = market_hot(day)
    hot = ({t: mh for t in new} if mh else
           hot_now(day, [(t, info.get(t, {}).get("sector", "")) for t in new if day.fresh(t)]))
    if hot and not quiet:
        note(a, now, (f"Not buying {', '.join(hot)}: the market is overbought ({mh}, last night)." if mh else
                      "Not buying " + "; ".join(f"{t} (overbought: {w})" for t, w in hot.items()) + ".")
             + " Your rule: nothing overbought gets bought. It checks again every 30 minutes, and on later days while "
               "the pick is on the list.", "note")
    new = [t for t in new if t not in hot]
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
        why = (f"On my AI picks list ({since}), {rank} by relative strength among liquid coins"
               + (f": {inf['why']}." if inf.get("why") else "."))
        plan = dict(text=f"hold while it ranks in the top {SC.CFG['AI_KEEP']} (checked each night) and sell the morning "
                         "after it drops out.")
        if buy_coin(a, now, t, px[t][0], budget, why, plan):
            acted += 1
    if quiet:
        return
    if waiting:
        note(a, now, f"Waiting for a live price to {', '.join(waiting)}; trying again every 30 minutes.", "note")
    if not acted and not waiting and not hot:
        hold = sorted(p["ticker"] for p in a["positions"])
        note(a, now, f"No trades: my list didn't change{' last night' if as_of == day.prev_day else ''}, so I'm holding "
                     f"{plural(len(hold), 'coin')}"
                     + (f" ({', '.join(hold)})." if hold else "."), "day")


def marks(a, day):
    px = day.price([p["ticker"] for p in a["positions"]])
    for p in a["positions"]:
        if day.fresh(p["ticker"]):
            mark(p, day.now, px[p["ticker"]][0])


# ------------------------------------------------------------------ D: OVTLYR's trading plans
def legs(a, leg):
    return [p for p in a["positions"] if p.get("leg") == leg]


def lc(text):
    """A check's text to go mid-sentence: 'Market breadth: ...' -> 'market breadth: ...' (tickers stay as they are)."""
    return text[:1].lower() + text[1:] if text[:2].istitle() else text


def heat_target(r):
    """The deck's heatmap target from the heatmap at entry (RSI here): under 50: 63; 50-75: +10 points; 75 and up: +5."""
    return 63.0 if r < 50 else r + 10 if r < 75 else r + 5


def m_exits(p, d, btc):
    """Plan M's closing-price exits for one coin, judged on the last bar of its daily bars `d` (today so far at the
    afternoon check, last night's close in the morning) and Bitcoin's `btc`. Returns the reasons, if any."""
    c, pl = d["Close"], p["plan"]
    last, out = float(c.iloc[-1]), []
    if last < pl["stop"]:
        out.append(f"under the stop at {usd(pl['stop'])}, {P['D_STOP_ATR']:g} ATR under the entry")
    e10, e20 = float(SC.ema(c, 10).iloc[-1]), float(SC.ema(c, 20).iloc[-1])
    if e10 < e20:
        out.append(f"its 10 EMA ({usd(e10)}) under its 20 EMA ({usd(e20)}), the 10/20 bearish cross")
    if p["ticker"] != BENCH:
        sc, s20 = float(btc["Close"].iloc[-1]), float(SC.ema(btc["Close"], 20).iloc[-1])
        if sc < s20:
            out.append(f"{BENCH} at {usd(sc)}, under its 20 EMA ({usd(s20)})")
    r = float(SC.rsi(c).iloc[-1])
    if r >= pl["heat"]:
        out.append(f"RSI {r:.0f}, at the heatmap target of {pl['heat']:.0f}: selling into strength")
    o, lo, cl = (d[k].to_numpy(float) for k in ("Open", "Low", "Close"))
    days = list(d.index.date)
    since = dt.date.fromisoformat(p["buy"]["t"][:10])
    for g in range(1, len(cl)):                        # gap & crap: a 5%+ gap up since the buy...
        if days[g] < since or o[g] < cl[g - 1] * (1 + P["D_GAP"]):
            continue
        crap = [j for j in range(g + 1, min(g + 1 + P["D_GAP_DAYS"], len(cl))) if cl[j] < lo[g]]
        if crap:                                       # ...then a close under that day's low within 3 days
            out.append(f"a gap and crap: up {(o[g] / cl[g - 1] - 1) * 100:.1f}% at the open on {day_str(days[g])}, then "
                       f"under that day's low of {usd(lo[g])}")
            break
    hi = float(d["High"].iloc[-1])
    hit = [b for b in SC.ov_blocks(d.iloc[:-1]) if b["fresh"] and b["bot"] > p["buy"]["price"] and hi >= b["bot"]]
    if hit:
        b = min(hit, key=lambda b: b["bot"])
        out.append(f"into the order block at {usd(b['bot'])}-{usd(b['top'])} from {day_str(b['start'])}: selling into strength")
    return out


def d_watch(a, day):
    """Every run: mark the positions to the latest prices and sell a Plan M coin at its emergency exit."""
    px = day.price([p["ticker"] for p in a["positions"]])
    for p in list(a["positions"]):
        t = p["ticker"]
        if not day.fresh(t):
            continue
        price = px[t][0]
        mark(p, day.now, price)
        if p["leg"] == "M" and price <= p["plan"]["emergency"]:
            sell_coin(a, p, day.now, price, f"It fell to {usd(price)}, through the emergency exit at "
                                            f"{usd(p['plan']['emergency'])} ({P['D_EMERGENCY_ATR']:g} ATR under the "
                                            "entry), where the plan says to sell without waiting for the close.")


def d_exits(a, day, sd, plan, bars):
    """The morning's exits: Plan M signals at last night's close (the afternoon check sees the price before the
    close), 120 days and category breadth; Plan ETF's sell signals."""
    now = day.now
    px = day.price([p["ticker"] for p in a["positions"]])
    btc = bars.get(BENCH)
    for p in [p for p in legs(a, "M") if day.fresh(p["ticker"])]:
        t, why = p["ticker"], None
        held = (day.today - dt.date.fromisoformat(p["buy"]["t"][:10])).days
        sec = (plan or {}).get("sectors", {}).get(p.get("sector") or "")
        d = bars.get(t)
        if held >= P["D_MAX_DAYS"]:
            why = f"It has been held {held} days; the plan closes a trade after {P['D_MAX_DAYS']}."
        elif sec and sec["bull"] <= sec["bull_ema"]:
            why = (f"The {p['sector']} category's breadth turned bearish in {day.source(sd).replace('screener', 'OVTLYR plan')}: "
                   f"{sec['bull']:.0f}% of its coins have the 10 EMA above the 20, not above the 10-day average of "
                   f"{sec['bull_ema']:.0f}%.")
        elif d is not None and btc is not None and len(d) > 60 and d.index[-1].date() == day.prev_day == btc.index[-1].date():
            fr = m_exits(p, d, btc)
            if fr:
                why = (f"{t} closed at {usd(float(d['Close'].iloc[-1]))} on {day_str(day.prev_day)} (midnight UTC): " + "; ".join(fr)
                       + ". That showed only at the close, after the afternoon check, so it sells this morning.")
        if why:
            sell_coin(a, p, now, px[t][0], why)
    for p in legs(a, "ETF"):
        e = (plan or {}).get("etf", {}).get(p["ticker"])
        if e and e["sell"] and day.fresh(p["ticker"]):
            sell_coin(a, p, now, px[p["ticker"]][0], "Plan ETF sell signal last night: " + "; ".join(e["sell"]) + ".")


def d_buys(a, day, sd, plan, bars):
    """The morning's buys: Plan M setups, then Plan ETF (Bitcoin / Ether) with the cash left; the rest stays cash."""
    now, today = day.now, day.today
    news = []                                          # what the plan said, for the day's note when nothing is bought
    n0 = sum(e["kind"] == "buy" for e in a["log"])
    paused = a.get("pause") and today.isoformat() < a["pause"]
    sold_today = {p["ticker"] for p in a["closed"] if p["sell"]["t"][:10] == today.isoformat()}
    if sd and plan is None:
        news.append(f"The latest OVTLYR plan is from {day_str(sd)}, too old to trade on (a nightly run failed)")
    elif plan is None:
        news.append("There's no OVTLYR plan yet")
    src = day.source(sd).replace("screener", "OVTLYR plan") if sd else ""
    if plan is not None and paused:
        news.append(f"No new trades until {day_str(dt.date.fromisoformat(a['pause']))}, after {P['D_LOSERS']} losing trades in one day")
    elif plan is not None:
        # Plan M
        m, btc = plan["market"], bars.get(BENCH)
        s20 = float(SC.ema(btc["Close"], 20).iloc[-1]) if btc is not None and len(btc) > 60 else None
        held = {p["ticker"] for p in a["positions"]}
        cand = [s for s in plan["setups"] if s["ticker"] not in held and s["ticker"] not in sold_today]
        mh = market_hot(day)
        if mh:
            news.append(f"Plan M waits: the market is overbought ({mh}, last night), and your rule buys nothing then")
        elif not m["ok"]:
            news.append("Plan M is off: " + "; ".join(lc(c["text"]) for c in m["checks"] if not c["ok"]))
        elif s20 is None:
            news.append(f"Plan M waits: {BENCH}'s daily prices didn't load")
        elif float(btc["Close"].iloc[-1]) < s20:
            news.append(f"Plan M waits: {BENCH} closed at {usd(float(btc['Close'].iloc[-1]))}, under its 20 EMA ({usd(s20)}), "
                        "one of the plan's exits")
        elif plan["setups"] and not cand:
            news.append(f"Plan M: the setups in {src} are already held or were sold today")
        elif not cand:
            f = plan["funnel"]
            why = [f"{f['signal']} coins had a buy signal", f"{f['rules']} of them passed the coin rules",
                   f"{f['sector']} were in a passing category"]
            if f["near_ob"]:
                why.append(f"{f['near_ob']} of those were within {SC.OV['OB_GAP']:.0%} of an order block")
            news.append(f"Plan M: no setups in {src}" + (f" ({'; '.join(why)})" if f["signal"] else ""))
        else:
            px = day.price([s["ticker"] for s in cand])
            hot = hot_now(day, [(s["ticker"], s["sector"]) for s in cand if day.fresh(s["ticker"])])
            skipped = []
            for s in cand:
                t = s["ticker"]
                if not day.fresh(t):
                    skipped.append(f"{t} had no live price")
                    continue
                if t in hot:
                    skipped.append(f"{t} was overbought: {hot[t]}")
                    continue
                S = px[t][0]
                if S <= s["e10"]:
                    skipped.append(f"{t} was at {usd(S)}, under its 10 EMA ({usd(s['e10'])})")
                    continue
                if s["ob_up"] and S >= s["ob_up"] / (1 + SC.OV["OB_GAP"]):
                    skipped.append(f"{t} was at {usd(S)}, within {SC.OV['OB_GAP']:.0%} of the order block at {usd(s['ob_up'])}")
                    continue
                risk, atr = P["D_RISK"] * value(a), s["atr"]
                want = risk / (P["D_SIZE_ATR"] * atr)
                fill = S * (1 + P["SLIP"])
                have = a["cash"]
                budget = min(want * fill, have)
                if budget < P["D_MIN"]:
                    skipped.append(f"{t} is set up, but only {money(have)} is left to spend")
                    break
                sec = plan["sectors"].get(s["sector"], {})
                cross = dt.date.fromisoformat(s["cross"])
                rise = (f"{s['rsi_prev']:.0f} to {s['rsi']:.0f}" if round(s["rsi_prev"]) != round(s["rsi"]) else
                        f"{s['rsi_prev']:.1f} to {s['rsi']:.1f}")
                why = (f"Plan M setup in {src}: a buy signal on {day_str(cross)} (the 10 EMA crossing above the 20), the "
                       f"10/20/50 uptrend, the price over the 10 EMA ({usd(s['e10'])}) and RSI rising ({rise}). Its category, "
                       f"{s['sector']}, passes (breadth {sec.get('bull', 0):.0f}% against a {sec.get('bull_ema', 0):.0f}% "
                       f"average, RSI {sec.get('rsi', 0):.0f} above {BENCH}'s {m['spy']['rsi']:.0f}), and so do all the market checks. "
                       + (f"The nearest order block above is at {usd(s['ob_up'])}, {(s['ob_up'] / S - 1) * 100:.1f}% up. "
                          if s["ob_up"] else "No untouched order block above it. ")
                       + f"Size: {P['D_RISK']:.0%} of the account ({money(risk)}) at risk over {P['D_SIZE_ATR']:g} ATR "
                       f"({usd(P['D_SIZE_ATR'] * atr)} a coin) is {qty_str(want)} {t} ({money(want * fill)})"
                       + (f", more than the {money(have)} it has, so it buys what that covers. " if want * fill > have else ". ")
                       + "The coin itself, not the deck's 80-delta calls: coins have no options.")
                stop, emer = fill - P["D_STOP_ATR"] * atr, fill - P["D_EMERGENCY_ATR"] * atr
                heat = heat_target(s["rsi"])
                pl = dict(stop=SC.rp(stop), emergency=SC.rp(emer), atr=atr, heat=round(heat, 1))
                pl["text"] = (f"at about 3:30 PM New York time, sell on a price under {usd(stop)} ({P['D_STOP_ATR']:g} ATR "
                              f"under the entry), the 10 EMA under the 20, {BENCH} under its 20 EMA, RSI at {heat:.0f} (the "
                              "heatmap target), a gap and crap, or reaching an order block above; sell at once under "
                              f"{usd(emer)} ({P['D_EMERGENCY_ATR']:g} ATR under); sell the morning after the {s['sector']} "
                              f"category's breadth turns bearish, or after {P['D_MAX_DAYS']} days.")
                pos = buy_coin(a, now, t, S, budget, why, pl)
                if pos:
                    pos.update(leg="M", sector=s["sector"])
            obs = [s for s in skipped if " was overbought: " in s]
            if skipped and not any(p["leg"] == "M" and p["buy"]["t"] == tstr(now) for p in a["positions"]):
                news.append("Plan M: " + "; ".join(skipped[:5]))
            elif obs:                                # a buy went through: still say what your rule left out
                news.append("Plan M: " + "; ".join(obs[:5]))
        # Plan ETF, with the cash left: Bitcoin or Ether itself
        held = {p["ticker"] for p in a["positions"]}
        ready, etf_news = [], []
        for fund, e in plan["etf"].items():
            if fund in held:
                etf_news.append(f"holding {fund}")
                continue
            if fund in sold_today or e["sell"]:
                etf_news.append(f"{fund} has a sell signal")
                continue
            if not e["ok"]:
                etf_news.append(f"{fund} isn't set up: " + ", ".join(lc(c["text"]) for c in e["checks"] if not c["ok"]))
                continue
            q = day.price([fund])
            if not day.fresh(fund):
                etf_news.append(f"{fund} had no live price")
                continue
            h = mh and f"the market is overbought ({mh}, last night)" or hot_now(day, [(fund, "")]).get(fund)
            if h:
                etf_news.append(f"{fund} isn't bought: " + (h if mh else f"it is overbought ({h})"))
                continue
            lo, hi = e["e20"], e["e20"] + SC.OV["ZONE_ATR"] * e["atr"]
            if not lo <= q[fund][0] <= hi:
                etf_news.append(f"{fund} isn't set up: it is at {usd(q[fund][0])} this morning, outside the value zone "
                                f"({usd(lo)}-{usd(hi)})")
                continue
            ready.append((fund, e, q[fund][0], lo, hi))
        for i, (fund, e, U, lo, hi) in enumerate(ready):
            have = a["cash"]
            budget = have / (len(ready) - i)
            if budget < P["D_MIN"]:
                etf_news.append(f"{fund} is set up, but only {money(have)} is left to spend")
                break
            why = (f"Plan ETF in {src}: there's cash with no Plan M trade to take, and {fund} passes every Plan ETF check: "
                   + "; ".join(c["text"] for c in e["checks"])
                   + f". This morning it is at {usd(U)}, inside the value zone ({usd(lo)}-{usd(hi)}). "
                   + (f"{ready[1][0]} is set up too, so each gets half. " if len(ready) == 2 and i == 0 else "")
                   + f"There are no 3x crypto funds like TQQQ or SPXL, so it buys {fund} itself.")
            pl = dict(text=f"sell at about 10:00 New York time the morning after a sell signal on {fund}: its 10 EMA under its "
                           f"20 EMA, a close more than {SC.OV['HOT_ATR']:g} ATR above its 20 EMA, or reaching an order block at "
                           f"least {SC.OV['ETF_OB_AGE']} days old.")
            pos = buy_coin(a, now, fund, U, budget, why, pl)
            if pos:
                pos.update(leg="ETF", sector="")
        if etf_news:
            news.append("Plan ETF: " + "; ".join(etf_news))
    if a["cash"] >= P["D_MIN"] and plan is not None:
        news.append(f"Plan #SICADFU: {money(a['cash'])} waits as cash (SGOV is a Treasury fund, not a coin)")
    if sum(e["kind"] == "buy" for e in a["log"]) == n0:
        note(a, now, "No new buy. " + ". ".join(news) + "." if news else "No new buy.", "day")
    elif news:
        note(a, now, ". ".join(news) + ".", "note")


def d_late(a, day):
    """Plan M's closing-price exits, judged on the live price in the afternoon, as the deck does before the close."""
    ms = legs(a, "M")
    if not ms:
        return
    tks = [p["ticker"] for p in ms]
    bars = day.mkt.daily(tks + [BENCH], day.prev_day, period="2y")
    sess = day.mkt.session(tks + [BENCH], day.today)
    px = day.price(tks + [BENCH])
    if bars.get(BENCH) is None or BENCH not in sess or not day.fresh(BENCH):
        print(f"  afternoon check skipped: no {BENCH} prices")
        return
    btc = with_today(bars[BENCH], sess[BENCH], px[BENCH][0], day.today)
    for p in ms:
        t, d = p["ticker"], bars.get(p["ticker"])
        if d is None or len(d) < 60 or t not in sess or not day.fresh(t):
            continue
        fr = m_exits(p, with_today(d, sess[t], px[t][0], day.today), btc)
        if fr:
            sell_coin(a, p, day.now, px[t][0], f"This afternoon {t} is at {usd(px[t][0])}: " + "; ".join(fr) + ".")


def d_pause(a, day):
    """3 losing trades in one day: no new trades for a week."""
    today = day.today.isoformat()
    lost = [p for p in a["closed"] if p["sell"]["t"][:10] == today and p.get("leg") in ("M", "ETF") and p["pnl"] < 0]
    if len(lost) >= P["D_LOSERS"] and not (a.get("pause") and a["pause"] > today):
        a["pause"] = (day.today + dt.timedelta(days=P["D_PAUSE"])).isoformat()
        note(a, day.now, f"{plural(len(lost), 'losing trade')} today ({', '.join(p['ticker'] for p in lost)}): no new trades until "
                         f"{day_str(dt.date.fromisoformat(a['pause']))}, as the plan says. It keeps what it holds.", "note")


def d_trade(a, day, first, late):
    sd, plan = day.ovtlyr()
    d_watch(a, day)
    if first:
        tks = [p["ticker"] for p in legs(a, "M")]
        bars = day.mkt.daily(tks + [BENCH], day.prev_day, period="2y")
        d_exits(a, day, sd, plan, bars)
        d_buys(a, day, sd, plan, bars)
    if late:
        d_late(a, day)
    d_pause(a, day)


# ------------------------------------------------------------------ the run
def close_day(a, day, btc_close):
    """Value everything at 4 PM New York time and add the day to the chart."""
    marks(a, day)
    v = r2(value(a))
    prev = a["equity"][-1]["v"] if a["equity"] else a["start_cash"]
    a["equity"].append(dict(d=day.today.isoformat(), v=v, spy=SC.rp(btc_close)))
    b0 = a["equity"][0]["spy"]
    note(a, day.now, f"The day's value at 4 PM New York time: {money(v)}, {(v / prev - 1) * 100:+.2f}% on the day, "
                     f"{(v / a['start_cash'] - 1) * 100:+.2f}% since the start ({BENCH} {(btc_close / b0 - 1) * 100:+.2f}%). "
                     f"Cash {money(a['cash'])}, {plural(len(a['positions']), 'position')} open.", "close")


def end_trial(a, day):
    why = f"The trial ended on {day_str(dt.date.fromisoformat(a['end']))}, so everything is sold."
    px = day.price([p["ticker"] for p in a["positions"]])
    for p in list(a["positions"]):
        if day.fresh(p["ticker"]):
            sell_coin(a, p, day.now, px[p["ticker"]][0], why)


def start(a, day, btc_daily):
    """The first run of the trial: $1,000 at the previous day's close, so Bitcoin is measured from the same point."""
    if a["equity"]:
        return
    prev = btc_daily[btc_daily.index.date == day.prev_day]
    a["equity"].append(dict(d=day.prev_day.isoformat(), v=a["start_cash"], spy=SC.rp(prev["Close"].iloc[-1])))
    end = dt.date.fromisoformat(a["end"])
    note(a, day.now, f"Trial started with {money(a['start_cash'])}. It runs to {day_str(end)}, {end.year}.", "day")


def step(a, day, btc_daily):
    """One account's part of a run. Returns what it did in a few words, or None when only prices moved."""
    now, today = day.now, day.today.isoformat()
    steps = a["days"].get(today, [])
    if a.get("over") or today < a["start"] or now.time() < P["OPEN"]:
        return None
    if now.time() >= P["CLOSE"]:
        if "close" in steps or btc_daily.index[-1].date() != day.today:
            if a["id"] == "D":
                d_watch(a, day)
            else:
                a_exits(a, day) if a["id"] in ("A", "C") else marks(a, day)
            return None
        start(a, day, btc_daily)
        close_day(a, day, float(btc_daily["Close"].iloc[-1]))
        a["days"][today] = steps + ["close"]
        if today >= a["end"] and not a["positions"]:
            a["over"] = True
            note(a, now, f"Trial over. Final value {money(value(a))}, {(value(a) / a['start_cash'] - 1) * 100:+.1f}% "
                         "since the start.", "day")
        return "closed the day"
    if not day.fresh(BENCH):
        return None
    n0 = len(a["log"])
    first = "morning" not in steps
    mk = "late" if a["id"] == "D" else "buys"       # C buys after 2 PM Central; D checks its exits in the afternoon
    late = (a["id"] == "C" and now.time() >= P["C_BUY"] or a["id"] == "D" and now.time() >= P["D_LATE"]) \
        and mk not in steps and today < a["end"]
    if first:
        start(a, day, btc_daily)
    if today >= a["end"]:
        end_trial(a, day)
    elif a["id"] in ("A", "C"):
        a_exits(a, day)
        if (first and a["id"] == "A") or late:      # A buys in the morning, C at the first run after 2 PM Central
            a_buys(a, day)
    elif a["id"] == "D":
        d_trade(a, day, first, late)
    else:
        b_trade(a, day, quiet=not first)
        marks(a, day)
    if first or late:
        a["days"][today] = steps + (["morning"] if first else []) + ([mk] if late else [])
    trades = sum(e["kind"] in ("buy", "sell") for e in a["log"][n0:])
    if first or late:
        what = ("morning and " + ("closing check" if a["id"] == "D" else "buys") if first and late else "morning" if first
                else "closing check" if a["id"] == "D" else "afternoon")
        return f"{what}, {plural(trades, 'trade')}"
    return plural(trades, "trade") if trades else None


def load(state_dir, aid):
    f = Path(state_dir) / f"{aid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else new_account(aid)


def save(state_dir, accts):
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    for aid, a in accts.items():
        (Path(state_dir) / f"{aid}.json").write_text(json.dumps(a, separators=(",", ":")), encoding="utf-8")


def run(state_dir, mkt, now, hist, dry=False):
    """One scheduled run. Returns (what each account did, the accounts, accounts that hit an error),
    or None when there's nothing to do (before the trial, or no fresh Bitcoin price)."""
    accts = {aid: load(state_dir, aid) for aid in IDS}
    for a in accts.values():
        if not a["equity"]:
            a["start"] = P["START"]                     # not started yet: follow the settings (and --start in dry runs)
    if now.date().isoformat() < P["START"]:
        return None
    day = Day(mkt, now, hist)
    btc = day.price([BENCH]).get(BENCH)
    if btc is None or not day.fresh(BENCH):
        return None                                      # Yahoo's crypto prices are late or missing: try next run
    btc_daily = mkt.daily([BENCH], day.today, period="10d").get(BENCH)
    if btc_daily is None or not len(btc_daily) or btc_daily.index[0].date() >= day.today:
        return None
    day.prev_day = max(d for d in btc_daily.index.date if d < day.today)
    did, errors = {}, []
    for aid in list(accts):
        keep = copy.deepcopy(accts[aid])
        try:
            r = step(accts[aid], day, btc_daily)
        except Exception:
            traceback.print_exc()
            accts[aid] = keep                            # undo the half-done run; the next run tries again
            errors.append(aid)
            continue
        if r:
            did[aid] = r
    for a in accts.values():
        a["mark"] = dict(t=tstr(now), v=r2(value(a)), spy=SC.rp(btc[0]))
        a["updated"] = tstr(now)
        a["rules"], a["fills"] = rules(a["id"]), FILLS
    if not dry:
        save(state_dir, accts)
    return did, accts, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="folder with the account files, A.json to D.json (created if missing)")
    ap.add_argument("--history", default=str(Path(__file__).resolve().parent / "history"))
    ap.add_argument("--dry-run", action="store_true", help="print what would happen, save nothing")
    ap.add_argument("--at", help='pretend it is this New York time, e.g. "2026-10-13 10:05" (prices are still the latest)')
    ap.add_argument("--message", help="write a commit message to this file when something worth a commit happened")
    ap.add_argument("--start", help="dry runs: pretend the trial starts on this date (to test on a day before the start)")
    a = ap.parse_args()
    if a.start and not a.dry_run:
        sys.exit("--start is only for dry runs")
    if a.start:
        P["START"] = a.start
    now = pd.Timestamp(a.at, tz=NY) if a.at else pd.Timestamp.now(tz=NY)
    res = run(a.state, Yahoo(a.history), now, a.history, a.dry_run)
    if res is None:
        print(f"{tstr(now)} New York: nothing to do (before the trial, or no fresh {BENCH} price).")
        return
    did, accts, errors = res
    for acct in accts.values():
        for e in acct["log"]:
            if e["t"] == tstr(now):
                print(f"[{acct['id']}] {e['kind']}: {e['text']}")
        print(f"[{acct['id']}] value {money(value(acct))}, cash {money(acct['cash'])}, "
              f"{plural(len(acct['positions']), 'position')}" + (" (dry run, not saved)" if a.dry_run else ""))
    msg = (f"Crypto paper trading {tstr(now)} New York: " + "; ".join(f"{k} {v}" for k, v in did.items())) if did else None
    print(msg or "Only prices moved.")
    if msg and a.message:
        Path(a.message).write_text(msg + "\n", encoding="utf-8")
    if errors:
        sys.exit(f"Account {', '.join(errors)} hit an error and was left as it was; the next run tries again.")


if __name__ == "__main__":
    main()
