// Screenshots + layout checks of every screen, light and dark, at 1280 and 1920 px.
//   python scripts/app_demo.py --port 20199      (in another terminal)
//   node app/scripts/screenshots.mjs [outDir] [port]
// Uses the Chromium that Playwright finds (PLAYWRIGHT_CHROMIUM or /opt/pw-browsers).
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync } from "node:fs";

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
  await page.waitForFunction(() => !document.body.innerText.match(/Esperando…|En cola/), null, { timeout: 60000 });
}

async function run(theme, width, full) {
  const height = width === 1920 ? 1080 : 800;
  const browser = await chromium.launch({ executablePath: exe });
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme === "oscuro" ? "dark" : "light", locale: "es-ES" });
  await ctx.addInitScript((t) => localStorage.setItem("webllm.tema", t), theme);
  const page = await ctx.newPage();
  const tag = `${theme === "oscuro" ? "oscuro" : "claro"}-${width}`;

  await page.goto(base);
  if (full) {
    await page.getByText("Bienvenido a webllm").waitFor();
    await shot(page, `${tag}-01-guia-paso1`);
    await page.getByRole("button", { name: "Siguiente" }).click();
    for (const ai of ["qwen", "meta"]) {
      await page.locator(`[data-ai="${ai}"]`).getByRole("button", { name: "Comprobar" }).click();
    }
    await page.getByText("Sesión abierta").first().waitFor();
    await page.getByText("Sin sesión").first().waitFor();
    await shot(page, `${tag}-02-guia-paso2`);
  }
  await page.getByRole("button", { name: "Saltar la guía" }).click();

  await page.goto(base + "#/");
  await page.getByText("Tus IAs").waitFor();
  await shot(page, `${tag}-03-inicio`);

  await page.goto(base + "#/preguntar");
  await page.getByText("¿A quién?").waitFor();
  if (full) await shot(page, `${tag}-04-preguntar-vacio`);
  await page.getByRole("button", { name: "Probar este ejemplo" }).first().click();
  if (full) {
    await page.waitForTimeout(1800);
    await shot(page, `${tag}-05-preguntar-en-curso`);
  }
  await waitAnswers(page);
  await shot(page, `${tag}-06-preguntar-respuestas`);

  if (full) {
    await page.getByRole("button", { name: "Pásasela a…" }).first().click();
    await page.getByRole("menuitem", { name: /DeepSeek/ }).click();
    await page.getByText("Este es el mensaje que recibirá").waitFor();
    await shot(page, `${tag}-07-pasar-dialogo`);
    await page.getByRole("button", { name: /^Enviar a/ }).click();
    await page.waitForTimeout(500);
    await waitAnswers(page);
    await shot(page, `${tag}-08-pasar-respuesta`);
  }

  await page.goto(base + "#/historial");
  await page.getByRole("link").filter({ hasText: /Intacto|Alterado/ }).first().waitFor();
  await shot(page, `${tag}-09-historial`);
  if (full) {
    await page.getByRole("link").filter({ hasText: /Intacto|Alterado/ }).last().click();
    await page.getByText("Mensaje enviado").first().waitFor();
    await shot(page, `${tag}-10-historial-detalle`);
  }
  await browser.close();
}

for (const theme of ["claro", "oscuro"]) {
  await run(theme, 1280, true);
  await run(theme, 1920, false);
}
writeFileSync(`${out}/revision.json`, JSON.stringify(report, null, 2));
const bad = report.filter((r) => r.pageOverflow || r.mainOverflow || r.wrappedFooters || r.smallText.length || r.clipped.length);
console.log(`${report.length} capturas; con problemas: ${bad.length}`);
for (const b of bad) console.log(JSON.stringify(b));
if (bad.length) process.exitCode = 1;
