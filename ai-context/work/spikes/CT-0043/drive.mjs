// Drives the CoAgent page: click a shot, talk in the chat, answer the interrupt, capture.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
const chrome = spawn(process.env.HOME + "/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell",
  ["--remote-debugging-port=9343", "--no-sandbox", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await sleep(1500);
const t = (await (await fetch("http://127.0.0.1:9343/json")).json()).find((x) => x.type === "page");
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pend = new Map(); const external = new Set();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
  if (m.method === "Network.requestWillBeSent") { const u = new URL(m.params.request.url); if (!["127.0.0.1", "localhost"].includes(u.hostname) && u.protocol.startsWith("http")) external.add(u.hostname); }
  if (m.id && pend.has(m.id)) pend.get(m.id)(m); });
const send = (method, params = {}) => new Promise((res) => { const n = ++id; pend.set(n, res); ws.send(JSON.stringify({ id: n, method, params })); });
const js = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result.result.value;
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1300, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: "http://127.0.0.1:5190/" }); await sleep(6000);
async function say(text) {
  await js(`(() => { const t = document.querySelector('textarea'); t.focus(); return !!t; })()`);
  await send("Input.insertText", { text });
  await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
}
async function waitFor(expr, ms = 90000) { const end = Date.now() + ms; while (Date.now() < end) { if (await js(expr)) return true; await sleep(500); } return false; }
async function shot(file) { const s = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(file, Buffer.from(s.result.data, "base64")); }
const out = (label, value) => console.log(label, JSON.stringify(value));
const assistantCount = `document.querySelectorAll('[data-message-role="assistant"], .copilotKitAssistantMessage, [class*="assistant" i]').length`;

await js(`document.querySelector('[data-shot="P3"]').click()`);
let before = await js(assistantCount);
await say("Qual plano estou olhando agora, e o que falta para produzir o bloco A? Aponte o plano que precisa de atenção.");
out("answered", await waitFor(`${assistantCount} > ${before} && !document.body.innerText.includes('Thinking')`));
await sleep(4000);
out("state", await js(`document.querySelector('[data-testid="state"]').innerText`));
out("highlight", await js(`document.querySelector('[data-testid="highlight"]')?.parentElement?.getAttribute('data-shot') || ''`));
out("chat", await js(`document.querySelector('textarea').closest('div').parentElement.parentElement.innerText.slice(-900)`));
await shot(process.argv[2] + "-1.png");
await say("Pode iniciar o workflow do bloco A.");
out("confirm shown", await waitFor(`!!document.querySelector('[data-testid="confirm"]')`));
out("confirm text", await js(`document.querySelector('[data-testid="confirm"]')?.innerText || ''`));
await shot(process.argv[2] + "-2.png");
await js(`[...document.querySelectorAll('[data-testid="confirm"] button')].find(b => b.textContent.startsWith('Sim')).click()`);
await sleep(15000);
out("chat after", await js(`document.body.innerText.slice(-600)`));
await shot(process.argv[2] + "-3.png");
out("external hosts", [...external]);
ws.close(); chrome.kill();
