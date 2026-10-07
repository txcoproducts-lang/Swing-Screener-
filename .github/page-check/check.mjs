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
  // paper trading tiles and each account's breakdown
  await p.waitForSelector(".pp-tile", { timeout: 15000 }).catch(() => {});
  await p.evaluate(() => { const e = document.getElementById("pp"); if (e) window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 60); });
  log(`[${name}] paper tiles: ${(await p.$$eval(".pp-tile", ts => ts.map(t => t.innerText.replace(/\n/g, " | ")))).join(" || ") || "none: " + (await p.$eval("#pp", e => e.textContent).catch(() => "no section"))}`);
  await p.screenshot({ path: `${out}/${name}-0-paper.png` });
  for (const id of ["A", "C", "B", "D"]) {
    if (!(await p.$(`.pp-tile[data-acct="${id}"]`))) continue;
    await p.click(`.pp-tile[data-acct="${id}"]`); await p.waitForTimeout(400);
    log(`[${name}] paper ${id}: ${await p.$$eval("#pm .pm-cards .card", cs => cs.map(c => c.innerText.replace(/\n/g, " ")).join(" | "))}`);
    await p.screenshot({ path: `${out}/${name}-0-paper-${id}.png` });
    await p.$eval("#pm .pm-body", b => { const h = [...b.querySelectorAll("h3")][2]; if (h) b.scrollTop = h.offsetTop - 10; });
    await p.waitForTimeout(150);
    await p.screenshot({ path: `${out}/${name}-0-paper-${id}-log.png` });
    await p.keyboard.press("Escape"); await p.waitForTimeout(150);
  }
  for (const k of ["nu", "bo", "ai"]) {
    await p.click(`.bar.pk button[data-pk="${k}"]`); await p.waitForTimeout(300);
    await p.evaluate(() => { const e = document.querySelector(".bar.pk"); window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 40); });
    log(`[${name}] top picks ${k}: ${await p.$$eval(`.pkl[data-pk="${k}"] tbody tr`, r => r.length)} rows`);
    await p.screenshot({ path: `${out}/${name}-1-picks-${k}.png` });
  }
  // the OVTLYR plan's Plan M list (opened), the breadth heatmap, and the sector charts with their breadth strips
  const at = sel => p.evaluate(s => { const e = document.querySelector(s); if (e) window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 40); return !!e; }, sel);
  if (await p.$("#ovm")) {
    await p.evaluate(() => { document.getElementById("ovm").open = true; }); await at("#ovm"); await p.waitForTimeout(300);
    log(`[${name}] Plan M list: ${await p.$eval("#ovm summary", e => e.innerText.replace(/\n/g, " "))}`);
    await p.screenshot({ path: `${out}/${name}-1-planm.png` });
  }
  if (await at("#hm")) {
    await p.waitForTimeout(200);
    log(`[${name}] heatmap: ${await p.$$eval("#hm .hmr", rs => rs.map(r => r.innerText.replace(/\n/g, " ").trim()).filter(Boolean).join(" | "))}`);
    await p.screenshot({ path: `${out}/${name}-1-breadth.png` });
  }
  if (await at("#bln")) {
    await p.waitForTimeout(300);
    const line = async () => `${await p.$eval("#blg", e => e.options[e.selectedIndex].text)}: ${await p.$eval("#blk", e => e.innerText.replace(/\n/g, " | "))}`;
    log(`[${name}] breadth line: ${await line()}`);
    await p.screenshot({ path: `${out}/${name}-1-breadth-line.png` });
    const tech = await p.$$eval("#blg option", o => (o.find(x => x.text === "Technology") || {}).value);
    if (tech != null) {
      await p.selectOption("#blg", tech); await p.waitForTimeout(400);
      log(`[${name}] breadth line: ${await line()}`);
      await p.screenshot({ path: `${out}/${name}-1-breadth-line-tech.png` });
      await p.selectOption("#blg", "0"); await p.waitForTimeout(200);
    }
  }
  if (await at(".charts")) {
    await p.waitForTimeout(500);
    log(`[${name}] strips: ${await p.$$eval(".ch .bl", bs => bs.map(b => b.closest(".ch").dataset.sector + ": " + b.innerText).join(" | "))}`);
    await p.screenshot({ path: `${out}/${name}-1-sector-charts.png` });
  }
  await p.click('.bar.pk button[data-pk="nu"]');
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
