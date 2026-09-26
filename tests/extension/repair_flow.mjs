// PLAN-v5 F6 with the real extension and bridge (see harness.mjs) on test chat pages that "changed their design":
//   - layer 1: a French page with a modern text box and labels in French: found and answered without help;
//   - layer 3: answers with meaningless classes and no copy button: an AI (the demo's) points at the answer in the
//     page's x-ray, it is tried on the page sending nothing, kept as a dated patch, and the answer already on the
//     page is read (the question is NOT sent twice); nothing of the conversation (the question, the answer, the
//     private titles in the sidebar) is in what the AI received; the next question needs no AI;
//   - an AI answering with code: refused, nothing kept, nothing sent again;
//   - undoing a patch: the extension stops using it at once;
//   - layer 4, "Enséñame" with 3 clicks (the text box, the send button, the answer): the clicks do nothing on the
//     page, and then the page works;
//   - "Parar" presses the site's own stop button;
//   - the daily check opens each chat and sends nothing;
//   - observer mode: "Continuar en la web" opens the conversation in a normal tab, and 2 turns written there by
//     hand are recorded in the same conversation (history and vault); "Registrar esta conversación" from the
//     extension's icon.
//   node tests/extension/repair_flow.mjs      (prints one line per check, exits 1 on failure)
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { checks, sleep, startWorld } from "./harness.mjs";

const { say, failed } = checks();
let w = null;
const lines = (file) => (existsSync(file) ? readFileSync(file, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)) : []);
try {
  const site = (key, host, path) => (url) => ({ key, name: key[0].toUpperCase() + key.slice(1), by: "Prueba", url: url(host, path),
    group: "1", purpose: "prueba", family: "Prueba", tags: ["general"], account: "no", private: true });
  const SITES = [["extranjera", "chat.extranjera.test", "/extranjera/"], ["rara", "chat.rara.test", "/rara/"],
    ["codigo", "chat.codigo.test", "/rara/codigo/"], ["ensena", "chat.ensena.test", "/rara/"], ["lenta", "chat.lenta.test", "/lento/"],
    ["observa", "chat.observa.test", "/"]];
  w = await startWorld({ limitS: 60, catalog: (url) => SITES.map(([k, h, p]) => site(k, h, p)(url)) });
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);
  const connect = async (keys) => {
    const conn = await w.call("/api/conectar-varias", { keys });
    const addTab = w.ctx.pages().find((p) => p.url().includes("add.html") && !p.isClosed()) ?? (await w.ctx.waitForEvent("page", { timeout: 15000 }));
    await addTab.waitForLoadState();
    await addTab.getByRole("button", { name: "Permitir y conectar" }).click();
    let b = conn.body;
    for (let i = 0; i < 300 && !["done", "failed"].includes(b.status); i++) { await sleep(500); b = (await w.call(`/api/conectar-varias/${b.batch_id}`)).body; }
    await addTab.close().catch(() => {});
    return Object.fromEntries(b.results.map((r) => [r.key, r.status]));
  };
  const page = (host) => w.ctx.pages().find((p) => p.url().includes(host) && !p.url().includes("popup.html"));
  const ask = async (model, content) => {
    const r = await fetch(`${w.api}/gw/v1/chat/completions`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
      body: JSON.stringify({ model, stream: false, messages: [{ role: "user", content }] }) });
    return { status: r.status, run: r.headers.get("x-webllm-run"), body: await r.json() };
  };
  const text = (r) => r.body.choices?.[0]?.message?.content ?? `(${r.body.error?.code}: ${r.body.error?.message})`;
  const sent = (host) => page(host).evaluate(() => document.querySelectorAll(".msg.user").length);
  const repairs = (siteKey) => lines(join(w.tmp, "data", "state", "reparaciones.jsonl")).filter((x) => !siteKey || x.site === siteKey);
  const prompts = () => lines(join(w.tmp, "data", "demo_reparaciones.jsonl"));
  const ficha = async (ai) => (await w.call(`/api/ficha/${ai}`)).body;

  // each part on its own: with an older extension a failure must not hide the cases after it
  const part = async (name, fn) => {
    try { await fn(); } catch (e) { say(false, `${name}: error: ${e && e.message ? e.message.split("\n")[0] : e}`); }
  };
  let f1 = {};

  // 1-3. Connecting ("Conectar varias": the "pong" test is where a changed page shows): layer 1 alone for the
  // French page; layer 3 for the page whose answers cannot be read; code from the AI refused.
  await part("conectar", async () => {
    const got = await connect(["extranjera", "rara", "codigo", "lenta", "observa"]);
    say(got.extranjera === "ok" && repairs("extranjera").length === 0,
      `capa 1: una web en francés con caja moderna («Envoyer», «Copier la réponse») se conecta sin ayuda (${got.extranjera})`);
    const fixed = repairs("rara").at(-1);
    say(got.rara === "ok" && fixed?.result === "guardada" && fixed?.ai === "zai" && (await sent("chat.rara.test")) === 1,
      `capa 3: la web cuyas respuestas no se podían leer se conecta gracias a la reparación (${fixed?.result}, IA ${fixed?.ai}, eligió ${JSON.stringify(fixed?.chosen)}); el «pong» se envió una sola vez`);
    const refused = repairs("codigo").at(-1);
    say(got.codigo !== "ok" && refused?.result === "rechazada" && /not JSON|candidate/.test(refused?.why ?? "") && (await sent("chat.codigo.test")) === 1 &&
        !(await ficha("codigo")).arreglos?.length,
      `una IA que responde con código: rechazada («${refused?.why}»), nada guardado, nada reenviado; la web queda «${got.codigo}»`);
    f1 = await ficha("rara");
    say(f1.arreglos?.[0]?.by?.includes("z.ai") && f1.arreglos[0].active && f1.arreglos[0].what === "la respuesta" && /^\d{4}-\d\d-\d\d \d\d:\d\d/.test(f1.arreglos[0].when),
      `el arreglo queda en su ficha, con fecha y quién lo hizo: ${JSON.stringify(f1.arreglos?.[0])}`);
    const before = prompts().length;
    const r1 = await ask("rara", "Otra pregunta");
    say(r1.status === 200 && text(r1) === "hola qué tal" && prompts().length === before,
      `la siguiente pregunta ya funciona sin preguntar a ninguna IA: «${text(r1)}»`);
  });

  // 4. Undo: the extension stops using the patch at once (with AI repairs off, the answer cannot be read again).
  await part("deshacer", async () => {
    await w.call("/api/reparar", { enabled: false });
    const undone = await w.call("/api/ficha/rara/deshacer", { index: f1.arreglos[0].index });
    const r2 = await ask("rara", "Y ahora?");
    say(undone.status === 200 && !undone.body.arreglos[0].active && r2.body.error?.code === "empty_answer" && repairs("rara").at(-1)?.result === "apagada",
      `«Deshacer» funciona al momento: la extensión ya no usa el arreglo; con la reparación apagada no se pregunta a ninguna IA y te dice: «${r2.body.error?.message?.slice(0, 110)}»`);
  });

  // 4b. Repairs on again, after a confidential question: repaired, read, sent once, and nothing of the
  //     conversation in what the AI received.
  await part("reparar otra vez", async () => {
    await w.call("/api/reparar", { enabled: true });
    const secret = "Pregunta confidencial número 7 sobre mi empresa";
    const n0 = await sent("chat.rara.test");
    const r3 = await ask("rara", secret);
    const n1 = await sent("chat.rara.test");
    const avisos = r3.body.webllm?.avisos ?? [];
    const seen = prompts().at(-1)?.prompt ?? "";
    const leaks = [secret, "confidencial", "hola qué tal", "Mi plan secreto", "Receta de la abuela"].filter((t) => seen.includes(t));
    say(r3.status === 200 && text(r3) === "hola qué tal" && n1 === 1 && avisos.some((a) => /había cambiado/.test(a) && /sin enviar nada/.test(a)),
      `reparada otra vez tras una pregunta: se lee, en la página hay ${n1} mensaje tuyo (se envió una vez) y la respuesta lo dice: «${avisos.find((a) => /cambiado/.test(a))?.slice(0, 100)}…»`);
    say(!!seen && leaks.length === 0 && /"kind": ?"block"/.test(seen) && /"after_your_message": ?true/.test(seen),
      `la IA solo vio la estructura de la página: ni la pregunta, ni la respuesta, ni los títulos privados de la barra lateral (fugas: ${JSON.stringify(leaks)})`);
  });

  // 5. Layer 4: "Enséñame" with 3 clicks, on a page connected with the AI repairs off.
  await part("enséñame", async () => {
    await w.call("/api/reparar", { enabled: false });
    const e0 = await connect(["ensena"]);
    const p5 = page("chat.ensena.test");
    const b5 = await p5.evaluate(() => document.querySelectorAll(".msg.user").length);
    const teachOne = async (what, sel) => {
      const pending = w.call("/api/ensename", { ia: "ensena", what });
      for (let i = 0; i < 40 && !(await p5.evaluate(() => !!document.querySelector("[data-webllm-teach]")).catch(() => false)); i++) await sleep(250);
      await p5.locator(sel).last().click();
      return pending;
    };
    const t1 = await teachOne("input", "#box");
    const t2 = await teachOne("send", "#send");
    const t3 = await teachOne("answer", ".x1");
    const a5 = await p5.evaluate(() => document.querySelectorAll(".msg.user").length);
    const e1 = await connect(["ensena"]);
    const e2 = await ask("ensena", "Segunda");
    const fe = await ficha("ensena");
    say(e0.ensena !== "ok" && [t1, t2, t3].every((t) => t.status === 200) && b5 === a5 && e1.ensena === "ok" && e2.status === 200 &&
        text(e2) === "hola qué tal" && fe.arreglos.filter((a) => a.by === "tú").length === 3,
      `capa 4, «Enséñame» con 3 clics (caja, enviar, respuesta): tus clics no envían nada (${b5} → ${a5}), la web se conecta (${e0.ensena} → ${e1.ensena}) y responde: «${text(e2)}»`);
    await w.call("/api/reparar", { enabled: true });
  });

  // 6. "Parar" presses the site's own stop button.
  await part("parar", async () => {
    const stopping = ask("lenta", "Algo largo");
    let writing = false;
    for (let i = 0; i < 60 && !writing; i++) { await sleep(250); writing = await page("chat.lenta.test")?.evaluate(() => !!document.querySelector("[aria-label='Stop generating']")).catch(() => false); }
    await sleep(1500);
    await fetch(`${w.api}/gw/v1/parar`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" }, body: "{}" });
    const stoppedAnswer = await stopping;
    await sleep(2500);
    const stoppedPage = await page("chat.lenta.test").evaluate(() => ({ stopped: !!window.__stopped, clicks: window.__clicks }));
    say(stoppedAnswer.body.error?.code === "cancelled" && stoppedPage.stopped && stoppedPage.clicks.includes("Stop generating"),
      `«Parar» pulsa también el botón de parar de la web (clics en la página: ${JSON.stringify(stoppedPage.clicks)})`);
  });

  // 7. The daily check: each chat opened and looked at; nothing sent.
  await part("comprobación diaria", async () => {
    await w.call("/api/revisar", {});
    let rev = (await w.call("/api/revision")).body;
    for (let i = 0; i < 240 && rev.running; i++) { await sleep(500); rev = (await w.call("/api/revision")).body; }
    const mineChecked = rev.sites.filter((x) => SITES.some(([k]) => k === x.site));  // (the real Qwen, z.ai… cannot open here)
    const connected = SITES.filter(([k]) => k !== "codigo");
    const sentOnCheck = await Promise.all(connected.map(([, h]) => page(h)?.evaluate(() => document.querySelectorAll(".msg.user").length).catch(() => -1)));
    say(!rev.running && mineChecked.length === connected.length && mineChecked.every((x) => x.state === "bien") && sentOnCheck.every((n) => n === 0),
      `la comprobación diaria abre cada chat conectado y no envía nada: ${mineChecked.map((x) => `${x.site}:${x.state}`).join(", ")}`);
  });

  // 8. Observer: "Continuar en la web", then 2 turns written by hand in that tab (with the memory on).
  await part("observador", async () => {
    const vaultDir = join(w.tmp, "vault");
    mkdirSync(vaultDir);
    await w.call("/api/memoria", { dir: vaultDir, enabled: true });
    await w.call("/api/reparar", { enabled: true });
    const o0 = await ask("observa", "Empiezo aquí");
    const cont = await w.call("/api/continuar", { run_id: o0.run });
    let tab = null;
    for (let i = 0; i < 60 && !tab; i++) {
      await sleep(250);
      for (const p of w.ctx.pages()) {
        if (p.url().includes("chat.observa.test") && (await p.evaluate(() => !!document.querySelector("[data-webllm-observe]")).catch(() => false))) tab = p;
      }
    }
    const small = await w.frontTab();
    for (const q of ["Segunda pregunta, escrita a mano", "Tercera pregunta, también a mano"]) {
      await tab.locator("#box").fill(q);
      await tab.locator("#box").press("Enter");
      await tab.waitForFunction((n) => document.querySelectorAll(".msg.user").length === n && document.querySelector("[aria-label='Copy response']"), q.startsWith("Segunda") ? 1 : 2, { timeout: 20000 });
      await sleep(9000);  // the observer waits for the answer to be stable
    }
    const runs = readdirSync(join(w.tmp, "data", "runs")).map((d) => lines(join(w.tmp, "data", "runs", d, "journal.jsonl"))).filter((l) => l[0]?.kind === "observed");
    const turns = runs.map((l) => ({ follows: l[0].follows, by: l.find((x) => x.kind === "flow")?.by, status: l.find((x) => x.kind === "flow")?.status }));
    if (runs.length !== 2) console.log("observador:", JSON.stringify(cont), await w.sw.evaluate(() => JSON.stringify(observers)).catch((e) => String(e)),
      w.log.split("\n").filter((l) => /Observ/.test(l)).join("\n"));
    say(cont.status === 200 && tab && runs.length === 2 && turns.every((t) => t.follows === o0.run && t.by === "ivan" && t.status === "ok"),
      `«Continuar en la web» abre la conversación en una pestaña normal (la ventanita sigue en ${small ? "su sitio" : "?"}) y 2 turnos escritos a mano quedan en la misma conversación: ${JSON.stringify(turns)}`);
    const notes = readdirSync(join(vaultDir, "webllm", "Desde webllm")).map((f) => readFileSync(join(vaultDir, "webllm", "Desde webllm", f), "utf8"));
    const note = notes.find((t) => t.includes("Empiezo aquí"));
    say(!!note && note.includes("Segunda pregunta, escrita a mano") && note.includes("Tercera pregunta, también a mano") && (note.match(/en la web de Observa/g) ?? []).length === 2,
      "la conversación entera (la pregunta de webllm y tus 2 turnos en la web) está en la misma nota del vault");
  });

  // 9. "Registrar esta conversación" from the extension's icon, in a chat Iván opened himself.
  await part("registrar", async () => {
    const mine = await w.ctx.newPage();
    await mine.goto(w.url("chat.observa.test", "/?propia=1"));  // (step 8's tab is still on "/")
    const tabId = await w.sw.evaluate(async (u) => (await chrome.tabs.query({})).find((t) => t.url === u)?.id, mine.url());
    const extId = new URL(w.sw.url()).host;
    const popup = await w.ctx.newPage();
    await popup.goto(`chrome-extension://${extId}/popup.html?tab=${tabId}`);
    await popup.getByText(/Si registras|webllm está registrando|no es un chat|no tiene permiso|No pude/).first().waitFor({ timeout: 10000 });
    const said = await popup.locator("#msg").innerText();
    if (!/Si registras/.test(said)) console.log("popup dice:", said, "tab", tabId);
    await popup.getByRole("button", { name: "Registrar esta conversación" }).click();
    await popup.getByRole("button", { name: "Dejar de registrar" }).waitFor({ timeout: 10000 });
    await mine.bringToFront();
    await mine.locator("#box").fill("Una conversación que abrí yo");
    await mine.locator("#box").press("Enter");
    let own = [];
    for (let i = 0; i < 80 && !own.length; i++) {
      await sleep(500);
      own = readdirSync(join(w.tmp, "data", "runs")).map((d) => lines(join(w.tmp, "data", "runs", d, "journal.jsonl")))
        .filter((l) => l[0]?.kind === "observed" && !l[0].follows);
    }
    await popup.reload();
    await popup.getByRole("button", { name: "Dejar de registrar" }).click();
    await popup.getByRole("button", { name: "Registrar esta conversación" }).waitFor({ timeout: 10000 });
    const badgeGone = await mine.evaluate(() => !document.querySelector("[data-webllm-observe]"));
    say(own.length === 1 && own[0].find((x) => x.kind === "flow")?.by === "ivan" && badgeGone,
      "«Registrar esta conversación» desde el icono de la extensión: se guarda lo que escribes, y «Dejar de registrar» lo para (y quita el aviso de la página)");
  });
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-60).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
