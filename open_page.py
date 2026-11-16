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
import argparse
import re, datetime as dt, html, sys
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
    """The user's breadth colours (red moved to 85 on 2026-11-16): over 85 or under 30 red, 30-75 rising dark green,
    75-85 rising light green, falling yellow."""
    return S.bfill(rise, on)


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
    prev2_f = {t: d.iloc[:-1] for t, d in prev_f.items()}       # the close before last night, for the last day's drop-outs
    P2 = scan(prev2_f, sectors, subs, sp500)[0]
    open_f = {}                                    # today's bar cut off at the opening price: what the gap alone did
    for t, d in now_f.items():
        d = d.copy(); o = d["Open"].iloc[-1]
        d.iloc[-1, d.columns.get_loc("Close")] = o; d.iloc[-1, d.columns.get_loc("High")] = o; d.iloc[-1, d.columns.get_loc("Low")] = o
        open_f[t] = d
    O = scan(open_f, sectors, subs, sp500)[0]
    tks = N.index.intersection(P.index).intersection(P2.index).intersection(O.index)
    N, P, P2, O = N.loc[tks], P.loc[tks], P2.loc[tks], O.loc[tks]
    prev2c = pd.Series({t: float(prev2_f[t]["Close"].iloc[-1]) for t in tks})
    prev_day2 = pd.Timestamp(next(iter(prev2_f.values())).index[-1]).date()
    prevc = pd.Series({t: float(prev_f[t]["Close"].iloc[-1]) for t in tks})
    opn = pd.Series({t: float(now_f[t]["Open"].iloc[-1]) for t in tks})
    last = N.close
    gap, day, since = (opn / prevc - 1) * 100, (last / prevc - 1) * 100, (last / opn - 1) * 100
    prev_day = pd.Timestamp(next(iter(prev_f.values())).index[-1]).date()
    # every label carries a date and a time (the user's rule): no bare "today", "now" or "last night"
    md_ = lambda x: f"{x:%a %b} {x.day}"
    TD, PD, PD2 = md_(today), md_(prev_day), md_(prev_day2)
    CL, CL2 = f"{PD} close (3:00 PM CT)", f"{PD2} close (3:00 PM CT)"
    OPN = f"{TD} open (8:30 AM CT)"
    NOWT = f"{at:%-I:%M %p} CT" if at is not None else "3:00 PM CT"     # the time of the prices used (a preview uses the close)
    NOW = f"{TD} {NOWT}"

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
        ind.append(dict(tks=list(idx), name=name, sector=N.loc[idx, "sector"].mode().iloc[0] if len(idx) else "", n=len(idx), P=a, N=b, state=st,
                        day=float(day[idx].mean()), gap=float(gap[idx].mean())))
    order = {"Still in uptrend": 0, "Joined the uptrend": 1, "Left the uptrend": 2, "Not in uptrend": 3}
    ind.sort(key=lambda r: (order[r["state"]], -r["N"], -r["day"]))

    # ---- stocks
    stay = tks[P.core & N.core]
    joined, left = tks[~P.core & N.core], tks[P.core & ~N.core]
    new_buy = tks[N.buy & ~P.buy]
    lost_buy = tks[P.buy & ~N.buy]                 # lost overnight / at the open
    lost_day = tks[P2.buy & ~P.buy]                # lost on the last trading day's close
    new_day = tks[~P2.buy & P.buy]                 # new on the last trading day's close
    gap_made = tks[~P.buy & O.buy & (gap > 0)]     # the overnight gap up alone (at the opening price) made the buy signal
    gap_kept, gap_faded = gap_made[N.loc[gap_made].buy], gap_made[~N.loc[gap_made].buy]
    nP2, nP, nN = int(P2.buy.sum()), int(P.buy.sum()), int(N.buy.sum())
    gaps = gap[gap >= GAP].sort_values(ascending=False).index

    def why_lost(p, n):
        """Why a stock that had a buy signal (p) doesn't any more (n), in plain words."""
        if not n.core:
            return "fell out of the uptrend" + (" (under the 150 MA)" if n.x1020 and n.vs50 > 0 else " (10 EMA under the 20 or price under the 50 EMA)")
        if n.blocked:
            return "blocked: " + (n.ob or "market breadth over 75")
        if p.setup == "Momentum":
            if n.rsi > 80:
                return f"too hot: RSI {n.rsi:.0f} over 80"
            if n.rsi < 55:
                return f"lost momentum: RSI {n.rsi:.0f} under 55"
            if n.ext > 3:
                return f"stretched: {n.ext:.1f} ATRs over the 20 EMA"
            return "fell back from its breakout / 52-week high"
        if p.setup == "Pullback":
            if n.rsi > 50:
                return f"bounced: RSI {n.rsi:.0f} back over 50 (pullback over)"
            return "no longer near the 20 EMA"
        return "no longer a setup"

    def why_new(t):
        p, n = P.loc[t], N.loc[t]
        w = [f"the {gap[t]:+.1f}% gap up opened it into a buy signal"] if t in gap_made else []
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
    TH = (f'<th>Ticker</th><th>Sector</th><th class="num">Gap {TD}</th><th class="num">{TD} 8:30 AM → {NOWT}</th>'
          f'<th class="num">{PD} close → {TD} {NOWT}</th><th class="num">Price {NOWT}</th>')

    def table(rows, head=TH, extra_th="", empty=f"None on {TD}.", tid=""):
        if not rows:
            return f'<div class="sub">{empty}</div>'
        return f'<div class="wrap"><table class="tb"{f" id={tid}" if tid else ""}><thead><tr>{head}{extra_th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

    up_tag = lambda t: ("✓ uptrend" if N.loc[t].core else "regular up" if N.loc[t].reg_up else "—")
    nb_rows = [stock_tr(t, f'<td>{esc(tierlbl(N.loc[t]))}</td><td class="c">{"<b class=pos>✓ gap</b>" if t in gap_made else ""}</td>'
                           f'<td class="sub" style="white-space:normal;min-width:200px">{esc(why_new(t))}</td>')
               for t in sorted(new_buy, key=lambda t: (N.loc[t].tier != "Super", -N.loc[t].score))]
    lb_rows = [stock_tr(t, f'<td>{esc(tierlbl(P.loc[t]))}</td><td style="white-space:normal;min-width:200px">{esc(why_lost(P.loc[t], N.loc[t]))}</td>')
               for t in sorted(lost_buy, key=lambda t: day[t])]
    d1 = (prevc / prev2c - 1) * 100
    ld_rows = [f'<tr><td>{tk(t)}</td><td class="sub">{esc(sn(N.loc[t].sector))}</td><td class="num">{pc(d1[t])}</td><td class="num">${prevc[t]:,.2f}</td>'
               f'<td>{esc(tierlbl(P2.loc[t]))}</td><td style="white-space:normal;min-width:200px">{esc(why_lost(P2.loc[t], P.loc[t]))}</td>'
               f'<td>{f"<b class=pos>back by {NOWT}</b>" if N.loc[t].buy else "still out"}</td></tr>' for t in sorted(lost_day, key=lambda t: d1[t])]
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
    SEC_TH = (f'<th>Sector</th><th class="num">Gap {TD}</th><th class="num">{PD} close → {TD} {NOWT}</th><th class="c">Breadth {PD} close → {TD} {NOWT}</th><th>Direction</th>'
              f'<th class="num">Stocks in uptrend</th><th class="c">ETF uptrend</th>')
    still = [s for s in secs if s["state"] == "Still rising"]
    tup = [s for s in secs if s["state"] == "Turned up"]
    tdn = [s for s in secs if s["state"] == "Turned down"]
    etf_up = [s for s in secs if s["upP"] and s["upN"]]
    ind_up = [r for r in ind if r["state"] in ("Still in uptrend", "Joined the uptrend")]
    names = lambda L: ", ".join(sn(s["name"]) for s in L) or "none"

    # ---- every change from last night's close to now, good or bad, for the market and each sector
    def rules(d):
        """Your trend rules on one ETF / index: {rule: (passes, detail)}."""
        c = d["Close"]
        e10, e20, e50 = S.ema(c, 10).iloc[-1], S.ema(c, 20).iloc[-1], S.ema(c, 50).iloc[-1]
        m150 = (S.ema(c, 150) if S.CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()).iloc[-1]
        px = c.iloc[-1]
        return {"10 EMA above the 20 EMA": e10 > e20, "price above the 50 EMA": px > e50, "price above the 150 MA": px > m150,
                "20 EMA above the 50 EMA": e20 > e50, "price above the 10 EMA": px > e10, "price above the 20 EMA": px > e20}

    def zone_word(z):
        return {2: "over 75 (overbought)", -1: "under 30 (oversold)", 0: "between 30 and 75"}[z]

    def group_changes(name, a, b, etf, nP_, nN_, hotP_, hotN_):
        """[(good True / bad False / None, text)] for one group: the market (S&P 500) or a sector."""
        ch = []
        add = lambda g, t: ch.append((g, t))
        e = etfs.get(etf)
        if e is not None and len(e) > 200 and e.index[-1].date() == today:
            p = e.iloc[:-1]
            pc_ = float(p["Close"].iloc[-1]); g_ = (float(e["Open"].iloc[-1]) / pc_ - 1) * 100; d_ = (float(e["Close"].iloc[-1]) / pc_ - 1) * 100
            if abs(g_) >= 0.05:
                add(g_ > 0, f"{etf} opened {'up' if g_ > 0 else 'down'} {abs(g_):.1f}% ({pc_:,.2f} → {float(e['Open'].iloc[-1]):,.2f})")
            add(d_ >= 0 if abs(d_) >= 0.05 else None, f"{etf} is {d_:+.1f}% since last night's close, {'holding above' if d_ >= g_ else 'below'} where it opened")
            rP, rN = rules(p), rules(e)
            for k in rP:
                if rP[k] != rN[k]:
                    add(bool(rN[k]), f"{etf} at {NOW}: {'' if rN[k] else 'no longer '}{k}")
            uP, uN = all(rP[k] for k in list(rP)[:3]), all(rN[k] for k in list(rN)[:3])
            if uP != uN:
                add(uN, f"{etf} {'entered' if uN else 'left'} your uptrend (10 over 20, over the 50 EMA and the 150 MA)")
            else:
                add(None, f"{etf} {'still in' if uN else 'still not in'} your uptrend")
        if a and b:
            dr = b["rise"] - a["rise"]
            add(dr > 0 if abs(dr) >= 0.5 else None, f"Breadth (Rising) {a['rise']:.0f}% → {b['rise']:.0f}% ({dr:+.0f} points)")
            if a["on"] != b["on"]:
                add(b["on"], f"Breadth turned {'up: back above' if b['on'] else 'down: fell under'} its 10-day average ({b['avg']:.0f}%)")
            else:
                add(None, f"Breadth still {'above' if b['on'] else 'under'} its 10-day average ({b['avg']:.0f}%): {'upswing' if b['on'] else 'fading'}")
            if a["z"] != b["z"]:
                add(b["z"] == 0, f"Breadth moved from {zone_word(a['z'])} to {zone_word(b['z'])}")
            if a.get("up") is not None and b.get("up") is not None and abs(b["up"] - a["up"]) >= 0.5:
                add(b["up"] > a["up"], f"Stocks in your full uptrend {a['up']:.0f}% → {b['up']:.0f}%")
        if nP_ != nN_:
            add(nN_ > nP_, f"Stocks with a buy signal {nP_} → {nN_}")
        if bool(hotP_) != bool(hotN_):
            add(not hotN_, "No longer blocked: breadth back under 75" if not hotN_ else f"Blocked at {NOW}: {hotN_}")
        return ch

    secN = N.groupby("sector").buy.sum()
    secP = P.groupby("sector").buy.sum()
    rankP = {s_["name"]: i + 1 for i, s_ in enumerate(sorted(secs, key=lambda x: -x["P"]["rise"]))}
    rankN = {s_["name"]: i + 1 for i, s_ in enumerate(secs)}
    chg = []                                       # (group, [(good, text)])
    if mk:
        mc = group_changes("S&P 500", mk["P"], mk["N"], "SPY", nP, nN, hotP, hotN)
        spy = etfs.get("SPY")
        if spy is not None and len(spy) > 200 and spy.index[-1].date() == today:
            cP, cN = S.spy_checks(spy.iloc[:-1], mk["P"], hotP), S.spy_checks(spy, mk["N"], hotN)
            okP, okN = sum(bool(x[1]) for x in cP), sum(bool(x[1]) for x in cN)
            mc.insert(0, (okN > okP if okN != okP else None, f"Market checks (the Stocks page's checklist), {CL} → {NOW}: {okP} of {len(cP)} → {okN} of {len(cN)}"))
        v = etfs.get("^VIX")
        if v is not None and len(v) > 2 and v.index[-1].date() == today:
            vp, vo, vn = float(v["Close"].iloc[-2]), float(v["Open"].iloc[-1]), float(v["Close"].iloc[-1])
            mc.append((vn < vp if abs(vn - vp) >= 0.05 else None, f"VIX {vp:.2f} at the {CL} → {vn:.2f} at {NOW} (opened {vo:.2f}); {'calmer' if vn < vp else 'more fear'}"))
        ups, dns = int((gap >= 0.05).sum()), int((gap <= -0.05).sum())
        mc.append((ups > dns, f"{ups} stocks opened higher, {dns} lower ({len(gaps)} gapped up {GAP:g}%+, {int((gap <= -GAP).sum())} gapped down {GAP:g}%+)"))
        mc.append((len(new_buy) >= len(lost_buy) if (new_buy.size or lost_buy.size) else None,
                   f"Buy signals: {len(new_buy)} new, {len(lost_buy)} lost since last night's close"))
        mc.append((len(joined) >= len(left) if (joined.size or left.size) else None, f"Uptrend: {len(joined)} stocks joined, {len(left)} left"))
        chg.append(("Market (S&P 500 / SPY)", mc))
    for s_ in secs:
        sc = group_changes(s_["name"], s_["P"], s_["N"], s_["etf"], int(secP.get(s_["name"], 0)), int(secN.get(s_["name"], 0)),
                           S.breadth_hot(s_["name"], {s_["name"]: s_["P"]["rise"]}), S.breadth_hot(s_["name"], {s_["name"]: s_["N"]["rise"]}))
        rp, rn = rankP.get(s_["name"]), rankN.get(s_["name"])
        if rp and rn and rp != rn:
            sc.insert(0, (rn < rp, f"Rank by breadth #{rp} → #{rn} of {len(secs)}"))
        else:
            sc.insert(0, (None, f"Rank by breadth #{rn} of {len(secs)}, unchanged"))
        chg.append((s_["name"], sc))
    n_good = sum(g is True for _, L in chg for g, _ in L)
    n_bad = sum(g is False for _, L in chg for g, _ in L)
    mark = {True: '<i class="cg">▲</i>', False: '<i class="cb">▼</i>', None: '<i class="cn">•</i>'}

    def chg_card(name, L):
        g, b_ = sum(x is True for x, _ in L), sum(x is False for x, _ in L)
        return (f'<div class="card chg"><h3>{esc(sn(name) if name in S.SECTOR_ETF else name)} <span class="pill p-up">{g} better</span>'
                f'<span class="pill p-dn">{b_} worse</span></h3>' + "".join(f'<div class="cl">{mark[x]}<span>{esc(t)}</span></div>' for x, t in L) + '</div>')
    changes_html = "".join(chg_card(n, L) for n, L in chg)

    m = mk or {}
    mP, mN = m.get("P", {}), m.get("N", {})
    spy_line = (f'SPY opened {pc(m.get("gap"))} at the {OPN} vs the {CL}, and is {pc(m.get("day"))} at {NOW}. '
                f'SPY uptrend: {"✓" if m.get("upP") else "✗"} at the {CL} → {"✓" if m.get("upN") else "✗"} at {NOW}.') if m else ""
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
    chips = lambda L: " ".join(tk(t) for t in L) or '<span class="sub">none</span>'
    gtag = lambda t: f'<span style="white-space:nowrap">{tk(t)}<span class="gtag">▲{gap[t]:.1f}%</span></span>' if t in gap_made else tk(t)
    new_sorted = sorted(new_buy, key=lambda t: (t not in gap_made, -gap[t]))
    def cause(t):
        """What put the buy signal there, in a word or two, for the box."""
        p, n = P.loc[t], N.loc[t]
        if t in gap_made:
            return f"gap up ▲{gap[t]:.1f}%"
        if p.blocked:
            return "breadth back under 75"
        if not (p.core or p.reg_up):
            return "joined the uptrend"
        if n.setup == "Momentum" and n.brk20 and not p.brk20:
            return "broke 20-day high"
        if n.setup == "Momentum":
            return "momentum setup"
        return "pulled back into setup"
    ctag = lambda t: f'<span style="white-space:nowrap">{tk(t)}<span class="gtag{"" if t in gap_made else " ot"}">{esc(cause(t))}</span></span>'
    new_card = (f'<div class="card newc"><h3>New buy signals <a data-go="signals">Full list ›</a></h3>'
                f'<div class="lostg"><div><div class="lbig pos">{len(new_buy)}</div><div class="sub">new <b>overnight</b>: no buy signal at '
                f'the {CL}, one now ({len(gap_kept)} from the gap up)</div><div class="lchips">{" ".join(ctag(t) for t in new_sorted) or "<span class=sub>none</span>"}</div></div>'
                f'<div><div class="lbig pos">{len(gap_made)}</div><div class="sub">made by the <b>gap up</b>: the open alone was high enough for a buy signal'
                + (f' ({len(gap_faded)} faded out of it since the open: {", ".join(gap_faded)})' if len(gap_faded) else "")
                + f'</div><div class="lchips">{" ".join(gtag(t) for t in sorted(gap_made, key=lambda t: -gap[t])) or "<span class=sub>none</span>"}</div></div>'
                f'<div><div class="lbig pos">{len(new_day)}</div><div class="sub">new on <b>the {CL}</b>: none at the {CL2}'
                f' ({sum(N.loc[t].buy for t in new_day)} still have it at the open)</div><div class="lchips">{chips(sorted(new_day, key=lambda t: -d1[t]))}</div></div></div></div>')
    lost_card = (f'<div class="card lost"><h3>Lost buy signals <a data-go="lost">Full lists ›</a></h3>'
                 f'<div class="lostg"><div><div class="lbig neg">{len(lost_buy)}</div><div class="sub">lost <b>overnight</b>: had a buy signal at '
                 f'the {CL}, gone at the open</div><div class="lchips">{chips(sorted(lost_buy, key=lambda t: day[t]))}</div></div>'
                 f'<div><div class="lbig neg">{len(lost_day)}</div><div class="sub">lost on <b>the {CL}</b>: had one at the {CL2}'
                 f' ({sum(N.loc[t].buy for t in lost_day)} came back at the open)</div><div class="lchips">{chips(sorted(lost_day, key=lambda t: d1[t]))}</div></div>'
                 f'<div><div class="lbig">{nP2} → {nP} → {nN}</div><div class="sub">stocks with a buy signal: the {CL2} → the {CL} → {NOW}'
                 f' ({len(new_buy)} new at the open)</div></div></div></div>')
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
                          + K.zones(S.CFG)),
                      K.R("Direction", "Still rising = above its 10-day average last night and now. Turned up / Turned down = it crossed since last night."),
                      K.R("Stocks in uptrend", "Share of the sector's stocks in your full uptrend (EMA10 over EMA20, price over the 50 EMA and the 150 MA)."),
                      K.R("ETF uptrend", "Your uptrend rule on the sector's SPDR ETF, last night → now."),
                      K.R("Gap / Today", "The ETF's open and its latest price, against last night's close.")),
        industries=K.key(K.R("Industry", "GICS sub-industry from the S&amp;P 500 list, with 3 or more liquid stocks."),
                         K.R("In uptrend", "Half or more of its stocks in your full uptrend. Still in uptrend = last night and now; Joined / Left = it changed at the open."),
                         K.R("Gap / Today", "The average gap and move of its stocks.")),
        signals=K.key(K.R("New buy signals", "Not a buy signal last night, a buy signal now, because of the overnight move. \"Why it's new\" says what changed."),
                      K.R("From the gap / ▲%", "The gap up alone made it: scored at today's opening price (as if the day's candle were just the open), "
                          "it already gives a buy signal. The % is the gap over last night's close."),
                      K.R("New on the last close", "No buy signal two closes ago, one at last night's close (the full day's move)."),
                      K.R("Lost buy signals", "A buy signal last night, gone now."),
                      K.R("Setup", "Super = price over the 150 MA; Regular = under it. Momentum = breakout or near the 52-week high with RSI 55-80; "
                          "Pullback = a dip to the 20 EMA inside an uptrend."),
                      K.U("These use the open's price, not a close. A gap can fade during the day; the nightly page decides on the close.")),
        changes=K.key(K.R("What's listed", "For the market and every sector: the ETF's gap and move, each of your trend rules that flipped "
                          "(10 over 20, over the 50 EMA, over the 150 MA, 20 over 50, over the 10 and 20 EMA), entering or leaving your uptrend, breadth "
                          "(Rising) and its direction against its 10-day average, the 30 / 75 lines, stocks in your uptrend, buy-signal count, the over-75 block "
                          "and each sector's rank by breadth. The market adds the Stocks page's Today checks, VIX, how many stocks opened higher or lower, "
                          "and new vs lost buy signals and uptrends."),
                      K.R("▲ / ▼", "Better or worse for buying calls on the upswing (your long-only plan). A rising VIX counts as worse."),
                      K.U("Read the market card first, then the sectors in rank order. A sector with several ▼ (turned down, left its uptrend) is "
                          "not the strongest sector this morning, whatever last night said.")),
        lost=K.key(K.R("Lost overnight", "Had a buy signal at last night's close and doesn't now, scored on today's open and latest price. "
                       "Worst day first."),
                   K.R("Lost on the last close", "Had a buy signal two closes ago and lost it on last night's close (the full day's move). "
                       "\"At the open\" says whether it came back this morning."),
                   K.R("Why it's gone", "The first rule it now fails: out of the uptrend, blocked by breadth over 75, RSI out of the 55-80 momentum range, "
                       "stretched over 3 ATRs above the 20 EMA, off its breakout / 52-week high, or a pullback that bounced (RSI back over 50)."),
                   K.R("Buy signals count", "How many stocks had a buy signal two closes ago → last night → now. A falling count means more signals are lost than found."),
                   K.U("Check these before buying or adding: a stock you hold or were about to buy that shows up here has lost its setup. "
                       "Many losses at once, with breadth falling, means the market is pulling back.")),
        gaps=K.key(K.R("Gap up", f"Today's open at least {GAP:g}% over last night's close, biggest first."),
                   K.R("Since open", "Holding = trading at or above the open; fading = below it."),
                   K.R("Uptrend", "✓ uptrend = your full rule now; regular up = EMA10 over EMA20 and price over the 50 EMA, under the 150 MA."),
                   K.R("Buy signal", "Filled in when the stock gives a buy signal now.")),
        uptrend=K.key(K.R("Stayed in uptrend", "In your full uptrend last night and still in it now, best day first."),
                      K.R("Joined / Left", "Changed at the open.")),
    )
    def ind_detail(r):
        """The hidden row under an industry: each of its stocks and what changed for it, from the close to the open."""
        def ch(t):
            p, n = P.loc[t], N.loc[t]
            w = []
            if p.core != n.core:
                w.append("joined the uptrend" if n.core else "left the uptrend")
            if p.buy != n.buy:
                w.append("new buy signal" if n.buy else "lost its buy signal: " + why_lost(p, n))
            if t in gaps:
                w.append(f"gapped up {gap[t]:.1f}%")
            return "; ".join(w)
        tks_ = sorted(r["tks"], key=lambda t: (not ch(t), -day[t]))
        yn = lambda x: "✓" if x else "✗"
        rows = "".join(f'<tr><td>{tk(t)}</td><td class="sub" style="white-space:normal;min-width:150px">{esc(ch(t)) or "no change"}</td>'
                       f'<td class="c">{yn(P.loc[t].core)} → {yn(N.loc[t].core)}</td><td class="c">{yn(P.loc[t].buy)} → {yn(N.loc[t].buy)}</td>'
                       f'<td class="num">{pc(gap[t])}</td><td class="num">{pc(day[t])}</td></tr>' for t in tks_)
        return (f'<tr class="ixd" hidden><td colspan="7"><table class="tb ixt"><thead><tr><th>Stock</th><th>What changed</th>'
                f'<th class="c">Uptrend {PD} close → {NOWT}</th><th class="c">Buy signal {PD} close → {NOWT}</th>'
                f'<th class="num">Gap {TD}</th><th class="num">{PD} close → {NOWT}</th></tr></thead><tbody>{rows}</tbody></table></td></tr>')

    tabs = [
        ("summary", "Rundown", f'<div class="h1">How did the market open on {TD} (8:30 AM CT)?</div><div class="sub lead">{spy_line}</div>{keys["summary"]}'
         f'{new_card}<div style="height:14px"></div>{lost_card}<div class="card" style="margin-top:14px"><h3>What changed from the {CL} to {NOW} <a data-go="changes">Every change ›</a></h3>'
         f'<div class="sub">{n_good} changes for the better and {n_bad} for the worse across the market and {len(secs)} sectors, from '
         f'the {CL} to the open.</div>{"".join(f"<div class=cl>{mark[x]}<span>{esc(t)}</span></div>" for x, t in (chg[0][1] if chg else []))}</div>'
         f'<div class="steps four" style="margin-top:14px">{cards}</div><div class="g2" style="margin-top:14px">'
         f'<div class="card"><h3>New buy signals <a data-go="signals">All {len(new_buy)} ›</a></h3>{top_new or "<div class=sub>None at the open.</div>"}</div>'
         f'<div class="card"><h3>Biggest gap ups <a data-go="gaps">All {len(gaps)} ›</a></h3>{top_gap or "<div class=sub>No gap ups of 1% or more.</div>"}</div></div>'),
        ("changes", "What changed", f'<div class="h1">Everything that changed from the {CL} to {NOW}</div><div class="sub lead">From the {CL} to '
         f'the open: {n_good} better, {n_bad} worse. ▲ better for buying, ▼ worse, • no change or neutral.</div>{keys["changes"]}<div class="chgs">{changes_html}</div>'),
        ("lost", "Lost signals", f'<div class="card"><h3>Lost overnight: buy signal at the {CL}, gone at the open ({len(lost_buy)})</h3>{keys["lost"]}'
         + table(lb_rows, TH, f'<th>Setup at the {CL}</th><th>Why it\'s gone</th>', "No buy signals lost at the open.") + '</div>'
         f'<div class="card" style="margin-top:14px"><h3>Lost on the {CL}: buy signal at the {CL2}, gone at the next close ({len(lost_day)})</h3>'
         + table(ld_rows, f'<th>Ticker</th><th>Sector</th><th class="num">{PD2} close → {PD} close</th><th class="num">Close {PD}</th>', f'<th>Setup at the {CL2}</th><th>Why it\'s gone</th><th>At {NOW}</th>',
                 "No buy signals lost on that close.") + '</div>'),
        ("sectors", "Sectors", f'<div class="card"><h3>Market and sectors, last night → now</h3>{keys["sectors"]}'
         f'{table([sec_tr(mk)] if mk else [], SEC_TH) if mk else ""}<div style="height:10px"></div>{table([sec_tr(s) for s in secs], SEC_TH)}'
         f'<div class="sub" style="margin-top:8px">ETF still in uptrend: {esc(names(etf_up))}</div></div>'),
        ("industries", "Industries", f'<div class="card"><h3>Industries, last night → now</h3>{keys["industries"]}'
         f'<div class="mkt" style="margin-bottom:8px" id="indf"><button class="chip on" data-f="up">In uptrend ({len(ind_up)})</button>'
         f'<button class="chip" data-f="left">Left ({sum(r["state"] == "Left the uptrend" for r in ind)})</button><button class="chip" data-f="all">All ({len(ind)})</button></div>'
         + '<div class="hint">Tap an industry to see its stocks and what changed for each.</div>'
         + table([f'<tr class="ixr" data-k="{"up" if r["state"] in ("Still in uptrend", "Joined the uptrend") else "left" if r["state"] == "Left the uptrend" else "no"}">'
                  f'<td style="white-space:normal;min-width:160px"><b>{esc(r["name"])}</b> <span class="ixa">▸</span></td><td class="sub">{esc(sn(r["sector"]))}</td><td class="num">{r["n"]}</td>'
                  f'<td class="num">{r["P"]:.0f}% → {r["N"]:.0f}%</td><td>{pill(r["state"])}</td><td class="num">{pc(r["gap"])}</td><td class="num">{pc(r["day"])}</td></tr>' + ind_detail(r) for r in ind],
                 f'<th>Industry</th><th>Sector</th><th class="num">Stocks</th><th class="num">In uptrend {PD} close → {NOWT}</th><th>State</th><th class="num">Avg gap {TD}</th><th class="num">Avg {PD} close → {NOWT}</th>', tid="indt")
         + '</div>'),
        ("signals", "Buy signals", f'<div class="card"><h3>New buy signals since last night ({len(new_buy)})</h3>{keys["signals"]}'
         + table(nb_rows, TH, f'<th>Setup at {NOWT}</th><th class="c">From the {TD} gap</th><th>Why it\'s new</th>', "No new buy signals at the open.") + '</div>'
         + (f'<div class="card" style="margin-top:14px"><h3>Made by the gap up, gone since the open ({len(gap_faded)})</h3>'
            '<div class="hint">The open alone was high enough for a buy signal, but the price has slipped back since.</div>'
            + table([stock_tr(t) for t in gap_faded]) + '</div>' if len(gap_faded) else "")
         + f'<div class="sub" style="margin-top:10px">Lost buy signals have their own tab: <a data-go="lost">Lost signals ›</a></div>'),
        ("gaps", "Gap ups", f'<div class="card"><h3>Gap ups of {GAP:g}% or more ({len(gaps)})</h3>{keys["gaps"]}'
         + table(gp_rows, TH, f'<th>{TD} 8:30 AM → {NOWT}</th><th>Uptrend {NOWT}</th><th>Buy signal {NOWT}</th>', "No gap ups this morning.") + '</div>'),
        ("uptrend", "Uptrend list", f'<div class="card"><h3>Stayed in uptrend ({len(stay)})</h3>{keys["uptrend"]}' + table(st_rows) + '</div>'
         f'<div class="g2" style="margin-top:14px"><div class="card"><h3>Joined the uptrend ({len(joined)})</h3>{table([stock_tr(t) for t in joined])}</div>'
         f'<div class="card"><h3>Left the uptrend ({len(left)})</h3>{table([stock_tr(t) for t in left])}</div></div>'),
    ]
    nav = "".join(f'<a href="#{k}" data-t="{k}">{lbl}</a>' for k, lbl, _ in tabs)
    def dated(h):
        """Swap any relative time word left in the text for the date and time it means."""
        for a, b in (("Last night → now", f"{CL} → {NOW}"), ('"now"', f"the {NOW} side"), ("it now fails", f"it fails at {NOW}"),
                     ("the open's price", f"the {TD} 8:30 AM CT opening price"),
                     ("last night's close", f"the {CL}"), ("last night&#x27;s close", f"the {CL}"), ("since last night", f"since the {CL}"),
                     ("whatever last night", f"whatever the {CL}"), ("last night", f"at the {CL}"),
                     ("today's opening price", f"the {TD} 8:30 AM CT opening price"), ("today&#x27;s opening price", f"the {TD} 8:30 AM CT opening price"),
                     ("today's open", f"the {OPN}"), ("today&#x27;s open", f"the {OPN}"), ("so far today", f"as of {NOW}"),
                     ("this morning", f"by {NOW}"), ("since the open", f"since the {OPN}"), ("at the open", f"by {NOW}"),
                     ("the open", f"the {OPN}"), ("two closes ago", f"at the {CL2}"), ("the last close", f"the {CL}")):
            h = h.replace(a, b)
        h = re.sub(r"\b[Tt]oday\b", TD, h)
        return re.sub(r"(\b(?:at|by) |→ )?(?<![A-Za-z>])now\b", lambda m: (m.group(1) or "at ") + NOW, h)   # lower-case only: the ticker NOW stays
    tabs = [(k, lbl, dated(h)) for k, lbl, h in tabs]
    body = "".join(f'<section class="tab" id="p-{k}" hidden>{h}</section>' for k, _, h in tabs)
    when = f'{"Preview: " if preview else ""}{OPN} vs {CL} · prices as of {NOW}' + (" (that day's close)" if preview else "")
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


CSS = """.ixr{cursor:pointer}.ixr:hover td{background:rgba(0,0,0,.03)}.ixa{color:var(--mut);display:inline-block;transition:transform .15s}.ixr.open .ixa{transform:rotate(90deg)}
.ixd>td{background:#f7f8fa;padding:6px 8px 10px!important;white-space:normal!important}.ixt{width:100%;font-size:12.5px}.ixt th,.ixt td{background:transparent}
.g2>*,.steps>*{min-width:0}.card.newc{border:2px solid var(--up);background:#f7fdfa}
.gtag{font-size:10px;font-weight:800;color:var(--up);background:var(--upbg);border-radius:6px;padding:0 4px;margin-left:3px;vertical-align:1px}.gtag.ot{color:var(--fg);background:rgba(0,0,0,.06)}.chgs{display:grid;grid-template-columns:1fr 1fr;gap:14px}.chg h3{gap:6px}
.cl{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-top:1px solid var(--line);font-size:13px}.cl:first-of-type{border-top:0}
.cl i{font-style:normal;font-weight:800;width:14px;flex:none;text-align:center}.cg{color:var(--up)}.cb{color:var(--dn)}.cn{color:var(--mut)}
@media(max-width:760px){.chgs{grid-template-columns:1fr;gap:10px}}.card.lost{border:2px solid var(--dn);background:#fffafa}
.lostg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:4px}.lbig{font-size:34px;font-weight:800;letter-spacing:-.5px;line-height:1.1}
.lchips{display:flex;flex-wrap:wrap;gap:4px 10px;margin-top:8px;font-size:13px}
@media(max-width:760px){.lostg{grid-template-columns:1fr;gap:12px}.lbig{font-size:28px}}.pos{color:var(--up)}.neg{color:var(--dn)}.steps.four{grid-template-columns:repeat(4,1fr)}.step .big{font-size:18px}
.st{grid-template-columns:62px 1fr 60px minmax(0,1.4fr)}.st .sub:last-child{white-space:normal}
@media(max-width:1000px){.steps.four{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.steps.four{grid-template-columns:1fr}.st{grid-template-columns:54px 1fr 56px}.st .sub:last-child{display:none}}"""

JS = """(function(){const box=document.getElementById('indf');if(!box)return;const rows=document.querySelectorAll('#indt tbody tr.ixr');
rows.forEach(tr=>tr.onclick=e=>{if(e.target.closest('a'))return;const d=tr.nextElementSibling;d.hidden=!d.hidden;tr.classList.toggle('open',!d.hidden)});
function draw(f){rows.forEach(tr=>{tr.hidden=f!=='all'&&tr.dataset.k!==f;tr.nextElementSibling.hidden=true;tr.classList.remove('open')})}
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
        etfs = S.yf_batch(list(S.SECTOR_ETF.values()) + ["^VIX"], period="2y", interval="1d")   # ^VIX for the overnight changes
        today = nowny.date()
    preview = False
    if sum(d.index[-1].date() == today for d in frames.values()) < 0.5 * len(frames):
        if not a.any_day:
            print(f"No trading bar for {today} yet (a holiday, or the market isn't open): the Open page is left as it was.")
            return
        today = pd.Series([d.index[-1].date() for d in frames.values()]).mode().iloc[0]
        preview = True
        print(f"Preview: no bar for {nowny.date()}, using {today} as today.")
    at = None if preview else nowny.tz_convert("America/Chicago")
    r = build(frames, etfs, sectors, subs, sp500, today, a.out, at, preview)
    print("Open page:", r)


if __name__ == "__main__":
    main()
