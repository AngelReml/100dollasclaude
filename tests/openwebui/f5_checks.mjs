// PLAN-v5 F5 on the real screen: Open WebUI + the webllm pipe + webllm (the demo) with the memory on.
// A conversation kept in an Open WebUI folder ends up in that folder of the vault, written while it happens;
// each answer of each AI also lands in its own file (date as title), exactly as webllm's record has it
// (Iván's decision, 26-sep-2026). On the real screen (Chromium).
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_URL=http://127.0.0.1:PORT WEBLLM_DATA=DIR VAULT=DIR OUT=dir \
//     node tests/openwebui/f5_checks.mjs
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
const VAULT = process.env.VAULT;
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f5", "openwebui");
const BASE = join(VAULT, "webllm");

let failed = 0;
const say = (ok, text) => {
  if (!ok) failed++;
  console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
};
const shot = async (page, name) => { await page.waitForTimeout(300); await page.screenshot({ path: join(OUT, `${name}.png`) }); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Every .md under a folder (the test reads the vault; webllm never does). */
function mdFiles(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? mdFiles(join(dir, e.name)) : e.name.endsWith(".md") ? [join(dir, e.name)] : []);
}
async function until(fn, ms = 30000) {
  for (let t = 0; t < ms; t += 250) {
    const v = fn();
    if (v) return v;
    await sleep(250);
  }
  return fn();
}
/** A gateway question's journal lines, by its first line's time. */
function gatewayRuns(since) {
  const runs = join(process.env.WEBLLM_DATA, "runs");
  const out = [];
  for (const d of existsSync(runs) ? readdirSync(runs) : []) {
    const j = join(runs, d, "journal.jsonl");
    if (!existsSync(j)) continue;
    const lines = readFileSync(j, "utf8").trim().split("\n").map((x) => JSON.parse(x));
    if (lines[0].kind === "gateway" && Date.parse(lines[0].ts) >= since - 2000) out.push({ dir: join(runs, d), id: d, lines });
  }
  return out.sort((a, b) => Date.parse(a.lines[0].ts) - Date.parse(b.lines[0].ts));
}
const ownAnswer = (file) => readFileSync(file, "utf8").split("\n## Respuesta\n\n")[1];

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-ES" })).newPage();
try {
  // 1. The memory on in webllm, and a conversation inside an Open WebUI folder (made with its own API).
  const mem = await (await fetch(WEBLLM + "/api/memoria", { method: "POST", body: JSON.stringify({ dir: VAULT, enabled: true }),
    headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" } })).json();
  const signin = await (await fetch(OW + "/api/v1/auths/signin", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.OW_EMAIL, password: process.env.OW_PASSWORD }) })).json();
  const auth = { "Content-Type": "application/json", Authorization: `Bearer ${signin.token}` };
  let folder = await (await fetch(OW + "/api/v1/folders/", { method: "POST", headers: auth, body: JSON.stringify({ name: "Clientes 2026" }) })).json();
  if (!folder.id) { // run again on the same Open WebUI: the folder is already there
    folder = (await (await fetch(OW + "/api/v1/folders/", { headers: auth })).json()).find((f) => f.name === "Clientes 2026") ?? {};
  }
  const chat = await (await fetch(OW + "/api/v1/chats/new", { method: "POST", headers: auth, body: JSON.stringify({
    folder_id: folder.id, chat: { title: "Plan de clientes", models: ["webllm.qwen"], messages: [],
      history: { messages: {}, currentId: null }, params: {}, tags: [], files: [] } }) })).json();
  say(mem.enabled && folder.id && chat.id, `memoria encendida en webllm (${mem.dir}) y una conversación dentro de la carpeta «Clientes 2026» de Open WebUI`);

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

  // 2. While Qwen is still "writing" (the demo's chat takes 2 minutes), the note is already there, in the
  //    folder's name, with the question.
  await page.goto(OW + "/c/" + chat.id);
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const t1 = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("Resume este libro (demo: 2 minutos)");
  await page.keyboard.press("Enter");
  const stop = page.getByRole("button", { name: "Detener" });
  await stop.waitFor({ timeout: 20000 });
  const note = await until(() => mdFiles(join(BASE, "Clientes 2026")).find((f) => f.endsWith(" Plan de clientes.md")), 20000);
  const mid = note ? readFileSync(note, "utf8") : "";
  await shot(page, "01-escribiendo");
  say(note && mid.includes("Resume este libro") && mid.includes("esperando la respuesta") && (Date.now() - t1) < 60000,
    `mientras Qwen escribe, la nota ya está en webllm/Clientes 2026/ con tu pregunta (${note ? note.split("/").pop() : "no está"})`);

  // 3. "Detener": the note says it, and a stopped question has no answer file.
  await stop.click();
  const stopped = await until(() => note && readFileSync(note, "utf8").includes("Lo has parado tú"), 30000);
  say(stopped && mdFiles(join(BASE, "Respuestas")).length === 0, "«Detener» queda en la nota como «Lo has parado tú», sin archivo de respuesta");

  // 4. The next question: its answer in its own file, date first, identical to webllm's record, and the same
  //    text Open WebUI shows.
  const t2 = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Qué es la inflación?");
  await page.keyboard.press("Enter");
  // (the stopped question started seconds before: it is the one without an answer)
  const run = await until(() => gatewayRuns(t2).find((r) => r.lines.some((l) => l.kind === "flow" && l.status === "ok")), 60000);
  const own = await until(() => mdFiles(join(BASE, "Respuestas", "Qwen"))[0], 20000);
  const call = run?.lines.find((l) => l.kind === "flow");
  const journalText = call?.response_file ? readFileSync(join(run.dir, call.response_file), "utf8") : null;
  await page.waitForTimeout(1500);
  await shot(page, "02-respondida");
  const plain = (journalText ?? "").split("\n").map((x) => x.replace(/[*_`#>]/g, "").replace(/^\s*-\s*/, "").trim());
  const shown = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  const onScreen = journalText ? plain.filter((x) => x.length > 20).every((x) => shown.includes(x.replace(/\s+/g, " "))) : false;
  const name = own ? own.split("/").pop() : "";
  const same = !!own && ownAnswer(own) === journalText;
  say(own && /^\d{4}-\d\d-\d\d \d\d\.\d\d\.\d\d Qwen - ¿Qué es la inflación\.md$/.test(name) && same && onScreen > 0,
    `la respuesta tiene su propio archivo «Respuestas/Qwen/${name}», idéntico al registro (${same ? "sí" : "no"}) y a lo que enseña Open WebUI (${onScreen ? "sí" : "no"})`);

  // 5. One conversation = one note: both questions, and a link to the answer's own file.
  const text = note ? readFileSync(note, "utf8") : "";
  say((text.match(/^## Tú/gm) ?? []).length === 2 && text.includes(`](<../Respuestas/Qwen/${name}>)`) &&
    mdFiles(BASE).filter((f) => !f.includes("/Respuestas/") && !f.endsWith("Índice.md")).length === 1,
    "la misma conversación sigue en la misma nota, con sus dos preguntas y el enlace a la respuesta suelta");

  // 6. A conversation outside any folder, with an AI by API: "Sin proyecto", under the title Open WebUI gives it
  //    (never "New Chat"), and its answer under Respuestas/z.ai.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  await page.locator("#model-selector-model-button").click();
  await page.getByText("z.ai (API)", { exact: true }).first().click();
  const t3 = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Cuánto es 2 más 2?");
  await page.keyboard.press("Enter");
  const run3 = await until(() => gatewayRuns(t3).find((r) => r.lines.some((l) => l.kind === "flow" && l.provider === "zai")), 60000);
  const loose = await until(() => mdFiles(join(BASE, "Sin proyecto")).find((f) => / ¿?Cuánto es 2 más 2\.md$/.test(f)), 20000);
  const zai = await until(() => mdFiles(join(BASE, "Respuestas", "z.ai"))[0], 20000);
  const call3 = run3?.lines.find((l) => l.kind === "flow");
  const zaiText = call3?.response_file ? readFileSync(join(run3.dir, call3.response_file), "utf8") : null;
  await shot(page, "03-sin-carpeta");
  say(loose && zai && ownAnswer(zai) === zaiText,
    `una conversación sin carpeta va a «Sin proyecto» con su título (no «New Chat»), y su respuesta a «Respuestas/z.ai» (${loose ? loose.split("/").pop() : "no está"})`);
  console.log("VAULT\n" + mdFiles(BASE).map((f) => "  " + f.slice(VAULT.length + 1)).sort().join("\n"));
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
