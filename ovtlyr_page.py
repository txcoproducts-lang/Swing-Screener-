"""
The OVTLYR screener page (site/ovtlyr/): OVTLYR's trading plans from the deck the user shared, and nothing else.

screener.py builds tonight's plan (ovtlyr_plan) with the user's own overbought rule on top; this page leaves that rule
out, so it shows the deck's rules alone. Tabs: Today (which plan to run), Market, Sectors, Heatmap, Stocks, Plan ETF,
Rules. Heat = 14-day RSI, the stand-in for OVTLYR's private fear & greed heatmap; buy / sell signal = the 10 EMA
crossing over / under the 20; breadth = share of stocks with the 10 EMA over the 20.
"""
import datetime as dt, html, json
from pathlib import Path

HEAT_MAX, EXCLUDE = 70, ("Health Care",)
RULES = [("Buy signal", "the 10 EMA crossed over the 20 in the last 5 trading days"), ("Uptrend", "10 / 20 / 50 bullish trend"),
         ("Over 10 EMA", "price over the 10 EMA"), ("Heat rising", "heat (RSI) any value, rising"),
         ("$10-$350", "price range"), ("Sector passes", "the sector's 4 checks; Health Care is out"),
         ("Clear of OB", "more than 2% from an order block, any age"), ("No earnings", "4+ days to earnings")]
SHORT = {"Information Technology": "Tech", "Communication Services": "Comm.", "Consumer Discretionary": "Discretionary",
         "Consumer Staples": "Staples"}
RED, GREEN, YELLOW = "#f4a6a0", "#a8e0bf", "#f7dc7a"      # the user's three colours: overbought / good / oversold
C3 = ("#14202e", "#e8890c", "#2f6fed")                    # breadth, its 5-day and 10-day averages
esc = html.escape
sn = lambda s: SHORT.get(s, s)


def heat(v, up=True):
    """Red = overbought (70+); green only while the heat is rising; yellow when it's falling or oversold (under 30)."""
    return RED if v >= HEAT_MAX else YELLOW if v < 30 or not up else GREEN


hb = lambda v, up=True: f'<span class="hb" style="background:{heat(v, up)}">{v:.0f}</span>'
dot = lambda c: '<i class="d dy">✓</i>' if c == "1" else '<i class="d dn">✗</i>' if c == "0" else '<i class="d du" title="not checked">·</i>'
okb = lambda b: '<i class="d dy">✓</i>' if b else '<i class="d dn">✗</i>'
md = lambda s: f"{dt.date.fromisoformat(s):%b} {dt.date.fromisoformat(s).day}"
tk = lambda t: f'<a class="tk" href="https://www.tradingview.com/chart/?symbol={esc(t)}" target="_blank" rel="noopener">{esc(t)}</a>'


def ema(xs, n):
    out, k = [], 2 / (n + 1)
    for x in xs:
        out.append(x if not out or out[-1] is None else out[-1] if x is None else out[-1] + k * (x - out[-1]))
    return out


def spark(series, days, w=260, h=70, lines=(), colors=C3, labels=True):
    """A small SVG line chart: series = lists of values over days; lines = dashed guide levels."""
    vals = [v for s in series for v in s if v is not None] + list(lines)
    if not vals or len(series[0]) < 2:
        return ""
    lo, hi = min(vals) - 2, max(vals) + 2
    n = len(series[0])
    X = lambda i: 4 + i * (w - 8) / (n - 1)
    Y = lambda v: h - 14 - (v - lo) / (hi - lo) * (h - 22)
    g = "".join(f'<line x1="0" x2="{w}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#c27a00" stroke-dasharray="4 3"/>'
                f'<text x="{w - 2}" y="{Y(v) - 3:.1f}" text-anchor="end" font-size="9" fill="#c27a00">{v}</text>' for v in lines)
    p = "".join(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="'
                + " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s) if v is not None) + '"/>' for s, c in zip(series, colors))
    lab = (f'<text x="4" y="{h - 2}" font-size="9" fill="#6b7686">{md(days[0])}</text><text x="{w - 4}" y="{h - 2}" font-size="9" '
           f'fill="#6b7686" text-anchor="end">{md(days[-1])}</text>') if labels else ""
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">{g}{p}{lab}</svg>'


LEG = ('<span class="leg"><i style="background:#14202e"></i>breadth <i style="background:#e8890c"></i>5-day avg '
       '<i style="background:#2f6fed"></i>10-day avg</span>')


def plan_data(ov):
    """Tonight's plan with the user's own overbought rule taken out, so only the deck's rules decide."""
    secs = {}
    for n, v in ov["sectors"].items():
        m = [x for x in v["miss"] if not x.startswith("overbought by your rule")]
        secs[n] = dict(v, miss=m, ok=not m)
    mchecks = [c for c in ov["market"]["checks"] if c["k"] != "hot"]
    etf = {}
    for k, e in ov["etf"].items():
        ch = [c for c in e["checks"] if c["k"] not in ("hot", "cci")]
        etf[k] = dict(e, checks=ch, ok=bool(ch) and all(c["ok"] for c in ch) and not e.get("sell"))
    rows = []
    for r in ov.get("screen") or []:
        t, sec, close, rsi, age, k = r[:6]
        atr, earn = (r[6], r[7]) if len(r) > 7 else (None, None)
        k = k[:5] + ("1" if secs.get(sec, {}).get("ok") else "0") + k[7:]      # drop the "hot" flag (the user's rule)
        rows.append(dict(t=t, sec=sec, close=close, rsi=rsi, age=age, k=k, atr=atr, earn=earn,
                         miss=[RULES[i][0] for i, c in enumerate(k) if c == "0"]))
    rows.sort(key=lambda r: (len(r["miss"]), r["age"] if r["age"] is not None else 99, -r["rsi"]))
    return secs, mchecks, all(c["ok"] for c in mchecks), etf, rows


def build(ov, out_dir):
    """Write out_dir/ovtlyr/index.html from tonight's plan (ovtlyr_plan's dict, with hist and screen)."""
    secs, mchecks, m_ok, etf, rows = plan_data(ov)
    hist = ov.get("hist") or {}
    days = hist.get("t") or [ov["asof"]]
    spy = ov["market"]["spy"]
    ready = [r for r in rows if not r["miss"]]
    one = [r for r in rows if len(r["miss"]) == 1]
    order = sorted(secs, key=lambda n: (n in EXCLUDE, not secs[n]["ok"], -secs[n]["rsi"]))
    m_on, e_on = m_ok and bool(ready), any(e["ok"] for e in etf.values())

    def plan_strip():
        def etf_line(k, e):
            if e["ok"]:
                return f'<b>{k}</b> <span class="up">set up</span>'
            why = e["sell"][0].split(" (")[0] if e.get("sell") else next((c["text"].split(":")[0] for c in e["checks"] if not c["ok"]), "")
            return f'<b>{k}</b> <span class="sub">{esc(why)}</span>'
        box = lambda on, t, d: f'<div class="pl{" on" if on else ""}"><div class="pln">{t}</div><div class="sub">{d}</div></div>'
        return ('<div class="plans">'
                + box(m_on, "Plan M " + ("✓ on" if m_on else "off"),
                      f"{len(ready)} stock{'s' if len(ready) != 1 else ''} pass every rule" + ("" if m_ok else " · the market fails"))
                + box(e_on and not m_on, "Plan ETF " + ("✓ set up" if e_on else "· not set up"), "<br>".join(etf_line(k, e) for k, e in etf.items()))
                + box(not m_on and not e_on, "Plan #SICADFU" + (" ✓" if not m_on and not e_on else ""),
                      "cash waits in SGOV when nothing else is set up") + '</div>')

    def page_today():
        n_sec = sum(secs[n]["ok"] for n in secs)
        lay = [("Market", "40% of the move", f'{sum(c["ok"] for c in mchecks)} of {len(mchecks)} checks pass', m_ok, "market"),
               ("Sector", "30% of the move", f"{n_sec} of {len(secs)} sectors pass", n_sec > 0, "sectors"),
               ("Stock", "30% of the move", f"{len(ready)} ready · {len(one)} one rule away", bool(ready), "stocks")]
        cards = "".join(f'<div class="step"><div class="n">{a} · {b}</div><div class="big">{okb(ok)} {c}</div>'
                        f'<a class="go" data-go="{g}">Open {g} ›</a></div>' for a, b, c, ok, g in lay)
        sig = lambda r: "signal today" if r["age"] == 0 else f'signal {r["age"]}d ago'
        top = "".join(f'<div class="st">{tk(r["t"])}<span class="sub">{esc(sn(r["sec"]))}</span>{hb(r["rsi"], r["k"][3] == "1")}<span class="sub">{sig(r)}</span></div>'
                      for r in ready[:10]) or '<div class="sub">No stock passes every rule tonight.</div>'
        return (f'<div class="h1">What is the market telling us?</div><div class="sub lead">OVTLYR\'s plan for tonight, from the deck: '
                f'market first, then sector, then stock.</div>{plan_strip()}<div class="steps" style="margin-top:14px">{cards}</div>'
                f'<div class="card" style="margin-top:14px"><h3>Plan M stocks, freshest signal first <a data-go="stocks">All {len(ready)} ›</a></h3>{top}</div>')

    def page_market():
        c = {x["k"]: x for x in mchecks}
        mk = hist.get("mkt") or [[ov["market"]["breadth"]["pct"]]] * 3
        card = lambda k, t, v, d, ch="": (f'<div class="card"><h3>{okb(c[k]["ok"]) if k in c else ""} {t}</h3><div class="big2">{v}</div>'
                                          f'<div class="hint">{d}</div>{ch}</div>')
        e10, e20 = spy["e10"], spy["e20"]
        return (f'<div class="h1">Market · 40% of the move</div><div class="sub lead">All four must be true to continue with Plan M. '
                f'If not, go to Plan ETF or #SICADFU.</div><div class="g2">'
                + card("heat", "SPY heat under 70 and rising", f'{spy["rsi"]:.0f} <small>from {spy["rsi_prev"]:.0f}</small>',
                       "Heat = 14-day RSI, the stand-in for OVTLYR's fear &amp; greed heatmap. Last 3 months:",
                       spark([hist["spy"]], days, lines=(HEAT_MAX,)) if hist.get("spy") else "")
                + card("signal", "SPY buy signal", f'10 EMA {e10:.2f} <small>{"over" if e10 > e20 else "under"} the 20 EMA {e20:.2f}</small>',
                       "Buy signal = the 10 EMA crossing over the 20; sell signal = under it.")
                + card("trend", "SPY bullish trend 10 / 20 / 50", f'{spy["close"]:.2f} <small>{"over" if spy["close"] > spy["e50"] else "under"} '
                       f'the 50 EMA {spy["e50"]:.2f}</small>', "10 EMA over the 20 and price over the 50 EMA.")
                + card("breadth", "Full-stocks breadth: bullish cross of its 10 EMA",
                       f'{ov["market"]["breadth"]["pct"]:.0f}% <small>vs its 10-day average {ov["market"]["breadth"]["ema"]:.0f}%</small>',
                       f"Bull list % = stocks with the 10 EMA over the 20 (S&amp;P 500 + Nasdaq 100). {LEG}", spark(mk, days))
                + '</div>')

    def sector_tiles():
        out = []
        for n in order:
            v, h = secs[n], (hist.get("secs") or {}).get(n)
            b, e5, e10 = h["b"] if h else ([v["bull"]], [v["bull"]], [v["bull_ema"]])
            ex = n in EXCLUDE
            st = "excluded" if ex else "passes" if v["ok"] else "fails"
            a5 = "over" if b[-1] > e5[-1] else "under"
            a10 = "over" if b[-1] > e10[-1] else "under"
            out.append(f'<div class="tile{" ex" if ex else ""}" style="background:{heat(v["rsi"], v["rsi"] > v["rsi_prev"])}"><div class="tn"><b>{esc(sn(n))}</b>'
                       f'<span class="pill {"p-up" if st == "passes" else "p-dn" if st == "fails" else "p-n"}">{st}</span></div>'
                       f'<div class="tv">Heat {v["rsi"]:.0f} · breadth {b[-1]:.0f}%</div>'
                       f'<div class="tc">{spark([b, e5, e10], days, w=220, h=64, labels=False)}</div>'
                       f'<div class="tf">{a5} its 5-day ({e5[-1]:.0f}) · {a10} its 10-day ({e10[-1]:.0f})</div></div>')
        return (f'<div class="card" style="margin-bottom:14px"><h3>Sector breadth, last 3 months {LEG}</h3><div class="tiles">{"".join(out)}</div>'
                f'<div class="hint" style="margin-top:8px">Tile colour = the sector\'s heat: red 70+ (overbought), green 30-70 and rising, '
                f'yellow falling or under 30 (oversold). Breadth = % of its stocks with the 10 EMA over the 20.</div></div>')

    def page_sectors():
        srsi = spy["rsi"]
        trs = []
        for n in order:
            v, h = secs[n], (hist.get("secs") or {}).get(n)
            greed = v["rsi"] / srsi if srsi else 0
            nready = sum(1 for r in ready if r["sec"] == n)
            ex = n in EXCLUDE
            pill = ('<span class="pill p-n">excluded</span>' if ex else '<span class="pill p-up">passes</span>' if v["ok"]
                    else '<span class="pill p-dn">fails</span>')
            trs.append(f'<tr class="{"ex" if ex else ""}"><td><b>{esc(n)}</b>{"<div class=sub>excluded in the plan</div>" if ex else ""}</td>'
                       f'<td>{okb(v["bull"] > v["bull_ema"])} {v["bull"]:.0f}% <span class="sub">vs {v["bull_ema"]:.0f}%</span></td>'
                       f'<td class="sp">{spark(h["b"], days, w=120, h=34, labels=False) if h else ""}</td>'
                       f'<td>{okb(greed > 1)} {greed:.2f}</td><td>{okb(v["rsi"] < HEAT_MAX)} {hb(v["rsi"], v["rsi"] > v["rsi_prev"])}</td>'
                       f'<td>{okb(v["rsi"] > v["rsi_prev"])} <span class="sub">from {v["rsi_prev"]:.0f}</span></td><td>{pill}</td>'
                       f'<td class="num">{nready or ""}</td></tr>')
        return (f'<div class="h1">Sectors · 30% of the move</div><div class="sub lead">Plan M only trades sectors that pass all four. '
                f'SPY heat tonight: {srsi:.0f}.</div>{sector_tiles()}<div class="card"><div class="wrap"><table class="tb"><thead><tr>'
                '<th>Sector</th><th>Breadth over its 10-day avg</th><th>Breadth, 3 months</th><th>Relative greed &gt; 1</th>'
                '<th>Heat under 70</th><th>Heat rising</th><th></th><th>Ready</th></tr></thead><tbody>' + "".join(trs)
                + '</tbody></table></div><div class="hint" style="margin-top:8px">Relative greed = the sector\'s average stock heat ÷ SPY\'s '
                  'heat (over 1 = greedier than the market, the same as "constituent heatmap &gt; SPY"). Black = breadth, orange = 5-day '
                  'average, blue = 10-day average.</div></div>')

    def page_heat():
        out = []
        for n in order:
            v = secs[n]
            st = sorted([r for r in rows if r["sec"] == n], key=lambda r: -r["rsi"])
            cells = "".join(f'<a class="sc{" pick" if not r["miss"] else ""}" data-r="{int(not r["miss"])}" data-u="{int(r["k"][3] == "1")}" '
                            f'href="https://www.tradingview.com/chart/?symbol={esc(r["t"])}" target="_blank" rel="noopener" '
                            f'style="background:{heat(r["rsi"], r["k"][3] == "1")}"><b>{esc(r["t"])}</b><span>{r["rsi"]:.0f}{" ▲" if r["k"][3] == "1" else " ▼"}</span></a>'
                            for r in st)
            ex = n in EXCLUDE
            out.append(f'<div class="sg"><div class="sgh">{hb(v["rsi"], v["rsi"] > v["rsi_prev"])}<b>{esc(n)}</b>'
                       f'<span class="pill {"p-n" if ex else "p-up" if v["ok"] else "p-dn"}">{"excluded" if ex else "passes" if v["ok"] else "fails"}</span>'
                       f'<span class="sub" style="margin-left:auto">{len(st)} stocks</span></div><div class="sgr">{cells}</div></div>')
        scale = (f'<span style="background:{GREEN}">30-70 and rising</span><span style="background:{YELLOW}">falling or under 30</span>'
                 f'<span style="background:{RED}">70+ overbought</span>')
        return (f'<div class="h1">Fear &amp; greed heatmap</div><div class="sub lead">Every stock\'s heat, sectors that pass first. '
                f'▲ = heat rising. Outlined = passes every Plan M rule. Tap a stock for its chart.</div>'
                f'<div class="card" id="hmap"><div class="mkt" style="margin-bottom:8px"><button class="chip on" data-h="all">All stocks</button>'
                f'<button class="chip" data-h="r">Ready only</button><button class="chip" data-h="u">Heat rising</button>'
                f'<span class="scale">{scale}</span></div>{"".join(out)}</div>')

    def page_stocks():
        trs = []
        for r in rows:
            a = r["atr"]
            tgt = 63 if r["rsi"] < 50 else r["rsi"] + (10 if r["rsi"] < 75 else 5)
            st = '<span class="pill p-up">Ready</span>' if not r["miss"] else f'<span class="pill p-w">{esc(", ".join(r["miss"][:2]))}</span>'
            trs.append(f'<tr data-n="{len(r["miss"])}" data-s="{esc(r["sec"])}"><td>{tk(r["t"])}<div class="sub">{esc(sn(r["sec"]))}</div></td>'
                       f'<td class="num">{r["close"]:.2f}</td><td>{hb(r["rsi"], r["k"][3] == "1")}</td>'
                       f'<td class="num">{"—" if r["age"] is None else "today" if r["age"] == 0 else str(r["age"]) + "d"}</td>'
                       + "".join(f'<td class="c">{dot(c)}</td>' for c in r["k"])
                       + (f'<td class="num">{a:.2f}</td><td class="num">{r["close"] - a / 2:.2f}</td><td class="num">{r["close"] - 2 * a:.2f}</td>'
                          f'<td class="num">{250 / a:.0f}</td>' if a else '<td class="num">—</td>' * 4)
                       + f'<td class="num">{tgt:.0f}</td><td class="num">{md(r["earn"]) if r["earn"] else "—"}</td><td>{st}</td></tr>')
        head = "".join(f'<th class="c" title="{esc(d)}">{n}</th>' for n, d in RULES)
        opts = "".join(f'<option value="{esc(n)}">{esc(n)}</option>' for n in sorted(secs))
        first = 0 if ready else 1
        chips = "".join(f'<button class="chip{" on" if k == first else ""}" data-f="{k}">{t}</button>'
                        for k, t in ((0, f"Ready {len(ready)}"), (1, f"1 rule away {len(one)}"), (2, "2 rules away"), (99, f"All {len(rows)}")))
        return (f'<div class="h1">Stocks · 30% of the move</div><div class="sub lead">Every stock with 1M+ shares a day against Plan M\'s '
                f'stock rules. All of them must pass before position sizing. Tap a ticker for its chart.</div><div class="card" id="stk">'
                f'<div class="mkt" style="margin-bottom:10px">{chips}<select id="ssec"><option value="">All sectors</option>{opts}</select></div>'
                f'<div class="wrap"><table class="tb"><thead><tr><th>Stock</th><th class="num">Close</th><th>Heat</th><th class="num">Signal</th>{head}'
                f'<th class="num">ATR</th><th class="num">½ ATR stop</th><th class="num">2 ATR exit</th><th class="num">Shares per $10k</th>'
                f'<th class="num">Heat target</th><th class="num">Earnings</th><th></th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>'
                f'<div class="hint" style="margin-top:8px">Position size from the deck: account × 5% ÷ (2 × ATR), shown per $10,000 (calls = shares ÷ 80). '
                f'Heat target from the deck: heat under 50 → 63; 50-75 → 10 points higher; 75+ → 5 points higher. Options per the deck: monthly, 30+ days out, '
                f'200+ open interest, spread under 10%, extrinsic under 30%, aim for the 80 delta, $35 max per option. '
                f'Earnings are looked up only for stocks within a rule or two of a setup (· = not checked).</div></div>')

    def page_etf():
        cards = []
        for k, e in etf.items():
            bar = ""
            if e.get("atr"):
                zlo, zhi = e["e20"], e["e20"] + 2 * e["atr"]
                span = (zhi - zlo) * 2
                lo = zlo - span / 4
                pos = lambda v: max(0, min(100, (v - lo) / span * 100))
                bar = (f'<div class="zone"><b style="left:{pos(zlo):.0f}%;width:{pos(zhi) - pos(zlo):.0f}%"></b><i style="left:{pos(e["close"]):.0f}%"></i></div>'
                       f'<div class="sub">Value zone {zlo:.2f}-{zhi:.2f} (20 EMA to 2 ATR above). {e["under"]} closed {e["close"]:.2f}.</div>')
            chk = "".join(f'<div class="chk">{okb(c["ok"])}<span>{esc(c["text"])}</span></div>' for c in e["checks"])
            sell = "".join(f'<div class="warn2">Sell signal: {esc(x)}</div>' for x in e.get("sell") or [])
            cards.append(f'<div class="card"><h3>{k} <span class="sub">on {e["under"]}\'s signals</span><span class="pill {"p-up" if e["ok"] else "p-dn"}" '
                         f'style="margin-left:auto">{"set up" if e["ok"] else "not set up"}</span></h3>{bar}{chk}{sell}</div>')
        return (f'<div class="h1">Plan ETF</div><div class="sub lead">When there\'s extra cash but no Plan M setups. Shares, not options, '
                f'with all available cash. Heat under 70 (rising or not), buy signal, uptrend, in the value zone, order blocks 30+ days old '
                f'more than 2% away.</div><div class="g2">{"".join(cards)}</div>'
                f'<div class="card" style="margin-top:14px"><h3>Exit signals</h3><div class="hint">QQQ or SPY sell signal · 10/20 bearish cross · '
                f'close more than 3 ATR above the 20 EMA · a 30-day+ order block hit. Then Plan #SICADFU: SGOV with all available cash, sold on '
                f'the month\'s last trading day and bought back on the first.</div></div>')

    def page_rules():
        sec = [("Market · 40%", ["SPY heat under 70 and rising", "SPY buy signal", "SPY 10/20/50 bullish trend",
                                 "Full-stocks breadth: bullish cross of its 10 EMA"]),
               ("Sector · 30%", ["Sector breadth: bullish cross of its 10 EMA", "Sector relative greed over 1", "Sector stocks' heat over SPY's",
                                 "Sector stocks' heat under 70 and rising", "Health Care permanently excluded",
                                 "OVTLYR channels M1S1 / M2 (private, not checked)"]),
               ("Stock · 30%", ["Heat any value and rising", "Buy signal, good for 5 trading days", "10/20/50 bullish trend",
                                "More than 2% from an order block, any age", "Price over the 10 EMA", "Price $10-$350",
                                "1M+ average daily volume", "4+ days to earnings", "Positive backtest (private, not checked)"]),
               ("Plan M exits", ["OVTLYR sell signal", "Sector breadth turns bearish", "SPY closes under its 20 EMA", "Earnings",
                                 "Hit / close in an order block", "120+ calendar days", "10/20 bearish cross (trailing)",
                                 "Gap & crap (5%+ gap up, then a close under the gap day's low on days 3-5)", "½ ATR stop, 2 ATR emergency exit",
                                 "Heat targets: 0-50 → 63, 50-75 → 10 points, 75+ → 5 points", "3 losers in one day = no new trades for a week"])]
        return (f'<div class="h1">The OVTLYR rules</div><div class="sub lead">Everything this screener checks, from the deck you shared. '
                f'Grey = can\'t be checked from public data. Exits are listed for reference; this page doesn\'t track trades.</div><div class="g2">'
                + "".join(f'<div class="card"><h3>{t}</h3>' + "".join(
                    f'<div class="chk">{"<i class=\"d du\">·</i>" if "not checked" in x else "<i class=\"d dy\">✓</i>"}<span>{esc(x)}</span></div>'
                    for x in xs) + '</div>' for t, xs in sec) + '</div>'
                + '<div class="hint" style="margin-top:12px">Stand-ins for OVTLYR\'s private data: heat = 14-day RSI; buy / sell signal = the 10 EMA '
                  'crossing over / under the 20; breadth = share of stocks with the 10 EMA over the 20, against its 10-day average.</div>')

    tabs = [("today", "Today", page_today), ("market", "Market", page_market), ("sectors", "Sectors", page_sectors),
            ("heat", "Heatmap", page_heat), ("stocks", "Stocks", page_stocks), ("etf", "Plan ETF", page_etf), ("rules", "Rules", page_rules)]
    nav = "".join(f'<a href="#{k}" data-t="{k}">{n}</a>' for k, n, _ in tabs)
    body = "".join(f'<section class="tab" id="p-{k}" hidden>{f()}</section>' for k, _, f in tabs)
    when = (f'Prices at {ov["live_at"]}' if ov.get("live_at") else f'Close of {dt.date.fromisoformat(ov["asof"]):%a %b} '
            f'{dt.date.fromisoformat(ov["asof"]).day}')
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OVTLYR screener</title><style>{CSS}</style></head><body><header><div class="hd"><span class="logo"><i></i>OVTLYR screener</span>
<nav class="sw" aria-label="Market"><a href="../">Stocks</a><a href="../crypto/">Crypto</a><a class="on" href="./" aria-current="page">OVTLYR</a></nav>
<span class="asof">{when}</span></div><nav class="tabs">{nav}</nav></header><main>{body}</main><script>{JS}</script></body></html>"""
    d = Path(out_dir) / "ovtlyr"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(doc, encoding="utf-8")
    return dict(ready=len(ready), one=len(one), rows=len(rows))


JS = """function show(t){if(!document.getElementById('p-'+t))t='today';document.querySelectorAll('section.tab').forEach(s=>s.hidden=s.id!=='p-'+t);
document.querySelectorAll('nav.tabs a').forEach(a=>a.classList.toggle('on',a.dataset.t===t));if(location.hash.slice(1)!==t)history.replaceState(null,'','#'+t)}
document.querySelectorAll('nav.tabs a').forEach(a=>a.onclick=e=>{e.preventDefault();show(a.dataset.t);scrollTo(0,0)});
document.querySelectorAll('[data-go]').forEach(a=>a.onclick=()=>{show(a.dataset.go);scrollTo(0,0)});show(location.hash.slice(1)||'today');
(function(){const box=document.getElementById('stk');if(!box)return;let lim=+(box.querySelector('.chip.on')||{dataset:{f:0}}).dataset.f;const sel=document.getElementById('ssec');
function draw(){box.querySelectorAll('tbody tr').forEach(tr=>tr.hidden=+tr.dataset.n>lim||(sel.value&&tr.dataset.s!==sel.value))}
box.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{lim=+b.dataset.f;box.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x===b));draw()});sel.onchange=draw;draw()})();
(function(){const box=document.getElementById('hmap');if(!box)return;box.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{const h=b.dataset.h;
box.querySelectorAll('.chip').forEach(x=>x.classList.toggle('on',x===b));box.querySelectorAll('.sc').forEach(c=>c.hidden=h==='r'?c.dataset.r!=='1':h==='u'?c.dataset.u!=='1':false);
box.querySelectorAll('.sg').forEach(g=>g.hidden=!g.querySelector('.sc:not([hidden])'))})})();"""

CSS = """:root{--bg:#f4f6f9;--card:#fff;--fg:#14202e;--mut:#6b7686;--line:#e4e8ee;--acc:#2f6fed;--up:#12936b;--upbg:#e5f6ef;--dn:#d6453d;--dnbg:#fdeceb;--warn:#c27a00;--warnbg:#fff4de}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
header{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.hd{max-width:1180px;margin:auto;padding:12px 20px 0;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.logo{font-weight:800;font-size:18px;letter-spacing:-.3px}.logo i{display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--acc);margin-right:7px}
.sw{display:inline-flex;background:var(--bg);border-radius:999px;padding:3px}.sw a{padding:4px 14px;border-radius:999px;font-weight:600;font-size:13px;color:var(--mut);text-decoration:none}.sw a.on{background:#fff;color:var(--fg);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.asof{margin-left:auto;color:var(--mut);font-size:12px}
nav.tabs{max-width:1180px;margin:auto;padding:0 20px;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
nav.tabs a{padding:12px 12px 10px;color:var(--mut);font-weight:600;text-decoration:none;border-bottom:2.5px solid transparent;white-space:nowrap}
nav.tabs a.on{color:var(--fg);border-color:var(--acc)}
main{max-width:1180px;margin:auto;padding:18px 20px 40px}section[hidden],[hidden]{display:none!important}
.h1{font-size:21px;font-weight:800;letter-spacing:-.3px;margin:2px 0 4px}.lead{margin-bottom:12px}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.step{background:var(--card);border-radius:14px;padding:16px 18px;box-shadow:0 1px 2px rgba(20,32,46,.06);border:1px solid var(--line)}
.step .n{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.step .big{font-size:20px;font-weight:800;letter-spacing:-.4px;margin:4px 0 2px;display:flex;align-items:center;gap:8px}
.go,[data-go]{color:var(--acc);font-weight:600;font-size:13px;cursor:pointer}
.sub{color:var(--mut);font-size:13px}.up{color:var(--up)}.dn{color:var(--dn)}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap}
.p-up{background:var(--upbg);color:var(--up)}.p-dn{background:var(--dnbg);color:var(--dn)}.p-w{background:var(--warnbg);color:var(--warn)}.p-n{background:rgba(0,0,0,.06);color:var(--mut)}
.card{background:var(--card);border-radius:14px;border:1px solid var(--line);box-shadow:0 1px 2px rgba(20,32,46,.06);padding:16px 18px}
.card h3{margin:0 0 6px;font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.card h3 a{margin-left:auto;font-size:12px}
.card .hint{color:var(--mut);font-size:12px;margin-bottom:10px}
.st{display:grid;grid-template-columns:62px 1fr 40px 110px;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--line)}.st:first-of-type{border-top:0}
.tk{font-weight:800;color:var(--acc);text-decoration:none}
.chk{display:flex;gap:8px;align-items:center;padding:4px 0;font-size:13px}
.d{display:inline-flex;width:18px;height:18px;border-radius:50%;align-items:center;justify-content:center;font-style:normal;font-size:10px;font-weight:800;flex:none}
.dy{background:var(--upbg);color:var(--up)}.dn{background:var(--dnbg);color:var(--dn)}.du{background:var(--bg);color:#9aa3af}
.hb{display:inline-block;min-width:28px;text-align:center;border-radius:6px;padding:1px 6px;font-weight:800;font-size:12px;color:#14202e}
.plans{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.pl{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 12px;opacity:.75}
.pl.on{opacity:1;border:2px solid var(--up);background:#f3fbf7}.pln{font-weight:800;margin-bottom:2px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.big2{font-size:26px;font-weight:800;margin:4px 0}.big2 small{font-size:13px;color:var(--mut);font-weight:600}
.tb{width:100%;border-collapse:collapse;font-size:13px}.tb th{font-size:11px;color:var(--mut);text-align:left;padding:6px;border-bottom:1px solid var(--line);white-space:nowrap}
.tb td{padding:7px 6px;border-bottom:1px solid var(--line);white-space:nowrap}.tb td.c,.tb th.c{text-align:center}.num{text-align:right;font-variant-numeric:tabular-nums}
.tb th.num{text-align:right}.tb tr.ex td{opacity:.55}.tb td.sp{width:130px}.wrap{overflow-x:auto}
.chip{display:inline-flex;padding:4px 10px;border-radius:999px;font:600 12px/1.4 inherit;background:var(--bg);border:0;color:var(--fg);cursor:pointer}.chip.on{background:var(--fg);color:#fff}
.mkt{display:flex;flex-wrap:wrap;gap:6px;align-items:center}select{font:inherit;font-size:12px;padding:3px 6px;border-radius:8px;border:1px solid var(--line);background:#fff}
.scale{margin-left:auto;display:flex;gap:2px;align-items:center}.scale span{font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;color:#14202e}
.sg{border-top:1px solid var(--line);padding:10px 0}.sgh{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.sgr{display:grid;grid-template-columns:repeat(auto-fill,minmax(66px,1fr));gap:4px}.sc{border-radius:7px;padding:4px 6px;display:flex;flex-direction:column;font-size:11px;color:#14202e;text-decoration:none}.sc b{font-size:12px}.sc.pick{outline:2.5px solid var(--fg);outline-offset:-2.5px}
.zone{position:relative;height:12px;background:var(--bg);border-radius:6px;margin:8px 0 4px}.zone b{position:absolute;top:0;bottom:0;background:#bfe8d6;border-radius:6px}.zone i{position:absolute;top:-4px;bottom:-4px;width:3px;background:var(--fg);border-radius:2px}
.warn2{color:var(--dn);font-weight:600;font-size:13px;margin-top:6px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.tile{border-radius:12px;padding:10px 12px;color:#14202e}.tile.ex{opacity:.6}
.tn{display:flex;justify-content:space-between;align-items:center;gap:6px}.tv{font-size:12px;font-weight:600;margin:2px 0 4px}
.tc{background:rgba(255,255,255,.72);border-radius:8px;padding:2px}.tf{font-size:11px;margin-top:4px;font-weight:600}
.leg{font-size:11px;color:var(--mut);font-weight:500;display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap}.card h3 .leg{margin-left:auto}.leg i{width:12px;height:3px;display:inline-block;border-radius:2px}
@media(max-width:1000px){.tiles{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.hd{padding:10px 16px 0}.asof{width:100%;margin:0}nav.tabs{padding:0 10px}main{padding:12px 12px 30px}
.steps,.plans,.g2{grid-template-columns:1fr;gap:10px}.step{padding:14px}.card{padding:14px}.st{grid-template-columns:54px 1fr 36px}.st .sub:last-child{display:none}.scale{display:none}}"""


if __name__ == "__main__":         # preview from a saved plan: python ovtlyr_page.py history/ovtlyr_<date>.json out_dir
    import sys
    print(build(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), sys.argv[2]))
