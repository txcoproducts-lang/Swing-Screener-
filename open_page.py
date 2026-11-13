"""
The Open page (site/open/): a rundown right after the market opens, asked for by the user on 2026-11-13.

It runs once a day at about 9:35 AM New York (Open rundown workflow) and compares the market at the open with last night's
close, using the screener's own rules (screener.py): what stayed in the uptrend, overnight gap ups, sectors and
industries still in their uptrend, sector breadth still rising or turning, and stocks that now give a buy signal because
of the overnight move. "Now" is today's bar so far (today's open and the latest price); "last night" is the same data
without today's bar, so both sides are scored exactly the same way.

  python open_page.py --out open-out            the real run (writes open-out/open/index.html, nothing on a day with no trading)
  python open_page.py --out open-out --any-day  preview: if today has no bar yet, treats the last trading day as "today"
  python open_page.py --out open-out --demo     made-up prices, to check the page
"""
import argparse, datetime as dt, html, sys
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

import screener as S
import page_keys as K
import ovtlyr_page as OP

esc = html.escape
NY = "America/New_York"
GAP = 1.0                     # a gap up: today's open at least 1% over last night's close
RED, GREEN, YELLOW = K.RED, K.GREEN, K.YELLOW
sn = lambda s: S.SHORT_SECTOR.get(s, s) if isinstance(s, str) and s else "—"
tk = lambda t: f'<a class="tk" href="../?q={quote(t)}&amp;from=open">{esc(t)}</a>'


def pc(v, d=1, plus=True):
    if v is None or v != v:
        return '<span class="sub">—</span>'
    v = round(float(v), d) + 0.0                # no "-0.0%"
    cls = "pos" if v > 0 else "neg" if v < 0 else "sub"
    return f'<span class="{cls}">{v:+.{d}f}%</span>' if plus else f'{v:.{d}f}%'


def split(frames, today):
    """{ticker: frame up to now} and {ticker: frame up to last night}, for the tickers that have a bar today."""
    now, prev = {}, {}
    for t, d in frames.items():
        if len(d) > 212 and d.index[-1].date() == today:
            now[t], prev[t] = d, d.iloc[:-1]
    return now, prev


def scan(fr, sectors, subs, sp500):
    """The screener's own scoring for one side (now or last night): the stock table rows, breadth per group, and who
    gives a buy signal (a setup that isn't blocked by breadth over 75, in the full uptrend or EMA10 > EMA20 with price
    over the 50 EMA: what the paper accounts buy)."""
    df = pd.DataFrame([r for r in (S.analyze(t, d) for t, d in fr.items()) if r])
    df["sector"] = df.ticker.map(sectors).fillna("")
    df["sub"] = df.ticker.map(subs).fillna("")
    bh = S.breadth_history(fr, sectors, sp500)
    br = {g: round(float(b.rise.iloc[-1]), 1) for g, b in bh.items()}
    mkt_hot = S.breadth_hot(None, br)
    obr = S.overbought(fr, sectors, br)
    ob = {t: " and ".join(own + ([sec] if sec else [])) for t, (own, sec) in obr.items()}
    df["ob"] = df.ticker.map(ob).fillna("")
    would = df.setup.notna()
    df["blocked"] = would & ((df.ob != "") | bool(mkt_hot))
    df["buy"] = would & ~df.blocked & df.core            # Super setups only, as the paper accounts buy (rolled back 2026-11-13)
    return df.set_index("ticker"), bh, {g: S.swing_state(b) for g, b in bh.items()}, mkt_hot


def etf_trend(d):
    """The user's uptrend rule on one ETF: EMA10 > EMA20, price > EMA50 and price > the 150 MA."""
    c = d["Close"]
    m150 = S.ema(c, 150) if S.CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()
    return bool(S.ema(c, 10).iloc[-1] > S.ema(c, 20).iloc[-1] and c.iloc[-1] > S.ema(c, 50).iloc[-1] and c.iloc[-1] > m150.iloc[-1])


def bcol(rise, on):
    """The user's breadth colours: over 75 or under 30 red, 30-75 rising green (the only green), 30-75 falling yellow."""
    return RED if rise > S.CFG["OB_BREADTH"] or rise < S.CFG["OS_BREADTH"] else GREEN if on else YELLOW


def turn(a, b, words=("Still rising", "Turned up", "Turned down", "Still falling")):
    return words[0] if a and b else words[1] if b else words[2] if a else words[3]


PILL = {"Still rising": "p-up", "Turned up": "p-up", "Turned down": "p-dn", "Still falling": "p-n",
        "Still in uptrend": "p-up", "Joined the uptrend": "p-up", "Left the uptrend": "p-dn", "Not in uptrend": "p-n"}
pill = lambda s: f'<span class="pill {PILL.get(s, "p-n")}">{esc(s)}</span>'


def build(frames, etfs, sectors, subs, sp500, today, out_dir, at, preview=False):
    now_f, prev_f = split(frames, today)
    if len(now_f) < 0.5 * len(frames):
        return None
    N, bhN, swN, hotN = scan(now_f, sectors, subs, sp500)
    P, bhP, swP, hotP = scan(prev_f, sectors, subs, sp500)
    tks = N.index.intersection(P.index)
    N, P = N.loc[tks], P.loc[tks]
    prevc = pd.Series({t: float(prev_f[t]["Close"].iloc[-1]) for t in tks})
    opn = pd.Series({t: float(now_f[t]["Open"].iloc[-1]) for t in tks})
    last = N.close
    gap, day, since = (opn / prevc - 1) * 100, (last / prevc - 1) * 100, (last / opn - 1) * 100
    prev_day = pd.Timestamp(next(iter(prev_f.values())).index[-1]).date()

    # ---- market and sectors
    def etf_row(name):
        e = etfs.get(S.SECTOR_ETF.get(name, ""))
        if e is None or len(e) < 200 or e.index[-1].date() != today:
            return dict(etf=S.SECTOR_ETF.get(name, ""), gap=None, day=None, upP=None, upN=None)
        p = e.iloc[:-1]
        pc_ = float(p["Close"].iloc[-1])
        return dict(etf=S.SECTOR_ETF[name], gap=(float(e["Open"].iloc[-1]) / pc_ - 1) * 100, day=(float(e["Close"].iloc[-1]) / pc_ - 1) * 100,
                    upP=etf_trend(p), upN=etf_trend(e))
    groups = [g for g in S.SECTOR_ETF if g in swN and g in swP]
    sec = []
    for g in groups:
        a, b = swP[g], swN[g]
        sec.append(dict(name=g, P=a, N=b, state=turn(a["on"], b["on"]), **etf_row(g)))
    mk = next((s for s in sec if s["name"] == "S&P 500"), None)
    secs = [s for s in sec if s["name"] != "S&P 500"]
    secs.sort(key=lambda s: -s["N"]["rise"])

    # ---- industries (GICS sub-industries, 3+ liquid stocks): share of their stocks in your full uptrend
    ind = []
    for name, idx in N.groupby("sub").groups.items():
        if not name or len(idx) < 3:
            continue
        a, b = P.loc[idx, "core"].mean() * 100, N.loc[idx, "core"].mean() * 100
        st = turn(a >= 50, b >= 50, ("Still in uptrend", "Joined the uptrend", "Left the uptrend", "Not in uptrend"))
        ind.append(dict(name=name, sector=N.loc[idx, "sector"].mode().iloc[0] if len(idx) else "", n=len(idx), P=a, N=b, state=st,
                        day=float(day[idx].mean()), gap=float(gap[idx].mean())))
    order = {"Still in uptrend": 0, "Joined the uptrend": 1, "Left the uptrend": 2, "Not in uptrend": 3}
    ind.sort(key=lambda r: (order[r["state"]], -r["N"], -r["day"]))

    # ---- stocks
    stay = tks[P.core & N.core]
    joined, left = tks[~P.core & N.core], tks[P.core & ~N.core]
    new_buy = tks[N.buy & ~P.buy]
    lost_buy = tks[P.buy & ~N.buy]
    gaps = gap[gap >= GAP].sort_values(ascending=False).index

    def why_new(t):
        p, n = P.loc[t], N.loc[t]
        w = []
        if not (p.core or p.reg_up):
            w.append("joined the uptrend" if n.core else "10 EMA crossed over the 20 / price back over the 50 EMA")
        if p.blocked:
            w.append("no longer blocked: breadth back under 75")
        elif not isinstance(p.setup, str) or p.setup in ("Uptrend", "Overbought") or p.setup != p.setup:
            if n.setup == "Momentum" and n.brk20 and not p.brk20:
                w.append("the move broke its 20-day high")
            elif n.setup == "Momentum":
                w.append("RSI / 52-week high now fit a momentum setup")
            else:
                w.append("pulled back into a setup")
        return "; ".join(w) or "new setup"

    def stock_tr(t, extra=""):
        n = N.loc[t]
        return (f'<tr data-s="{esc(n.sector)}"><td>{tk(t)}</td><td class="sub">{esc(sn(n.sector))}</td><td class="num">{pc(gap[t])}</td>'
                f'<td class="num">{pc(since[t])}</td><td class="num">{pc(day[t])}</td><td class="num">${last[t]:,.2f}</td>{extra}</tr>')
    tierlbl = lambda n: f'{n.tier} {n.setup}' if isinstance(n.setup, str) and n.tier else (n.setup if isinstance(n.setup, str) else "")
    TH = '<th>Ticker</th><th>Sector</th><th class="num">Gap</th><th class="num">Since open</th><th class="num">Today</th><th class="num">Price</th>'

    def table(rows, head=TH, extra_th="", empty="None today.", tid=""):
        if not rows:
            return f'<div class="sub">{empty}</div>'
        return f'<div class="wrap"><table class="tb"{f" id={tid}" if tid else ""}><thead><tr>{head}{extra_th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

    up_tag = lambda t: ("✓ uptrend" if N.loc[t].core else "regular up" if N.loc[t].reg_up else "—")
    nb_rows = [stock_tr(t, f'<td>{esc(tierlbl(N.loc[t]))}</td><td class="sub" style="white-space:normal;min-width:200px">{esc(why_new(t))}</td>')
               for t in sorted(new_buy, key=lambda t: (N.loc[t].tier != "Super", -N.loc[t].score))]
    lb_rows = [stock_tr(t, f'<td class="sub">{esc(N.loc[t].ob or ("lost the uptrend" if not (N.loc[t].core or N.loc[t].reg_up) else "no longer a setup"))}</td>')
               for t in lost_buy]
    gp_rows = [stock_tr(t, f'<td>{"holding" if since[t] >= 0 else "fading"}</td><td>{up_tag(t)}</td><td>{esc(tierlbl(N.loc[t])) if N.loc[t].buy else ""}</td>')
               for t in gaps]
    st_rows = [stock_tr(t) for t in sorted(stay, key=lambda t: -day[t])]

    # ---- the page
    def sec_tr(s):
        a, b = s["P"], s["N"]
        cell = lambda x: f'<span class="hb" style="background:{bcol(x["rise"], x["on"])}">{x["rise"]:.0f}%</span>'
        upd = lambda x: "—" if x is None else ("✓" if x else "✗")
        return (f'<tr><td><b>{esc(sn(s["name"]))}</b> <span class="sub">{s["etf"]}</span></td><td class="num">{pc(s["gap"])}</td>'
                f'<td class="num">{pc(s["day"])}</td><td class="c">{cell(a)} → {cell(b)}</td><td>{pill(s["state"])}</td>'
                f'<td class="num">{a["up"] or 0:.0f}% → {b["up"] or 0:.0f}%</td><td class="c">{upd(s["upP"])} → {upd(s["upN"])}</td></tr>')
    SEC_TH = ('<th>Sector</th><th class="num">Gap</th><th class="num">Today</th><th class="c">Breadth last night → now</th><th>Direction</th>'
              '<th class="num">Stocks in uptrend</th><th class="c">ETF uptrend</th>')
    still = [s for s in secs if s["state"] == "Still rising"]
    tup = [s for s in secs if s["state"] == "Turned up"]
    tdn = [s for s in secs if s["state"] == "Turned down"]
    etf_up = [s for s in secs if s["upP"] and s["upN"]]
    ind_up = [r for r in ind if r["state"] in ("Still in uptrend", "Joined the uptrend")]
    names = lambda L: ", ".join(sn(s["name"]) for s in L) or "none"

    m = mk or {}
    mP, mN = m.get("P", {}), m.get("N", {})
    spy_line = (f'SPY opened {pc(m.get("gap"))} vs last night\'s close and is {pc(m.get("day"))} so far today. '
                f'SPY uptrend: {"✓" if m.get("upP") else "✗"} last night → {"✓" if m.get("upN") else "✗"} now.') if m else ""
    mstate = turn(mP.get("on"), mN.get("on")) if m else ""
    sumcards = [
        ("Market", f'{pill(mstate)}' if m else "—",
         f'S&amp;P 500 breadth {mP.get("rise", 0):.0f}% → {mN.get("rise", 0):.0f}%' + (" · over 75: no buys" if hotN else "")),
        ("Sectors", f'{len(still) + len(tup)} of {len(secs)} rising', f'still rising: {esc(names(still))}' + (f' · turned up: {esc(names(tup))}' if tup else "")
         + (f' · turned down: {esc(names(tdn))}' if tdn else "")),
        ("Industries", f'{len(ind_up)} in uptrend', f'{sum(r["state"] == "Joined the uptrend" for r in ind)} joined, {sum(r["state"] == "Left the uptrend" for r in ind)} left since last night'),
        ("Stocks", f'{len(new_buy)} new buy signal{"s" if len(new_buy) != 1 else ""}',
         f'{len(stay)} stayed in uptrend · {len(joined)} joined · {len(left)} left · {len(gaps)} gapped up {GAP:g}%+'),
    ]
    cards = "".join(f'<div class="step"><div class="n">{a}</div><div class="big">{b}</div><div class="sub">{c}</div></div>' for a, b, c in sumcards)
    top_new = "".join(f'<div class="st">{tk(t)}<span class="sub">{esc(sn(N.loc[t].sector))} · {esc(tierlbl(N.loc[t]))}</span><span>{pc(gap[t])}</span>'
                      f'<span class="sub">{esc(why_new(t))}</span></div>' for t in sorted(new_buy, key=lambda t: (N.loc[t].tier != "Super", -N.loc[t].score))[:8])
    top_gap = "".join(f'<div class="st">{tk(t)}<span class="sub">{esc(sn(N.loc[t].sector))} · {up_tag(t)}</span><span>{pc(gap[t])}</span>'
                      f'<span class="sub">{"holding" if since[t] >= 0 else "fading"} {pc(since[t])}</span></div>' for t in gaps[:8])

    keys = dict(
        summary=K.key(K.R("Last night → now", "Every number compares last night's close with the market right after today's open. "
                          "Both sides use the screener's own rules; \"now\" uses today's open and the latest price as if they were today's close."),
                      K.R("Market", "Still rising / Turned up / Turned down / Still falling = the S&amp;P 500's breadth (share of its stocks with the "
                          "10 EMA over the 20 and price over the 50 EMA) above or below its 10-day average, last night and now. Over 75 blocks every buy (your rule)."),
                      K.R("New buy signal", "A stock that gives a buy signal now and didn't last night: a Momentum or Pullback setup, not blocked by "
                          "breadth over 75, in your full uptrend (a Super setup). The same signal the paper accounts buy."),
                      K.U("Start with the market line. If it turned down or breadth is over 75, the new buy signals aren't buys yet. "
                          "Then look for new signals in the sectors that are still rising.")),
        sectors=K.key(K.R("Breadth", "Share of the sector's S&amp;P 500 stocks with the 10 EMA over the 20 and price over the 50 EMA. "
                          f'{K.sw(GREEN)}30-75 and rising (above its 10-day average) {K.sw(YELLOW)}30-75 and falling {K.sw(RED)}over 75 or under 30.'),
                      K.R("Direction", "Still rising = above its 10-day average last night and now. Turned up / Turned down = it crossed since last night."),
                      K.R("Stocks in uptrend", "Share of the sector's stocks in your full uptrend (EMA10 over EMA20, price over the 50 EMA and the 150 MA)."),
                      K.R("ETF uptrend", "Your uptrend rule on the sector's SPDR ETF, last night → now."),
                      K.R("Gap / Today", "The ETF's open and its latest price, against last night's close.")),
        industries=K.key(K.R("Industry", "GICS sub-industry from the S&amp;P 500 list, with 3 or more liquid stocks."),
                         K.R("In uptrend", "Half or more of its stocks in your full uptrend. Still in uptrend = last night and now; Joined / Left = it changed at the open."),
                         K.R("Gap / Today", "The average gap and move of its stocks.")),
        signals=K.key(K.R("New buy signals", "Not a buy signal last night, a buy signal now, because of the overnight move. \"Why it's new\" says what changed."),
                      K.R("Lost buy signals", "A buy signal last night, gone now."),
                      K.R("Setup", "Super = price over the 150 MA; Regular = under it. Momentum = breakout or near the 52-week high with RSI 55-80; "
                          "Pullback = a dip to the 20 EMA inside an uptrend."),
                      K.U("These use the open's price, not a close. A gap can fade during the day; the nightly page decides on the close.")),
        gaps=K.key(K.R("Gap up", f"Today's open at least {GAP:g}% over last night's close, biggest first."),
                   K.R("Since open", "Holding = trading at or above the open; fading = below it."),
                   K.R("Uptrend", "✓ uptrend = your full rule now; regular up = EMA10 over EMA20 and price over the 50 EMA, under the 150 MA."),
                   K.R("Buy signal", "Filled in when the stock gives a buy signal now.")),
        uptrend=K.key(K.R("Stayed in uptrend", "In your full uptrend last night and still in it now, best day first."),
                      K.R("Joined / Left", "Changed at the open.")),
    )
    tabs = [
        ("summary", "Rundown", f'<div class="h1">How did the market open?</div><div class="sub lead">{spy_line}</div>{keys["summary"]}'
         f'<div class="steps four">{cards}</div><div class="g2" style="margin-top:14px">'
         f'<div class="card"><h3>New buy signals <a data-go="signals">All {len(new_buy)} ›</a></h3>{top_new or "<div class=sub>None at the open.</div>"}</div>'
         f'<div class="card"><h3>Biggest gap ups <a data-go="gaps">All {len(gaps)} ›</a></h3>{top_gap or "<div class=sub>No gap ups of 1% or more.</div>"}</div></div>'),
        ("sectors", "Sectors", f'<div class="card"><h3>Market and sectors, last night → now</h3>{keys["sectors"]}'
         f'{table([sec_tr(mk)] if mk else [], SEC_TH) if mk else ""}<div style="height:10px"></div>{table([sec_tr(s) for s in secs], SEC_TH)}'
         f'<div class="sub" style="margin-top:8px">ETF still in uptrend: {esc(names(etf_up))}</div></div>'),
        ("industries", "Industries", f'<div class="card"><h3>Industries, last night → now</h3>{keys["industries"]}'
         f'<div class="mkt" style="margin-bottom:8px" id="indf"><button class="chip on" data-f="up">In uptrend ({len(ind_up)})</button>'
         f'<button class="chip" data-f="left">Left ({sum(r["state"] == "Left the uptrend" for r in ind)})</button><button class="chip" data-f="all">All ({len(ind)})</button></div>'
         + table([f'<tr data-k="{"up" if r["state"] in ("Still in uptrend", "Joined the uptrend") else "left" if r["state"] == "Left the uptrend" else "no"}">'
                  f'<td style="white-space:normal;min-width:160px"><b>{esc(r["name"])}</b></td><td class="sub">{esc(sn(r["sector"]))}</td><td class="num">{r["n"]}</td>'
                  f'<td class="num">{r["P"]:.0f}% → {r["N"]:.0f}%</td><td>{pill(r["state"])}</td><td class="num">{pc(r["gap"])}</td><td class="num">{pc(r["day"])}</td></tr>' for r in ind],
                 '<th>Industry</th><th>Sector</th><th class="num">Stocks</th><th class="num">In uptrend</th><th>State</th><th class="num">Avg gap</th><th class="num">Avg today</th>', tid="indt")
         + '</div>'),
        ("signals", "Buy signals", f'<div class="card"><h3>New buy signals since last night ({len(new_buy)})</h3>{keys["signals"]}'
         + table(nb_rows, TH, '<th>Setup</th><th>Why it\'s new</th>', "No new buy signals at the open.") + '</div>'
         f'<div class="card" style="margin-top:14px"><h3>Lost buy signals ({len(lost_buy)})</h3>'
         + table(lb_rows, TH, '<th>Why</th>', "None lost at the open.") + '</div>'),
        ("gaps", "Gap ups", f'<div class="card"><h3>Gap ups of {GAP:g}% or more ({len(gaps)})</h3>{keys["gaps"]}'
         + table(gp_rows, TH, '<th>Since open</th><th>Uptrend</th><th>Buy signal</th>', "No gap ups this morning.") + '</div>'),
        ("uptrend", "Uptrend list", f'<div class="card"><h3>Stayed in uptrend ({len(stay)})</h3>{keys["uptrend"]}' + table(st_rows) + '</div>'
         f'<div class="g2" style="margin-top:14px"><div class="card"><h3>Joined the uptrend ({len(joined)})</h3>{table([stock_tr(t) for t in joined])}</div>'
         f'<div class="card"><h3>Left the uptrend ({len(left)})</h3>{table([stock_tr(t) for t in left])}</div></div>'),
    ]
    nav = "".join(f'<a href="#{k}" data-t="{k}">{lbl}</a>' for k, lbl, _ in tabs)
    body = "".join(f'<section class="tab" id="p-{k}" hidden>{h}</section>' for k, _, h in tabs)
    when = (f'{"Preview: " if preview else ""}open of {today:%a %b} {today.day} vs close of {prev_day:%a %b} {prev_day.day}'
            + (f' · prices at {at}' if at else ""))
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market open</title><style>{OP.CSS}
{K.CSS}{CSS}</style></head><body><header><div class="hd"><span class="logo"><i></i>Market open</span>
<nav class="sw" aria-label="Market"><a href="../">Stocks</a><a href="../crypto/">Crypto</a><a href="../ovtlyr/">OVTLYR</a><a class="on" href="./" aria-current="page">Open</a></nav>
<span class="asof">{esc(when)}</span></div><nav class="tabs">{nav}</nav></header><main>{body}</main><script>{OP.JS.replace("'today'", "'summary'")}{JS}</script></body></html>"""
    d = Path(out_dir) / "open"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(doc, encoding="utf-8")
    return dict(new_buy=len(new_buy), gaps=len(gaps), stay=len(stay), joined=len(joined), left=len(left), ind_up=len(ind_up),
                sectors_rising=len(still) + len(tup))


CSS = """.g2>*,.steps>*{min-width:0}.pos{color:var(--up)}.neg{color:var(--dn)}.steps.four{grid-template-columns:repeat(4,1fr)}.step .big{font-size:18px}
.st{grid-template-columns:62px 1fr 60px minmax(0,1.4fr)}.st .sub:last-child{white-space:normal}
@media(max-width:1000px){.steps.four{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.steps.four{grid-template-columns:1fr}.st{grid-template-columns:54px 1fr 56px}.st .sub:last-child{display:none}}"""

JS = """(function(){const box=document.getElementById('indf');if(!box)return;const rows=document.querySelectorAll('#indt tbody tr');
function draw(f){rows.forEach(tr=>tr.hidden=f!=='all'&&tr.dataset.k!==f)}
box.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{box.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x===b));draw(b.dataset.f)});draw('up')})();"""


def demo():
    """Made-up prices with a bar for today, to check the page."""
    fr = S.demo_frames(n=120)
    rng = np.random.default_rng(3)
    today = pd.Timestamp.now(tz=NY).normalize().tz_localize(None)
    out = {}
    for t, d in fr.items():
        d = d[d.index < today]
        pc_ = d["Close"].iloc[-1]
        o = pc_ * (1 + rng.normal(0.004, 0.015)); c = o * (1 + rng.normal(0, 0.006))
        out[t] = pd.concat([d, pd.DataFrame({"Open": [o], "High": [max(o, c) * 1.002], "Low": [min(o, c) * 0.998], "Close": [c],
                                             "Volume": [d["Volume"].iloc[-20:].mean() * 0.1]}, index=[today])])
    secs = ["Information Technology", "Health Care", "Financials", "Energy", "Industrials", "Consumer Discretionary",
            "Communication Services", "Utilities"]
    sectors = {t: secs[i % len(secs)] for i, t in enumerate(out)}
    subs = {t: f"{sectors[t]} {i % 4}" for i, t in enumerate(out)}
    etfs = dict(zip(S.SECTOR_ETF.values(), list(out.values())[:len(S.SECTOR_ETF)]))
    return out, etfs, sectors, subs, set(out), today.date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="open-out")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--any-day", action="store_true", help="if today has no bar, preview with the last trading day as today")
    a = ap.parse_args()
    nowny = pd.Timestamp.now(tz=NY)
    if a.demo:
        frames, etfs, sectors, subs, sp500, today = demo()
    else:
        tickers, sectors, subs, sp500 = S.get_universe()
        frames = S.download_with_retry(tickers)
        if len(frames) < 0.8 * len(tickers):
            sys.exit(f"Only got data for {len(frames)} of {len(tickers)} tickers; not publishing a partial page.")
        etfs = S.yf_batch(list(S.SECTOR_ETF.values()), period="2y", interval="1d")
        today = nowny.date()
    preview = False
    if sum(d.index[-1].date() == today for d in frames.values()) < 0.5 * len(frames):
        if not a.any_day:
            print(f"No trading bar for {today} yet (a holiday, or the market isn't open): the Open page is left as it was.")
            return
        today = pd.Series([d.index[-1].date() for d in frames.values()]).mode().iloc[0]
        preview = True
        print(f"Preview: no bar for {nowny.date()}, using {today} as today.")
    at = None if a.demo or preview else f"{nowny.tz_convert('America/Chicago'):%-I:%M %p} Central"
    r = build(frames, etfs, sectors, subs, sp500, today, a.out, at, preview)
    print("Open page:", r)


if __name__ == "__main__":
    main()
