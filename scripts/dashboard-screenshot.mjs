// Screenshot the dashboard at any screen size, headless, from the wall panel.
//
//   scp scripts/dashboard-screenshot.mjs smarthome@192.168.0.176:/tmp/shot.mjs
//   ssh smarthome@192.168.0.176 'cd /tmp && node shot.mjs <view> <width> <height> <out.png> [scroll-selector] [js]'
//
// Run on the wall panel (Raspberry Pi 4) because it is a trusted host: the
// dashboard lets it in without a login. Node 24 and Chromium are already
// there. It opens its own headless Chromium with a fresh profile, so the
// panel's real screen is not touched.
//
//   view        a data-view to click, or any view name activateView() knows
//   width/height the screen to emulate (iPhone 15: 393 852, iPad Air 13 in
//               landscape: 1366 950 allowing for Safari's bar, wall panel: 1920 1080)
//   selector    optional: scroll this element into view first
//   js          optional: an expression (may return a promise) evaluated before
//               the shot; its result is printed. Handy for measuring, e.g.
//               which elements scroll, or stripping @container rules to see
//               what Safari before iPadOS 16 sees.
//
// Env CHROME_FLAGS adds Chromium flags.
// Headless: open the dashboard, click a view, screenshot the whole page.
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
const [view, width, height, out] = [process.argv[2], +process.argv[3], +process.argv[4], process.argv[5]];
const profile = mkdtempSync("/tmp/shot-");
const chrome = spawn("chromium", ["--headless=new", "--no-sandbox", "--disable-gpu", `--user-data-dir=${profile}`,
  "--remote-debugging-port=9333", `--window-size=${width},${height}`, ...(process.env.CHROME_FLAGS ? process.env.CHROME_FLAGS.split(" ") : []), "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch("http://127.0.0.1:9333/json")).json(); if (targets.length) break; } catch {}
  await sleep(500);
}
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const waiting = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const n = ++id; waiting.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 500 });
await send("Page.navigate", { url: "http://192.168.0.83:8000/" });
await sleep(9000);
const click = await send("Runtime.evaluate", { expression: `(() => { const b = document.querySelector('[data-view="${view}"]'); if (!b) { if (typeof activateView === 'function') { activateView('${view}'); return 'activated'; } return 'no nav'; } b.click(); return 'clicked'; })()`, returnByValue: true });
console.log(click.result?.result?.value);
await sleep(7000);
if (process.argv[6]) { await send("Runtime.evaluate", { expression: `document.querySelector("${process.argv[6]}")?.scrollIntoView({block: "start"})` }); await sleep(800); }
const errs = await send("Runtime.evaluate", { expression: `document.querySelector('#statusEvents')?.textContent + ' | ' + document.querySelector('#statusServicesCount')?.textContent`, returnByValue: true });
console.log(errs.result?.result?.value);
if (process.argv[7]) { const r = await send("Runtime.evaluate", { expression: process.argv[7], returnByValue: true, awaitPromise: true }); console.log(JSON.stringify(r.result?.result?.value)); }
const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
  clip: { x: 0, y: 0, width, height: (await send("Runtime.evaluate", { expression: "document.documentElement.scrollHeight", returnByValue: true })).result.result.value, scale: 1 } });
writeFileSync(out, Buffer.from(shot.result.data, "base64"));
chrome.kill(); process.exit(0);
