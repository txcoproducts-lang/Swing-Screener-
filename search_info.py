"""Ticker search (the user's ask, 2026-11-02): a search bar at the top of the Stocks and Crypto pages. Typing any ticker,
sector ETF, SPY (or BTC) or a sector's name opens the chart pop-up with every signal the screener has on it, in one panel:
its verdict, your trend rules and setup checks, the strongest sector, strongest stock score, every list it is on (Top
picks, AI picks, OVTLYR Plan M and the OVTLYR screener's 9 rules), price and momentum, options and earnings, its sector's
breadth and the market's. Shared by screener.py and crypto/screener.py: build() writes data/signals.json (loaded the first
time a pop-up opens), box() is the search bar, CSS and JS go into the page."""
import json
import math


def _ok(x):
    return None if x is None else 1 if x else 0


def _f(v, fmt="{:.2f}"):
    try:
        if v is None or v != v:
            return "n/a"
        return fmt.format(v)
    except Exception:
        return "n/a"


def _pct(v, d=1):
    if v is None or v != v:
        return "n/a"
    return f'<span class="{"up" if v > 0 else "dn" if v < 0 else ""}">{v:+.{d}f}%</span>'


def _px(v):
    """A price: cents for most, more digits for coins under $1."""
    v = _num(v)
    if v is None:
        return "n/a"
    return f"${v:,.2f}" if v >= 1 else f"${v:.6f}".rstrip("0")


def _num(x):
    try:
        x = float(x)
        return None if math.isnan(x) else x
    except Exception:
        return None


def build(S, market, df, sws, *, spy=None, mkt_hot="", lists=None, ov=None, calls=None, earn=None, picks=None,
          secb=None, breadth=None, vix=None, skipped=None, names=None):
    """Every signal per ticker, as {asof, mk, m: market card, s: {group: card}, t: {ticker: entry}}. A card is
    {t: title, rows: [[ok, label, value]]}, ok 1 = passes, 0 = fails, None = information. An entry is {g: its group,
    n: its name, h: the verdict line, x: its cards in order, with "@sec" / "@mkt" where its sector's and the market's go}.
    S is the screener module (its helpers and settings), market "stock" or "crypto"."""
    CFG, esc, md = S.CFG, S.html_esc, S.md
    crypto = market == "crypto"
    MK = getattr(S, "MARKET", "S&P 500")           # the market's breadth group
    BENCH = getattr(S, "BENCH", "SPY")
    unit, units = ("coin", "coins") if crypto else ("stock", "stocks")
    G = "Category" if crypto else "Sector"
    short = lambda n: esc(S.SHORT_SECTOR.get(n, n))
    tk = lambda t: f'<b class="tk" data-tk="{esc(t)}">{esc(t)}</b>'
    w = sws.get(MK)
    names = names or {}

    def state(x):
        if x["z"] == 2:
            return f'<span class="obt">overbought</span>, over the {CFG["OB_BREADTH"]} line since {md(x["zsince"])}'
        if x["z"] == -1:
            return f'<span class="ost">oversold</span>, under the {CFG["OS_BREADTH"]} line since {md(x["zsince"])}'
        return f'<span class="{S.bcls(x)}">{"▲ upswing" if x["on"] else "▼ fading"}</span> since {md(x["since"])}'

    # ---- the market
    mrows = []
    checks = S.spy_checks(spy, w, mkt_hot)
    n_ok = sum(ok for _, ok, _ in checks)
    mrows.append([_ok(n_ok == len(checks)), f'<b>{BENCH} {"is moving up" if n_ok == len(checks) else "is not moving up"}</b>',
                  f'{n_ok} of {len(checks)} checks'])
    if spy is not None and len(spy) > 1:
        c = spy.Close
        mrows.append([None, f"{BENCH} close", f'{_px(float(c.iloc[-1]))} {_pct((c.iloc[-1] / c.iloc[-2] - 1) * 100, 2)} today'])
    for text, ok, detail in checks:
        mrows.append([_ok(ok), text, detail])
    if w:
        mrows.append([_ok(S.bcls(w) == "up"), f"Rising ({'coins' if crypto else 'S&amp;P 500 stocks'})",
                      f'{w["rise"]:.0f}% · 10-day avg {w["avg"]:.0f}% · {state(w)}'])
        if w.get("up") is not None:
            mrows.append([None, f"{units.capitalize()} in your full uptrend", f'{w["up"]:.0f}%'])
    if breadth is not None and len(breadth):
        x = breadth.iloc[-1]
        try:
            mrows += [[_ok(x.pct50 > 50), "Above the 50-day average", f"{x.pct50:.0f}%"],
                      [_ok(x.pct200 > 50), "Above the 200-day average", f"{x.pct200:.0f}%"],
                      [_ok(x.adv > x.dec), "Advancing / declining today", f"{int(x.adv)} / {int(x.dec)}"],
                      [_ok(x.nh > x.nl), "New 52-week highs / lows", f"{int(x.nh)} / {int(x.nl)}"]]
        except Exception:
            pass
    if vix is not None and len(vix) > 30 and hasattr(S, "VIX_ZONES"):
        now = float(vix.iloc[-1])
        z = next(z for z in S.VIX_ZONES if z[0] <= now < z[1])
        rank = (vix.iloc[-252:] < now).mean() * 100
        mrows.append([_ok(now < 20), "VIX (fear gauge)", f'{now:.2f} · {z[2]} · higher than {rank:.0f}% of the last year'])
    if ov and ov.get("market"):
        om = ov["market"]
        mrows.append([_ok(om.get("ok")), "OVTLYR plan: market on", "yes" if om.get("ok") else "no"])
        for ch in om.get("checks") or []:
            mrows.append([_ok(ch.get("ok")), "OVTLYR: " + ch.get("text", ""), ""])
    if "has_setup" in df:
        n_set = int(df.has_setup.sum())
        n_sup = int((df.has_setup & (df.tier == "Super")).sum()) if "tier" in df else n_set
        mrows.append([None, "Setups tonight", f"{n_set} ({n_sup} Super, {n_set - n_sup} Regular)"])
    mcard = dict(t=f"Market ({BENCH})", rows=mrows)

    # ---- each sector
    secs = sorted((n for n in sws if n != MK), key=lambda n: -sws[n]["rise"])
    srow = {r.sector: r for r in secb.itertuples()} if secb is not None and len(secb) else {}
    scards = {}
    for i, n in enumerate(secs):
        x = sws[n]
        rows = [[_ok(i < 3), f"Rank by Rising", f"#{i + 1} of {len(secs)}"],
                [_ok(S.bcls(x) == "up"), "Rising",
                 f'{x["rise"]:.0f}% · 10-day avg {x["avg"]:.0f}% · {state(x)}'],
                [_ok(x["z"] != 2), f'Under your {CFG["OB_BREADTH"]} line (not overbought)', f'{x["rise"]:.0f}%']]
        if x.get("up") is not None:
            rows.append([None, "In your full uptrend", f'{x["up"]:.0f}%'])
        r = srow.get(n)
        if r is not None:
            try:
                rows += [[None, f"{units.capitalize()} in uptrend (whole scan)", f"{r.uptrend} of {r.liquid} ({r.up_pct:.0f}%)"],
                         [None, "Momentum / pullback setups", f"{r.momentum} / {r.pullback}"],
                         [None, "Advancing / declining today", f"{r.adv} / {r.dec}"]]
            except Exception:
                pass
        o = (ov or {}).get("sectors", {}).get(n)
        if o:
            rows.append([_ok(o.get("ok")), "OVTLYR sector rules", "pass" if o.get("ok") else "; ".join(o.get("miss") or []) or "fail"])
        if "ss_ok" in df and "strength" in df:
            top = df[(df.sector == n) & df.ss_ok].sort_values("strength", ascending=False).head(5)
            if len(top):
                rows.append([None, f"Strongest {units} on your list", " ".join(f'{tk(t)} {s:.0f}' for t, s in zip(top.ticker, top.strength))])
            else:
                rows.append([0, f"Strongest {units} on your list", "none tonight"])
        etf = S.SECTOR_ETF.get(n)
        scards[n] = dict(t=f"{G}: {short(n)}" + (f" ({esc(etf)})" if etf and not crypto else ""), rows=rows)

    # ---- each ticker
    T = {}
    L = lists or {}
    inl = {k: {r["ticker"]: (i + 1, r) for i, r in enumerate(L.get(k, {}).get("rows", []))} for k in ("nu", "bo", "ai")}
    hot = {h["ticker"]: (k, h.get("why", "")) for k in ("nu", "bo") for h in L.get(k, {}).get("hot", [])}
    ovs = {s["ticker"]: s for s in (ov or {}).get("setups", [])}
    ovd = {d["ticker"]: d for d in (ov or {}).get("dropped", []) if isinstance(d, dict)}
    ovr = {r[0]: r for r in (ov or {}).get("screen") or []}
    rules = getattr(S, "OV_RULES", ())
    labels = getattr(S, "OV_LABELS", {})
    opt = {}
    if picks is not None and "opt" in picks:
        opt = {t: o for t, o in zip(picks.ticker, picks.opt) if isinstance(o, dict)}
    ss_rank, buy_rank = {}, {}
    if "ss_ok" in df and "strength" in df:
        for i, t in enumerate(df[df.ss_ok].sort_values("strength", ascending=False).ticker):
            ss_rank[t] = i + 1
        try:
            for i, t in enumerate(S.ss_order(df)[0].ticker):
                buy_rank[t] = i + 1
        except Exception:
            pass
    n_list = len(ss_rank)
    mkt_ok = n_ok == len(checks)

    def call_txt(o, rule):
        px = (o["bid"] + o["ask"]) / 2 if o.get("quote") == "live" else o.get("last")
        v = (f'{o["exp"]} ${o["strike"]:g}C · {o.get("dte", "?")} days · delta {o["delta"]:.2f} · '
             f'{"mid" if o.get("quote") == "live" else "last"} {_f(px)}'
             + (f' · OI {o["oi"]:,}' if o.get("oi") is not None else ""))
        return [_ok(not o.get("miss")), f"Call ({rule})", v]

    for r in df.itertuples():
        t, g = r.ticker, (r.sector or "")
        gr = lambda k, d=None: getattr(r, k, d)
        has, tier, setup = bool(gr("has_setup", False)), gr("tier", "") or "", gr("setup", "") or ""
        ob = gr("ob", "") or ""
        # verdict
        if has:
            h = f'<b class="up">{esc(tier)} {esc(setup)} setup</b>'
        elif setup == "Overbought":
            h = f'<b class="dn">Overbought, no setup</b> ({esc(ob or mkt_hot)})'
        elif gr("core"):
            h = '<b>In your uptrend</b>, no setup tonight'
        elif gr("reg_up"):
            h = '<b>Regular uptrend</b> (under the 150), no setup tonight'
        else:
            h = '<b class="dn">Not in your uptrend</b>'
        if t in ss_rank:
            h += f' · on your strongest list, <b>#{ss_rank[t]}</b> of {n_list}'
        if t in buy_rank:
            h += f' · <b class="up">#{buy_rank[t]} in Your system\'s buying order</b>'
        if _num(gr("strength")) is not None:
            h += f' · strength score <b>{gr("strength"):.0f}</b>'
        h += f' · screener score {gr("score", 0):.0f}'

        # your trend rules and the setup checks
        vs20, rs_ = _num(gr("vs20")), _num(gr("rsi"))
        ext, depth, x2050 = _num(gr("ext")), _num(gr("depth")), gr("x2050")
        p50 = (_num(gr("vs50")) or 0) > 0
        trend = [[_ok(gr("x1020")), "EMA10 over EMA20", ""],
                 [_ok(p50), "Price over EMA50", _pct(gr("vs50"))],
                 [_ok(gr("p150")), f'Price over the 150-day {"EMA" if CFG["LONG_MA_TYPE"] == "EMA" else "average"}', ""],
                 [_ok(gr("core")), "Your uptrend (all three)", "yes" if gr("core") else "no"],
                 [_ok(gr("p200")), "Price over the 200-day", ""],
                 [_ok(gr("stack")), "Full stack (10 &gt; 20 &gt; 50 &gt; 150 &gt; 200)", ""]]
        if gr("cross"):
            trend.append([1, "EMA50 crossed over the 150 lately", f'{int(gr("days_since_cross") or 0)} days ago'])
        stp = [[_ok(has), "Setup tonight", f'{esc(tier)} {esc(setup)}' if has else "Overbought" if setup == "Overbought" else "none"]]
        if setup == "Overbought" or ob:
            stp.append([0, "Your overbought rule", esc(ob or mkt_hot)])
        elif mkt_hot:
            stp.append([0, "Your overbought rule (market)", esc(mkt_hot)])
        stp += [[None, "<i>Momentum needs</i>", ""],
                [_ok(rs_ is not None and 55 <= rs_ <= 80), "RSI 55-80", _f(rs_, "{:.0f}")],
                [_ok(ext is not None and ext <= 3), "At most 3 ATR over EMA20", _f(ext, "{:.1f} ATR")],
                [_ok(gr("brk20") or (_num(gr("from_hi")) or -99) >= -3), "20-day breakout or within 3% of the 52w high",
                 ("breakout · " if gr("brk20") else "") + _f(_num(gr("from_hi")), "{:+.1f}% from high")],
                [None, "<i>Pullback needs</i>", ""],
                [_ok(x2050), "EMA20 over EMA50", ""],
                [_ok(rs_ is not None and rs_ <= 50), "RSI 50 or under", _f(rs_, "{:.0f}")],
                [_ok(vs20 is not None and vs20 <= 2), "Back near / under EMA20 (within 2%)", _pct(vs20)],
                [_ok(depth is not None and depth >= 3), "3%+ off the 15-day high", _f(depth, "{:.1f}%")]]
        stp.append([None, "Screener score (trend 70% + setup 30 pts)", f'{gr("score", 0):.0f}'])

        # strongest sector, strongest stock
        sc = []
        if _num(gr("strength")) is not None:
            sc = [[None, "Strength score (0-100)", f'<b>{gr("strength"):.0f}</b>'],
                  [None, f"Market part (40% of {'the crypto market' if crypto else 'S&amp;P 500'} Rising)", f'{gr("ss_mkt"):.1f} pts'],
                  [None, f"{G} part (40% of its Rising)", _f(_num(gr("ss_sec")), "{:.1f} pts")],
                  [None, f"{unit.capitalize()} part (20% of its RS in its {G.lower()})", _f(_num(gr("ss_stk")), "{:.1f} pts")]]
            if _num(gr("rs_n")) is not None:
                sc.append([_ok(gr("rs_n") <= 3), f"Relative strength rank in its {G.lower()}", f'#{int(gr("rs_n"))} of {int(gr("rs_of"))}'])
            sc.append([_ok(gr("sec_on")), f"Its {G.lower()} in an upswing and under {CFG['OB_BREADTH']}", "yes" if gr("sec_on") else "no"])
            sc.append([_ok(gr("ss_ok")), "On the strongest list", f"#{ss_rank[t]} of {n_list}" if t in ss_rank else "no"])
            sc.append([_ok(t in buy_rank), "In Your system's buying order",
                       f"#{buy_rank[t]} in line" if t in buy_rank else "no"])

        # lists
        li = []
        for k, name in (("nu", "New uptrends"), ("bo", "Breakout watch"), ("ai", "AI picks")):
            if t in inl[k]:
                i, row = inl[k][t]
                v = f'#{row.get("rank") or i}'
                if k == "ai" and row.get("added"):
                    v += f' · since {row["added"]}' + (f' at ${row["price"]:,.2f}' if row.get("price") else "")
                li.append([1, f"Top picks: {name}", v])
            elif t in hot and hot[t][0] == k:
                li.append([0, f"Top picks: {name}", "left out: " + esc(hot[t][1])])
            else:
                li.append([0, f"Top picks: {name}", "not on it"])
        if ov is not None:
            s = ovs.get(t)
            li.append([_ok(bool(s)), "OVTLYR Plan M setup",
                       (("new tonight · " if s.get("new") else "") + f'buy signal {s.get("cross", "")}') if s else
                       ("dropped: " + esc(ovd[t].get("why") or "") if t in ovd else "no")])
            row = ovr.get(t)
            if row:
                bits = row[5]
                li.append([_ok(bits.count("0") == 0), "OVTLYR screener", f'{bits.count("1")} of {len(bits) - bits.count("-")} rules pass'])
                for rk, b in zip(rules, bits):
                    lab = labels.get(rk, (rk, ""))
                    li.append([None if b == "-" else _ok(b == "1"), "&nbsp;&nbsp;" + esc(lab[0]), "not checked" if b == "-" else ""])

        # price and momentum
        pm = [[None, "Close", _px(gr("close"))],
              [None, "1 day / 5 days / 1 month", f'{_pct(gr("chg1d"))} · {_pct(gr("chg5d"))} · {_pct(gr("chg1m"))}'],
              [_ok(rs_ is not None and rs_ < CFG.get("OB_RSI", 70)), "RSI (14)", _f(rs_, "{:.0f}")],
              [None, "CCI", _f(_num(gr("cci")), "{:.0f}")],
              [None, "ATR (daily range)", _f(_num(gr("atr_pct")), "{:.1f}%")],
              [None, "Volume vs 20-day average", _f(_num(gr("relvol")), "{:.1f}x")],
              [None, "From the 52-week high", _pct(gr("from_hi"))],
              [None, "vs EMA10 / 20 / 50", f'{_pct(gr("vs10"))} · {_pct(gr("vs20"))} · {_pct(gr("vs50"))}']]

        # options and earnings
        oe = []
        if not crypto:
            if t in opt:
                oe.append(call_txt(opt[t], f'screener: nearest {CFG.get("TARGET_DELTA", "")} delta'))
            c_ = (calls or {}).get(t)
            if isinstance(c_, dict):
                row = call_txt(c_, "your rules: 50-80 delta, 15-30 days, OI over 500")
                if c_.get("miss"):
                    row[2] += " · closest, misses " + "+".join(c_["miss"])
                oe.append(row)
            elif isinstance(c_, str):
                oe.append([0, "Call (your rules)", esc(c_)])
            if not oe:
                oe.append([None, "Call", "looked up for setups and Top picks only"])
            e = (earn or {}).get(t) or (ovr.get(t) or [None] * 8)[7]
            oe.append([None, "Next earnings", e or "not looked up (only for Top picks and near OVTLYR setups)"])

        x = [["Verdict: setup checks", stp], ["Your trend rules", trend]]
        if sc:
            x.append([f"Strongest {G.lower()}, strongest {unit}", sc])
        x += [["Lists it is on", li], ["Price and momentum", pm]]
        if oe:
            x.append(["Options and earnings", oe])
        x += ["@sec", "@mkt"]
        T[t] = dict(g=g, n=names.get(t, ""), h=h, x=x)

    # sector ETFs (indexes for crypto) and the benchmark: the group's card first
    for n, etf in S.SECTOR_ETF.items():
        if n == MK:
            if etf in T:
                T[etf]["x"] = ["@mkt"] + [c for c in T[etf]["x"] if c != "@mkt"]
                T[etf]["g"] = T[etf]["g"] or ""
            else:
                T[etf] = dict(g=MK, n="the market" if not crypto else "Bitcoin", h=f'<b>{esc(etf)}</b>: the market. '
                              + ('<b class="up">Moving up</b>' if mkt_ok else '<b class="dn">Not moving up</b>')
                              + f' ({n_ok} of {len(checks)} checks)', x=["@mkt"])
            continue
        if n not in scards:
            continue
        x_ = sws[n]
        h = (f'<b>{esc(etf)}</b>: the {short(n)} {G.lower()}, #{secs.index(n) + 1} of {len(secs)} by Rising, '
             f'<b>{x_["rise"]:.0f}%</b> rising, {state(x_)}')
        T[etf] = dict(g=n, n=f"{S.SHORT_SECTOR.get(n, n)} {G.lower()}", h=h, x=["@sec", "@mkt"])
    if ov:                                          # the OVTLYR Plan ETF funds
        for k, e in (ov.get("etf") or {}).items():
            if k in T:
                continue
            rows = [[_ok(e.get("ok")), "Plan ETF set up", "yes" if e.get("ok") else "no"]]
            rows += [[_ok(c.get("ok")), esc(c.get("text", "")), ""] for c in e.get("checks") or []]
            rows += [[0, "Sell: " + esc(s if isinstance(s, str) else s.get("text", "")), ""] for s in e.get("sell") or []]
            T[k] = dict(g=MK, n=f"3x fund on {e.get('under', '')}",
                        h=f'<b>{esc(k)}</b>: OVTLYR Plan ETF on {esc(e.get("under", ""))}, '
                          + ('<b class="up">set up</b>' if e.get("ok") else '<b class="dn">not set up</b>'),
                        x=[["OVTLYR Plan ETF", rows], "@mkt"])
    for t, (g, why) in (skipped or {}).items():     # downloaded but under the price / volume floor
        if t not in T:
            T[t] = dict(g=g or "", n=names.get(t, ""), h=f'<b>Not scanned:</b> {esc(why)}', x=["@sec", "@mkt"])

    alias = {"MARKET": BENCH, "THE MARKET": BENCH}
    if not crypto:
        alias.update({"S&P": "SPY", "S&P 500": "SPY", "SP500": "SPY", "SPX": "SPY"})
    for n, etf in S.SECTOR_ETF.items():
        if n == MK:
            continue
        alias[n.upper()] = etf
        alias[S.SHORT_SECTOR.get(n, n).upper()] = etf
    return dict(asof=str(getattr(df, "attrs", {}).get("asof", "")), mk=MK, m=mcard, s=scards, t=T, alias=alias)


def write(sig, out):
    d = out / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "signals.json").write_text(json.dumps(sig, separators=(",", ":")), encoding="utf-8")


def box(sig, market="stock"):
    """The search bar for the header, with every ticker in a list for suggestions."""
    if not sig:
        return ""
    opts = "".join(f'<option value="{t}">{e.get("n") or ""}</option>' for t, e in sorted(sig["t"].items()))
    ph = "Search a coin, category or BTC" if market == "crypto" else "Search a ticker, sector or SPY"
    return (f'<form class="srch" role="search" id="srch"><input id="sq" list="sidx" placeholder="{ph}" autocomplete="off" '
            f'autocapitalize="characters" spellcheck="false" enterkeyhint="search" aria-label="{ph}"><button>Search</button></form>'
            f'<datalist id="sidx">{opts}</datalist>')


def alias_js(sig):
    return json.dumps((sig or {}).get("alias") or {}, separators=(",", ":")).replace("</", "<\\/")


CSS = """
.srch{display:flex;gap:4px;flex:1 1 220px;max-width:340px}.srch input{flex:1;min-width:0;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:14px}
.srch button{background:var(--acc);color:#fff;border:0;border-radius:999px;padding:6px 12px;font-size:13px;font-weight:600;cursor:pointer}
@media(max-width:600px){.srch{order:5;flex:1 1 100%;max-width:none;margin-top:2px}.srch input{font-size:16px}}
#cms{border-bottom:1px solid var(--line);padding:6px 12px;font-size:13px;line-height:1.45;max-height:46%;overflow:auto}#cms[hidden]{display:none}
#cms>summary{cursor:pointer}#cms>summary .sml{color:var(--acc);font-size:12px;margin-left:6px}#cms[open]>summary .sml{display:none}
#cms .sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:8px;margin:6px 0 4px}
#cms .sc{background:var(--card);border-radius:8px;padding:6px 9px}#cms .sc h4{margin:0 0 3px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
#cms .sr{display:flex;gap:6px;font-size:12px;padding:1px 0;align-items:baseline}#cms .sr>i{font-style:normal;width:12px;flex:none;text-align:center;font-weight:700}
#cms .sr>i.ok{color:var(--up)}#cms .sr>i.no{color:var(--dn)}#cms .sr>i.in{color:var(--mut);font-weight:400}#cms .sr>span{flex:1}#cms .sr>b{font-weight:600;text-align:right}
#cms .sr>b{max-width:58%}#cms .nt{color:var(--mut);font-size:12px;margin-top:4px}
#cm .box:has(#cms[open]){overflow:auto}#cm .box:has(#cms[open]) #cms{max-height:none;overflow:visible}#cm .box:has(#cms[open]) #cmbt{max-height:none}
#cm .box:has(#cms[open]) #cmw{flex:none;height:max(420px,70vh)}#cm .box:has(#cms[open]) .top{position:sticky;top:0;background:var(--bg);z-index:4}
@media(max-width:600px){#cms .sg{grid-template-columns:1fr}}
"""

# needs the pop-up's openChart(t), cmSym, and setOn/tvDraw for the fallback; SALIAS is set by the page
JS = r"""
// ---- ticker search: every signal the screener has, in a panel over the chart (data/signals.json, loaded once)
let SIG=null,sigP=null;
function sigLoad(){return sigP||(sigP=fetch('data/signals.json').then(r=>{if(!r.ok)throw 0;return r.json()}).then(j=>SIG=j).catch(()=>null))}
function sigCard(c){if(!c)return'';return'<div class="sc"><h4>'+c.t+'</h4>'+c.rows.map(r=>'<div class="sr"><i class="'+(r[0]===1?'ok':r[0]===0?'no':'in')+'">'+(r[0]===1?'✓':r[0]===0?'✗':'·')+'</i><span>'+r[1]+'</span>'+(r[2]?'<b>'+r[2]+'</b>':'')+'</div>').join('')+'</div>'}
function sigDraw(t,open){const el=document.getElementById('cms');if(!el)return;el.hidden=false;el.open=!!open;
el.innerHTML='<summary>Loading every signal for '+t+'…</summary>';
sigLoad().then(S=>{if(t!==cmSym)return;if(!S){el.hidden=true;return}const e=S.t[t];let h,x;
if(!e){h='<b>'+t+'</b> is not tracked by the screener, so only the TradingView chart is here';x=['@mkt']}else{h=e.h;x=e.x}
const g=e&&e.g&&S.s[e.g];
const cards=x.map(c=>c==='@sec'?(g?sigCard(g):''):c==='@mkt'?sigCard(S.m):sigCard({t:c[0],rows:c[1]})).join('');
el.open=!!open&&!!e;el.innerHTML='<summary>'+(e&&e.n?'<span class="mut">'+e.n+'</span> · ':'')+h+'<span class="sml">Show every signal ▾</span></summary><div class="sg">'+cards+'</div>'+
(e?'':'<div class="nt">The screener scans '+(S.mk==='S&P 500'?'S&amp;P 500 and Nasdaq 100 stocks over $10 averaging 1M+ shares a day':'the coins on its list')+'; the market card above is tonight\'s.</div>');
el.querySelectorAll('.tk').forEach(a=>a.onclick=ev=>{ev.stopPropagation();openChart(a.dataset.tk,true)})})}
(function(){const f=document.getElementById('srch'),q=document.getElementById('sq');if(!f)return;
const known=new Set([...document.querySelectorAll('#sidx option')].map(o=>o.value));
function find(s){s=s.trim();if(!s)return null;const u=s.toUpperCase();
if(known.has(u))return u;const d=u.replace(/\./g,'-').replace(/\s+/g,'');if(known.has(d))return d;
if(SALIAS[u])return SALIAS[u];const c=d.replace(/-?USDT?$/,'');if(c!==d&&known.has(c))return c;
const o=[...document.querySelectorAll('#sidx option')].find(o=>o.textContent&&o.textContent.toUpperCase().includes(u)&&u.length>2);
return o?o.value:d}
f.onsubmit=e=>{e.preventDefault();const t=find(q.value);if(!t)return;q.blur();openChart(t,true);q.value=''};
q.addEventListener('input',e=>{if((!e.inputType||e.inputType==='insertReplacementText')&&known.has(q.value)){const t=q.value;q.blur();openChart(t,true);q.value=''}});
const p=new URLSearchParams(location.search).get('q');if(p){const t=find(p);if(t)openChart(t,true)}})();
"""
