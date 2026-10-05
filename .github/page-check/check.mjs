// Opens the live Pages site in Chromium, clicks through the charts and saves screenshots + a report.
import { chromium } from "playwright";
import fs from "node:fs";
const URL = process.env.PAGE_URL + "?t=" + Date.now();
const out = "shots"; fs.mkdirSync(out, { recursive: true });
const report = [];
const log = (...a) => { const s = a.join(" "); console.log(s); report.push(s); };
const b = await chromium.launch();
for (const [name, vp] of [["desktop", { width: 1400, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, colorScheme: name === "desktop" ? "dark" : "light" });
  const errs = [];
  p.on("pageerror", e => errs.push("pageerror: " + e.message));
  p.on("console", m => m.type() === "error" && errs.push("console: " + m.text()));
  p.on("requestfailed", r => errs.push("failed: " + r.url().slice(0, 120) + " " + (r.failure()?.errorText || "")));
  await p.goto(URL, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  log(`[${name}] title=${await p.title()} rows=${await p.$$eval("#t tbody tr", r => r.length)} sectorCharts=${await p.$$eval(".ch canvas", c => c.length)}`);
  await p.screenshot({ path: `${out}/${name}-1-top.png` });
  await (await p.$("#t")).scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${out}/${name}-2-table.png` });
  const tk = await p.$eval("#t tbody tr:not([style*='none']) .tk", e => e.dataset.tk);
  await p.click("#t tbody tr:not([style*='none']) .tk");
  await p.waitForTimeout(2500);
  log(`[${name}] opened ${tk}: legend="${(await p.$eval("#cmlg", e => e.textContent)).slice(0, 60)}"`);
  await p.screenshot({ path: `${out}/${name}-3-trend-daily.png` });
  await p.click('.bar.rng button[data-rng="5Y"]'); await p.waitForTimeout(1500);
  log(`[${name}] daily 5Y: legend="${(await p.$eval("#cmlg", e => e.textContent)).slice(0, 60)}"`);
  await p.screenshot({ path: `${out}/${name}-3-trend-daily-5y.png` });
  await p.click('.bar.rng button[data-rng="1Y"]'); await p.waitForTimeout(800);
  for (const iv of ["240", "W", "M"]) {
    await p.click(`.bar.tfb button[data-iv="${iv}"]`); await p.waitForTimeout(1500);
    log(`[${name}] ${iv}: legend="${(await p.$eval("#cmlg", e => e.textContent)).slice(0, 60)}"`);
    await p.screenshot({ path: `${out}/${name}-4-trend-${iv}.png` });
  }
  await p.click('.bar.src button[data-src="tv"]'); await p.waitForTimeout(8000);
  log(`[${name}] tradingview iframe=${await p.$$eval("#cmc iframe", f => f.length)}`);
  await p.screenshot({ path: `${out}/${name}-5-indicators.png` });
  log(`[${name}] errors: ${errs.length ? "\n  " + errs.join("\n  ") : "none"}`);
  await p.close();
}
await b.close();
fs.writeFileSync(`${out}/report.txt`, report.join("\n") + "\n");
