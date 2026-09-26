// Iván's report (2026-09-25): Meta AI (in Spanish) had fully written its answer, but webllm kept
// waiting and the answer never reached the app. webllm decides "finished" when the chat's "stop"
// button goes away; four ways a page can keep something that looks like "stop" on screen:
//   stopfijo        "Detener" is never removed after the answer (the page only adds "Copiar")
//   stopfuera       "Detener" is moved off-screen instead of removed
//   clasestop       a button whose class contains "stop" ("nonstop-toggle")
//   detenersiempre  a "Detener lectura en voz alta" button, there even before anything is asked
// Real extension + real bridge (see harness.mjs). Every answer must arrive, well inside the limit.
//   node tests/extension/stuck_stop.mjs      (prints one line per check, exits 1 on failure)
import { checks, startWorld } from "./harness.mjs";

const LIMIT_S = 45;
const CASES = [
  ["stopfijo", "«Detener» se queda después de responder"],
  ["stopfuera", "«Detener» se esconde fuera de la pantalla"],
  ["clasestop", "un botón con «stop» en su clase"],
  ["detenersiempre", "un «Detener lectura» fijo desde el principio"],
];
const { say, failed } = checks();
let w = null;
try {
  w = await startWorld({ limitS: LIMIT_S });
  say(w.chrome, `la extensión ${w.version} se conecta al puente (límite de respuesta: ${LIMIT_S} s)`);
  for (const [mode, what] of CASES) {
    const added = await w.add(w.url(`chat.${mode}.test`, `/${mode}/`));
    const t0 = Date.now();
    const events = added.status === "ok" ? await w.ask("¿Qué tal?", [added.key]) : [];
    const done = events.find((e) => e.type === "target_done");
    const took = Math.round((Date.now() - t0) / 1000);
    say(!!done?.ok && /hola qué tal/.test(done.text) && took < LIMIT_S,
      `${what}: ${added.status === "ok" ? `llega la respuesta en ${took} s: ${JSON.stringify(done?.text ?? done?.error)}`
                                          : `no se pudo añadir (${added.error ?? added.status})`}`);
    say(added.status === "ok", `${what}: la prueba de «Añadir» también termina (${added.status})`);
  }
} catch (e) {
  say(false, `error: ${e.stack || e}`);
} finally {
  if (failed() && w) console.log(w.log.slice(-3000));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
