// Digital twin: sterowanie przeglądarką przez Chrome DevTools Protocol (bez Puppeteera/Playwrighta).
// Node 22+: globalny WebSocket i fetch. Zbiera: zrzuty ekranu, błędy konsoli, błędy sieci, DOM.
//
//   CDP_URL=http://127.0.0.1:9222 APP_URL=http://127.0.0.1:8080 node --experimental-strip-types twin/cdp.ts twin/scenarios/*.cdp.tql
//
// Składnia scenariusza (podzbiór zgodny w duchu z GUI_* z autogrammar/testql):
//   GOTO /path | WAIT <css> | CLICK <css> | TYPE <css> "tekst" | PRESS Enter | SELECT <css> "wartość"
//   WAIT_TEXT <css> "fragment" | ASSERT_TEXT <css> "fragment" | SCREENSHOT name.png | CONSOLE_ERRORS <max> | SLEEP ms
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

import { lookup } from "node:dns/promises";

// Chrome odrzuca nagłówek Host, który nie jest IP/localhost -> w Dockerze zamieniamy nazwę usługi na IP.
const CDP = await (async (u: string) => {
  const url = new URL(u);
  if (!/^[\d.]+$|^localhost$/.test(url.hostname)) url.hostname = (await lookup(url.hostname, 4)).address;
  return url.origin;
})(process.env.CDP_URL ?? "http://127.0.0.1:9222");
const APP = process.env.APP_URL ?? "http://127.0.0.1:8080";
const OUT = process.env.ARTIFACTS ?? "artifacts/twin";
mkdirSync(OUT, { recursive: true });

class Page {
  ws!: WebSocket;
  id = 0;
  pending = new Map<number, (v: any) => void>();
  consoleErrors: string[] = [];
  networkErrors: string[] = [];
  events: any[] = [];

  async open() {
    const r = await fetch(`${CDP}/json/new?about:blank`, { method: "PUT" });
    const t: any = await r.json();
    const wsUrl = String(t.webSocketDebuggerUrl).replace(/^ws:\/\/[^/]+/, CDP.replace(/^http/, "ws"));
    this.ws = new WebSocket(wsUrl);
    await new Promise((ok, err) => { this.ws.onopen = ok; this.ws.onerror = err; });
    this.ws.onmessage = (m) => {
      const msg = JSON.parse(String(m.data));
      if (msg.id && this.pending.has(msg.id)) { this.pending.get(msg.id)!(msg); this.pending.delete(msg.id); return; }
      this.events.push(msg);
      if (msg.method === "Runtime.exceptionThrown") this.consoleErrors.push(msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text);
      if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") this.consoleErrors.push(msg.params.args.map((a: any) => a.value ?? a.description).join(" "));
      if (msg.method === "Network.responseReceived" && msg.params.response.status >= 500) this.networkErrors.push(`${msg.params.response.status} ${msg.params.response.url}`);
      if (msg.method === "Network.loadingFailed") this.networkErrors.push(`failed ${msg.params.errorText}`);
    };
    for (const d of ["Page", "Runtime", "Network", "Log"]) await this.send(`${d}.enable`);
    await this.send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 860, deviceScaleFactor: 1, mobile: false });
    return this;
  }

  send(method: string, params: Record<string, unknown> = {}): Promise<any> {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((ok, err) => {
      this.pending.set(id, (m) => (m.error ? err(new Error(`${method}: ${m.error.message}`)) : ok(m.result)));
      setTimeout(() => err(new Error(`${method}: timeout`)), 15000);
    });
  }

  async eval<T = any>(expr: string): Promise<T> {
    const r = await this.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  }

  async waitFor(expr: string, what: string, ms = 8000) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      if (await this.eval<boolean>(expr)) return;
      await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error(`timeout waiting for ${what}`);
  }
}

const q = (css: string) => `document.querySelector(${JSON.stringify(css)})`;

async function runScenario(file: string) {
  const page = await new Page().open();
  const steps: any[] = [];
  let ok = true;
  const lines = readFileSync(file, "utf8").split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  for (const line of lines) {
    const [, cmd, rest = ""] = line.match(/^(\w+)\s*(.*)$/) ?? [];
    const m = rest.match(/^(\S+(?:\s*\S+\])?)\s*(?:"(.*)")?$/) ?? [];
    const sel = m[1] ?? rest, arg = m[2] !== undefined ? JSON.parse(`"${m[2]}"`) : "";
    const t0 = Date.now();
    try {
      switch (cmd) {
        case "GOTO": await page.send("Page.navigate", { url: APP + rest }); await page.waitFor("document.readyState==='complete'", "load"); break;
        case "WAIT": await page.waitFor(`!!${q(sel)}`, sel); break;
        case "CLICK": await page.waitFor(`!!${q(sel)}`, sel); await page.eval(`${q(sel)}.click()`); break;
        case "TYPE": await page.eval(`${q(sel)}.focus(); ${q(sel)}.value=''`); await page.send("Input.insertText", { text: arg }); break;
        case "SELECT": await page.eval(`(e=>{e.value=${JSON.stringify(arg)};e.dispatchEvent(new Event('change'))})(${q(sel)})`); break;
        case "PRESS": for (const type of ["keyDown", "keyUp"]) await page.send("Input.dispatchKeyEvent", { type, key: rest, code: rest, windowsVirtualKeyCode: rest === "Enter" ? 13 : 0, text: rest === "Enter" && type === "keyDown" ? "\r" : undefined }); break;
        case "WAIT_TEXT": await page.waitFor(`(${q(sel)}?.textContent||'').includes(${JSON.stringify(arg)})`, `${sel} ~ "${arg}"`); break;
        case "ASSERT_TEXT": if (!(await page.eval<boolean>(`(${q(sel)}?.textContent||'').includes(${JSON.stringify(arg)})`))) throw new Error(`text "${arg}" not in ${sel}`); break;
        case "SCREENSHOT": { const s = await page.send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(OUT, rest), Buffer.from(s.data, "base64")); break; }
        case "CONSOLE_ERRORS": if (page.consoleErrors.length > Number(rest)) throw new Error(`console errors: ${page.consoleErrors.join(" | ")}`); break;
        case "SLEEP": await new Promise((r) => setTimeout(r, Number(rest))); break;
        default: throw new Error(`unknown command ${cmd}`);
      }
      steps.push({ line, ok: true, ms: Date.now() - t0 });
    } catch (e) {
      ok = false;
      steps.push({ line, ok: false, error: String(e), ms: Date.now() - t0 });
      const s = await page.send("Page.captureScreenshot", { format: "png" }).catch(() => null);
      if (s) writeFileSync(join(OUT, basename(file) + ".failure.png"), Buffer.from(s.data, "base64"));
      break;
    }
  }
  const dom = await page.eval<string>("document.body.innerText.slice(0, 4000)").catch(() => "");
  page.ws.close();
  return { scenario: file, ok, steps, consoleErrors: page.consoleErrors, networkErrors: page.networkErrors, domText: dom };
}

const files = process.argv.length > 2 ? process.argv.slice(2) :
  ["tests/generated", "twin/scenarios"].flatMap(dir => existsSync(dir)
    ? readdirSync(dir).filter(name => name.endsWith(".cdp.tql")).sort().map(name => join(dir, name)) : []);
if (!files.length) throw new Error("No CDP scenarios found; run make gen first");
const results = [];
for (const f of files) results.push(await runScenario(f));
const report = { ok: results.every((r) => r.ok), cdp: CDP, app: APP, results };
writeFileSync(join(OUT, "cdp-report.json"), JSON.stringify(report, null, 2));
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"} ${r.scenario}`);
  for (const s of r.steps) console.log(`  ${s.ok ? "✓" : "✗"} ${s.line}${s.error ? "  -> " + s.error : ""} (${s.ms}ms)`);
}
process.exit(report.ok ? 0 : 1);
