// PLAN-v5 F4 with the real extension and bridge (see harness.mjs) on the extended test chat page
// (fake_chat.html ?completa=1: a model selector, a "+" menu, mode toggles, file upload, a download in each
// answer, and "Publicar"/"Compartir" buttons; every click on the page is logged):
//   - "Descubrir" lists everything and presses no option and sends nothing;
//   - model and modes are put and confirmed on the page; with a selector that "does not change", nothing
//     is sent and it says why; a page without file upload: nothing is sent either;
//   - a PDF, an image and a 20 MB file reach the page with the same sha256;
//   - "Publicar" / "Compartir" are never pressed;
//   - a file the page made is saved and linked;
//   - "Enséñame dónde está": Iván's click on a nameless selector teaches it (and does nothing on the page).
//   node tests/extension/capabilities_flow.mjs      (prints one line per check, exits 1 on failure)
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { checks, sleep, startWorld } from "./harness.mjs";

const { say, failed } = checks();
const sha = (b) => createHash("sha256").update(b).digest("hex");
const b64 = (b) => Buffer.from(b).toString("base64");
let w = null;
try {
  const site = (key, host, path, extra = {}) => (url) => ({ key, name: key[0].toUpperCase() + key.slice(1), by: "Prueba",
    url: url(host, path), group: "1", purpose: "prueba", family: "Prueba", tags: ["general"], account: "no", private: true, ...extra });
  w = await startWorld({
    limitS: 60,
    catalog: (url) => [
      site("completa", "chat.completa.test", "/completa/", { models: [{ match: "ultra", rank: 1 }, { match: "pro", rank: 2 }],
        models_source: "prueba", models_checked: "2026-09-26" })(url),
      site("roto", "chat.roto.test", "/completa/selectorroto/")(url),
      site("sinarch", "chat.sinarch.test", "/completa/sinarchivos/")(url),
      site("oculto", "chat.oculto.test", "/completa/modelooculto/")(url),
    ],
  });
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);
  const conn = await w.call("/api/conectar-varias", { keys: ["completa", "roto", "sinarch", "oculto"] });
  const tab = w.ctx.pages().find((p) => p.url().includes("add.html")) ?? (await w.ctx.waitForEvent("page", { timeout: 15000 }));
  await tab.waitForLoadState();
  await tab.getByRole("button", { name: "Permitir y conectar" }).click();
  let b = conn.body;
  for (let i = 0; i < 240 && !["done", "failed"].includes(b.status); i++) { await sleep(500); b = (await w.call(`/api/conectar-varias/${b.batch_id}`)).body; }
  say(b.connected === 4, `las cuatro webs de prueba conectadas (${b.results.map((r) => `${r.key}:${r.status}`).join(", ")})`);
  const page = (host) => w.ctx.pages().find((p) => p.url().includes(host));

  // 1. Descubrir: read-only. (It opens the chat afresh, so the page's click log starts empty.)
  const d = await w.call("/api/descubrir", { ia: "completa" });
  const f = d.body;
  const p1 = page("chat.completa.test");
  const clicks = await p1.evaluate(() => window.__clicks);
  const sent = await p1.evaluate(() => document.querySelectorAll(".msg.user").length);
  const menusOpen = await p1.evaluate(() => document.querySelectorAll("[role='menu']").length);
  const options = ["Modelo Pro", "Modelo Ultra", "Subir archivo", "Investigación profunda", "Crear imagen", "Publicar", "Compartir conversación", "Pensar", "Buscar en la web"];
  const pressed = clicks.filter((c) => options.includes(c));
  const openedMenus = clicks.filter((c) => /Modelo Rápido ▾|Adjuntar y más/.test(c));
  say(d.status === 200 && JSON.stringify(f.models.map((m) => m.name).sort()) === JSON.stringify(["Modelo Pro", "Modelo Rápido", "Modelo Ultra"]) &&
      f.plus.length === 3 && f.modes.map((m) => m.name).join() === "Pensar,Buscar en la web" && f.files[0].accept.includes(".pdf"),
    `«Descubrir» lo lista todo: modelos ${JSON.stringify(f.models?.map((m) => m.name))}, «+» ${JSON.stringify(f.plus)}, modos ${JSON.stringify(f.modes?.map((m) => m.name))}, archivos ${f.files?.[0]?.accept}`);
  say(openedMenus.length >= 2 && pressed.length === 0 && sent === 0 && menusOpen === 0,
    `al descubrir solo abre y cierra menús: clics ${JSON.stringify(clicks)}; opciones pulsadas ${pressed.length}; mensajes enviados ${sent}; menús abiertos ${menusOpen}`);
  say(f.strongest === "Modelo Ultra" && f.models[0].strongest && f.models.find((m) => m.name === "Modelo Rápido")?.known === false,
    `el más potente según su tabla: ${f.strongest}; «Modelo Rápido» sale como nuevo, sin datos`);

  // 2. A question from Open WebUI's side (the gateway): the strongest model, two modes, three files.
  const pdf = Buffer.from("%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n");
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");
  const big = Buffer.alloc(20 * 1024 * 1024, 7);
  big.write("webllm", 12345);
  const files = [["prueba.pdf", "application/pdf", pdf], ["prueba.png", "image/png", png], ["grande.bin", "application/octet-stream", big]]
    .map(([name, mime, data]) => ({ name, mime, data: b64(data), sha256: sha(data) }));
  const t0 = Date.now();
  const r = await fetch(`${w.api}/gw/v1/chat/completions`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
    body: JSON.stringify({ model: "completa", stream: false, messages: [{ role: "user", content: "¿Qué recibiste?" }], webllm: { modes: ["pensar", "investigar"], files } }) });
  const ans = await r.json();
  const text = ans.choices?.[0]?.message?.content ?? JSON.stringify(ans);
  const p2 = page("chat.completa.test");
  const received = await p2.evaluate(() => window.__received);
  say(r.status === 200 && /modelo=Modelo Ultra/.test(text) && /modos=pensar,investigar/.test(text),
    `modelo y modos puestos y confirmados en la página: «${text.slice(0, 120)}» (${Math.round((Date.now() - t0) / 1000)} s)`);
  say(JSON.stringify(received?.map((x) => x.sha256)) === JSON.stringify(files.map((x) => x.sha256)),
    `el PDF, la imagen y el archivo de 20 MB llegan a la web con la misma huella: ${JSON.stringify(received?.map((x) => [x.name, x.size, x.sha256.slice(0, 10)]))}`);
  const avisos = ans.webllm?.avisos ?? [];
  say(avisos.some((a) => /Modelo Ultra/.test(a) && /comprobado en su web/.test(a)) && avisos.some((a) => /se subieron a/.test(a)),
    `la respuesta dice lo que se usó de verdad: ${JSON.stringify(avisos)}`);
  const made = avisos.find((a) => /generó «informe.txt»/.test(a));
  const path = made?.match(/guardado en (.+)\.$/)?.[1];
  const expected = await p2.evaluate(() => window.__lastDownload);
  say(!!path && readFileSync(path, "utf8") === expected, `lo que genera la web se guarda y se enlaza: ${path}`);
  const allClicks = await p2.evaluate(() => window.__clicks);
  say(!allClicks.some((c) => /Publicar|Compartir/.test(c)), `«Publicar» y «Compartir» no se pulsan nunca (${allClicks.length} clics en la página)`);
  const run = r.headers.get("x-webllm-run");
  const journal = readFileSync(`${w.tmp}/data/runs/${run}/journal.jsonl`, "utf8").trim().split("\n").map((l) => JSON.parse(l));
  const call = journal.find((l) => l.kind === "flow");
  say(call?.used?.model === "Modelo Ultra" && call.used.files.length === 3 && call.downloads?.length === 1,
    `el registro guarda modelo, modos, archivos (huellas) y descarga: ${JSON.stringify({ model: call?.used?.model, modes: call?.used?.modes?.map((m) => m.mode), files: call?.used?.files?.map((x) => x.sha256.slice(0, 8)) })}`);

  // 3. What the page does not confirm is never sent.
  await w.call("/api/descubrir", { ia: "roto" });
  const bad = await fetch(`${w.api}/gw/v1/chat/completions`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
    body: JSON.stringify({ model: "roto@modelopro", stream: false, messages: [{ role: "user", content: "hola" }] }) });
  const badBody = await bad.json();
  const rotoSent = await page("chat.roto.test").evaluate(() => document.querySelectorAll(".msg.user").length);
  say(badBody.error?.code === "not_confirmed" && rotoSent === 0, `con un selector que no cambia no se envía nada: ${badBody.error?.code} — «${badBody.error?.message?.slice(0, 90)}»`);
  const noUp = await fetch(`${w.api}/gw/v1/chat/completions`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
    body: JSON.stringify({ model: "sinarch", stream: false, messages: [{ role: "user", content: "hola" }], webllm: { files: [files[1]] } }) });
  const noUpBody = await noUp.json();
  const sinSent = await page("chat.sinarch.test").evaluate(() => document.querySelectorAll(".msg.user").length);
  say(noUpBody.error?.code === "file_not_attached" && sinSent === 0, `una web que no deja subir archivos: no se envía nada — «${noUpBody.error?.message?.slice(0, 80)}»`);

  // 4. "Enséñame dónde está": the model selector is a nameless ⚙; Iván clicks it once.
  const f0 = (await w.call("/api/descubrir", { ia: "oculto" })).body;
  const teaching = w.call("/api/ensename", { ia: "oculto", what: "model" });
  let banner = false;
  for (let i = 0; i < 40 && !banner; i++) { await sleep(250); banner = await page("chat.oculto.test").evaluate(() => !!document.querySelector("[data-webllm-teach]")).catch(() => false); }
  const p4 = page("chat.oculto.test");
  await p4.locator("#modelo").click();
  const taught = await teaching;
  const openedByTeach = await p4.evaluate(() => document.querySelectorAll("[role='menu']").length);
  const f1 = (await w.call("/api/descubrir", { ia: "oculto" })).body;
  say(!f0.found.model && banner && taught.status === 200 && openedByTeach === 0 && f1.models.length === 3,
    `«Enséñame»: sin él no encuentra el selector; tu clic no hace nada en la web (menús abiertos: ${openedByTeach}) y después lee ${f1.models.length} modelos`);
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-40).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
