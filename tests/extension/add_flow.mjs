// "+ Añadir otra IA" end to end with the real extension and bridge (see harness.mjs).
//   node tests/extension/add_flow.mjs      (prints one line per check, exits 1 on failure)
import { checks, startWorld } from "./harness.mjs";

const { say, failed } = checks();
let w = null;
try {
  w = await startWorld();
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);
  const steps = (st) => st.steps.map((s) => `${s.ok ? "✓" : "✗"} ${s.text}`).join(" · ");

  // A site that works.
  const ok = await w.add(w.url("chat.pruebaia.test"));
  say(ok.status === "ok" && ok.key === "pruebaia", `añadir ${ok.name}: ${ok.status} — ${steps(ok)}${ok.detail ? ` [${ok.detail.slice(0, 300)}]` : ""}`);
  const ai = (await w.call("/api/estado")).body.ais.find((a) => a.name === "pruebaia");
  say(!!ai && ai.custom && ai.state === "lista", `aparece entre tus IAs: ${JSON.stringify(ai && { label: ai.label, custom: ai.custom, state: ai.state, icon: ai.icon, url: ai.url })}`);

  // Ask it a question after the extension "forgot" the site (as after a Chrome restart):
  // the bridge sends the site's name and address with the job.
  await w.sw.evaluate(() => delete self.WEBLLM_SITES.pruebaia);
  const done = (await w.ask("Responde solo con la palabra: pong", ["pruebaia"])).find((e) => e.type === "target_done");
  say(!!done?.ok && /pong/i.test(done.text), `pregunta a la IA añadida: ok=${done?.ok} texto=${JSON.stringify(done?.text)} (${done?.seconds} s)`);
  const after = (await w.call("/api/estado")).body.ais.find((a) => a.name === "pruebaia");
  say(after?.today === 2, `el guardián la cuenta: hoy ${after?.today} de ${after?.cap} (prueba + pregunta)`);

  // Sites that cannot be used: nothing is saved, and the reason is plain.
  const nobox = await w.add(w.url("chat.sinbox.test", "/nobox/"));
  say(nobox.status === "failed" && nobox.error === "no_input", `sin caja de texto: ${nobox.error} — «${nobox.message}»`);
  const login = await w.add(w.url("chat.conlogin.test", "/login/"));
  say(login.status === "failed" && login.error === "login_required", `pide entrar: ${login.error} — «${login.message}»`);
  const names = (await w.call("/api/estado")).body.ais.map((a) => a.name);
  say(!names.includes("sinbox") && !names.includes("conlogin"), "las que fallan no se guardan");

  // Remove it.
  const q = await w.call("/api/quitar", { ia: "pruebaia" });
  const gone = !(await w.call("/api/estado")).body.ais.some((a) => a.name === "pruebaia");
  say(q.status === 200 && gone, "quitar la IA añadida");
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-40).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
