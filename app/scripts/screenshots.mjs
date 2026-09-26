// Screenshots + layout checks of every screen, light and dark, at 1280 and 1920 px.
//   python scripts/app_demo.py --port 20199      (in another terminal)
//   node app/scripts/screenshots.mjs [outDir] [port]
// Uses the Chromium that Playwright finds (PLAYWRIGHT_CHROMIUM or /opt/pw-browsers).
import { chromium } from "playwright-core";
import { mkdirSync, mkdtempSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const out = process.argv[2] ?? "docs/capturas/fase3";
const port = process.argv[3] ?? "20199";
const base = `http://127.0.0.1:${port}/app/`;
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(out, { recursive: true });
const report = [];

async function check(page, name) {
  const r = await page.evaluate(() => {
    const vw = window.innerWidth;
    const main = document.querySelector("main");
    const small = new Set();
    const clipped = [];
    for (const el of document.querySelectorAll("body *")) {
      const s = getComputedStyle(el);
      if (s.display === "none" || s.visibility === "hidden") continue;
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (own && el.getBoundingClientRect().width > 0 && parseFloat(s.fontSize) < 15 && !el.closest(".sr-only")) small.add(`${el.tagName}:${parseFloat(s.fontSize)}px:"${el.textContent.trim().slice(0, 30)}"`);
      if (own && s.overflowX === "hidden" && el.scrollWidth > el.clientWidth + 1 && !el.className.toString().includes("truncate") && !el.closest(".sr-only")) clipped.push(el.textContent.trim().slice(0, 40));
    }
    const wrappedFooters = [...document.querySelectorAll("[data-footer]")].filter((f) => f.getBoundingClientRect().height > 70).length;
    return {
      wrappedFooters,
      pageOverflow: document.documentElement.scrollWidth > vw,
      mainOverflow: main ? main.scrollWidth > main.clientWidth + 1 : false,
      smallText: [...small].slice(0, 8),
      clipped: clipped.slice(0, 8),
    };
  });
  report.push({ name, ...r });
  return r;
}

async function shot(page, name) {
  await page.waitForTimeout(250);
  await page.screenshot({ path: `${out}/${name}.png` });
  await check(page, name);
}

async function waitAnswers(page) {
  await page.waitForFunction(() => !document.body.innerText.match(/Esperando…|En cola|Te espera/), null, { timeout: 60000 });
}

// "+ Añadir otra IA" (PLAN-v3 7b): a blocked address, a site that works, one that does not, and Quitar.
async function addAnAi(page, tag) {
  const dialog = page.getByRole("dialog");
  const address = dialog.getByLabel("Dirección de la web");
  await page.goto(base);
  await page.getByRole("button", { name: "Añadir otra IA" }).click();
  await address.fill("https://chatgpt.com");
  await dialog.getByRole("button", { name: "Probar y añadir" }).click();
  await dialog.getByText("no se puede añadir").waitFor();
  await shot(page, `${tag}-11-anadir-bloqueada`);

  await address.fill("https://openrouter.ai/chat"); // not in the catalog (the plan leaves it to "Añadir otra IA")
  await dialog.getByRole("button", { name: "Probar y añadir" }).click();
  await dialog.getByText("Permitir y probar").waitFor();
  await shot(page, `${tag}-12-anadir-permiso`);
  await dialog.getByText("Enviando una prueba").waitFor({ timeout: 15000 });
  await shot(page, `${tag}-13-anadir-probando`);
  await dialog.getByText("¡Listo!").waitFor({ timeout: 15000 });
  await shot(page, `${tag}-14-anadir-lista`);
  await dialog.getByRole("button", { name: "Hecho" }).click();

  const card = page.locator('[data-card="openrouter"]');
  await card.getByText("Añadida por ti").waitFor();
  await card.scrollIntoViewIfNeeded();
  await shot(page, `${tag}-15-inicio-anadida`);

  await page.getByRole("button", { name: "Añadir otra IA" }).click();
  await address.fill("https://nochat.example.com");
  await dialog.getByRole("button", { name: "Probar y añadir" }).click();
  await dialog.getByText("No encontré la caja de texto").waitFor({ timeout: 15000 });
  await shot(page, `${tag}-16-anadir-fallo`);
  await dialog.getByRole("button", { name: "Cerrar", exact: true }).last().click();

  await card.getByRole("button", { name: "Quitar" }).click();
  await card.getByText("¿Quitar Openrouter de webllm?").waitFor();
  await shot(page, `${tag}-17-quitar-confirmar`);
  await card.getByRole("button", { name: "Sí, quitar" }).click();
  await card.waitFor({ state: "detached" });
}

// A chat waiting for Iván (a verification): it says so and the question goes on after.
async function waitingForYou(page, tag) {
  await page.goto(base + "#/preguntar");
  await page.getByLabel("Tu pregunta").fill("¿Qué es la inflación? (demo: verificación)");
  await page.getByRole("button", { name: /^Preguntar a/ }).click();
  await page.getByText("pide una verificación").waitFor({ timeout: 15000 });
  await page.waitForTimeout(2500);
  await shot(page, `${tag}-18-te-espera`);
  await waitAnswers(page);
}

// "Parar todo" (PLAN-v5 F2): a question to a chat that takes minutes; from Inicio, one click stops it and
// its job in Chrome, and says what it stopped; the question's card says "Lo has parado tú".
async function stopAll(page, tag) {
  await page.goto(base + "#/preguntar");
  await page.getByRole("button", { name: /^IAs: / }).click();
  await page.getByRole("menuitem", { name: "Ninguna" }).click();
  await page.getByRole("menuitemcheckbox", { name: /Qwen/ }).click();
  await page.keyboard.press("Escape");
  await page.getByLabel("Tu pregunta").fill("Resume este libro (demo: 3 minutos)");
  await page.getByRole("button", { name: /^Preguntar a \d/ }).click(); // not "Preguntar a z.ai" left by apiLimit
  await page.getByText(/Esperando…/).first().waitFor();
  await page.goto(base + "#/");
  const stop = page.getByRole("button", { name: "Parar todo" });
  await stop.waitFor();
  await shot(page, `${tag}-21-inicio-parar-todo`);
  await stop.click();
  await page.getByText("Parado: 1 pregunta y 1 chat de la ventanita.").waitFor({ timeout: 10000 });
  await shot(page, `${tag}-22-parado`);
  await page.goto(base + "#/historial");
  await page.getByRole("link").filter({ hasText: "Resume este libro" }).first().click();
  await page.getByText(/Lo has parado tú/).first().waitFor({ timeout: 10000 });
  await shot(page, `${tag}-23-historial-parado`);
}

// "Conectores" (PLAN-v5 F3): the catalog, "Conectar varias" with four of them (one asks to log in and Iván
// "logs in"; one has no text box; one sends you to another address), and the lists after.
async function conectores(page, tag) {
  const api = (path, body) => fetch(`http://127.0.0.1:${port}${path}`, { method: body ? "POST" : "GET",
    headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  for (const ia of ["kimi", "grok"]) await api("/api/quitar", { ia }); // a previous run connected them
  await page.goto(base + "#/conectores");
  const start = page.getByRole("button", { name: "Conectar varias" });
  await start.waitFor();
  await page.locator('[data-catalog="kimi"]').waitFor();
  await shot(page, `${tag}-24-conectores`);
  await start.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Ninguna" }).waitFor();
  await shot(page, `${tag}-25-conectar-varias`);
  await dialog.getByRole("button", { name: "Ninguna" }).click();
  for (const name of [/^Kimi/, /^Grok/, /^Felo/, /^Duck\.ai/]) await dialog.getByLabel(name).check();
  await dialog.getByRole("button", { name: "Conectar 4" }).click();
  await dialog.getByText(/Te espera: entra con tu cuenta/).waitFor({ timeout: 30000 });
  await shot(page, `${tag}-26-conectando`);
  await dialog.getByText(/^Listo: \d+ de 4 conectadas|^No se conectó/).waitFor({ timeout: 60000 }); // the X is "Cerrar" too
  await shot(page, `${tag}-27-resultado`);
  await dialog.getByRole("button", { name: "Cerrar" }).last().click();
  await page.locator('[data-catalog="felo"]').scrollIntoViewIfNeeded();
  await shot(page, `${tag}-28-no-funcionan`);
}

// Each chat's card (PLAN-v5 F4): "Descubrir" (read-only), a tie in the catalog's table that Iván resolves,
// and "Enséñame dónde está" for a chat whose model selector webllm cannot find.
async function fichas(page, tag) {
  const api = (path, body) => fetch(`http://127.0.0.1:${port}${path}`, { method: "POST",
    headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" }, body: JSON.stringify(body) });
  await api("/api/ficha/qwen/potente", { model: null }); // a previous run chose one
  await api("/api/ficha/meta/olvidar", {});
  await page.goto(base);
  const dialog = page.getByRole("dialog");
  await page.locator('[data-card="qwen"]').getByRole("button", { name: "Ficha: modelos y modos" }).click();
  await dialog.getByRole("button", { name: /^Descubrir/ }).click();
  await dialog.getByText("Empate: dime cuál").first().waitFor({ timeout: 15000 });
  await shot(page, `${tag}-29-ficha-empate`);
  await dialog.locator('[data-model="Qwen3.8-Max"]').getByRole("button", { name: "Este es el más potente" }).click();
  await dialog.getByText("El más potente (tú)").waitFor();
  await shot(page, `${tag}-30-ficha-elegido`);
  await page.keyboard.press("Escape");
  await page.locator('[data-card="meta"]').getByRole("button", { name: "Ficha: modelos y modos" }).click();
  await dialog.getByRole("button", { name: /^Descubrir/ }).click();
  await dialog.getByText("¿Falta algo? Enséñame dónde está").waitFor({ timeout: 15000 });
  await shot(page, `${tag}-31-ficha-ensename`);
  await dialog.getByRole("button", { name: "El selector de modelos" }).click();
  await page.getByText("Aprendido. Pulsa Descubrir otra vez.").waitFor({ timeout: 15000 });
  await dialog.getByRole("button", { name: "Descubrir otra vez" }).click();
  await dialog.locator('[data-model="Llama 5"]').waitFor({ timeout: 15000 });
  await shot(page, `${tag}-32-ficha-aprendida`);
  await page.keyboard.press("Escape");
}

// "Memoria en Obsidian" (PLAN-v5 F5): off, then on in a folder (a temporary one), with one question from the
// app written there (the conversation and each answer on its own), and "Reescribir todo" asking first.
async function memoria(page, tag) {
  const api = (path, body) => fetch(`http://127.0.0.1:${port}${path}`, { method: "POST",
    headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const vault = mkdtempSync(join(tmpdir(), "vault-demo-"));
  await page.goto(base);
  const card = page.locator('[data-card="memoria"]');
  await card.getByText("Apagada").waitFor();
  await card.scrollIntoViewIfNeeded();
  await shot(page, `${tag}-33-memoria-apagada`);
  await card.getByRole("textbox").fill(vault);
  await card.getByRole("button", { name: "Encender la memoria" }).click();
  await card.getByText("Guardando").waitFor();
  await page.goto(base + "#/preguntar");
  await page.getByRole("button", { name: "Probar este ejemplo" }).first().click();
  await page.waitForTimeout(500);
  await waitAnswers(page);
  await page.goto(base);
  await card.getByText(/[1-9]\d* respuestas?/).waitFor(); // the card reads the memory when Inicio opens
  await card.scrollIntoViewIfNeeded();
  await shot(page, `${tag}-34-memoria-guardando`);
  // what this run asked before the memory was on (it starts each run off) comes in: more conversations
  const count = (t) => Number((t.match(/(\d+) conversaci/) ?? [0, 0])[1]);
  const before = count(await card.innerText());
  await card.getByRole("button", { name: "Copiar también lo de antes" }).click();
  await page.waitForFunction(([n, re]) => Number((document.querySelector('[data-card="memoria"]').innerText.match(new RegExp(re)) ?? [0, 0])[1]) > n,
    [before, "(\\d+) conversaci"], { timeout: 30000 });
  await card.scrollIntoViewIfNeeded();
  await shot(page, `${tag}-35-memoria-lo-de-antes`);
  await card.getByRole("button", { name: "Reescribir todo" }).click();
  await page.getByRole("dialog").getByText("¿Reescribir todo?").waitFor();
  await shot(page, `${tag}-36-memoria-reescribir`);
  await page.getByRole("dialog").getByRole("button", { name: "Cancelar" }).click();
  const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]));
  console.log(`vault ${tag}:\n` + walk(vault).map((f) => "  " + f.slice(vault.length + 1)).join("\n"));
}

// An API AI out of free quota (OpenRouter's 429, F0): it says so, shows what the service answered
// and offers to ask another AI, which only happens when Iván presses it.
async function apiLimit(page, tag) {
  await page.goto(base + "#/preguntar");
  await page.getByRole("button", { name: /^IAs: / }).click();
  await page.getByRole("menuitem", { name: "Ninguna" }).click();
  await page.getByRole("menuitemcheckbox", { name: /Nemotron/ }).click();
  await page.keyboard.press("Escape");
  await page.getByLabel("Tu pregunta").fill("¿Qué es la inflación? (demo: límite)");
  await page.getByRole("button", { name: /^Preguntar a/ }).click();
  await waitAnswers(page);
  const card = page.getByRole("alert").filter({ hasText: "Nemotron ha llegado a su límite" });
  await card.waitFor();
  await card.scrollIntoViewIfNeeded();
  await shot(page, `${tag}-19-limite-api`);
  const other = card.getByRole("button", { name: /^Preguntar a / });
  const label = (await other.innerText()).replace(/^Preguntar a /, "").trim();
  await other.click();
  await page.getByText(`(a ${label})`).first().waitFor({ timeout: 15000 });
  await waitAnswers(page);
  await page.getByText(`(a ${label})`).first().scrollIntoViewIfNeeded();
  await shot(page, `${tag}-20-limite-otra-ia`);
}

async function run(theme, width, full) {
  const height = width === 1920 ? 1080 : 800;
  const browser = await chromium.launch({ executablePath: exe });
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme === "oscuro" ? "dark" : "light", locale: "es-ES" });
  await ctx.addInitScript((t) => localStorage.setItem("webllm.tema", t), theme);
  const page = await ctx.newPage();
  const tag = `${theme === "oscuro" ? "oscuro" : "claro"}-${width}`;
  if (full) { // the memory starts off: its scene turns it on and then copies what this run asked before
    await fetch(`http://127.0.0.1:${port}/api/memoria`, { method: "POST", body: JSON.stringify({ enabled: false }),
      headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" } });
  }

  // With Chrome connected and chats ready, the guide must NOT open by itself.
  await page.goto(base);
  await page.getByText("Tus IAs").waitFor();
  await page.waitForTimeout(1500);
  if (await page.getByText("Bienvenido a webllm").count()) report.push({ name: `${tag}-guia`, clipped: ["la guía se abrió sola con todo listo"], smallText: [] });
  await shot(page, `${tag}-01-inicio`);

  if (full) {
    await page.getByRole("button", { name: "Ver la guía otra vez" }).click();
    await page.getByText("Bienvenido a webllm").waitFor();
    await page.getByRole("button", { name: "Siguiente" }).click();
    await page.locator('[data-ai="meta"]').getByRole("button", { name: "Conectar" }).click();
    if (await page.getByText("Esperando a que entres").waitFor({ timeout: 5000 }).then(() => true, () => false)) {
      await shot(page, `${tag}-02-guia-conectar-esperando`);
    }
    await page.locator('[data-ai="meta"]').getByText("Conectada").waitFor({ timeout: 30000 });
    await shot(page, `${tag}-03-guia-conectada-sola`);
    await page.getByRole("button", { name: "Saltar la guía" }).click();
  }

  await page.goto(base + "#/preguntar");
  await page.getByText("¿A quién?").waitFor();
  if (full) {
    await shot(page, `${tag}-04-preguntar-vacio`);
    await page.getByRole("button", { name: /^IAs: / }).click();
    await page.getByRole("menuitemcheckbox").first().waitFor();
    await shot(page, `${tag}-05-elegir-ias`);
    await page.keyboard.press("Escape");
  }
  await page.getByRole("button", { name: "Probar este ejemplo" }).first().click();
  if (full) {
    await page.waitForTimeout(1800);
    await shot(page, `${tag}-06-preguntar-en-curso`);
  }
  await waitAnswers(page);
  await shot(page, `${tag}-07-preguntar-respuestas`);

  if (full) {
    await page.getByRole("button", { name: "Pásasela a…" }).first().click();
    await page.getByRole("menuitem", { name: /DeepSeek/ }).click();
    await page.getByText("Este es el mensaje que recibirá").waitFor();
    await shot(page, `${tag}-08-pasar-dialogo`);
    await page.getByRole("button", { name: /^Enviar a/ }).click();
    await page.waitForTimeout(500);
    await waitAnswers(page);
  }

  await page.goto(base + "#/historial");
  await page.getByRole("link").filter({ hasText: /Intacto|Alterado/ }).first().waitFor();
  await shot(page, `${tag}-09-historial`);
  if (full) {
    await page.getByRole("link").filter({ hasText: /Intacto|Alterado/ }).last().click();
    await page.getByText("Mensaje enviado").first().waitFor();
    await shot(page, `${tag}-10-historial-detalle`);
    await addAnAi(page, tag);
    await waitingForYou(page, tag);
    await apiLimit(page, tag);
    await stopAll(page, tag);
    await conectores(page, tag);
    await fichas(page, tag);
    await memoria(page, tag);
  }
  await browser.close();
}

for (const theme of ["claro", "oscuro"]) {
  await run(theme, 1280, true);
  await run(theme, 1920, false);
}
writeFileSync(`${out}/revision.json`, JSON.stringify(report, null, 2));
const bad = report.filter((r) => r.pageOverflow || r.mainOverflow || r.wrappedFooters || r.smallText?.length || r.clipped?.length);
console.log(`${report.length} capturas; con problemas: ${bad.length}`);
for (const b of bad) console.log(JSON.stringify(b));
if (bad.length) process.exitCode = 1;
