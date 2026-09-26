// PLAN-v5 F4 on the real screen: Open WebUI → webllm's gateway → the REAL extension in Chromium → the
// extended test chat page (tests/extension/fake_chat.html ?completa=1). Checks that:
//   - the model selector lists the chat's own models, the strongest first and saying so (D18/D22);
//   - a file attached in Open WebUI reaches the chat's page whole (same sha256);
//   - a switch of the "+" changes the mode really used on the page;
//   - the answer says what was used, read back from the page.
//   OW_URL=... OW_EMAIL=... OW_PASSWORD=... WEBLLM_PYTHON=python WEBLLM_TEST_PORT=... OUT=dir node tests/openwebui/f4_checks.mjs
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { checks, sleep, startWorld } from "../extension/harness.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OW = process.env.OW_URL ?? "http://127.0.0.1:20210";
const OUT = process.env.OUT ?? join(root, "docs", "capturas", "f4", "openwebui");
const { say, failed } = checks();
const shot = async (page, name) => { await page.waitForTimeout(300); await page.screenshot({ path: join(OUT, `${name}.png`) }); };

mkdirSync(OUT, { recursive: true });
let w = null;
let browser = null;
try {
  // webllm with the real extension, and one test chat from its catalog, connected and discovered.
  w = await startWorld({
    limitS: 60,
    catalog: (url) => [{ key: "completa", name: "Completa", by: "Prueba", url: url("chat.completa.test", "/completa/"), group: "1",
      purpose: "prueba", family: "Prueba", tags: ["general"], account: "no", private: true,
      models: [{ match: "ultra", rank: 1 }, { match: "pro", rank: 2 }], models_source: "prueba", models_checked: "2026-09-26" }],
  });
  const conn = await w.call("/api/conectar-varias", { keys: ["completa"] });
  const perm = w.ctx.pages().find((p) => p.url().includes("add.html")) ?? (await w.ctx.waitForEvent("page", { timeout: 15000 }));
  await perm.waitForLoadState();
  await perm.getByRole("button", { name: "Permitir y conectar" }).click();
  let b = conn.body;
  for (let i = 0; i < 120 && !["done", "failed"].includes(b.status); i++) { await sleep(500); b = (await w.call(`/api/conectar-varias/${b.batch_id}`)).body; }
  const card = (await w.call("/api/descubrir", { ia: "completa" })).body;
  say(b.connected === 1 && card.strongest === "Modelo Ultra", `webllm con la extensión de verdad: «Completa» conectada y su ficha leída (el más potente: ${card.strongest})`);

  // Open WebUI pointed at this webllm (the installer, as Iván runs it).
  const signin = await (await fetch(OW + "/api/v1/auths/signin", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: process.env.OW_EMAIL, password: process.env.OW_PASSWORD }) })).json();
  const setup = spawnSync(process.env.WEBLLM_PYTHON ?? "python3", [join(root, "scripts", "openwebui_setup.py"), "--openwebui", OW,
    "--clave", signin.token, "--webllm", w.api, "--webllm-token", "demo-token"], { encoding: "utf8" });
  say(setup.status === 0 && /Listo\./.test(setup.stdout), `el instalador pone webllm en Open WebUI (${setup.status})`);

  browser = await chromium.launch({ executablePath: exe, args: ["--no-proxy-server"] });
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-ES" })).newPage();
  await page.goto(OW + "/auth");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  await page.getByPlaceholder("Ingresa tu correo electrónico").fill(process.env.OW_EMAIL);
  await page.getByPlaceholder("Ingresa tu contraseña").fill(process.env.OW_PASSWORD);
  await page.getByRole("button", { name: "Iniciar Sesión" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/auth"), { timeout: 20000 });
  await page.goto(OW + "/");
  await page.locator("#chat-input").waitFor({ timeout: 20000 });
  const ok = page.getByRole("button", { name: "Vale, ¡Vamos!" });
  if (await ok.count()) await ok.click();

  // The chat's own models in the selector, the strongest first and saying so.
  await page.locator("#model-selector-model-button").click();
  await page.waitForTimeout(800);
  const listed = await page.locator("body").innerText();
  await shot(page, "01-selector-con-modelos");
  const strongestShown = /Completa · Modelo Ultra \(web\) — el más potente/.test(listed);
  const unknownShown = /Completa · Modelo Rápido \(web\) \(nuevo, sin datos\)/.test(listed);
  say(strongestShown && unknownShown, "el selector muestra los modelos del chat: «Completa · Modelo Ultra (web) — el más potente» y los que no tienen datos, marcados");
  await page.getByText("Completa (web)", { exact: true }).first().click();

  // A file attached like in any chat, and the "Buscar en la web" switch of the "+".
  const pdf = Buffer.from("%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");
  writeFileSync(join(OUT, "..", "prueba.pdf"), pdf);
  await page.locator("input[type=file][multiple]").setInputFiles([join(OUT, "..", "prueba.pdf")]);
  await page.waitForTimeout(4000);
  await page.locator("#integration-menu-button").click();
  await page.waitForTimeout(500);
  const toggle = page.getByText("Buscar en la web", { exact: true }).first();
  const hasToggle = (await toggle.count()) > 0;
  if (hasToggle) await toggle.click(); // the row is the button (aria-pressed), the switch is drawn inside it
  const pressed = hasToggle ? await toggle.locator("xpath=ancestor::button[1]").getAttribute("aria-pressed") : null;
  await shot(page, "02-archivo-e-interruptor");
  await page.keyboard.press("Escape");
  await page.locator("#chat-input").click();
  await page.keyboard.type("¿Qué recibiste?");
  await page.keyboard.press("Enter");
  const answered = await page.getByText(/Recibido: modelo=Modelo Ultra/).first().waitFor({ timeout: 120000 }).then(() => true, () => false);
  await page.waitForTimeout(1500);
  await shot(page, "03-respuesta");

  const chat = w.ctx.pages().find((p) => p.url().includes("chat.completa.test"));
  const got = await chat.evaluate(() => ({ received: window.__received, modes: window.__modes }));
  const sha = createHash("sha256").update(pdf).digest("hex");
  say(answered && got.received?.length === 1 && got.received[0].name === "prueba.pdf" && got.received[0].sha256 === sha,
    `el archivo adjuntado en Open WebUI llega entero a la web del chat: ${JSON.stringify(got.received?.map((f) => [f.name, f.sha256.slice(0, 12)]))} (original ${sha.slice(0, 12)})`);
  say(hasToggle && pressed === "true" && got.modes?.buscar === true && (await page.getByText(/modos=buscar/).count()) > 0,
    `el interruptor «Buscar en la web» del «+» cambia el modo usado en la web: ${JSON.stringify(got.modes)}`);
  const status = await page.locator("body").innerText();
  say(/Respondió Completa con el modelo «Modelo Ultra» y el modo «Buscar en la web» \(comprobado en su web\)/.test(status) &&
      /«prueba\.pdf» se subió a Completa \(Prueba\), con la misma huella/.test(status),
    "la respuesta dice lo que se usó de verdad, leído en la web: modelo, modo y a quién se subió el archivo");
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-30).join("\n"));
  await browser?.close();
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
