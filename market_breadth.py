"""
Market breadth tab (user's ask, 2026-11-26), modeled on two OVTLYR screens: their "Full Stocks" chart (Bull List % with
its 20 and 50 EMAs, and the count of stocks in an uptrend vs a downtrend each day) and their "Market Breadth" table
(Trend, Alert, Breadth, OC, F&G, Constituent Heatmap and TS for the whole market, SPY, DIA, QQQ and the 11 sectors).

OVTLYR's formulas are private, so every number here is a stand-in rebuilt from the prices this screener already has.
OVTLYR's "price" line (a sum of every stock's price, meaningless to trade) is left out on purpose.

  Bull List %   = Rising, your breadth rule: the share of the group's stocks with the 10 EMA over the 20 and the close
                  over the 50 EMA. Same number as the rest of the page for SPY and the sectors (S&P 500 stocks only).
  Uptrend       = stocks with the 10 EMA over the 20 EMA (a looser test, so it's always more than the Bull List);
  Downtrend     = the rest.
  Signal on     = Bull List % above both its 20-day and 50-day EMAs (the green / red bars in the counts chart).
  OC            = two day-over-day checks, +1 / -1 each (0 on no change): Bull List % up, uptrend count up. -2..+2.
  TS            = OC plus two more: Bull List % above its 20 EMA, above its 50 EMA (+1 / -1 each). -4..+4.
  Trend         = your uptrend rule on the index / sector ETF itself (10 EMA > 20, close > 50 EMA and > the 150 line);
                  Bearish = the mirror; else Mixed.
  Alert         = the faster early warning on the ETF: close over the 10 EMA and the 5 EMA over the 10 (or both under).
  F&G           = the ETF's fear & greed, 0-100: the average of (a) where its distance from its 125-day average ranks in the
                  last year and (b) 100 minus where its 20-day volatility ranks in the last year (calm = greed).
  Heatmap       = the average 14-day RSI of the group's stocks (the OVTLYR page's heatmap stand-in), moving up / down vs
                  the close before.
"""
import json

import numpy as np
import pandas as pd

# The Dow Jones Industrial Average's 30 members (since NVDA and SHW joined in Nov 2024). The scan has no Dow list of
# its own, so this is fixed here; update it if the Dow changes.
DOW30 = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "JNJ",
         "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT"]
WARM = 60          # skip the first days while the EMAs warm up


def _sgn(s):
    return np.sign(s.fillna(0)).astype(int)


def group_series(rise, upm, R, cols):
    """One group's day-by-day numbers."""
    cols = [c for c in cols if c in rise.columns]
    n = rise[cols].notna().sum(axis=1)
    b = (rise[cols].mean(axis=1) * 100)
    u = (upm[cols] == 1).sum(axis=1)
    g = pd.DataFrame(dict(b=b, n=n, u=u, d=n - u, heat=R[cols].mean(axis=1)))
    g = g[g.n > 0]
    b1 = g.b.round(1)
    g["e20"], g["e50"] = g.b.ewm(span=20, adjust=False).mean(), g.b.ewm(span=50, adjust=False).mean()
    a10 = g.b.ewm(span=10, adjust=False).mean().round(1)
    g["on"] = pd.Series(np.where(b1 > a10, 1.0, np.where(b1 < a10, 0.0, np.nan)), index=g.index).ffill().fillna(0.0)   # rising = above its 10-day average (as the rest of the page)
    g["oc"] = _sgn(b1.diff()) + _sgn(g.u.diff())
    g["ts"] = g.oc + np.where(b1 > g.e20.round(1), 1, -1) + np.where(b1 > g.e50.round(1), 1, -1)
    g["sig"] = ((b1 > g.e20.round(1)) & (b1 > g.e50.round(1))).astype(int)
    return g.iloc[WARM:], len(cols)


def etf_state(S, d):
    """Trend, Alert and F&G for an index / sector ETF: the last two closes."""
    if d is None or len(d) < 260:
        return None
    c = d["Close"].astype(float)
    e = {n: S.ema(c, n) for n in (5, 10, 20, 50)}
    m150 = S.ema(c, 150) if S.CFG["LONG_MA_TYPE"] == "EMA" else c.rolling(150).mean()
    up = (e[10] > e[20]) & (c > e[50]) & (c > m150)
    dn = (e[10] < e[20]) & (c < e[50]) & (c < m150)
    aup, adn = (c > e[10]) & (e[5] > e[10]), (c < e[10]) & (e[5] < e[10])
    word = lambda u, x: "Bullish" if u else "Bearish" if x else "Mixed"
    mom = c / c.rolling(125).mean() - 1
    vol = c.pct_change().rolling(20).std()
    rank = lambda s: s.tail(260).rolling(252).apply(lambda x: (x <= x[-1]).mean() * 100, raw=True)
    fg = ((rank(mom) + (100 - rank(vol))) / 2).dropna()
    return dict(trend=word(up.iloc[-1], dn.iloc[-1]), alert=word(aup.iloc[-1], adn.iloc[-1]),
                fg=round(float(fg.iloc[-1]), 1) if len(fg) else None,
                fg0=round(float(fg.iloc[-2]), 1) if len(fg) > 1 else None, date=d.index[-1].date().isoformat())


def build(S, frames, sectors, sp500, ndx, etf_frames, market="stock"):
    """Everything the tab shows: the groups' day-by-day series (for the chart) and the table rows."""
    tks = list(frames)
    per = lambda f: pd.DataFrame({t: f(frames[t]["Close"]) for t in tks}).sort_index()
    C = per(lambda c: c)
    e10, e20, e50 = (per(lambda c, n=n: S.ema(c, n)) for n in (10, 20, 50))
    R = per(lambda c: S.rsi(c))
    ok = C.notna()
    rise = ((e10 > e20) & (C > e50)).astype(float).where(ok)
    upm = (e10 > e20).astype(float).where(ok)
    C.index = rise.index = upm.index = R.index = pd.DatetimeIndex([pd.Timestamp(i.strftime("%Y-%m-%d")) for i in C.index])

    sp = [t for t in tks if t in sp500]
    groups = [dict(n="All stocks", s="All stocks", k="m", tks=tks, etf=None,
                   sub="S&amp;P 500 + Nasdaq 100" if market == "stock" else "every coin in the scan"),
              dict(n="S&P 500", s="SPY", k="m", tks=sp, etf="SPY", sub="S&amp;P 500 stocks")]
    if market == "stock":
        groups += [dict(n="Dow 30", s="DIA", k="m", tks=[t for t in tks if t in DOW30], etf="DIA", sub="Dow 30 stocks"),
                   dict(n="Nasdaq 100", s="QQQ", k="m", tks=[t for t in tks if t in ndx], etf="QQQ", sub="Nasdaq 100 stocks")]
    secs = {}
    for t in sp:
        secs.setdefault(sectors.get(t) or "Other", []).append(t)
    for name in sorted(secs, key=lambda n: S.SHORT_SECTOR.get(n, n)):
        if name in S.SECTOR_ETF and name != "S&P 500" and len(secs[name]) >= 5:
            groups.append(dict(n=name, s=S.SHORT_SECTOR.get(name, name), k="s", tks=secs[name], etf=S.SECTOR_ETF[name], sub=""))

    ser = {}
    for g in groups:
        if len(g["tks"]) < 5:
            continue
        ser[g["n"]], g["cnt"] = group_series(rise, upm, R, g["tks"])
    groups = [g for g in groups if g["n"] in ser]
    idx = ser["All stocks"].index
    r1 = lambda v: [None if x != x else round(float(x), 1) for x in v]
    chart = dict(t=[d.strftime("%Y-%m-%d") for d in idx], g=[])
    rows = []
    for g in groups:
        s = ser[g["n"]].reindex(idx)
        chart["g"].append(dict(n=g["n"], s=g["s"], b=r1(s.b), e20=r1(s.e20), e50=r1(s.e50),
                               u=[None if x != x else int(x) for x in s.u], d=[None if x != x else int(x) for x in s.d],
                               sig="".join("1" if x == 1 else "0" for x in s.sig),
                               oc="".join(str(int(x) + 2) if x == x else "2" for x in s.oc),
                               ts="".join(str(int(x) + 4) if x == x else "4" for x in s.ts)))
        x, x0 = s.iloc[-1], s.iloc[-2]
        on = pd.Series(s.sig.to_numpy() == 1)
        k = int(np.flatnonzero(on.ne(on.shift()).to_numpy())[-1])
        rows.append(dict(n=g["n"], s=g["s"], k=g["k"], etf=g["etf"], sub=g["sub"], cnt=g["cnt"],
                         b=round(float(x.b), 1), on=bool(x.on), u=int(x.u), d=int(x.d), du=int(x.u - x0.u), dd=int(x.d - x0.d),
                         oc=int(x.oc), oc0=int(x0.oc), ts=int(x.ts), ts0=int(x0.ts),
                         heat=round(float(x.heat), 1), heat0=round(float(x0.heat), 1),
                         sig=bool(x.sig), sig_since=idx[k].date().isoformat(),
                         etfs=etf_state(S, (etf_frames or {}).get(g["etf"])) if g["etf"] else None))
    return dict(asof=idx[-1].date().isoformat(), prev=idx[-2].date().isoformat(), rows=rows, chart=chart)


# ------------------------------------------------------------------ page
def _wd(day):
    import datetime as dt
    d = dt.date.fromisoformat(day)
    return f"{d:%a %b} {d.day}"


def fg_word(v):
    return ("Extreme fear" if v < 25 else "Fear" if v < 45 else "Neutral" if v <= 55 else "Greed" if v <= 75 else "Extreme greed")


def breadth_word(S, v, on):
    if v > S.CFG["OB_BREADTH"]:
        return "Overbought"
    if v < S.CFG["OS_BREADTH"]:
        return "Bearish"
    if not on:
        return "Fading"
    return "Bullish" if v <= S.CFG["PRIME_BREADTH"] else "Bullish, stretched"


def html(S, mb, unit="stock"):
    """The tab's HTML (table + chart box) and its data for the page script."""
    D, P = _wd(mb["asof"]), _wd(mb["prev"])
    us = unit + "s"

    def sc(v):
        return f'<b class="{"up" if v > 0 else "dn" if v < 0 else "mut"}">{v:+d}</b>' if v else '<b class="mut">0</b>'

    def tw(w):
        return f'<span class="{"up" if w == "Bullish" else "dn" if w == "Bearish" else "mut"}">{w}</span>'

    def row(r):
        e = r["etfs"] or {}
        bc = S.bfill(r["b"], r["on"])
        cells = [
            f'<td><b>{S.html_esc(r["s"])}</b>' + (f' <span class="tk mut" data-tk="{r["etf"]}">{r["etf"]}</span>' if r["etf"] and r["etf"] != r["s"] else "")
            + (f'<div class="mut sm">{r["sub"]}</div>' if r["sub"] else "") + '</td>',
            f'<td><span class="rb" style="background:{bc}">{r["b"]:.1f}%</span> <span class="sm">{breadth_word(S, r["b"], r["on"])}</span>'
            f'<div class="mut sm">{"▲ above" if r["on"] else "▼ under"} its 10-day avg</div></td>',
            f'<td>{r["u"]:,} <span class="mut sm">{r["du"]:+,d}</span> / {r["d"]:,} <span class="mut sm">{r["dd"]:+,d}</span>'
            f'<div class="mut sm">of {r["cnt"]:,}</div></td>',
            f'<td>{"<b class=up>On</b>" if r["sig"] else "<b class=mut>Off</b>"}<div class="mut sm">since {S.md(r["sig_since"])}</div></td>',
            f'<td>{tw(e["trend"])}</td><td>{tw(e["alert"])}</td>' if e else '<td class="mut">–</td><td class="mut">–</td>',
            f'<td>{sc(r["oc0"])}</td><td>{sc(r["oc"])}</td><td>{sc(r["ts0"])}</td><td>{sc(r["ts"])}</td>',
        ]
        if e and e.get("fg") is not None:
            upf = e["fg0"] is None or e["fg"] >= e["fg0"]
            cells.append(f'<td><b class="{"up" if upf else "wn"}">{e["fg"]:.0f}</b> <span class="sm">{fg_word(e["fg"])}</span>'
                         f'<div class="mut sm">{"▲" if upf else "▼"} from {e["fg0"]:.0f}</div></td>' if e["fg0"] is not None else
                         f'<td><b>{e["fg"]:.0f}</b> <span class="sm">{fg_word(e["fg"])}</span></td>')
        else:
            cells.append('<td class="mut">–</td>')
        mv = r["heat"] >= r["heat0"]
        cells.append(f'<td><b>{r["heat"]:.1f}</b> <span class="{"up" if mv else "wn"} sm">{"Moving up" if mv else "Moving down"}</span>'
                     f'<div class="mut sm">from {r["heat0"]:.1f}</div></td>')
        return f'<tr data-g="{S.html_esc(r["n"])}">' + "".join(cells) + "</tr>"

    head = ("<th>{}</th><th>Breadth (Bull List %)</th><th>Uptrend / downtrend</th><th>Signal</th><th>Trend</th><th>Alert</th>"
            f"<th>OC {P}</th><th>OC {D}</th><th>TS {P}</th><th>TS {D}</th><th>F&amp;G</th><th>Constituent heatmap</th>")
    mk = [r for r in mb["rows"] if r["k"] == "m"]
    sx = [r for r in mb["rows"] if r["k"] == "s"]
    a = mb["rows"][0]
    summ = (f'<div class="mbs"><b>The {D} close (3:00 PM CT):</b> {a["b"]:.1f}% of all {a["cnt"]:,} {us} on the Bull List, '
            f'<span class="rb" style="background:{S.bfill(a["b"], a["on"])}">{breadth_word(S, a["b"], a["on"])}</span>. '
            f'{a["u"]:,} in an uptrend ({a["du"]:+,d} vs the {P} close), {a["d"]:,} in a downtrend ({a["dd"]:+,d}). '
            f'Signal {"<b class=up>on</b>" if a["sig"] else "<b class=dn>off</b>"} since {_wd(a["sig_since"])}. '
            f'OC {a["oc"]:+d}, TS {a["ts"]:+d}.</div>')
    table = ('<div class="wrap"><table id="mbt"><thead><tr>' + head.format("Market") + '</tr></thead><tbody>'
             + "".join(row(r) for r in mk) + '</tbody>'
             + ('<tbody><tr class="mbh">' + head.format("Sector").replace("<th>", "<td>").replace("</th>", "</td>") + '</tr>'
                + "".join(row(r) for r in sx) + '</tbody>' if sx else "") + '</table></div>')
    chart = ('<div class="bln" id="mbc"><div class="blh"><b>Bull List % and uptrend / downtrend counts</b>'
             '<select id="mbg" aria-label="Group">' + "".join(f'<option value="{i}">{S.html_esc(g["s"])}</option>'
                                                             for i, g in enumerate(mb["chart"]["g"]))
             + '</select><div class="bar blr">' + "".join(f'<button data-r="{k}"' + (' class="on"' if k == 63 else '') + f'>{lbl}</button>'
                                                        for lbl, k in (("3M", 63), ("6M", 126), ("1Y", 252), ("All", 0)))
             + '</div></div><div class="blk" id="mbk"></div><div class="mbc1"></div><div class="mbl">Uptrend ▲ / downtrend ▼ '
               f'{us}</div><div class="mbc2"></div></div>')
    hint = (f'<div class="hint">Stand-ins for OVTLYR\'s market breadth screens, rebuilt from this page\'s prices (their formulas are '
            f'private). Bull List % = Rising, your breadth rule (10 EMA over the 20, close over the 50 EMA). Uptrend = the 10 EMA '
            f'over the 20, downtrend = the rest. Tap a row to chart it. Open "How to read this" for what every column means.</div>')
    return ('<h2>Market breadth</h2>' + S.hk("mbreadth") + hint + summ + chart + table), mb["chart"]


CSS = (".mbs{background:var(--card);border-radius:10px;padding:9px 12px;margin:8px 0;font-size:14px;line-height:1.5}"
       ".mbs .rb,#mbt .rb{display:inline-block;border-radius:6px;padding:0 6px;color:#14202e;font-weight:700}"
       "#mbt td{vertical-align:middle;text-align:left}#mbt th{text-align:left}#mbt .sm{font-size:11.5px}#mbt tbody tr[data-g]{cursor:pointer}"
       "#mbt tr.mbh td{background:color-mix(in srgb,var(--acc) 6%,var(--card));color:var(--mut);font-weight:600;position:static}"
       "#mbt tr.mbh td:first-child{position:sticky;left:0}"
       "#mbt tr.sel td{background:color-mix(in srgb,var(--acc) 9%,var(--card))}"
       ".mbc1{height:230px}.mbc2{height:170px}.mbl{font-size:11px;color:var(--mut);margin:4px 0 0}"
       "@media(max-width:600px){.mbc1{height:200px}.mbc2{height:150px}}")

JS = r"""
(function(){const el=document.getElementById('mbc');if(!el||!MB)return;
const lg=document.getElementById('mbk'),sel=document.getElementById('mbg'),b1=el.querySelector('.mbc1'),b2=el.querySelector('.mbc2'),N=MB.t.length;
if(!window.LightweightCharts){b1.hidden=b2.hidden=true;lg.textContent='The chart could not load (chart library blocked).';return}
const cs=getComputedStyle(document.documentElement),V=n=>cs.getPropertyValue(n).trim();let g=0,span=63;
const opt=fmt=>({autoSize:true,localization:{locale:'en-US',priceFormatter:fmt},layout:{background:{color:'transparent'},textColor:V('--mut'),fontSize:11,attributionLogo:false},
grid:{vertLines:{visible:false},horzLines:{color:V('--line')}},rightPriceScale:{borderVisible:false,minimumWidth:56,scaleMargins:{top:0.08,bottom:0.08}},
timeScale:{borderVisible:false,lockVisibleTimeRangeOnResize:true},crosshair:{horzLine:{visible:false,labelVisible:false}},handleScroll:false,handleScale:false});
const c1=LightweightCharts.createChart(b1,opt(v=>+v.toFixed(1)+'%')),c2=LightweightCharts.createChart(b2,opt(v=>Math.abs(Math.round(v)).toLocaleString('en-US')));
const L=(c,col,w)=>c.addLineSeries({color:col,lineWidth:w||2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerRadius:3});
const s50=L(c1,'#e0a020'),s20=L(c1,'#e8762b'),sb=L(c1,V('--up'),2.5);
[[OSL,V('--dn'),'oversold'],[50,V('--mut'),''],[PRL,V('--mut'),''],[OBL,V('--dn'),'overbought']].forEach(([p,col,t])=>sb.createPriceLine({price:p,color:col,lineWidth:1,lineStyle:2,axisLabelVisible:!!t,title:t}));
sb.applyOptions({autoscaleInfoProvider:o=>{const r=o();if(!r||!r.priceRange)return r;r.priceRange.minValue=Math.min(r.priceRange.minValue,0);r.priceRange.maxValue=Math.max(r.priceRange.maxValue,OBL+5);return r}});
const hu=c2.addHistogramSeries({priceLineVisible:false,lastValueVisible:false,base:0}),hd=c2.addHistogramSeries({priceLineVisible:false,lastValueVisible:false,base:0});
const au=L(c2,'#7b3fe4',2),ad=L(c2,'#7b3fe4',2);
const ema=(a,n)=>{const k=2/(n+1);let p=null;return a.map(v=>v==null?null:(p=p==null?v:v*k+p*(1-k)))};
const DAY=t=>new Date(t+'T12:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'});
const sg=v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toLocaleString('en-US'),cl=v=>v>0?'up':v<0?'dn':'mut';
function leg(i){const G=MB.g[g];if(i==null||i<0||i>=N)i=N-1;if(G.b[i]==null){lg.textContent='';return}
const oc=+G.oc[i]-2,ts=+G.ts[i]-4,du=i>0&&G.u[i-1]!=null?G.u[i]-G.u[i-1]:0,dd=i>0&&G.d[i-1]!=null?G.d[i]-G.d[i-1]:0,on=G.sig[i]==='1';
const it=(c,l,x)=>'<span class="li"><i class="lk" style="background:'+c+'"></i>'+l+' <b>'+(x==null?'–':x.toFixed(1)+'%')+'</b></span>';
lg.innerHTML='<div><span class="li"><b>'+DAY(MB.t[i])+' close</b></span>'+it(V('--up'),'Bull List',G.b[i])+it('#e8762b','20 EMA',G.e20[i])+it('#e0a020','50 EMA',G.e50[i])+'</div>'
+'<div><span class="li">▲ <b>'+G.u[i].toLocaleString('en-US')+'</b> up <span class="'+cl(du)+'">'+sg(du)+'</span></span><span class="li">▼ <b>'+G.d[i].toLocaleString('en-US')+'</b> down <span class="'+cl(-dd)+'">'+sg(dd)+'</span></span>'
+'<span class="li">OC <b class="'+cl(oc)+'">'+(oc>0?'+':'')+oc+'</b></span><span class="li">TS <b class="'+cl(ts)+'">'+(ts>0?'+':'')+ts+'</b></span>'
+'<span class="li">Signal <b class="'+(on?'up':'mut')+'">'+(on?'on':'off')+'</b></span></div>'}
let sync=false;
function fit(){[c1,c2].forEach(c=>{const ts=c.timeScale();if(!span||span>=N)ts.fitContent();else ts.setVisibleLogicalRange({from:N-span-0.5,to:N-0.5})})}
function show(){const G=MB.g[g],f=a=>MB.t.map((t,i)=>a[i]==null?{time:t}:{time:t,value:a[i]});
sb.setData(f(G.b));s20.setData(f(G.e20));s50.setData(f(G.e50));
const UPC=V('--up'),DNC=V('--dn'),G1='#9aa3b0',G2='#c9ced6';
hu.setData(MB.t.map((t,i)=>G.u[i]==null?{time:t}:{time:t,value:G.u[i],color:G.sig[i]==='1'?UPC:G1}));
hd.setData(MB.t.map((t,i)=>G.d[i]==null?{time:t}:{time:t,value:-G.d[i],color:G.sig[i]==='1'?DNC:G2}));
const eu=ema(G.u,10),ed=ema(G.d,10);au.setData(f(eu));ad.setData(f(ed.map(v=>v==null?null:-v)));
fit();requestAnimationFrame(()=>requestAnimationFrame(fit));leg(null);
document.querySelectorAll('#mbt tr[data-g]').forEach(r=>r.classList.toggle('sel',r.dataset.g===G.n))}
const save=()=>{try{localStorage.setItem('mb',JSON.stringify({n:MB.g[g].n,span}))}catch(e){}};
const btns=[...el.querySelectorAll('.blr button')],setSpan=k=>{span=k;btns.forEach(b=>b.classList.toggle('on',+b.dataset.r===k))};
function pick(n){const j=MB.g.findIndex(x=>x.n===n);if(j<0)return;g=j;sel.value=String(j);save();show()}
sel.onchange=()=>{g=+sel.value;save();show()};
btns.forEach(b=>b.onclick=()=>{setSpan(+b.dataset.r);save();fit()});
document.querySelectorAll('#mbt tr[data-g]').forEach(r=>r.addEventListener('click',e=>{if(e.target.closest('[data-tk]'))return;pick(r.dataset.g);el.scrollIntoView({behavior:'smooth',block:'start'})}));
[[c1,c2,hu,'u'],[c2,c1,sb,'b']].forEach(([a,b,s,k])=>{a.subscribeCrosshairMove(p=>{if(sync)return;sync=true;
if(p.point&&p.logical!=null){const i=Math.max(0,Math.min(N-1,Math.round(p.logical))),v=MB.g[g][k][i];if(v!=null)b.setCrosshairPosition(v,MB.t[i],s);leg(i)}else{b.clearCrosshairPosition();leg(null)}sync=false})});
[[b1,c1,sb,'b'],[b2,c2,hu,'u']].forEach(([box,c,s,k])=>box.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')return;
const l=c.timeScale().coordinateToLogical(e.clientX-box.getBoundingClientRect().left);if(l==null)return;const i=Math.max(0,Math.min(N-1,Math.round(l)));
if(MB.g[g].b[i]==null)return;c1.setCrosshairPosition(MB.g[g].b[i],MB.t[i],sb);c2.setCrosshairPosition(MB.g[g].u[i],MB.t[i],hu);leg(i)}));
document.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse'&&!el.contains(e.target)){c1.clearCrosshairPosition();c2.clearCrosshairPosition();leg(null)}});
try{const s=JSON.parse(localStorage.getItem('mb')||'null'),j=s?MB.g.findIndex(x=>x.n===s.n):-1;
if(j>=0){g=j;sel.value=String(j)}if(s&&btns.some(b=>+b.dataset.r===s.span))setSpan(s.span)}catch(e){}
show()})();
"""
