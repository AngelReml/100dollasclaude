// PLAN-v5 F1 check 5, which needs F2 (tools through webllm): a harmless MCP tool (the time) is switched
// on in Open WebUI; an AI by API, through webllm, asks to use it; Open WebUI asks Iván first; only after
// "Allow" does the tool run, and the answer uses what it said. Then F2's "Parar": Open WebUI's own stop
// button ("Detener") in the middle of a long answer from a web chat ends it in webllm as stopped by Iván,
// and the same chat answers the next question normally. And F2's exit: a web chat, an AI by API and a
// model on this PC answer from Open WebUI, and webllm's record has the three. On the real screen (Chromium).
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_DATA=DIR MCP_URL=http://127.0.0.1:PORT/mcp OUT=dir \
//     node tests/openwebui/f2_checks.mjs
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OW = process.env.OW_URL ?? "http://127.0.0.1:20210";
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f2");

let failed = 0;
const say = (ok, text) => {
  if (!ok) failed++;
  console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
};
const shot = async (page, name) => { await page.waitForTimeout(300); await page.screenshot({ path: join(OUT, `${name}.png`) }); };

/** Every gateway question since `since` (ms): its first journal line plus the call line. */
function gatewayRuns(since) {
  const runs = join(process.env.WEBLLM_DATA, "runs");
  const out = [];
  for (const d of existsSync(runs) ? readdirSync(runs) : []) {
    const j = join(runs, d, "journal.jsonl");
    if (!existsSync(j)) continue;
    const lines = readFileSync(j, "utf8").trim().split("\n").map((x) => JSON.parse(x));
    if (lines[0].kind === "gateway" && Date.parse(lines[0].ts) >= since - 2000) out.push({ dir: join(runs, d), lines });
  }
  return out.sort((a, b) => Date.parse(a.lines[0].ts) - Date.parse(b.lines[0].ts));
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-ES" })).newPage();
try {
  // The MCP server, connected the way an administrator does it (this test instance's own).
  const signin = await (await fetch(OW + "/api/v1/auths/signin", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.OW_EMAIL, password: process.env.OW_PASSWORD }) })).json();
  const auth = { "Content-Type": "application/json", Authorization: `Bearer ${signin.token}` };
  const saved = await fetch(OW + "/api/v1/configs/tool_servers", { method: "POST", headers: auth, body: JSON.stringify({
    TOOL_SERVER_CONNECTIONS: [{ url: process.env.MCP_URL, path: "", type: "mcp", auth_type: "none", key: "",
      config: { enable: true }, info: { id: "hora", name: "Hora" } }] }) });
  say(saved.ok, `el servidor MCP «Hora» queda conectado a Open WebUI (${saved.status})`);

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

  // An AI by API, and the tool switched on for this conversation.
  await page.locator("#model-selector-model-button").click();
  await page.getByText("z.ai (API)", { exact: true }).first().click();
  await page.locator("#integration-menu-button").click();
  await page.waitForTimeout(600);
  await page.getByText(/^Herramientas/).first().click(); // its tools are in a submenu ("Herramientas 1 >")
  await page.waitForTimeout(600);
  const toolRow = page.getByText("Hora", { exact: true }).first();
  const hasTool = await toolRow.count();
  await shot(page, "01-herramienta-en-el-mas");
  if (hasTool) await toolRow.click();
  await page.keyboard.press("Escape");
  say(!!hasTool, "la herramienta «Hora» sale en el «+» de la caja de texto");

  const since = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Qué hora es?");
  await page.keyboard.press("Enter");
  const allow = page.getByRole("button", { name: /^(Allow|Permitir)$/ }).first();
  const asked = await allow.waitFor({ timeout: 30000 }).then(() => true, () => false);
  await shot(page, "02-pide-permiso");
  const before = await page.locator("body").innerText();
  say(asked && !/Según tu herramienta/.test(before), "antes de usar la herramienta, Open WebUI te pregunta (Allow / Deny) y aún no ha hecho nada");
  if (asked) await allow.click();
  const answered = await page.getByText(/Según tu herramienta: Son las 10:30/).first().waitFor({ timeout: 30000 }).then(() => true, () => false);
  await shot(page, "03-respuesta-con-la-herramienta");
  say(answered, "después de «Allow», la herramienta se usa y la respuesta dice lo que dijo: «Son las 10:30»");

  const runs = gatewayRuns(since);
  const calls = runs.flatMap((r) => r.lines.filter((l) => l.kind === "flow").flatMap((l) => l.tool_calls ?? []));
  const withResult = runs.some((r) => readFileSync(join(r.dir, "messages", "respuestas.md"), "utf8").includes("Son las 10:30"));
  say(calls.some((c) => c.name === "hora_hora_actual") && withResult,
    `el registro de webllm guarda la petición de herramienta (${calls.map((c) => c.name).join(", ")}) y la respuesta con su resultado`);

  // "Detener" (Open WebUI's stop button) while a web chat is still writing a long answer.
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  await page.locator("#model-selector-model-button").click();
  await page.getByText("Qwen (web)", { exact: true }).first().click();
  const t6 = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("Resume este libro (demo: 3 minutos)");
  await page.keyboard.press("Enter");
  const stopButton = page.getByRole("button", { name: "Detener" });
  await stopButton.waitFor({ timeout: 20000 });
  await page.waitForTimeout(3000); // Qwen is "writing" (the demo's chat takes 3 minutes)
  await shot(page, "04-respuesta-larga");
  await stopButton.click();
  const ended = async (since, not = []) => {
    for (let i = 0; i < 80; i++) {
      const run = gatewayRuns(since).find((r) => !not.includes(r.dir) && r.lines.some((l) => l.kind === "flow_end"));
      if (run) return run;
      await page.waitForTimeout(250);
    }
    return null;
  };
  const stopped = await ended(t6);
  const tookS = (Date.now() - t6) / 1000;
  await shot(page, "05-detenida");
  const stoppedCall = stopped?.lines.find((l) => l.kind === "flow");
  say(stoppedCall?.code === "cancelled" && tookS < 60,
    `«Detener» en Open WebUI corta la respuesta de un chat web y webllm la guarda como parada por ti (${stoppedCall?.code ?? "sin registro"}, ${tookS.toFixed(0)} s de 180)`);

  const t7 = Date.now();
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Qué es la inflación?");
  await page.keyboard.press("Enter");
  const next = await ended(t7, [stopped?.dir]);
  await shot(page, "06-siguiente-pregunta");
  const nextCall = next?.lines.find((l) => l.kind === "flow");
  say(nextCall?.status === "ok", `después, la misma IA contesta la siguiente pregunta con normalidad (${nextCall?.status ?? "sin registro"})`);

  // F2's exit: a web chat, an AI by API and a model on this PC all answer from Open WebUI, and webllm's
  // record has the three.
  const three = [["Qwen (web)", "qwen"], ["z.ai (API)", "zai"], ["LM Studio · qwen2.5-1.5b-instruct (tu PC)", "lmstudio:qwen2.5-1.5b-instruct"]];
  const seen = [next?.dir];
  const okCalls = [];
  for (const [label] of three) {
    await page.goto(OW + "/");
    await page.locator("#chat-input").waitFor({ timeout: 20000 });
    await page.locator("#model-selector-model-button").click();
    await page.getByText(label, { exact: true }).first().click();
    const t = Date.now();
    await page.locator("#chat-input").click();
    await page.keyboard.type("¿Qué es la inflación?");
    await page.keyboard.press("Enter");
    const run = await ended(t, seen); // webllm's record says it finished
    seen.push(run?.dir);
    const call = run?.lines.find((l) => l.kind === "flow");
    if (call?.status === "ok") okCalls.push(call);
    await page.waitForTimeout(1000); // the answer on screen
  }
  await shot(page, "07-tu-pc-responde");
  const who = okCalls.map((l) => l.provider);
  say(three.every(([, name]) => who.includes(name)) && okCalls.length === 3,
    `una IA web, una por API y una de tu PC responden desde Open WebUI y el registro de webllm tiene las tres (${who.join(", ")})`);
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
