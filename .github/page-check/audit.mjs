// Deep audit of the live site: every ticker's chart data, table numbers vs raw data, and every control.
import { chromium } from "playwright";
import fs from "node:fs";
const URL = process.env.PAGE_URL + "?t=" + Date.now();
const out = []; const log = s => { console.log(s); out.push(s); };
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1400, height: 900 } });
const errs = []; p.on("pageerror", e => errs.push(e.message));
await p.goto(URL, { waitUntil: "networkidle" }); await p.waitForTimeout(1000);

// ---- 1. data files for every clickable ticker
const res = await p.evaluate(async () => {
  const tks = [...new Set([...document.querySelectorAll(".tk")].map(e => e.dataset.tk))];
  const rows = Object.fromEntries([...document.querySelectorAll("#t tbody tr")].map(r => {
    const v = [...r.cells].map(c => c.dataset.v); return [v[0], { close: +v[3], open: +v[4], d1: +v[5], d5: +v[6], m1: +v[7], contract: r.cells[18]?.textContent || "" }];
  }));
  const issues = [], stats = { tickers: tks.length, missingFile: [], missingTf: {}, numMismatch: [] };
  for (const tk of tks) {
    let D; try { const r = await fetch("data/" + encodeURIComponent(tk) + ".json"); if (!r.ok) throw r.status; D = await r.json(); }
    catch (e) { stats.missingFile.push(tk); continue; }
    for (const tf of ["4H", "D", "W", "M"]) {
      const s = D[tf]; if (!s) { (stats.missingTf[tf] ||= []).push(tk); continue; }
      const n = s.t.length;
      for (const k of ["o", "h", "l", "c", "v", "e10", "e20", "e50", "m150", "tr"]) if (s[k].length !== n) issues.push(`${tk} ${tf} ${k} length ${s[k].length}!=${n}`);
      for (let i = 0; i < n; i++) {
        if (i && !(s.t[i] > s.t[i - 1])) { issues.push(`${tk} ${tf} time not increasing at ${s.t[i - 1]} -> ${s.t[i]}`); break; }
        if ([s.o[i], s.h[i], s.l[i], s.c[i]].some(x => x == null)) { issues.push(`${tk} ${tf} null OHLC at ${s.t[i]}`); break; }
        if (s.h[i] + 0.011 < Math.max(s.o[i], s.c[i]) || s.l[i] - 0.011 > Math.min(s.o[i], s.c[i])) { issues.push(`${tk} ${tf} bad high/low at ${s.t[i]}`); break; }
      }
      // trend state recomputed from the published lines
      for (let i = 0; i < n; i++) {
        if (s.m150[i] == null) continue;
        const up = s.e10[i] > s.e20[i] && s.c[i] > s.e50[i] && s.c[i] > s.m150[i];
        const dn = s.e10[i] < s.e20[i] && s.c[i] < s.e50[i] && s.c[i] < s.m150[i];
        const want = up ? 1 : dn ? -1 : 0;
        if (want !== s.tr[i] && ![s.e10[i] - s.e20[i], s.c[i] - s.e50[i], s.c[i] - s.m150[i]].some(x => Math.abs(x) < 0.02)) { issues.push(`${tk} ${tf} trend ${s.tr[i]} != ${want} at ${s.t[i]}`); break; }
      }
      // order blocks [start, end, top, bottom, side, fresh]: inside the window, and each box ends where price first came back
      const at = new Map(s.t.map((t, i) => [t, i]));
      for (const z of s.ob || []) {
        const a = at.get(z[0]), e = at.get(z[1]), back = i => z[4] > 0 ? s.l[i] <= z[2] + 0.011 : s.h[i] >= z[3] - 0.011,
          clearlyIn = i => z[4] > 0 ? s.l[i] < z[2] - 0.011 : s.h[i] > z[3] + 0.011;   // published prices are rounded to cents
        if (a == null || e == null || e < a || !(z[2] >= z[3]) || Math.abs(z[4]) !== 1) { issues.push(`${tk} ${tf} bad order block ${JSON.stringify(z)}`); break; }
        if (z[5] ? e !== n - 1 : !back(e)) { issues.push(`${tk} ${tf} order block ends wrong ${JSON.stringify(z)}`); break; }
        let early = -1; for (let i = a + 6; i < e; i++) if (clearlyIn(i)) { early = i; break; }
        if (early >= 0) { issues.push(`${tk} ${tf} order block touched at ${s.t[early]} before its end ${JSON.stringify(z)}`); break; }
        stats.ob = (stats.ob || 0) + 1; if (z[5]) stats.obFresh = (stats.obFresh || 0) + 1;
      }
      if (tf === "D") (stats.dailyBars ||= []).push(n);
    }
    const r = rows[tk], s = D.D;
    if (r && s) {
      const n = s.c.length, pc = (a, b) => (a / b - 1) * 100;
      const chk = { close: [r.close, s.c[n - 1]], open: [r.open, s.o[n - 1]], d1: [r.d1, pc(s.c[n - 1], s.c[n - 2])], d5: [r.d5, pc(s.c[n - 1], s.c[n - 6])], m1: [r.m1, pc(s.c[n - 1], s.c[n - 22])] };
      for (const [k, [a, b2]] of Object.entries(chk)) { const tol = k === "close" || k === "open" ? 0.02 : 0.15; if (Math.abs(a - b2) > tol) stats.numMismatch.push(`${tk} ${k}: table ${a.toFixed(2)} vs data ${b2.toFixed(2)}`); }
    }
  }
  stats.withContract = Object.values(rows).filter(r => r.contract.trim()).length;
  stats.lastDates = Object.fromEntries(["D", "4H", "W", "M"].map(k => [k, null]));
  return { issues, stats };
});
log(`tickers with charts: ${res.stats.tickers}`);
log(`order block boxes: ${res.stats.ob || 0} (${res.stats.obFresh || 0} untouched)`);
{ const d = (res.stats.dailyBars || []).sort((a, b) => a - b); log(`daily bars per ticker: min ${d[0]}, median ${d[d.length >> 1]}, max ${d[d.length - 1]} (5 years is about 1,260)`); }
log(`missing data files: ${res.stats.missingFile.join(", ") || "none"}`);
for (const [tf, l] of Object.entries(res.stats.missingTf)) log(`missing ${tf}: ${l.length} (${l.slice(0, 15).join(", ")})`);
log(`data issues: ${res.issues.length}`); res.issues.slice(0, 40).forEach(i => log("  " + i));
log(`table vs data mismatches: ${res.stats.numMismatch.length}`); res.stats.numMismatch.slice(0, 40).forEach(i => log("  " + i));
log(`rows with an options contract: ${res.stats.withContract}`);

// ---- 1b. top picks lists against the chart data
const pk = await p.evaluate(async () => {
  const out = { issues: [], counts: {}, calls: {}, misses: {}, none: {} };
  const asof = (document.querySelector(".meta").textContent.match(/as of (\d{4}-\d{2}-\d{2})/) || [])[1];
  const v = (r, i) => r.cells[i].dataset.v;
  for (const id of ["pk-nu", "pk-bo", "pk-ai"]) {
    const rows = [...document.querySelectorAll(`#${id} tbody tr`)];
    out.counts[id] = rows.length;
    const head = [...document.querySelectorAll(`#${id} thead th`)].map(t => t.textContent), ci = h => head.indexOf(h);
    const [vo, v5, cc, dl, pm, oi, ea] = ["Volume", "5-day volume", "Call 15-30d", "Δ", "Premium", "OI", "Earnings"].map(ci);
    if (rows.length && [vo, v5, cc, dl, pm, oi].some(i => i < 0)) out.issues.push(`${id}: missing a volume or call column (${head.join(", ")})`);
    const secs = {};
    for (const r of rows) {
      const tk = v(r, 0); let D;
      try { const x = await fetch("data/" + encodeURIComponent(tk) + ".json"); if (!x.ok) throw x.status; D = await x.json(); }
      catch (e) { out.issues.push(`${id} ${tk}: no chart data`); continue; }
      const s = D.D, n = s.c.length, last = s.c[n - 1];
      const near = i => [s.e10[i] - s.e20[i], s.c[i] - s.e50[i], s.c[i] - s.m150[i]].some(x => Math.abs(x) < 0.05);
      // volume (shares) against the chart data, and the call against the rules: 15-30 days, delta 0.50-0.80, OI over 500;
      // a grey call (class miss) is the closest one when none fits, with each rule it misses in red
      if (vo >= 0 && v5 >= 0) {
        const off = (a, b) => a === "" || Math.abs(+a - b) > 0.02 * Math.max(1, b);
        const vol1 = s.v[n - 1], vol5 = s.v.slice(n - 5).reduce((a, b) => a + b, 0);
        if (off(v(r, vo), vol1)) out.issues.push(`${id} ${tk}: volume ${v(r, vo)} vs data ${vol1}`);
        if (off(v(r, v5), vol5)) out.issues.push(`${id} ${tk}: 5-day volume ${v(r, v5)} vs data ${vol5}`);
      }
      if (cc >= 0 && dl >= 0 && pm >= 0 && oi >= 0) {
        const exp = v(r, cc);
        if (exp) {
          const miss = !!r.cells[cc].querySelector(".miss");
          (miss ? out.misses : out.calls)[id] = ((miss ? out.misses : out.calls)[id] || 0) + 1;
          const days = +(r.cells[cc].querySelector(".dte")?.textContent.match(/\d+/) || [NaN])[0];
          const k = +((r.cells[cc].querySelector("span")?.textContent || "").match(/\$([\d.]+)/) || [])[1], d = +v(r, dl), o = v(r, oi);
          const daysOk = days >= 15 && days <= 30, oiOk = o === "" || +o > 500;
          if (!miss && !daysOk) out.issues.push(`${id} ${tk}: call ${days} days out`);
          if (!miss && !oiOk) out.issues.push(`${id} ${tk}: call open interest ${o}`);
          if (miss && daysOk && oiOk) out.issues.push(`${id} ${tk}: grey call ${days} days, OI ${o} fits the rules`);
          if (miss && (!!r.cells[cc].querySelector(".dte .warn") !== !daysOk || !!r.cells[oi].querySelector(".warn") !== !oiOk))
            out.issues.push(`${id} ${tk}: grey call red marks wrong (${days} days, OI ${o})`);
          if (!(exp > asof)) out.issues.push(`${id} ${tk}: call expires ${exp}, list is as of ${asof}`);
          if (!(d >= 0.5 && d <= 0.8)) out.issues.push(`${id} ${tk}: call delta ${d}`);
          if (!(+v(r, pm) > 0)) out.issues.push(`${id} ${tk}: premium ${v(r, pm)}`);
          if (!(k > 0.5 * last && k < 1.15 * last)) out.issues.push(`${id} ${tk}: strike ${k} vs close ${last}`);
          if (ea >= 0 && v(r, ea) !== "") {
            const toExp = (Date.parse(exp) - Date.parse(asof)) / 864e5, toE = +v(r, ea), flag = !!r.cells[cc].querySelector(".ef");
            if (flag !== (toE <= toExp)) out.issues.push(`${id} ${tk}: earnings flag ${flag} (earnings in ${toE} days, expiry in ${toExp})`);
          }
        } else out.none[id] = [...(out.none[id] || []), `${tk} (${r.cells[cc].textContent}: ${r.cells[cc].querySelector("[title]")?.title || ""})`];
      }
      if (id === "pk-nu") {
        if (Math.abs(+v(r, 1) - last) > 0.02) out.issues.push(`${id} ${tk}: close ${v(r, 1)} vs data ${last}`);
        if (!(s.tr[n - 1] === 1 && s.tr[n - 2] !== 1) && !near(n - 1) && !near(n - 2)) out.issues.push(`${id} ${tk}: not a new uptrend in the data (${s.tr[n - 2]} -> ${s.tr[n - 1]})`);
      } else if (id === "pk-bo") {
        const lvl = +v(r, 2), below = +v(r, 3), base = +v(r, 4), hi = Math.max(...s.h.slice(n - 50));
        if (Math.abs(+v(r, 1) - last) > 0.02) out.issues.push(`${id} ${tk}: close ${v(r, 1)} vs data ${last}`);
        if (Math.abs(lvl - hi) > 0.02) out.issues.push(`${id} ${tk}: breakout level ${lvl} vs 50-day high ${hi}`);
        if (Math.abs(below - (last / lvl - 1) * 100) > 0.15 || below < -5.05 || below > 0) out.issues.push(`${id} ${tk}: "below it" ${below}`);
        if (!(base >= 5)) out.issues.push(`${id} ${tk}: base ${base} days`);
        if (s.tr[n - 1] !== 1 && !near(n - 1)) out.issues.push(`${id} ${tk}: not in an uptrend`);
      } else {
        const sec = r.querySelector(".sec").textContent; secs[sec] = (secs[sec] || 0) + 1;
        if (v(r, 4) !== "" && Math.abs(+v(r, 4) - last) > 0.02) out.issues.push(`${id} ${tk}: now ${v(r, 4)} vs data ${last}`);
        if (v(r, 2) === asof && Math.abs(+v(r, 3) - last) > 0.02) out.issues.push(`${id} ${tk}: picked today at ${v(r, 3)} but closed ${last}`);
        if (v(r, 2) > asof) out.issues.push(`${id} ${tk}: picked in the future (${v(r, 2)})`);
      }
    }
    if (id === "pk-ai") {
      if (rows.length > 10) out.issues.push(`AI picks: ${rows.length} rows (max 10)`);
      for (const [k, c] of Object.entries(secs)) if (k && c > 3) out.issues.push(`AI picks: ${c} in ${k} (max 3)`);
      const ranks = rows.map(r => +v(r, 1)).filter(x => x);
      if (ranks.some(x => x > 20)) out.issues.push(`AI picks: a rank above 20 (${ranks.join(",")})`);
    }
  }
  return out;
});
log(`top picks: ${pk.counts["pk-nu"] || 0} new uptrends, ${pk.counts["pk-bo"] || 0} breakout watch, ${pk.counts["pk-ai"] || 0} AI picks; issues: ${pk.issues.length}`);
pk.issues.slice(0, 40).forEach(i => log("  " + i));
for (const id of ["pk-nu", "pk-bo", "pk-ai"]) {
  const no = pk.none[id] || [];
  log(`${id} calls that fit: ${pk.calls[id] || 0} of ${pk.counts[id] || 0}, closest shown in grey: ${pk.misses[id] || 0}` +
      (no.length ? `; none for ${no.slice(0, 12).join(", ")}` : ""));
}
for (const k of ["nu", "bo", "ai"]) {
  await p.click(`.bar.pk button[data-pk="${k}"]`);
  const shown = await p.$$eval(".pkl", d => d.filter(x => !x.hidden).map(x => x.dataset.pk).join(","));
  if (shown !== k) log(`top picks tab ${k}: shows "${shown}"`);
}
await p.click('.bar.pk button[data-pk="nu"]');

// ---- 2. controls
const vis = () => p.$$eval("#t tbody tr", r => r.filter(x => x.style.display !== "none").length);
for (const f of ["setups", "Momentum", "Pullback", "all"]) {
  await p.click(`.bar:not(.tf):not(.iv):not(.pk) button[data-f="${f}"]`);
  const n = await vis(); const bad = await p.$$eval("#t tbody tr", (r, f) => r.filter(x => x.style.display !== "none" && !(f === "all" || (f === "setups" ? x.dataset.setup !== "Uptrend" : x.dataset.setup === f))).length, f);
  log(`filter ${f}: ${n} rows, ${bad} wrong`);
}
const secs = await p.$$eval("#s tbody tr", r => r.map(x => x.dataset.sector));
for (const s of secs) {
  await p.evaluate(s => document.querySelector(`#s tbody tr[data-sector="${s}"]`).click(), s);
  const wrong = await p.$$eval("#t tbody tr", (r, s) => r.filter(x => x.style.display !== "none" && x.dataset.sector !== s).length, s);
  const n = await vis(); if (wrong) log(`sector ${s}: ${wrong} rows from other sectors`); else log(`sector ${s}: ${n} rows ok`);
  await p.evaluate(s => document.querySelector(`#s tbody tr[data-sector="${s}"]`).click(), s);
}
const cols = await p.$$eval("#t thead th", t => t.length);
let sortBad = 0;
for (let i = 2; i <= 13; i++) {
  await p.click(`#t thead th:nth-child(${i})`);
  const v = await p.$$eval(`#t tbody tr td:nth-child(${i})`, c => c.map(x => parseFloat(x.dataset.v)).filter(x => !isNaN(x)));
  if (v.some((x, j) => j && x < v[j - 1])) { sortBad++; log(`sort col ${i} not ascending`); }
}
log(`sorted ${cols} columns checked 2-13, ${sortBad} bad`);
for (const tf of ["D", "W", "M"]) await p.click(`.bar.tf button[data-tf="${tf}"]`);

// ---- 3. open every ticker's Trend chart on every timeframe
const tks = await p.$$eval(".tk", e => [...new Set(e.map(x => x.dataset.tk))]);
let opened = 0; const chartErr = [];
for (const tk of tks) {
  await p.evaluate(tk => document.querySelector(`.tk[data-tk="${tk}"]`).click(), tk);
  for (const iv of ["D", "D5Y", "240", "W", "M"]) {
    const before = errs.length;
    if (iv === "D5Y") await p.click('.bar.rng button[data-rng="5Y"]');
    else await p.click(`.bar.tfb button[data-iv="${iv}"]`);
    await p.waitForTimeout(250);
    if (iv === "D5Y") await p.click('.bar.rng button[data-rng="1Y"]');
    const lg = await p.$eval("#cmlg", e => e.textContent);
    if (!/trend|No trend/i.test(lg) || errs.length > before) chartErr.push(`${tk} ${iv}: "${lg.slice(0, 50)}" ${errs.slice(before).join(" | ")}`);
  }
  await p.keyboard.press("Escape"); opened++;
}
log(`opened ${opened} tickers x 4 timeframes (daily also at 5Y), problems: ${chartErr.length}`); chartErr.slice(0, 40).forEach(i => log("  " + i));
// ---- 4. paper trading: the accounts add up, every trade has its reasons, and the tiles and breakdown match the data
const paper = await p.evaluate(async () => {
  const SRC = "https://raw.githubusercontent.com/txcoproducts-lang/Swing-Screener-/paper-trading/paper/";
  const money = v => (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const lines = [];
  for (const id of ["A", "C", "B"]) {
    let a; try { a = await (await fetch(SRC + id + ".json?v=" + Date.now(), { cache: "no-store" })).json(); } catch (e) { lines.push(`${id}: could not load (${e})`); continue; }
    const bad = [], near = (x, y, tol = 0.05) => Math.abs(x - y) <= tol;
    const all = a.positions.concat(a.closed);
    const cash = a.start_cash - all.reduce((s, q) => s + q.buy.cost, 0) + a.closed.reduce((s, q) => s + q.sell.proceeds, 0);
    if (!near(cash, a.cash, 0.1)) bad.push(`cash ${a.cash} but the trades add up to ${cash.toFixed(2)}`);
    const v = a.cash + a.positions.reduce((s, q) => s + q.last.value, 0);
    if (a.mark && !near(v, a.mark.v)) bad.push(`value ${a.mark.v} but cash + positions = ${v.toFixed(2)}`);
    if (a.cash < -0.01) bad.push(`negative cash ${a.cash}`);
    for (const q of all) {
      if (!q.buy.why || !q.plan || !q.plan.text) bad.push(`${q.label}: no buy reason or plan`);
      if (q.kind === "call" && !(q.buy.dte >= 15 && q.buy.dte <= 30 && q.buy.delta >= 0.5 && q.buy.delta <= 0.8 && q.buy.oi > 500)) bad.push(`${q.label}: bought outside your rules (${q.buy.dte}d, delta ${q.buy.delta}, OI ${q.buy.oi})`);
      if (!a.log.some(e => e.kind === "buy" && e.t === q.buy.t && e.text.includes(q.ticker))) bad.push(`${q.label}: no log line for the buy`);
    }
    for (const q of a.closed) {
      if (!q.sell.why) bad.push(`${q.label}: no sell reason`);
      if (!near(q.pnl, q.sell.proceeds - q.buy.cost, 0.011)) bad.push(`${q.label}: P&L ${q.pnl} != ${(q.sell.proceeds - q.buy.cost).toFixed(2)}`);
      if (!a.log.some(e => e.kind === "sell" && e.t === q.sell.t && e.text.includes(q.ticker))) bad.push(`${q.label}: no log line for the sale`);
    }
    if (a.id !== "B" && a.positions.length > 2) bad.push(`${a.positions.length} positions, more than 2`);
    if (a.id === "C") for (const q of all) if (q.buy.t.slice(11, 16) < "15:00") bad.push(`${q.label}: bought at ${q.buy.t.slice(11, 16)} ET, before 2 PM Central`);
    if (a.equity.length && a.equity[0].v !== a.start_cash) bad.push(`chart starts at ${a.equity[0].v}`);
    for (let i = 1; i < a.equity.length; i++) if (!(a.equity[i].d > a.equity[i - 1].d)) bad.push(`chart dates out of order at ${a.equity[i].d}`);
    const tile = document.querySelector(`.pp-tile[data-acct="${id}"] .pp-val`);
    const want = money(a.mark ? a.mark.v : a.cash);
    if (!tile) bad.push("no tile on the page"); else if (tile.textContent !== want) bad.push(`tile shows ${tile.textContent}, data says ${want}`);
    if (tile) {
      tile.closest(".pp-tile").click();
      await new Promise(r => setTimeout(r, 300));
      const m = document.getElementById("pm");
      const np = m.querySelectorAll(".pm-pos").length, nc = m.querySelectorAll(".pm-trade").length;
      if (np !== a.positions.length || nc !== a.closed.length) bad.push(`breakdown shows ${np} open / ${nc} closed, data has ${a.positions.length} / ${a.closed.length}`);
      m.querySelector(".pm-x").click();
    }
    lines.push(`${id} ${a.name}: ${money(a.mark ? a.mark.v : a.cash)} (updated ${a.updated || "never"}), cash ${money(a.cash)}, ${a.positions.length} open, ` +
               `${a.closed.length} closed, ${a.log.length} log lines, ${a.equity.length} closes; problems: ${bad.length ? bad.join("; ") : "none"}`);
  }
  return lines;
});
paper.forEach(l => log("paper " + l));
log(`page errors overall: ${errs.length ? errs.slice(0, 10).join(" | ") : "none"}`);
await b.close();
fs.mkdirSync("shots", { recursive: true }); fs.writeFileSync("shots/audit.txt", out.join("\n") + "\n");
