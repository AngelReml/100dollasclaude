// PLAN-v5 F8 on the real screen: Open WebUI + the webllm pipe + webllm (the demo). "webllm · Automático" is in the
// selector and is never what a new chat opens with (D21.3); a question gets its answer from the AI Automático chose,
// and the first line says which and why; the record keeps what it chose; the next question with no signal goes on
// with the conversation; an idea gets the Committee's plan (nothing sent).
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_URL=http://127.0.0.1:PORT WEBLLM_DATA=DIR OUT=dir \
//     node tests/openwebui/f8_checks.mjs
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
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f8", "openwebui");
const ROUTE = /Automático eligió (.+?) para «([^»]+)» \(([^)]*)\)/;

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
const lastAnswer = async (page) => (await page.locator("#response-content-container").last().innerText().catch(() => "")) || "";
async function ask(page, text) {
  await page.locator("#chat-input").click();
  await page.keyboard.type(text);
  await page.keyboard.press("Enter");
}
async function pick(page, name) {
  await page.locator("#model-selector-model-button").click();
  await page.getByText(name, { exact: true }).first().click();
}

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

  // 1. In the selector, and never what a new chat opens with.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const opensWith = (await page.locator("#model-selector-model-button").innerText()).trim();
  await page.locator("#model-selector-model-button").click();
  const inList = await page.getByText("webllm · Automático", { exact: true }).first().isVisible().catch(() => false);
  await page.keyboard.press("Escape");
  say(inList && !/Automático|Comité/.test(opensWith),
    `«webllm · Automático» está en el selector y un chat nuevo no se abre con él (se abre con «${opensWith}»)`);

  // 2. A code question: the chosen AI answers; the first line says which and why; the record keeps it.
  await pick(page, "webllm · Automático");
  const before = known();
  await ask(page, "Hazme un script en Python que sume dos números");
  const run = await until(() => since(before).find((r) => r.lines[0].automatico && r.lines.some((l) => l.kind === "flow_end")), 120000);
  const shown = await until(async () => { const t = await lastAnswer(page); return ROUTE.test(t) && t.split("\n").length > 1 ? t : null; }, 30000);
  await page.waitForTimeout(800);
  await shot(page, "01-codigo");
  const m = (shown || "").match(ROUTE);
  const head = run?.lines[0] ?? {};
  say(!!m && m[2] === "Código" && head.automatico?.tipo === "codigo" && head.provider === head.automatico?.eligio,
    `una pregunta de código: la primera línea dice qué eligió y por qué («${m ? m[0] : shown?.slice(0, 80)}») y el registro lo guarda (${head.automatico?.eligio})`);

  // 3. The next question with no signal goes on with the conversation.
  const before2 = known();
  await ask(page, "¿y cómo lo pruebo?");
  await until(() => since(before2).find((r) => r.lines.some((l) => l.kind === "flow_end")), 120000);
  const next = await until(async () => { const t = await lastAnswer(page); return /sigue la conversación/.test(t) ? t : null; }, 30000);
  say(!!next && /para «Código»/.test(next), "la siguiente pregunta, sin señales, sigue la conversación («Código»)");

  // 4. An idea: the Committee's plan, and nothing is sent.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  await pick(page, "webllm · Automático");
  const before3 = known();
  await ask(page, "¿Merece la pena montar una tienda online de cerámica hecha a mano?");
  const plan = await until(async () => { const t = await lastAnswer(page); return /Plan del Comité/.test(t) ? t : null; }, 30000);
  await page.waitForTimeout(1200);
  await shot(page, "02-idea");
  say(!!plan && /Automático eligió webllm · Comité para «Evaluar una idea»/.test(plan.replace(/\*\*/g, "")) && since(before3).length === 0,
    `una idea recibe el plan del Comité con la primera línea de Automático, y no se envía nada (${since(before3).length} envíos)`);
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
