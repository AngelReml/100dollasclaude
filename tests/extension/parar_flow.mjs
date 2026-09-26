// PLAN-v5 D9/D21 "Parar": a question to a chat that writes slowly is stopped halfway (Open WebUI's stop
// button or "Parar todo"). The real extension must stop driving the page at once, the question must end
// as "lo has parado tú", and the same chat must answer the next question normally (nothing left stuck).
// Real extension + real bridge (see harness.mjs).
//   node tests/extension/parar_flow.mjs      (prints one line per check, exits 1 on failure)
import { checks, sleep, startWorld } from "./harness.mjs";

const { say, failed } = checks();
let w = null;
try {
  w = await startWorld({ limitS: 60 });
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);
  const added = await w.add(w.url("chat.lentaia.test", "/lento/"));
  say(added.status === "ok", `chat lento añadido: ${added.key} (${added.status})`);

  const gw = (text) => fetch(`${w.api}/gw/v1/chat/completions`, {
    method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
    body: JSON.stringify({ model: added.key, stream: true, messages: [{ role: "user", content: text }] }),
  }).then((r) => r.text());

  const t0 = Date.now();
  const asking = gw("Cuéntame algo");
  await sleep(4000); // the page is writing the answer, word by word
  const stop = await (await fetch(`${w.api}/gw/v1/parar`, { method: "POST", headers: { Authorization: "Bearer demo-token" } })).json();
  const tStop = Date.now();
  const text = await asking;
  const took = Math.round((Date.now() - tStop) / 100) / 10;
  say(stop.parados === 1 && stop.chats.includes(added.key), `«Parar todo» para 1 pregunta y el trabajo en Chrome (${JSON.stringify(stop)})`);
  say(/"cancelled"/.test(text) && /Lo has parado tú/.test(text) && took < 3,
    `la pregunta termina como «Lo has parado tú» en ${took} s`);
  await sleep(2500); // the extension looks every 1.5 s
  const stillDriving = await w.sw.evaluate(() => Object.keys(runningJob));
  say(!stillDriving.length, `la extensión ya no maneja la página (trabajos en curso: ${JSON.stringify(stillDriving)})`);

  const again = await gw("Otra pregunta");
  const answer = [...again.matchAll(/"content": "([^"]*)"/g)].map((m) => m[1]).join("");
  say(/esta respuesta tarda/.test(answer), `el mismo chat contesta la siguiente con normalidad: ${JSON.stringify(answer)} (${Math.round((Date.now() - t0) / 1000)} s en total)`);
} catch (e) {
  say(false, `error: ${e.stack || e}`);
} finally {
  if (failed() && w) console.log(w.log.slice(-3000));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
