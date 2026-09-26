// PLAN-v5 F1: Open WebUI as webllm's face, checked on the real screen (Chromium), the way Iván
// uses it: Open WebUI 0.11.x with webllm installed by scripts/openwebui_setup.py, talking to the
// webllm demo (scripts/app_demo.py --data DIR: real bridge, gateway and journal; fake Chrome).
// One line per check (BIEN / FALLO + what was seen); screenshots in OUT.
//   OW_URL=http://127.0.0.1:20210 OW_EMAIL=... OW_PASSWORD=... WEBLLM_DATA=DIR OUT=dir \
//     node tests/openwebui/f1_checks.mjs [--largo]      (--largo adds check 3: a 6-minute answer)
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OW = process.env.OW_URL ?? "http://127.0.0.1:20210";
const DATA = process.env.WEBLLM_DATA;
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f1");
const LONG = process.argv.includes("--largo");
const MODELS = ["Qwen (web)", "DeepSeek (web)", "z.ai (web)", "Meta AI (web)", "z.ai (API)", "groq (API)", "Nemotron (API)"];

let failed = 0;
const say = (ok, text) => {
  if (!ok) failed++;
  console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
};
const sha = (buf) => createHash("sha256").update(buf).digest("hex");

/** The gateway's journal line of the newest question sent after `since` (ms). */
function lastGatewayLine(since) {
  const runs = join(DATA, "runs");
  const found = [];
  for (const d of existsSync(runs) ? readdirSync(runs) : []) {
    const j = join(runs, d, "journal.jsonl");
    if (!existsSync(j)) continue;
    const first = JSON.parse(readFileSync(j, "utf8").split("\n")[0]);
    if (first.kind === "gateway" && Date.parse(first.ts) >= since - 2000) found.push({ dir: join(runs, d), ...first });
  }
  return found.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts)).at(-1) ?? null;
}

async function shot(page, name) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, `${name}.png`) });
}

async function newChat(page) {
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const ok = page.getByRole("button", { name: "Vale, ¡Vamos!" });
  if (await ok.count()) await ok.click();
}

async function send(page, text) {
  await page.locator("#chat-input").click();
  await page.keyboard.type(text);
  await page.keyboard.press("Enter");
}

/** The last answer is finished: its folded thinking block says how long it took. */
async function finished(page, timeout = 60000) {
  await page.getByText(/Pensando durante/).last().waitFor({ timeout });
  await page.waitForTimeout(800);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-ES" });
const page = await ctx.newPage();
try {
  // Log in (the test instance's own administrator: made up for this test, never Iván's).
  await page.goto(OW + "/auth");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500); // the form is ready only after the page's own code has started
  await page.getByPlaceholder("Ingresa tu correo electrónico").fill(process.env.OW_EMAIL);
  await page.getByPlaceholder("Ingresa tu contraseña").fill(process.env.OW_PASSWORD);
  await page.getByRole("button", { name: "Iniciar Sesión" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/auth"), { timeout: 20000 });
  await newChat(page);

  // 9a. In Spanish.
  const spanish = (await page.locator("body").innerText()).match(/Nuevo Chat|Buscar|Sugerido|Explícame algo/g) ?? [];
  say(new Set(spanish).size >= 3, `9. la interfaz sale en español (${[...new Set(spanish)].join(", ")})`);

  // 1. Every webllm AI in the model selector.
  await page.locator("#model-selector-model-button").click();
  await page.waitForTimeout(600);
  const menu = await page.locator("body").innerText();
  const missing = MODELS.filter((m) => !menu.includes(m));
  await shot(page, "01-selector");
  say(!missing.length, `1. los modelos de webllm salen en el selector${missing.length ? `; faltan: ${missing.join(", ")}` : ` (${MODELS.length} + los de tu PC)`}`);
  await page.keyboard.press("Escape");

  // 2 + 9b. A chat that waits for Iván: the note is visible while waiting, the answer arrives after,
  //          and the folded thinking block keeps what happened.
  let since = Date.now();
  await send(page, "¿Qué es la inflación? (demo: verificación)");
  const waitingNote = page.getByText(/te espera: resuelve la verificación/).first();
  const seenWaiting = await waitingNote.waitFor({ timeout: 15000 }).then(() => true, () => false);
  await shot(page, "02-te-espera");
  say(seenWaiting, "9. mientras el chat te espera, el aviso se ve sin abrir nada («te espera: resuelve la verificación…»)");
  await finished(page);
  const answerShown = await page.getByText(/La inflación es cuando las cosas cuestan/).count();
  await shot(page, "03-respuesta");
  say(answerShown > 0, "2. la respuesta llega por partes: primero los avisos, después el texto");
  await page.getByText(/Pensando durante/).last().click();
  await page.waitForTimeout(600);
  const opened = await page.locator("body").innerText();
  await shot(page, "04-pensando-abierto");
  say(/Preguntando a Qwen/.test(opened) && /te espera/.test(opened),
    "9. el bloque plegable «Pensando durante…» guarda lo que pasó (Preguntando a Qwen…, te espera…)");

  // 4. The conversation id reaches webllm (the memory groups by it).
  const chatId = (page.url().match(/\/c\/([\w-]+)/) ?? [])[1];
  const line = lastGatewayLine(since);
  say(!!chatId && line?.chat_id === chatId, `4. webllm recibe el identificador de la conversación (${chatId} → ${line?.chat_id})`);

  // 11. The "Pensar más" switch in the "+" of the text box reaches webllm.
  await newChat(page);
  await page.locator("#integration-menu-button").click();
  await page.waitForTimeout(500);
  const toggle = page.getByText("Pensar más").first();
  const hasToggle = await toggle.count();
  await shot(page, "05-interruptor");
  if (hasToggle) {
    await page.getByRole("switch").first().click().catch(() => toggle.click());
    await page.keyboard.press("Escape");
  }
  await shot(page, "06-interruptor-encendido");
  since = Date.now();
  await send(page, "Hola, ¿qué tal?");
  await finished(page);
  const modes = lastGatewayLine(since)?.modes ?? [];
  say(!!hasToggle && modes.includes("pensar"),
    `11. el interruptor «Pensar más» sale en el «+» y llega a webllm (modos recibidos: ${JSON.stringify(modes)})`);

  // 12. Files attached like in any chat arrive whole (same sha256) at webllm.
  const pdf = Buffer.from("%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n" +
    "4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 60 Td (Hola webllm) Tj ET\nendstream endobj\n" +
    "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");
  writeFileSync(join(OUT, "..", "prueba.pdf"), pdf);
  writeFileSync(join(OUT, "..", "prueba.png"), png);
  await newChat(page);
  await page.locator("input[type=file][multiple]").setInputFiles([join(OUT, "..", "prueba.pdf"), join(OUT, "..", "prueba.png")]);
  await page.waitForTimeout(4000); // Open WebUI uploads them
  await shot(page, "07-adjuntos");
  since = Date.now();
  await send(page, "¿Qué dicen estos archivos?");
  await finished(page);
  await shot(page, "08-adjuntos-respuesta");
  const stillSays = await page.getByText(/no ha visto «prueba\.pdf», «prueba\.png»/).count(); // names each file (F2)
  say(stillSays > 0, "12. al terminar sigue a la vista que la IA aún no ha visto los archivos (lo que ves es lo que se usó)");
  const files = lastGatewayLine(since)?.files ?? [];
  const byHash = Object.fromEntries(files.map((f) => [f.sha256, f.name]));
  say(!!byHash[sha(pdf)] && !!byHash[sha(png)],
    `12. los archivos llegan enteros a webllm, con la misma huella: ${files.map((f) => `${f.name} ${f.sha256.slice(0, 10)}`).join(", ") || "ninguno"} ` +
    `(esperadas: pdf ${sha(pdf).slice(0, 10)}, png ${sha(png).slice(0, 10)})`);

  // 7 (the mechanism; Iván's own prompt-forge is tried on his PC). A SKILL.md added to Open WebUI,
  //   picked with "$" in the text box, reaches the AI inside the conversation's instructions.
  const signin = await (await fetch(OW + "/api/v1/auths/signin", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.OW_EMAIL, password: process.env.OW_PASSWORD }) })).json();
  await fetch(OW + "/api/v1/skills/create", { method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${signin.token}` },
    body: JSON.stringify({ id: "forja-de-prueba", name: "forja-de-prueba", description: "Skill de prueba para webllm",
      content: "---\nname: forja-de-prueba\ndescription: Skill de prueba para webllm\n---\n\nResponde siempre empezando por la palabra FORJA-OK.\n" }) });
  await newChat(page);
  await page.locator("#chat-input").click();
  await page.keyboard.type("$forja");
  const picked = await page.getByText("forja-de-prueba").first().waitFor({ timeout: 10000 }).then(() => true, () => false);
  await shot(page, "09-skill-elegir");
  await page.keyboard.press("Enter");
  since = Date.now();
  await page.keyboard.type(" Hola, ¿qué tal?");
  await page.keyboard.press("Enter");
  await finished(page);
  const sentWithSkill = lastGatewayLine(since);
  const message = sentWithSkill ? readFileSync(join(sentWithSkill.dir, "messages", "respuestas.md"), "utf8") : "";
  say(picked && message.includes('<skill name="forja-de-prueba">') && message.includes("FORJA-OK"),
    "7. una skill (SKILL.md) elegida con «$» en la caja de texto llega a la IA dentro de sus instrucciones");

  // 3. A 6-minute answer is not cut (webllm says "sigo" every 10 s while it waits).
  if (LONG) {
    await newChat(page);
    since = Date.now();
    await send(page, "Cuéntame algo largo (demo: 6 minutos)");
    const ok = await finished(page, 9 * 60000).then(() => true, () => false);
    const took = Math.round((Date.now() - since) / 1000);
    await shot(page, "10-seis-minutos");
    const text = await page.locator("body").innerText();
    say(ok && took >= 360 && !/Error|error/.test(text.split("Cuéntame algo largo").at(-1)),
      `3. una respuesta de 6 minutos no se corta: llegó a los ${took} s`);
  }
} catch (e) {
  say(false, `error: ${e.stack || e}`);
  await shot(page, "zz-error").catch(() => {});
} finally {
  await browser.close();
}
process.exitCode = failed ? 1 : 0;
