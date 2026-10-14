// The Backtests tab: every backtest on one page. screener.py (and crypto/screener.py) put this file in the page with
// window.BTDATA: the four plans' 10-year backtests (research/plan_backtest.py, history/plan_backtests.json), the
// research tests behind the page's lists and signals, and where the paper accounts live. The paper trial's numbers
// are read from GitHub here, as the Paper trading tab does. Text is only ever set with textContent.
(function () {
const B = window.BTDATA, box = document.getElementById('btx');
if (!B || !box) return;
const IDS = ['A', 'C', 'B', 'D'];
const NAME = {A: 'Your system', C: 'Your system, after 2 PM', B: "Claude's picks", D: 'OVTLYR plan'};
const COL = {A: '#2f6fed', C: '#12936b', B: '#d6453d', D: '#8e44c9', bench: '#8a94a3'};
const BENCH = B.bench;

document.head.appendChild(Object.assign(document.createElement('style'), {textContent: `
.bx-kps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 4px}
.bx-kp{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.bx-tag{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--mut)}
.bx-num{font-size:20px;font-weight:800;letter-spacing:-.3px;margin:2px 0}.bx-sub{font-size:12px;color:var(--mut)}
.bx-h3{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin:20px 0 8px}
.bx-card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 1px 2px rgba(20,32,46,.05)}
.bx-tb{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:4px}
.bx-seg{display:inline-flex;background:var(--bg);border-radius:999px;padding:3px;gap:2px}
.bx-seg button{border:0;background:none;padding:5px 12px;border-radius:999px;font-size:12px;font-weight:600;color:var(--mut);cursor:pointer}
.bx-seg button.on{background:var(--card);color:var(--fg);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.bx-lg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--mut);margin:4px 0}
.bx-lg i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.bx-chart{position:relative}.bx-svg{display:block;max-width:100%;touch-action:pan-y}
.bx-grid{stroke:var(--line);stroke-width:1}.bx-ax{fill:var(--mut);font-size:11px}.bx-cross{stroke:var(--mut);stroke-width:1}
.bx-tip{position:absolute;top:4px;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.15);white-space:nowrap;line-height:1.5;z-index:3}
.bx-tip i{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}
.bx-pg{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.bx-ph{display:flex;align-items:center;gap:8px;font-size:15px}.bx-ph b{font-weight:700}.bx-ph .bx-pill{margin-left:auto}
.bx-dot{width:10px;height:10px;border-radius:50%;flex:none}
.bx-pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap;background:var(--bg);color:var(--mut)}
.bx-pill.up{background:#e5f6ef;color:var(--up)}.bx-pill.dn{background:#fdeceb;color:var(--dn)}
.bx-rules{font-size:12px;color:var(--mut);margin:3px 0 8px;line-height:1.45}
.bx-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.bx-bh{font-weight:700;font-size:13px;margin:2px 0}
.bx-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;border-top:1px solid var(--line);margin-top:8px;padding-top:8px;font-size:12px;color:var(--mut)}
.bx-stats b{display:block;font-size:14px;color:var(--fg)}
.bx-more{margin-top:8px;font-size:13px}.bx-more summary{cursor:pointer;color:var(--acc);font-weight:600}
.bx-more table{border-collapse:collapse;width:100%;margin-top:6px;font-size:12px}.bx-more td,.bx-more th{padding:3px 6px;text-align:right;border-bottom:1px solid var(--line)}
.bx-more td:first-child,.bx-more th:first-child{text-align:left}.bx-more th{color:var(--mut);font-weight:600}
.bx-more .up{color:var(--up);font-weight:600}.bx-more .dn{color:var(--dn);font-weight:600}.bx-more p{color:var(--mut);font-size:12px;margin:6px 0}
.bx-none{display:flex;align-items:center;justify-content:center;min-height:120px;border:1px dashed var(--line);border-radius:10px;color:var(--mut);font-size:12px;text-align:center;padding:10px}
.bx-acc{border-bottom:1px solid var(--line);padding:11px 0}.bx-acc:last-child{border:0}
.bx-acc summary{display:flex;gap:4px 10px;align-items:center;cursor:pointer;flex-wrap:wrap}.bx-acc summary b{font-size:14px}.bx-acc summary .bx-pill{margin-left:auto}
.bx-acc .bx-txt{font-size:12px;color:var(--mut);margin:6px 0 8px;line-height:1.5}
.bx-bars{display:flex;flex-direction:column;gap:6px;max-width:640px}.bx-br{display:grid;grid-template-columns:170px 1fr 58px;gap:8px;align-items:center;font-size:12px}
.bx-br span:first-child{color:var(--mut)}.bx-bt{position:relative;height:12px;background:var(--bg);border-radius:6px}.bx-bt b{position:absolute;top:0;bottom:0;border-radius:6px}
.bx-bt i{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--line)}.bx-br .v{font-weight:700;text-align:right}
@media(max-width:760px){.bx-kps{grid-template-columns:1fr 1fr;gap:8px}.bx-num{font-size:17px}.bx-pg,.bx-two{grid-template-columns:1fr}
.bx-card{padding:12px}.bx-stats{grid-template-columns:1fr 1fr}.bx-acc summary .bx-pill{margin-left:0}.bx-br{grid-template-columns:110px 1fr 52px}}`}));

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
const money = v => (v < 0 ? '-$' : '$') + Math.abs(v).toLocaleString('en-US', {maximumFractionDigits: 0});
const pct = (v, d = 1) => v == null ? 'n/a' : (Math.abs(v) < 0.5 * Math.pow(10, -d) ? '' : v < 0 ? '-' : '+') + Math.abs(v).toFixed(d) + '%';
const day = d => new Date(d.slice(0, 10) + 'T12:00:00Z');
const md = d => day(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
const my = d => day(d).toLocaleDateString('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'});
const yr = d => "'" + d.slice(2, 4);
const mdy = d => day(d).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
function niceTicks(lo, hi, n) {
  const raw = (hi - lo) / n || 1, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag, out = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}
function legend(lines) {
  return el('div', {class: 'bx-lg'}, lines.map(l => el('span', {}, el('i', {style: 'background:' + l.color + (l.dash ? ';opacity:.6' : '')}), l.name)));
}

// A line chart: dates x, one or more lines ({name, color, dash, vals}), money or percent axis, hover for the values.
function lineChart(wrap, dates, lines, o) {
  o = Object.assign({money: true, base: 1000, h: 220, label: md}, o);
  const draw = () => {
    wrap.replaceChildren();
    const n = dates.length;
    if (n < 2) { wrap.append(el('div', {class: 'bx-none', text: o.empty || 'Not enough days yet for a chart.'})); return; }
    const W = Math.max(260, Math.floor(wrap.clientWidth || 300)), H = W < 420 ? Math.min(o.h, 190) : o.h, m = {l: o.money ? 56 : 48, r: 10, t: 10, b: 22};
    const vals = lines.flatMap(l => l.vals).filter(v => v != null).concat(o.base != null ? [o.base] : []);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.06, o.money ? 5 : 1);
    const ticks = niceTicks(o.money && lo >= 0 ? Math.max(0, lo - pad) : lo - pad, hi + pad, 4);
    lo = ticks[0]; hi = ticks[ticks.length - 1];
    const iw = W - m.l - m.r, X = i => m.l + i * iw / (n - 1), Y = v => m.t + (hi - v) / (hi - lo) * (H - m.t - m.b);
    const fmt = v => o.money ? '$' + v.toLocaleString('en-US') : (v > 0 ? '+' : '') + v.toLocaleString('en-US') + '%';
    const s = svg('svg', {class: 'bx-svg', width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || lines.map(l => l.name).join(', ')});
    ticks.forEach(t => {
      s.append(svg('line', {class: 'bx-grid', x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t)}));
      s.append(svg('text', {class: 'bx-ax', x: m.l - 6, y: Y(t) + 4, 'text-anchor': 'end'}, fmt(t)));
    });
    if (o.base != null) s.append(svg('line', {x1: m.l, x2: W - m.r, y1: Y(o.base), y2: Y(o.base), stroke: '#c9d0da', 'stroke-dasharray': '3 3'}));
    const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 64))));
    let prev = o.label(dates[n - 1]);
    for (let i = 0, last = null; i < n; i += every) {
      const t = o.label(dates[i]);
      if ((i && n - 1 - i < every * 0.6) || t === last || t === prev) continue;
      s.append(svg('text', {class: 'bx-ax', x: X(i), y: H - 5, 'text-anchor': i ? 'middle' : 'start'}, t));
      last = t;
    }
    s.append(svg('text', {class: 'bx-ax', x: X(n - 1), y: H - 5, 'text-anchor': 'end'}, o.label(dates[n - 1])));
    lines.forEach(l => {
      const segs = [];
      let cur = '';
      l.vals.forEach((v, i) => { if (v == null) { if (cur) segs.push(cur); cur = ''; } else cur += (cur ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1); });
      if (cur) segs.push(cur);
      s.append(svg('path', {d: segs.join(''), fill: 'none', stroke: l.color, 'stroke-width': l.dash ? 1.6 : 2.2, 'stroke-linejoin': 'round',
        'stroke-dasharray': l.dash ? '5 4' : 'none'}));
    });
    const cross = svg('line', {class: 'bx-cross', y1: m.t, y2: H - m.b, visibility: 'hidden'});
    const dots = lines.map(l => svg('circle', {r: 3.5, fill: l.color, stroke: '#fff', 'stroke-width': 1.5, visibility: 'hidden'}));
    const hit = svg('rect', {x: m.l, y: 0, width: iw, height: H, fill: 'transparent'});
    s.append(cross, ...dots, hit);
    const tip = el('div', {class: 'bx-tip', hidden: true});
    const show = ev => {
      const r = s.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round((ev.clientX - r.left - m.l) / iw * (n - 1))));
      const x = X(i);
      cross.setAttribute('visibility', 'visible'); cross.setAttribute('x1', x); cross.setAttribute('x2', x);
      tip.replaceChildren(el('b', {text: mdy(dates[i])}));
      lines.forEach((l, k) => {
        const v = l.vals[i];
        dots[k].setAttribute('visibility', v == null ? 'hidden' : 'visible');
        if (v == null) return;
        dots[k].setAttribute('cx', x); dots[k].setAttribute('cy', Y(v));
        tip.append(el('div', {}, el('i', {style: 'background:' + l.color}), l.name + ' ' + (o.money ? money(v) + ' (' + pct((v / 1000 - 1) * 100) + ')' : pct(v, 0))));
      });
      tip.hidden = false;
      const tw = tip.offsetWidth;
      tip.style.left = Math.min(Math.max(0, x + (x > W / 2 ? -tw - 12 : 12)), W - tw) + 'px';
    };
    const hide = () => { cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); tip.hidden = true; };
    hit.addEventListener('pointermove', show);
    hit.addEventListener('pointerdown', show);
    hit.addEventListener('pointerleave', hide);
    wrap.append(s, tip);
  };
  charts.set(wrap, draw);
  draw();
}
const charts = new Map();
let rt;
window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => charts.forEach(f => f()), 150); });
// the tab starts hidden (no width yet): redraw when it's opened
new MutationObserver(() => { if (!box.closest('section').hidden) charts.forEach(f => f()); })
  .observe(box.closest('section'), {attributes: true, attributeFilter: ['hidden']});

// ---------------------------------------------------------------- data
const plans = (B.plans && B.plans.plans) || {};
function trialSeries(a) {        // the paper account's closes (plus now), and the benchmark from the same $1,000
  const pts = a.equity.map(e => ({d: e.d, v: e.v, s: e.spy}));
  if (a.mark && pts.length && a.mark.t.slice(0, 10) > pts[pts.length - 1].d) pts.push({d: a.mark.t.slice(0, 10), v: a.mark.v, s: a.mark.spy});
  const s0 = pts.length ? pts[0].s : 1;
  pts.forEach(p => { p.b = a.start_cash * p.s / s0; });
  return pts;
}
function trialLines(accts) {     // every account on one date axis (accounts that start later begin at their start)
  const dates = [...new Set(IDS.flatMap(id => accts[id] ? trialSeries(accts[id]).map(p => p.d) : []))].sort();
  const lines = IDS.filter(id => accts[id]).map(id => {
    const m = new Map(trialSeries(accts[id]).map(p => [p.d, p.v]));
    return {id, name: NAME[id], color: COL[id], vals: dates.map(d => m.has(d) ? m.get(d) : null)};
  });
  const first = IDS.map(id => accts[id]).filter(Boolean).sort((a, b) => (a.equity[0] || {d: 'z'}).d < (b.equity[0] || {d: 'z'}).d ? -1 : 1)[0];
  if (first) {
    const m = new Map(trialSeries(first).map(p => [p.d, p.b]));
    lines.push({name: BENCH, color: COL.bench, dash: true, vals: dates.map(d => m.has(d) ? m.get(d) : null)});
  }
  return {dates, lines};
}
function btLines(ids) {
  const any = ids.map(id => plans[id]).find(Boolean);
  if (!any) return {dates: [], lines: []};
  const dates = any.curve.map(c => c[0]);
  const lines = ids.filter(id => plans[id]).map(id => ({id, name: NAME[id], color: COL[id], vals: plans[id].curve.map(c => c[1])}));
  lines.push({name: BENCH, color: COL.bench, dash: true, vals: any.curve.map(c => c[2])});
  return {dates, lines};
}
const trialVal = a => a.mark ? a.mark.v : a.equity.length ? a.equity[a.equity.length - 1].v : a.start_cash;

// ---------------------------------------------------------------- the page
function render(accts) {
  charts.clear();
  const have = IDS.filter(id => accts[id]);
  const ranked = IDS.slice().sort((a, b) => (accts[b] ? trialVal(accts[b]) : -1) - (accts[a] ? trialVal(accts[a]) : -1));
  const lead = ranked.find(id => accts[id]);
  const tested = IDS.filter(id => plans[id]);
  const beat = tested.filter(id => plans[id].final > plans[id].bench_final);
  const anyA = have.map(id => accts[id])[0];
  const dayN = anyA ? Math.max(0, anyA.equity.length - 1) : 0;
  const days = anyA ? Math.round((day(anyA.end) - day(anyA.start)) / 864e5 * (B.unit === 'coin' ? 1 : 252 / 365)) : 0;
  const benchRet = a => { const p = trialSeries(a); return p.length ? (p[p.length - 1].b / a.start_cash - 1) * 100 : 0; };
  const kp = (t, n, s) => el('div', {class: 'bx-kp'}, el('div', {class: 'bx-tag', text: t}), el('div', {class: 'bx-num', text: n}), el('div', {class: 'bx-sub', text: s}));
  const kps = el('div', {class: 'bx-kps'},
    kp('Backtests on this page', String(tested.length + B.research.length), `${tested.length} plans, ${B.research.length} research test${B.research.length === 1 ? '' : 's'}`),
    kp(`Plans that beat ${BENCH}`, tested.length ? `${beat.length} of ${tested.length}` : 'Not run yet',
       tested.length ? `over ${plans[tested[0]].years} years` + (beat.length ? ': ' + beat.map(id => NAME[id]).join(', ') : '') : 'The 10-year backtests are on their way'),
    kp('Paper trial', anyA ? `Day ${dayN} of ${days}` : '…', anyA ? `${mdy(anyA.start)} to ${mdy(anyA.end)}` : 'Loading the accounts'),
    kp('Leading the trial', lead ? NAME[lead] : '…', lead ? `${pct((trialVal(accts[lead]) / 1000 - 1) * 100)} vs ${BENCH} ${pct(benchRet(accts[lead]))}` : ''));

  // all four plans on one graph, paper trial or backtest
  const head = el('div', {class: 'bx-num'});
  const sub = el('div', {class: 'bx-sub'});
  const lg = el('div');
  const wrap = el('div', {class: 'bx-chart'});
  const seg = el('div', {class: 'bx-seg'});
  const show = mode => {
    seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === mode));
    const {dates, lines} = mode === 'trial' ? trialLines(accts) : btLines(IDS);
    const ends = lines.filter(l => l.id).map(l => [l, [...l.vals].reverse().find(v => v != null)]).sort((a, b) => b[1] - a[1]);
    head.textContent = ends.length ? `${ends[0][0].name} leads at ${money(ends[0][1])}` : mode === 'trial' ? 'Loading the paper accounts…' : 'The 10-year backtests are on their way';
    sub.textContent = mode === 'trial' ? `The paper accounts, $1,000 each, against ${BENCH} from the same start` :
      tested.length ? `$1,000 in each plan from ${mdy(plans[tested[0]].start)} to ${mdy(plans[tested[0]].end)}, against holding ${BENCH}` : '';
    lg.replaceChildren(legend(lines));
    lineChart(wrap, dates, lines, {h: 260, label: mode === 'trial' ? md : yr, empty: mode === 'trial' ? 'The chart starts after the first trading day.' : 'Not run yet.'});
    cards.forEach(f => f());
  };
  seg.append(el('button', {'data-m': 'trial', text: 'Paper trial', onclick: () => show('trial')}),
             el('button', {'data-m': 'bt', text: '10-year backtest', onclick: () => show('bt')}));
  const board = el('div', {class: 'bx-card'}, el('div', {class: 'bx-tb'}, el('div', {}, el('div', {class: 'bx-tag', text: 'All four plans, $1,000 each'}), head, sub), seg), lg, wrap);

  // a card per plan: its backtest and its paper trial, best trial first
  const cards = [];
  const planCards = ranked.map(id => {
    const p = plans[id], a = accts[id];
    const pill = !p ? el('span', {class: 'bx-pill', text: 'Not run yet'}) :
      el('span', {class: 'bx-pill ' + (p.final > p.bench_final ? 'up' : 'dn'), text: p.final > p.bench_final ? `Beat ${BENCH}` : `Trailed ${BENCH}`});
    const btw = el('div', {class: 'bx-chart'}), trw = el('div', {class: 'bx-chart'});
    const btHead = p ? `${money(p.final)} · ${pct(p.cagr)} a year vs ${BENCH} ${pct(p.bench_cagr)}` : 'Not run yet';
    const tv = a ? trialVal(a) : null;
    const trHead = a ? `${money(tv)} ${pct((tv / a.start_cash - 1) * 100)} vs ${BENCH} ${pct(benchRet(a))}` : 'Loading…';
    cards.push(() => {
      if (p) lineChart(btw, p.curve.map(c => c[0]), [{name: NAME[id], color: COL[id], vals: p.curve.map(c => c[1])},
        {name: BENCH, color: COL.bench, dash: true, vals: p.curve.map(c => c[2])}], {h: 180, label: yr});
      else btw.replaceChildren(el('div', {class: 'bx-none', text: 'The 10-year backtest is on its way.'}));
      if (a) { const t = trialSeries(a); lineChart(trw, t.map(x => x.d), [{name: NAME[id], color: COL[id], vals: t.map(x => x.v)},
        {name: BENCH, color: COL.bench, dash: true, vals: t.map(x => x.b)}], {h: 180}); }
    });
    const stat = (l, v) => el('div', {}, l, el('b', {text: v}));
    const more = p ? el('details', {class: 'bx-more'}, el('summary', {text: 'Full backtest'}),
      el('p', {text: p.rules}),
      el('table', {}, el('thead', {}, el('tr', {}, ['Year', NAME[id], BENCH].map(h => el('th', {text: h})))),
        el('tbody', {}, Object.entries(p.by_year).map(([y, v]) => el('tr', {}, el('td', {text: y === p.start.slice(0, 4) ? y + ' (from ' + md(p.start) + ')' : y === p.end.slice(0, 4) ? y + ' (to ' + md(p.end) + ')' : y}),
          el('td', {class: v[0] > v[1] ? 'up' : 'dn', text: pct(v[0])}), el('td', {text: pct(v[1])}))))),
      el('p', {text: `${p.trades} trades, ${p.win}% winners, average trade ${pct(p.avg_trade)} (median ${pct(p.median_trade)}). ` +
        `Green years beat ${BENCH}. Every fill 0.05% worse than the price; no other costs. Past results don't promise future ones.`})) : null;
    return el('div', {class: 'bx-card'},
      el('div', {class: 'bx-ph'}, el('span', {class: 'bx-dot', style: 'background:' + COL[id]}), el('b', {text: NAME[id]}), pill),
      el('div', {class: 'bx-rules', text: (p ? p.rules : a && a.rules ? a.rules[0] : '').split('. ')[0].replace(/\.$/, '') + '.'}),
      el('div', {class: 'bx-two'},
        el('div', {}, el('div', {class: 'bx-tag', text: p ? `Backtest ${p.start.slice(0, 4)}-${p.end.slice(0, 4)}` : 'Backtest'}), el('div', {class: 'bx-bh', text: btHead}), btw),
        el('div', {}, el('div', {class: 'bx-tag', text: a ? 'Paper trial since ' + md(a.start) : 'Paper trial'}), el('div', {class: 'bx-bh', text: trHead}), trw)),
      p ? el('div', {class: 'bx-stats'}, stat('Worst drop', pct(p.maxdd, 0)), stat(`${BENCH}'s worst`, pct(p.bench_maxdd, 0)),
        stat('Trades', p.trades.toLocaleString('en-US')), stat('In the market', p.invested + '% of the time')) : null,
      more);
  });

  // the research tests, folded
  const res = el('div', {class: 'bx-card', style: 'padding:2px 16px'}, B.research.map((r, i) => {
    const body = el('div');
    const d = el('details', {class: 'bx-acc', open: i === 0},
      el('summary', {}, el('b', {text: r.name}), el('span', {class: 'bx-sub', text: r.scope}), el('span', {class: 'bx-pill', text: r.verdict})),
      el('div', {class: 'bx-txt', text: r.text}), body);
    const fill = () => {
      if (r.bars) {
        const m = Math.max(...r.bars.map(b => Math.abs(b[1]))) || 1;
        body.replaceChildren(el('div', {class: 'bx-bars'}, r.bars.map(([l, v, c]) => el('div', {class: 'bx-br'}, el('span', {text: l}),
          el('span', {class: 'bx-bt'}, el('b', {style: (v >= 0 ? 'left:50%' : 'right:50%') + ';width:' + (Math.abs(v) / m * 48).toFixed(1) + '%;background:' + c}), el('i')),
          el('span', {class: 'v', style: 'color:' + c, text: (v > 0 && r.sign ? '+' : '') + v + (r.unit || '')})))));
      } else if (r.line) {
        lineChart(body, r.line.dates, r.line.lines, {h: 200, money: r.line.money !== false, base: r.line.money === false ? 0 : 1000, label: yr});
        body.prepend(legend(r.line.lines));
      }
    };
    fill();
    d.addEventListener('toggle', () => { if (d.open && r.line) fill(); });
    return d;
  }));

  box.replaceChildren(kps, el('div', {class: 'bx-h3', text: 'Plans side by side'}), board,
    el('div', {class: 'bx-h3', text: 'Each plan'}), el('div', {class: 'bx-pg'}, planCards),
    B.research.length ? el('div', {class: 'bx-h3', text: 'Research'}) : null, B.research.length ? res : null,
    el('div', {class: 'note', text: B.note || ''}));
  show(have.length ? 'trial' : 'bt');
}

render({});
const v = Math.floor(Date.now() / 60000);
Promise.allSettled(IDS.map(id => fetch(B.paperSrc + id + '.json?v=' + v, {cache: 'no-store'}).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })))
  .then(res => { const accts = {}; res.forEach(r => { if (r.status === 'fulfilled') accts[r.value.id] = r.value; }); render(accts); });
})();
