// PLAN-v5 F3 "Conectar varias" with the real extension and bridge (see harness.mjs), on three chat sites
// of a test catalog: one connects at once, one asks to log in and connects when "Iván" logs in (he clicks
// "Sign in" himself: webllm types nothing), one has no text box and stays "No funciona todavía" with its
// diagnosis. ONE permission request for the three (Chrome's prompt itself is simulated, as in 7b).
//   node tests/extension/catalog_flow.mjs      (prints one line per check, exits 1 on failure)
import { checks, sleep, startWorld } from "./harness.mjs";

const { say, failed } = checks();
let w = null;
try {
  w = await startWorld({
    loginWaitS: 60,
    catalog: (url) => [
      { key: "primera", name: "Primera", by: "Prueba", url: url("chat.primera.test"), group: "1", purpose: "prueba",
        family: "Prueba", tags: ["general"], account: "no", private: true },
      { key: "entrar", name: "ConCuenta", by: "Prueba", url: url("chat.entrar.test", "/entrar/"), group: "1",
        purpose: "prueba", family: "Prueba", tags: ["general"], account: "si", private: true },
      { key: "sinbox", name: "SinCaja", by: "Prueba", url: url("chat.sinbox.test", "/nobox/"), group: "2",
        purpose: "prueba", family: "Prueba", tags: ["general"], account: "desconocido", private: true, may_fail: "prueba" },
      { key: "otracuenta", name: "OtraCuenta", by: "Prueba", url: url("chat.otracuenta.test", "/redirige/"), group: "1",
        purpose: "prueba", family: "Prueba", tags: ["general"], account: "si", private: true },
      { key: "mudada", name: "Mudada", by: "Prueba", url: url("chat.mudada.test", "/mudada/"), group: "1",
        purpose: "prueba", family: "Prueba", tags: ["general"], account: "desconocido", private: true },
    ],
  });
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);

  const start = await w.call("/api/conectar-varias", { keys: ["primera", "entrar", "sinbox", "otracuenta", "mudada"] });
  say(start.status === 200 && start.body.status === "permission", `«Conectar varias» empieza pidiendo permiso (${start.status} ${start.body.status})`);
  const id = start.body.batch_id;

  // Iván's click on the permission page; count how many times it asks Chrome, and for what.
  const tab = w.ctx.pages().find((p) => p.url().includes("add.html")) ?? (await w.ctx.waitForEvent("page", { timeout: 15000 }));
  await tab.waitForLoadState();
  const listed = await tab.locator("#list li").allInnerTexts();
  await tab.evaluate(() => {
    const real = chrome.permissions.request.bind(chrome.permissions);
    window.__asked = [];
    chrome.permissions.request = (arg) => { window.__asked.push(arg); return real(arg); };
  });
  await tab.getByRole("button", { name: "Permitir y conectar" }).click();
  await sleep(300);
  const asked = await tab.evaluate(() => window.__asked).catch(() => null);
  say(listed.length === 5 && asked?.length === 1 && asked[0].origins.length === 5,
    `una sola petición de permiso para las cinco: ${JSON.stringify(asked?.map((a) => a.origins.map((o) => o.replace(/:\d+\//, "/"))))}`);

  // The one that asks to log in: shown to Iván, in front, waiting; he logs in himself.
  let b = start.body;
  for (let i = 0; i < 120; i++) {
    b = (await w.call(`/api/conectar-varias/${id}`)).body;
    const r = b.results.find((x) => x.key === "entrar");
    if (r?.steps?.some((s) => s.step === "login" && s.ok === null)) break;
    await sleep(500);
  }
  const waiting = b.results.find((x) => x.key === "entrar");
  const front = await w.frontTab();
  say(b.current === "entrar" && waiting?.steps?.some((s) => s.step === "login") && /chat\.entrar\.test/.test(front ?? ""),
    `la que pide entrar se enseña y te espera: ${waiting?.steps?.map((s) => s.text).join(" · ")} (delante: ${front?.replace(/:\d+/, "")})`);
  await sleep(3000); // Iván takes a moment
  const login = w.ctx.pages().find((p) => p.url().includes("chat.entrar.test"));
  const typed = await login.evaluate(() => [document.getElementById("email")?.value, document.getElementById("password")?.value]);
  say(typed.every((v) => v === ""), `webllm no escribe nada en la pantalla de acceso (email y contraseña vacíos: ${JSON.stringify(typed)})`);
  await login.getByRole("button", { name: "Sign in" }).click();

  // The one that sends you to another address to log in (like Google): webllm waits, Iván logs in there.
  for (let i = 0; i < 120; i++) {
    b = (await w.call(`/api/conectar-varias/${id}`)).body;
    if (b.results.find((x) => x.key === "otracuenta")?.steps?.some((s) => s.step === "login" && s.ok === null)) break;
    await sleep(500);
  }
  const elsewhere = await w.frontTab();
  say(/accounts\.cuentas\.test(:\d+)?\/signin/.test(elsewhere ?? ""), `la que te manda a otra dirección para entrar te espera allí: ${elsewhere?.replace(/:\d+/, "").slice(0, 60)}`);
  await sleep(2000);
  const accounts = w.ctx.pages().find((p) => p.url().includes("accounts.cuentas.test"));
  await accounts.getByRole("button", { name: "Sign in" }).click();

  for (let i = 0; i < 240 && !["done", "failed"].includes(b.status); i++) {
    await sleep(500);
    b = (await w.call(`/api/conectar-varias/${id}`)).body;
  }
  const by = Object.fromEntries(b.results.map((r) => [r.key, r]));
  say(b.status === "done" && by.primera.status === "ok", `la primera conecta a la primera: ${by.primera.status}`);
  say(by.entrar.status === "ok", `la que pedía entrar conecta cuando entras: ${by.entrar.status} — ${by.entrar.message}`);
  const cat = (await w.call("/api/catalogo")).body.ais;
  const sinbox = cat.find((a) => a.key === "sinbox");
  say(by.sinbox.status === "no_funciona" && sinbox.state === "no_funciona" && sinbox.diagnosis_saved,
    `la que no tiene caja queda «No funciona todavía» con su diagnóstico guardado: «${sinbox.message}»`);
  say(by.otracuenta.status === "ok", `y conecta cuando vuelves de entrar: ${by.otracuenta.status} — ${by.otracuenta.message}`);
  say(by.mudada.status === "no_funciona" && /nueva\.test/.test(by.mudada.message),
    `la que se ha mudado no se queda esperando: dice adónde lleva — «${by.mudada.message.replace(/:\d+/, "")}»`);

  // The connected ones are AIs now: each answered its "pong" through the guard, and they answer questions.
  const ais = (await w.call("/api/estado")).body.ais;
  const mine = ais.filter((a) => ["primera", "entrar", "otracuenta"].includes(a.name));
  say(mine.length === 3 && mine.every((a) => a.catalog && a.today === 1) && !ais.some((a) => ["sinbox", "mudada"].includes(a.name)),
    `solo las conectadas son tus IAs, cada una con 1 mensaje (la prueba): ${JSON.stringify(mine.map((a) => [a.name, a.today, a.cap]))}`);
  const done = (await w.ask("Responde solo con la palabra: pong", ["entrar"])).find((e) => e.type === "target_done");
  say(!!done?.ok && /pong/i.test(done.text), `la que pedía entrar contesta una pregunta: ok=${done?.ok} ${JSON.stringify(done?.text)}`);
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-40).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
