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
log(`missing data files: ${res.stats.missingFile.join(", ") || "none"}`);
for (const [tf, l] of Object.entries(res.stats.missingTf)) log(`missing ${tf}: ${l.length} (${l.slice(0, 15).join(", ")})`);
log(`data issues: ${res.issues.length}`); res.issues.slice(0, 40).forEach(i => log("  " + i));
log(`table vs data mismatches: ${res.stats.numMismatch.length}`); res.stats.numMismatch.slice(0, 40).forEach(i => log("  " + i));
log(`rows with an options contract: ${res.stats.withContract}`);

// ---- 2. controls
const vis = () => p.$$eval("#t tbody tr", r => r.filter(x => x.style.display !== "none").length);
for (const f of ["setups", "Momentum", "Pullback", "all"]) {
  await p.click(`.bar:not(.tf):not(.iv) button[data-f="${f}"]`);
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
  for (const iv of ["D", "240", "W", "M"]) {
    const before = errs.length;
    await p.click(`.bar.tfb button[data-iv="${iv}"]`); await p.waitForTimeout(250);
    const lg = await p.$eval("#cmlg", e => e.textContent);
    if (!/trend|No trend/i.test(lg) || errs.length > before) chartErr.push(`${tk} ${iv}: "${lg.slice(0, 50)}" ${errs.slice(before).join(" | ")}`);
  }
  await p.keyboard.press("Escape"); opened++;
}
log(`opened ${opened} tickers x 4 timeframes, problems: ${chartErr.length}`); chartErr.slice(0, 40).forEach(i => log("  " + i));
log(`page errors overall: ${errs.length ? errs.slice(0, 10).join(" | ") : "none"}`);
await b.close();
fs.mkdirSync("shots", { recursive: true }); fs.writeFileSync("shots/audit.txt", out.join("\n") + "\n");
