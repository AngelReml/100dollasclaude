// PLAN-v5 F7 on the real screen: Open WebUI + the webllm pipe + webllm (the demo: its fake chats and APIs follow the
// Committee's protocol). "webllm · Comité" in the selector; the idea; the plan (nothing sent); "adelante"; the
// progress in the thinking block; the fusion document with its 8 sections; the record with its green lock; the
// vault's copy with the annex (when the memory is on).
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_URL=http://127.0.0.1:PORT WEBLLM_DATA=DIR [VAULT=DIR] OUT=dir \
//     node tests/openwebui/f7_checks.mjs
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OW = process.env.OW_URL ?? "http://127.0.0.1:20220";
const WEBLLM = process.env.WEBLLM_URL ?? "http://127.0.0.1:20221";
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f7", "openwebui");
const DEMO = { Authorization: "Bearer demo-token", "Content-Type": "application/json" };
const SECTIONS = ["Resumen", "Veredicto del Comité", "En qué coinciden", "En qué discrepan", "Riesgos principales",
  "Condiciones para seguir adelante", "Recomendación final", "Próximos pasos concretos"];

let failed = 0;
const say = (ok, text) => {
  if (!ok) failed++;
  console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
};
const shot = async (page, name) => { await page.waitForTimeout(300); await page.screenshot({ path: join(OUT, `${name}.png`) }); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, ms = 30000) {
  for (let t = 0; t < ms; t += 250) {
    const v = await fn();
    if (v) return v;
    await sleep(250);
  }
  return fn();
}
/** Every run, by name: new ones are found by name, never by position (ids of the same second sort randomly). */
function runs() {
  const dir = join(process.env.WEBLLM_DATA, "runs");
  return (existsSync(dir) ? readdirSync(dir) : []).flatMap((d) => {
    const j = join(dir, d, "journal.jsonl");
    return existsSync(j) ? [{ id: d, lines: readFileSync(j, "utf8").trim().split("\n").map((x) => JSON.parse(x)) }] : [];
  });
}
const known = () => new Set(runs().map((r) => r.id));
const since = (seen) => runs().filter((r) => !seen.has(r.id));

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "es-ES" })).newPage();
try {
  await page.goto(OW + "/auth");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  await page.getByPlaceholder("Ingresa tu correo electrónico").fill(process.env.OW_EMAIL);
  await page.getByPlaceholder("Ingresa tu contraseña").fill(process.env.OW_PASSWORD);
  await page.getByRole("button", { name: "Iniciar Sesión" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/auth"), { timeout: 20000 });
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const ok = page.getByRole("button", { name: "Vale, ¡Vamos!" });
  if (await ok.count()) await ok.click();

  // 1. "webllm · Comité" is in the selector; the idea gets the plan, and nothing is sent.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  await page.locator("#model-selector-model-button").click();
  const inList = await page.getByText("webllm · Comité", { exact: true }).first().isVisible().catch(() => false);
  await page.getByText("webllm · Comité", { exact: true }).first().click();
  const before = known();
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Merece la pena guardar cada respuesta de cada IA en su propio archivo con la fecha como título?");
  await page.keyboard.press("Enter");
  const plan = await until(async () => (await page.getByText("Plan del Comité").count()) > 0, 30000);
  await page.waitForTimeout(1200);
  const sentForPlan = since(before);  // a plan is webllm's own text: no question is recorded, nothing is sent
  await shot(page, "01-plan");
  const shown = (await page.locator("body").innerText());
  say(inList && plan && /adelante/.test(shown) && /Coste/.test(shown) && /Tiempo/.test(shown) && sentForPlan.length === 0,
    `«webllm · Comité» está en el selector; la idea recibe el plan (quién, rol, coste, tiempo) y no se envía nada (${sentForPlan.length} envíos)`);

  // 2. "adelante": it runs; its progress in the thinking block; the document with its 8 sections.
  const before2 = known();
  await page.locator("#chat-input").click();
  await page.keyboard.type("adelante");
  await page.keyboard.press("Enter");
  const run = await until(() => since(before2).find((r) => r.lines[0].kind === "committee" && r.lines.some((l) => l.kind === "flow_end")), 240000);
  await until(async () => (await page.getByText("Próximos pasos concretos").count()) > 0, 30000);
  await page.waitForTimeout(1500);
  const body = await page.locator("body").innerText();
  const all8 = SECTIONS.every((s) => body.includes(s));
  await shot(page, "02-documento");
  const tally = run?.lines.find((l) => l.kind === "committee_count");
  const valid = tally ? tally.members.filter((m) => m.status === "valid").length : 0;
  say(!!run && all8 && valid % 2 === 1 && valid >= 3 && /recuento: \d+ a favor/.test(body),
    `«adelante»: el Comité se hace y el documento de fusión sale con sus 8 apartados; recuento impar (${valid} veredictos: ${tally?.decision})`);
  const think = page.getByText(/Pensando|Pensamiento|Thought/).first();
  if (await think.count()) await think.click().catch(() => {});
  await page.waitForTimeout(600);
  const thought = await page.locator("body").innerText();
  await shot(page, "03-progreso");
  say(/recibe su rol/.test(thought) && /Recuento:/.test(thought) && /documento de fusión/.test(thought),
    "el progreso (roles, veredictos, recuento, fusión) está en el bloque plegable de razonamiento");

  // 3. The record: its green lock; the history calls it "Comité".
  const h = await (await fetch(`${WEBLLM}/api/historial/${run?.id}`, { headers: DEMO })).json();
  say(h.lock === true && h.kind === "comite",
    `el registro del Comité tiene el candado verde (${h.lock}) y el historial lo llama «Comité»`);

  // 4. The vault: the document with the annex (every verdict with its AI's name) and the seal.
  if (process.env.VAULT) {
    const dir = join(process.env.VAULT, "webllm", "Comités");
    const file = await until(() => existsSync(dir) && readdirSync(dir).find((f) => f.endsWith(".md")), 20000);
    const text = file ? readFileSync(join(dir, file), "utf8") : "";
    say(!!file && text.includes("## Anexo") && text.includes("Sello del registro") && SECTIONS.every((s) => text.includes(s)),
      `en tu memoria: Comités/${file}, con el documento, el anexo de cada veredicto (con el nombre de su IA) y el sello`);
  }
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
