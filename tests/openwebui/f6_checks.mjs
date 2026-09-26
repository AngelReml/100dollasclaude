// PLAN-v5 F6 on the real screen: Open WebUI + the webllm pipe + webllm (the demo, whose fake Chrome "writes"
// one turn by hand in the web 3 s after it is opened).
//   - «Continuar en la web» is a button under the answers of a web chat, not under an AI by API;
//   - pressing it opens that exact conversation (webllm is told which one) and Open WebUI says so;
//   - what Iván wrote by hand in the web goes with his next question in Open WebUI, and the answer says so.
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_URL=http://127.0.0.1:PORT WEBLLM_DATA=DIR OUT=dir \
//     node tests/openwebui/f6_checks.mjs
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
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f6", "openwebui");
const DEMO = { Authorization: "Bearer demo-token", "Content-Type": "application/json" };

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
/** Every run's journal lines, oldest first. */
function runs() {
  const dir = join(process.env.WEBLLM_DATA, "runs");
  return (existsSync(dir) ? readdirSync(dir) : []).sort().flatMap((d) => {
    const j = join(dir, d, "journal.jsonl");
    return existsSync(j) ? [{ id: d, dir: join(dir, d), lines: readFileSync(j, "utf8").trim().split("\n").map((x) => JSON.parse(x)) }] : [];
  });
}
const button = (page) => page.getByRole("button", { name: "Continuar en la web" });

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-ES" })).newPage();
try {
  const signin = await (await fetch(OW + "/api/v1/auths/signin", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.OW_EMAIL, password: process.env.OW_PASSWORD }) })).json();
  const auth = { "Content-Type": "application/json", Authorization: `Bearer ${signin.token}` };
  const chat = await (await fetch(OW + "/api/v1/chats/new", { method: "POST", headers: auth, body: JSON.stringify({
    chat: { title: "Seguir en la web", models: ["webllm.qwen"], messages: [], history: { messages: {}, currentId: null },
      params: {}, tags: [], files: [] } }) })).json();
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

  // 1. A web chat's answer has «Continuar en la web» under it.
  await page.goto(OW + "/c/" + chat.id);
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const before = runs().length;
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Qué es la inflación?");
  await page.keyboard.press("Enter");
  const asked = await until(() => runs().slice(before).find((r) => r.lines[0].kind === "gateway" && r.lines.some((l) => l.kind === "flow_end")), 60000);
  await button(page).last().waitFor({ timeout: 20000 }).catch(() => {});
  const shown = await button(page).count();
  await shot(page, "01-boton");
  say(!!asked && shown >= 1, `bajo la respuesta de Qwen (un chat web) está «Continuar en la web» (${shown} botón)`);

  // 2. Pressing it: that conversation is opened in Chrome (webllm is told which one), and Open WebUI says so.
  await button(page).last().click();
  const toast = await until(async () => (await page.getByText(/Abierta en tu Chrome la conversación de Qwen/).count()) > 0, 20000);
  const estado = await (await fetch(WEBLLM + "/api/estado", { headers: DEMO })).json();
  const watching = (estado.observing ?? []).find((o) => o.follows === asked?.id);
  await shot(page, "02-abierta");
  say(toast && !!watching, `al pulsarlo: «Abierta en tu Chrome la conversación de Qwen…», y webllm registra esa conversación (${watching?.label ?? "no"}, sigue a ${asked?.id})`);

  // 3. The turn written by hand in the web is recorded in the same conversation.
  const hand = await until(() => runs().find((r) => r.lines[0].kind === "observed" && r.lines[0].follows === asked?.id), 20000);
  const byIvan = hand?.lines.find((l) => l.kind === "flow");
  say(!!hand && byIvan?.by === "ivan" && hand.lines[0].chat_id === chat.id,
    `lo que escribes a mano en la web queda en la misma conversación, marcado como tuyo (${hand?.id ?? "no"})`);

  // 4. Back in Open WebUI: the next question takes it along, and the answer says so.
  const before2 = runs().length;
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Y cómo me protejo?");
  await page.keyboard.press("Enter");
  const next = await until(() => runs().slice(before2).find((r) => r.lines[0].kind === "gateway" && r.lines.some((l) => l.kind === "flow_end")), 60000);
  const call = next?.lines.find((l) => l.kind === "flow");
  const sentText = call?.message_file ? readFileSync(join(next.dir, call.message_file), "utf8") : "";
  const note = await until(async () => (await page.getByText(/Con tu pregunta va también el mensaje que escribiste directamente en la web de Qwen, con su respuesta/).count()) > 0, 20000);
  await shot(page, "03-de-vuelta");
  say(sentText.includes("Esto lo escribí a mano en la web (demo)") && sentText.includes("Y esto contestó la web (demo).") &&
      sentText.indexOf("Esto lo escribí a mano") < sentText.indexOf("¿Y cómo me protejo?") && note,
    "de vuelta en Open WebUI, tu siguiente pregunta lleva lo que escribiste en la web, en su sitio, y la respuesta lo dice");

  // 5. An AI by API has no web conversation: no button under its answer.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  await page.locator("#model-selector-model-button").click();
  await page.getByText("z.ai (API)", { exact: true }).first().click();
  const before3 = runs().length;
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Cuánto es 2 más 2?");
  await page.keyboard.press("Enter");
  const api = await until(() => runs().slice(before3).find((r) => r.lines.some((l) => l.kind === "flow" && l.provider === "zai")), 60000);
  await page.waitForTimeout(2500);
  await shot(page, "04-api-sin-boton");
  say(!!api && (await button(page).count()) === 0, "bajo la respuesta de z.ai (por API) no hay «Continuar en la web»");
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
