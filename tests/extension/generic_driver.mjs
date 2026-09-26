// Runs extension/driver.js in real Chromium against a chat page it has no
// selectors for (tests/extension/fake_chat.html), the way the "+ Añadir otra IA"
// test does: find the box, type, send, wait, read the answer.
//   node tests/extension/generic_driver.mjs     (prints one line per case, exits 1 on failure)
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const common = require(join(root, "extension", "common.js"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const page_html = readFileSync(join(here, "fake_chat.html"));
const server = createServer((req, res) => { res.setHeader("Content-Type", "text/html"); res.end(page_html); });
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({ executablePath: exe });
const ctx = await browser.newContext({ permissions: ["clipboard-read", "clipboard-write"] });
const site = common.genericSite("Prueba", base);
const PROMPT = "Responde solo con la palabra: pong";
let failed = 0;

async function drive(query, expect) {
  const page = await ctx.newPage();
  await page.goto(base + query);
  await page.addScriptTag({ path: join(root, "extension", "driver.js") });
  const call = (op, ...args) => page.evaluate(([o, a]) => window.__webllmDriver[o](...a), [op, args]);
  const st = await call("state", site);
  let result;
  if (expect === "login") {
    result = st.loginWall && !st.input ? "login detectado" : `FALLO: ${JSON.stringify(st)}`;
  } else {
    const ins = await call("insert", site, PROMPT);
    const snd = await call("send", site);
    let s2;
    for (let i = 0; i < 40; i++) {
      await page.waitForTimeout(250);
      s2 = await call("state", site);
      if (!s2.generating && s2.lastAnswerLen > 0 && i > 2) break;
    }
    let out = await call("capture", site);
    if (!out.ok) out = await call("fallback", site);
    const good = ins.ok && snd.ok && out.ok && /pong/i.test(out.text) && out.via === expect;
    result = `${good ? "BIEN" : "FALLO"}: escribir=${ins.method} enviar=${snd.method} leer=${out.via} texto=${JSON.stringify(out.text)}`;
  }
  if (!/^BIEN|login detectado/.test(result)) failed++;
  console.log(`${query.padEnd(14)} ${result}`);
  await page.close();
}

// After a finished answer, is the page still "writing"? Pages that park the "stop" button
// off-screen, or have a button whose class contains "stop", must read as finished.
async function settled(query) {
  const page = await ctx.newPage();
  await page.goto(base + query);
  await page.addScriptTag({ path: join(root, "extension", "driver.js") });
  const call = (op, ...args) => page.evaluate(([o, a]) => window.__webllmDriver[o](...a), [op, args]);
  await call("insert", site, PROMPT);
  await call("send", site);
  let st;
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(250);
    st = await call("state", site);
    if (st.copyCount > 0) break;
  }
  await page.waitForTimeout(500);
  st = await call("state", site);
  const good = st.copyCount > 0 && !st.generating;
  if (!good) failed++;
  console.log(`${query.padEnd(14)} ${good ? "BIEN" : "FALLO"}: terminada=${st.copyCount > 0} sigue_escribiendo=${st.generating}`);
  await page.close();
}

await drive("?copy=1", "copy-button");
await drive("?copy=0", "dom");
await drive("?editable=1", "copy-button");
await drive("?login=1", "login");
await settled("?stopfuera=1");
await settled("?clasestop=1");
await browser.close();
server.close();
process.exitCode = failed ? 1 : 0;
