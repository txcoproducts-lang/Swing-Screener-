import { chromium } from "playwright";
import fs from "node:fs";
const V = {
  a_std_rsi_only: ["STD;RSI"],
  b_legacy_rsi_only: ["RSI@tv-basicstudies"],
  c_legacy_rsi_macd: ["RSI@tv-basicstudies", "MACD@tv-basicstudies"],
  d_full_legacy: [{id:"MAExp@tv-basicstudies",inputs:{length:10}},{id:"MAExp@tv-basicstudies",inputs:{length:20}},{id:"MAExp@tv-basicstudies",inputs:{length:50}},{id:"MASimple@tv-basicstudies",inputs:{length:200}},"RSI@tv-basicstudies","MACD@tv-basicstudies"],
  e_rsi_first: ["RSI@tv-basicstudies","MACD@tv-basicstudies",{id:"MAExp@tv-basicstudies",inputs:{length:10}},{id:"MAExp@tv-basicstudies",inputs:{length:20}},{id:"MAExp@tv-basicstudies",inputs:{length:50}},{id:"MASimple@tv-basicstudies",inputs:{length:200}}],
  f_std_all: ["STD;EMA","STD;RSI","STD;MACD"],
};
fs.mkdirSync("shots", { recursive: true });
const b = await chromium.launch();
const out = [];
for (const [k, st] of Object.entries(V)) {
  const p = await b.newPage({ viewport: { width: 1200, height: 800 } });
  const errs = []; p.on("pageerror", e => errs.push(e.message));
  // load the live site so the widget sees the real origin, then replace the body with a bare widget
  await p.goto(process.env.PAGE_URL, { waitUntil: "domcontentloaded" });
  await p.evaluate(st => { document.body.innerHTML = '<div id="w" style="height:780px"></div>';
    const s = document.createElement("script"); s.src = "https://s3.tradingview.com/tv.js";
    s.onload = () => new TradingView.widget({ container_id: "w", autosize: true, symbol: "NVDA", interval: "D", theme: "dark", locale: "en", studies: st });
    document.head.appendChild(s); }, st);
  await p.waitForTimeout(9000);
  await p.screenshot({ path: `shots/probe-${k}.png` });
  out.push(`${k}: ${errs.join(" | ") || "no errors"}`);
  await p.close();
}
await b.close();
fs.writeFileSync("shots/report.txt", out.join("\n") + "\n"); console.log(out.join("\n"));
