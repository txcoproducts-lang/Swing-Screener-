// Paper trading widgets. paper.py trades four $1,000 paper accounts on GitHub Actions and saves them on the
// paper-trading branch; this reads them from GitHub, draws a tile per account and opens the full breakdown
// (chart against SPY, open positions, closed trades with reasons, the daily log, the rules) on click.
// screener.py puts this file inside the page. Text from the accounts is only ever set with textContent.
(function () {
const SRC = 'https://raw.githubusercontent.com/txcoproducts-lang/Swing-Screener-/paper-trading/paper/';
const REPO = 'https://github.com/txcoproducts-lang/Swing-Screener-';
const IDS = ['A', 'C', 'B', 'D'];
const SUB = {A: 'Your screener setups and option rules', C: 'Your rules, buying only after 2 PM Central', B: 'My AI picks list, as shares',
  D: "OVTLYR's Plan M, Plan ETF and SGOV, as shares"};
const WHEN = {A: '10:00 AM New York time', C: '2:00 PM Central', B: '10:00 AM New York time', D: '10:00 AM New York time'};
const KIND = {buy: 'Bought', sell: 'Sold', close: 'Close', day: 'Decision', note: 'Note'};
const box = document.getElementById('pp');
if (!box) return;

document.head.appendChild(Object.assign(document.createElement('style'), {textContent: `
.pp{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:10px;margin:10px 0 18px}
.pp-tile{background:var(--card);border-radius:10px;padding:12px 14px;cursor:pointer;border:1px solid transparent;color:var(--fg)}
.pp-tile:hover,.pp-tile:focus-visible{border-color:var(--acc);outline:none}
.pp-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.pp-h b{font-size:15px}.pp-h span{font-size:12px}
.pp-val{font-size:28px;font-weight:700;margin-top:6px;font-variant-numeric:tabular-nums}
.pp-d{font-size:13px}.pp-d .up,.pp-d .dn{font-weight:600}
.pp-spark{display:block;width:100%;height:56px;margin:8px 0 6px}
.pp-line{fill:none;stroke:var(--acc);stroke-width:2;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.pp-base,.pm-start{stroke:var(--mut);stroke-width:1;stroke-dasharray:3 3;opacity:.7;vector-effect:non-scaling-stroke}
.pp-f{display:flex;justify-content:space-between;gap:8px;font-size:12px}.pp-more{color:var(--acc);font-weight:600;white-space:nowrap}
#pm{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:40;display:flex;align-items:center;justify-content:center}#pm[hidden]{display:none}
.pm-box{background:var(--bg);color:var(--fg);border-radius:12px;width:min(980px,96vw);max-height:92vh;display:flex;flex-direction:column;overflow:hidden}
.pm-top{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line)}.pm-top b{font-size:17px}.pm-top .sp{flex:1}
.pm-x{background:none;border:0;color:var(--fg);font-size:24px;line-height:1;cursor:pointer;padding:0 4px}
.pm-body{overflow-y:auto;padding:12px 14px 22px;overscroll-behavior:contain}
.pm-body h3{font-size:14px;margin:20px 0 6px}
.pm-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.pm-lg{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--mut);margin:12px 0 4px}
.pm-lg i{display:inline-block;width:16px;height:2px;vertical-align:middle;margin-right:6px}
.pm-chart{position:relative;min-height:60px}.pm-svg{display:block;max-width:100%;touch-action:pan-y}
.pm-grid{stroke:var(--line);stroke-width:1}.pm-ax{fill:var(--mut);font-size:11px}.pm-lab{fill:var(--fg);font-size:11px;font-weight:600;paint-order:stroke;stroke:var(--bg);stroke-width:4px;stroke-linejoin:round}.pm-lab.s{fill:var(--mut)}
.pm-acct{fill:none;stroke:var(--acc);stroke-width:2;stroke-linejoin:round}.pm-spy{fill:none;stroke:var(--mut);stroke-width:2;stroke-linejoin:round}
.pm-cross{stroke:var(--mut);stroke-width:1}
.pm-tip{position:absolute;top:4px;pointer-events:none;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.15);white-space:nowrap;line-height:1.5}
.pm-tip i{display:inline-block;width:10px;height:2px;vertical-align:middle;margin-right:5px}
.pm-tbl{margin-top:6px;font-size:12px}.pm-tbl summary{cursor:pointer;color:var(--acc)}.pm-tbl table td,.pm-tbl table th{padding:4px 8px}
.pm-pos,.pm-trade{border-top:1px solid var(--line);padding:9px 0}
.pm-row,.pm-trade summary{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px}.pm-row .sp,.pm-trade summary .sp{flex:1}
.pm-trade summary{cursor:pointer}.pm-trade summary::marker{color:var(--mut)}
.pm-why{font-size:12px;color:var(--mut);margin-top:4px;line-height:1.45}.pm-why b{color:var(--fg);font-weight:600}
.pm-none{color:var(--mut);font-size:13px;padding:4px 0}
.pm-dh{font-weight:600;font-size:13px;margin:12px 0 4px}
.pm-e{display:grid;grid-template-columns:64px 66px 1fr;gap:6px;font-size:12px;padding:3px 0;line-height:1.45}
.pm-t{color:var(--mut)}.pm-k{font-weight:600;color:var(--mut)}.k-buy .pm-k{color:var(--up)}.k-sell .pm-k{color:var(--dn)}
.pm-btn{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer;margin-top:6px}
.pm-rules{margin:4px 0;padding-left:20px;font-size:13px;line-height:1.5}.pm-rules li{margin-bottom:4px}
.pm-body .note a,.pm-src a{color:var(--acc)}
@media(max-width:600px){.pm-box{width:100vw;max-height:100dvh;height:100dvh;border-radius:0}.pm-top .mut{display:none}
.pm-e{grid-template-columns:auto 1fr}.pm-e>span:last-child{grid-column:1/-1}}`}));

// ---------------------------------------------------------------- helpers
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
function svg(tag, attrs, text) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
const num = (v, d = 2) => Math.abs(v).toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d});
const money = v => (v < 0 ? '-$' : '$') + num(v);
const smoney = v => (v < 0 ? '-$' : '+$') + num(v);
const pct = v => (v < 0 ? '-' : '+') + Math.abs(v).toFixed(1) + '%';
const day = d => new Date(d.slice(0, 10) + 'T12:00:00Z');
const md = d => day(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
const wd = d => day(d).toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC'});
const mdy = d => day(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
const tm = t => { const [h, m] = t.slice(11, 16).split(':').map(Number); return (h % 12 || 12) + ':' + String(m).padStart(2, '0') + (h < 12 ? ' AM' : ' PM'); };
const cls = v => v > 0.004 ? 'up' : v < -0.004 ? 'dn' : '';
const arrow = v => v > 0.004 ? '▲ ' : v < -0.004 ? '▼ ' : '';
const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

function tkr(t) {
  return el('span', {class: 'tk', 'data-tk': t, text: t, onclick: e => {
    e.preventDefault(); e.stopPropagation();
    if (typeof window.openChart === 'function') window.openChart(t);
  }});
}

function stats(a) {
  const v = a.mark ? a.mark.v : a.cash + a.positions.reduce((s, p) => s + p.last.value, 0);
  const s0 = a.equity.length ? a.equity[0].spy : null;
  const spyNow = a.mark && a.mark.spy;
  const real = a.closed.reduce((s, p) => s + p.pnl, 0);
  return {v, pnl: v - a.start_cash, ret: (v / a.start_cash - 1) * 100, spyRet: s0 && spyNow ? (spyNow / s0 - 1) * 100 : null,
          real, wins: a.closed.filter(p => p.pnl > 0).length};
}

// The account's value at each close, plus "now" while the market is open; SPY scaled to the same $1,000 start.
function series(a) {
  const pts = a.equity.map(e => ({d: e.d, v: e.v, s: e.spy}));
  if (a.mark && pts.length && a.mark.t.slice(0, 10) > pts[pts.length - 1].d)
    pts.push({d: a.mark.t.slice(0, 10), v: a.mark.v, s: a.mark.spy, now: a.mark.t});
  const s0 = pts.length ? pts[0].s : 1;
  pts.forEach(p => { p.spy = a.start_cash * p.s / s0; });
  return pts;
}

// ---------------------------------------------------------------- tiles
function spark(a) {
  const pts = series(a), W = 300, H = 56;
  const s = svg('svg', {class: 'pp-spark', viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none', 'aria-hidden': 'true'});
  if (pts.length < 2) { s.append(svg('line', {class: 'pp-base', x1: 0, x2: W, y1: H / 2, y2: H / 2})); return s; }
  const vs = pts.map(p => p.v).concat([a.start_cash]);
  const lo = Math.min(...vs), hi = Math.max(...vs), r = (hi - lo) || 1;
  const x = i => i * W / (pts.length - 1), y = v => H - 4 - (v - lo) / r * (H - 8);
  s.append(svg('line', {class: 'pp-base', x1: 0, x2: W, y1: y(a.start_cash), y2: y(a.start_cash)}));
  s.append(svg('polyline', {class: 'pp-line', points: pts.map((p, i) => x(i).toFixed(1) + ',' + y(p.v).toFixed(1)).join(' ')}));
  return s;
}

function tile(a) {
  const st = stats(a), started = a.equity.length > 0;
  const open = () => openAcct(a.id, t);
  const t = el('div', {class: 'pp-tile', role: 'button', tabindex: '0', 'data-acct': a.id, 'aria-label': a.name + ', open the full breakdown',
                       onclick: open, onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }},
    el('div', {class: 'pp-h'}, el('b', {text: a.name}),
       el('span', {class: 'mut', text: a.over ? 'Finished' : started && a.mark ? 'Updated ' + md(a.mark.t) + ', ' + tm(a.mark.t) + ' ET' : 'Not started yet'})),
    el('div', {class: 'mut', text: SUB[a.id] || ''}),
    el('div', {class: 'pp-val', text: money(st.v)}),
    started
      ? el('div', {class: 'pp-d'}, el('span', {class: cls(st.pnl), text: arrow(st.pnl) + smoney(st.pnl) + ' (' + pct(st.ret) + ')'}),
           ' since ' + md(a.start), st.spyRet != null ? el('span', {class: 'mut', text: ' · SPY ' + pct(st.spyRet)}) : null)
      : el('div', {class: 'pp-d mut', text: 'Starts ' + wd(a.start) + ' at about ' + (WHEN[a.id] || WHEN.A) + '.'}),
    spark(a),
    el('div', {class: 'pp-f mut'},
       el('span', {text: started ? plural(a.positions.length, 'open position') + ' · ' + plural(a.closed.length, 'closed trade') : 'Runs to ' + mdy(a.end)}),
       el('span', {class: 'pp-more', text: 'Full breakdown →'})));
  return t;
}

// ---------------------------------------------------------------- the breakdown
function niceTicks(lo, hi, n) {
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag, out = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}

function drawChart(wrap, a) {
  const pts = series(a);
  wrap.replaceChildren();
  if (pts.length < 2) { wrap.append(el('div', {class: 'pm-none', text: 'The chart starts after the first trading day.'})); return; }
  const W = Math.max(280, Math.floor(wrap.clientWidth)), H = W < 520 ? 200 : 250, m = {l: 54, r: 10, t: 14, b: 24};
  const vals = pts.flatMap(p => [p.v, p.spy]).concat([a.start_cash]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = Math.max((hi - lo) * 0.08, 5);
  const ticks = niceTicks(lo - pad, hi + pad, 4);
  lo = ticks[0]; hi = ticks[ticks.length - 1];
  const n = pts.length, iw = W - m.l - m.r;
  const X = i => m.l + i * iw / (n - 1), Y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
  const s = svg('svg', {class: 'pm-svg', width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': `${a.name}: ${money(pts[n - 1].v)} against ${money(pts[n - 1].spy)} for SPY from the same $1,000 start`});
  ticks.forEach(t => {
    s.append(svg('line', {class: 'pm-grid', x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t)}));
    s.append(svg('text', {class: 'pm-ax', x: m.l - 6, y: Y(t) + 4, 'text-anchor': 'end'}, '$' + t.toLocaleString('en-US')));
  });
  s.append(svg('line', {class: 'pm-start', x1: m.l, x2: W - m.r, y1: Y(a.start_cash), y2: Y(a.start_cash)}));
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 70))));
  for (let i = 0; i < n; i += every) {
    if (i && n - 1 - i < every / 2) continue;
    s.append(svg('text', {class: 'pm-ax', x: X(i), y: H - 6, 'text-anchor': i ? 'middle' : 'start'}, md(pts[i].d)));
  }
  s.append(svg('text', {class: 'pm-ax', x: X(n - 1), y: H - 6, 'text-anchor': 'end'}, pts[n - 1].now ? 'Now' : md(pts[n - 1].d)));
  const path = k => pts.map((p, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(p[k]).toFixed(1)).join('');
  s.append(svg('path', {class: 'pm-spy', d: path('spy')}));
  s.append(svg('path', {class: 'pm-acct', d: path('v')}));
  // direct labels at the right end, pushed apart when the lines end close together
  let ya = Y(pts[n - 1].v), ys = Y(pts[n - 1].spy);
  const up = ya <= ys;
  if (Math.abs(ya - ys) < 26) { const c = (ya + ys) / 2; ya = c + (up ? -8 : 18); ys = c + (up ? 18 : -8); } else { ya += up ? -8 : 16; ys += up ? 16 : -8; }
  ya = Math.min(Math.max(ya, m.t + 10), H - m.b - 4); ys = Math.min(Math.max(ys, m.t + 10), H - m.b - 4);
  s.append(svg('text', {class: 'pm-lab', x: W - m.r, y: ya, 'text-anchor': 'end'}, a.name + ' ' + money(pts[n - 1].v)));
  s.append(svg('text', {class: 'pm-lab s', x: W - m.r, y: ys, 'text-anchor': 'end'}, 'SPY ' + money(pts[n - 1].spy)));
  // crosshair and tooltip
  const cross = svg('line', {class: 'pm-cross', y1: m.t, y2: H - m.b, visibility: 'hidden'});
  const da = svg('circle', {r: 4, fill: cssVar('--acc'), stroke: cssVar('--bg'), 'stroke-width': 2, visibility: 'hidden'});
  const ds = svg('circle', {r: 4, fill: cssVar('--mut'), stroke: cssVar('--bg'), 'stroke-width': 2, visibility: 'hidden'});
  const hit = svg('rect', {x: m.l, y: 0, width: iw, height: H, fill: 'transparent'});
  s.append(cross, ds, da, hit);
  const tip = el('div', {class: 'pm-tip', hidden: true});
  const show = ev => {
    const r = s.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round((ev.clientX - r.left - m.l) / iw * (n - 1))));
    const p = pts[i], x = X(i);
    [cross, da, ds].forEach(e => e.setAttribute('visibility', 'visible'));
    cross.setAttribute('x1', x); cross.setAttribute('x2', x);
    da.setAttribute('cx', x); da.setAttribute('cy', Y(p.v)); ds.setAttribute('cx', x); ds.setAttribute('cy', Y(p.spy));
    tip.replaceChildren(el('b', {text: p.now ? 'Now (' + tm(p.now) + ' ET)' : i === 0 ? md(p.d) + ' close (start)' : md(p.d) + ' close'}),
      el('div', {}, el('i', {style: 'background:var(--acc)'}), a.name + ' ' + money(p.v) + ' (' + pct((p.v / a.start_cash - 1) * 100) + ')'),
      el('div', {}, el('i', {style: 'background:var(--mut)'}), 'SPY ' + money(p.spy) + ' (' + pct((p.spy / a.start_cash - 1) * 100) + ')'));
    tip.hidden = false;
    const tw = tip.offsetWidth;
    tip.style.left = Math.min(Math.max(0, x + (x > W / 2 ? -tw - 12 : 12)), W - tw) + 'px';
  };
  const hide = () => { [cross, da, ds].forEach(e => e.setAttribute('visibility', 'hidden')); tip.hidden = true; };
  hit.addEventListener('pointermove', show);
  hit.addEventListener('pointerdown', show);
  hit.addEventListener('pointerleave', hide);
  wrap.append(s, tip);
}

function chartBlock(a) {
  const wrap = el('div', {class: 'pm-chart'});
  const pts = series(a);
  const rows = pts.map((p, i) => el('tr', {},
    el('td', {text: p.now ? 'Now (' + tm(p.now) + ' ET)' : md(p.d) + (i ? '' : ' (start)')}),
    el('td', {text: money(p.v)}), el('td', {class: i ? cls(p.v - pts[i - 1].v) : '', text: i ? pct((p.v / pts[i - 1].v - 1) * 100) : ''}),
    el('td', {text: money(p.spy)})));
  const table = el('details', {class: 'pm-tbl'}, el('summary', {text: 'Show these numbers as a table'}),
    el('div', {class: 'wrap'}, el('table', {}, el('thead', {}, el('tr', {}, ['Close', a.name, 'Day', 'SPY from $1,000'].map(h => el('th', {text: h})))),
      el('tbody', {}, rows.reverse()))));
  return [pts.length < 2 ? null : el('div', {class: 'pm-lg'},
            el('span', {}, el('i', {style: 'background:var(--acc)'}), a.name),
            el('span', {}, el('i', {style: 'background:var(--mut)'}), 'SPY, if the same $1,000 had bought it'),
            el('span', {}, el('i', {style: 'background:none;border-top:1px dashed var(--mut)'}), '$1,000 start')),
          wrap, pts.length > 1 ? table : null];
}

function posCard(p) {
  const val = p.last.value, pnl = val - p.buy.cost, call = p.kind === 'call';
  const what = call ? p.label.slice(p.ticker.length + 1) + ' · ' + plural(p.qty, 'contract') : p.qty + ' shares';
  const now = call && p.last.bid != null ? ` (bid ${money(p.last.bid)} / ask ${money(p.last.ask)})` : '';
  return el('div', {class: 'pm-pos'},
    el('div', {class: 'pm-row'}, tkr(p.ticker), el('span', {text: what}), el('span', {class: 'sp'}),
       el('b', {class: cls(pnl), text: arrow(pnl) + smoney(pnl) + ' (' + pct(pnl / p.buy.cost * 100) + ')'})),
    el('div', {class: 'pm-why', text: `Bought ${md(p.buy.t)}, ${tm(p.buy.t)} ET at ${money(p.buy.price)} for ${money(p.buy.cost)}. ` +
       `Now ${money(p.last.price)}${now}, worth ${money(val)} (${md(p.last.t)}, ${tm(p.last.t)} ET).`}),
    el('div', {class: 'pm-why'}, el('b', {text: 'Plan: '}), p.plan.text),
    p.exit ? el('div', {class: 'pm-why'}, el('b', {text: 'Selling: '}), p.exit) : null,
    el('div', {class: 'pm-why'}, el('b', {text: 'Why I bought it: '}), p.buy.why));
}

function tradeRow(p) {
  const what = p.kind === 'call' ? p.label.slice(p.ticker.length + 1) + ' · ' + plural(p.qty, 'contract') : p.qty + ' shares';
  return el('details', {class: 'pm-trade'},
    el('summary', {}, tkr(p.ticker), el('span', {text: what}),
       el('span', {class: 'mut', text: `${md(p.buy.t)} to ${md(p.sell.t)}, ${plural(p.days, 'day')}`}), el('span', {class: 'sp'}),
       el('b', {class: cls(p.pnl), text: arrow(p.pnl) + smoney(p.pnl) + ' (' + pct(p.pnl_pct) + ')'})),
    el('div', {class: 'pm-why'}, el('b', {text: `Bought ${md(p.buy.t)}, ${tm(p.buy.t)} ET at ${money(p.buy.price)} for ${money(p.buy.cost)}. `}), p.buy.why),
    el('div', {class: 'pm-why'}, el('b', {text: `Sold ${md(p.sell.t)}, ${tm(p.sell.t)} ET at ${money(p.sell.price)} for ${money(p.sell.proceeds)}. `}), p.sell.why));
}

function logBlock(a) {
  const byDay = {};
  a.log.forEach(e => { (byDay[e.t.slice(0, 10)] = byDay[e.t.slice(0, 10)] || []).push(e); });
  const days = Object.keys(byDay).sort().reverse(), wrap = el('div', {});
  const show = k => {
    wrap.replaceChildren(...days.slice(0, k).map(d => el('div', {},
      el('div', {class: 'pm-dh', text: wd(d)}),
      byDay[d].map(e => el('div', {class: 'pm-e k-' + e.kind},
        el('span', {class: 'pm-t', text: tm(e.t)}), el('span', {class: 'pm-k', text: KIND[e.kind] || e.kind}), el('span', {text: e.text}))))));
    if (days.length > k) wrap.append(el('button', {class: 'pm-btn', text: 'Show ' + plural(days.length - k, 'older day'), onclick: () => show(k + 20)}));
  };
  show(10);
  return days.length ? wrap : el('div', {class: 'pm-none', text: 'Nothing yet. The first entries come with the first trades on ' + wd(a.start) + '.'});
}

function card(label, value, sub, c) {
  return el('div', {class: 'card'}, el('div', {class: 'lbl', text: label}), el('div', {class: 'val ' + (c || ''), text: value}), el('div', {class: 'sub', text: sub}));
}

let pm = null, opener = null, curId = null;
function openAcct(id, from) {
  const a = accts[id];
  if (!a) return;
  opener = from || null;
  curId = id;
  if (!pm) {
    pm = el('div', {id: 'pm', hidden: true, onclick: e => { if (e.target === pm) closeAcct(); }});
    document.body.append(pm);
  }
  const st = stats(a), started = a.equity.length > 0, inv = st.v - a.cash;
  const closed = a.closed.slice().sort((x, y) => (y.sell.t > x.sell.t) - (y.sell.t < x.sell.t));
  const chart = chartBlock(a);
  pm.replaceChildren(el('div', {class: 'pm-box', role: 'dialog', 'aria-modal': 'true', 'aria-label': a.name + ' paper account'},
    el('div', {class: 'pm-top'}, el('b', {text: a.name}), el('span', {class: 'mut', text: SUB[a.id] || ''}), el('span', {class: 'sp'}),
       el('button', {class: 'pm-x', 'aria-label': 'Close', text: '×', onclick: closeAcct})),
    el('div', {class: 'pm-body'},
      el('div', {class: 'hint', text: `Paper trading, $1,000 to start, ${mdy(a.start)} to ${mdy(a.end)}` +
         (a.mark ? `. Updated ${md(a.mark.t)}, ${tm(a.mark.t)} ET.` : '. Not started yet.')}),
      el('div', {class: 'pm-cards', style: 'margin-top:10px'},
        card('Value', money(st.v), started ? smoney(st.pnl) + ' since the start' : 'Starting cash'),
        card('Return', started ? pct(st.ret) : '0.0%', st.spyRet != null ? 'SPY ' + pct(st.spyRet) + ' over the same days' : 'SPY is measured from the same start', started ? cls(st.pnl) : ''),
        card('Cash', money(a.cash), plural(a.positions.length, 'open position') + (a.positions.length ? ' worth ' + money(inv) : '')),
        card('Closed trades', String(a.closed.length), a.closed.length ? `${st.wins} won, ${a.closed.length - st.wins} lost, ${smoney(st.real)} in all` : 'None yet')),
      chart,
      el('h3', {text: 'Open positions'}),
      a.positions.length ? a.positions.map(posCard) : el('div', {class: 'pm-none', text: started ? 'None right now, all cash.' : 'None yet.'}),
      el('h3', {text: 'Closed trades, newest first'}),
      closed.length ? closed.map(tradeRow) : el('div', {class: 'pm-none', text: 'None yet.'}),
      el('h3', {text: 'Daily log (New York time)'}), logBlock(a),
      el('h3', {text: 'How this account trades'}), el('ol', {class: 'pm-rules'}, a.rules.map(r => el('li', {text: r}))),
      el('div', {class: 'note', text: a.fills}),
      el('div', {class: 'note pm-src'}, 'Every update is saved as a commit: ',
        el('a', {href: REPO + '/commits/paper-trading', target: '_blank', rel: 'noopener', text: 'history'}), ' · ',
        el('a', {href: REPO + '/blob/paper-trading/paper/' + a.id + '.json', target: '_blank', rel: 'noopener', text: 'raw data'})))));
  pm.hidden = false;
  document.body.style.overflow = 'hidden';
  drawChart(chart[1], a);
  pm.querySelector('.pm-x').focus();
}
function closeAcct() {
  if (!pm || pm.hidden) return;
  pm.hidden = true;
  document.body.style.overflow = '';
  if (opener) opener.focus();
}
window.addEventListener('keydown', e => {      // capture: the chart pop-up closes first when it's on top
  const cm = document.getElementById('cm');
  if (e.key === 'Escape' && pm && !pm.hidden && (!cm || cm.hidden)) closeAcct();
}, true);
const cm = document.getElementById('cm');
if (cm) new MutationObserver(() => { if (cm.hidden && pm && !pm.hidden) document.body.style.overflow = 'hidden'; })
  .observe(cm, {attributes: true, attributeFilter: ['hidden']});
let resizeT = null;
window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(() => {
  const w = pm && !pm.hidden && pm.querySelector('.pm-chart');
  if (w && accts[curId]) drawChart(w, accts[curId]);
}, 150); });

// ---------------------------------------------------------------- loading
let accts = {};
function load() {
  const v = Math.floor(Date.now() / 60000);
  return Promise.allSettled(IDS.map(id => fetch(SRC + id + '.json?v=' + v, {cache: 'no-store'}).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })))
    .then(res => {
      const list = res.filter(r => r.status === 'fulfilled').map(r => r.value);   // an account that fails to load is skipped
      if (!list.length) {
        if (!Object.keys(accts).length) box.replaceChildren(el('div', {class: 'hint', text: 'The paper trading accounts could not be loaded right now. Try again in a few minutes.'}));
        return;
      }
      accts = {};
      list.forEach(a => { accts[a.id] = a; });
      box.replaceChildren(...list.map(tile));
    });
}
box.replaceChildren(el('div', {class: 'hint', text: 'Loading the paper trading accounts…'}));
load();
setInterval(() => { if (!document.hidden && (!pm || pm.hidden)) load(); }, 5 * 60 * 1000);
})();
