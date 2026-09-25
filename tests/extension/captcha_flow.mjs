// Iván's report (2026-09-25): asking all the chats at once, one shows a verification; by the time
// he solves it, the app had marked chats as failed and the late answers were lost.
// Here, with the real extension and bridge (see harness.mjs): two chats asked at once, the answer
// time limit is 10 s, one chat shows a verification that "Iván" solves after 20 s. Both answers
// must arrive, the verification tab must stay in front while he works on it, and the app must
// say "te espera" meanwhile.
//   node tests/extension/captcha_flow.mjs      (prints one line per check, exits 1 on failure)
import { checks, sleep, startWorld } from "./harness.mjs";

const LIMIT_S = 10;
const SOLVE_AFTER_S = 20;
const { say, failed } = checks();
let w = null;
try {
  w = await startWorld({ limitS: LIMIT_S });
  say(w.chrome, `la extensión ${w.version} se conecta al puente (límite de respuesta: ${LIMIT_S} s)`);
  const a = await w.add(w.url("chat.captchaia.test", "/captcha/"));
  const b = await w.add(w.url("chat.otraia.test"));
  say(a.status === "ok" && b.status === "ok", `dos chats añadidos: ${a.name} (${a.status}), ${b.name} (${b.status})`);

  const t0 = Date.now();
  const asking = w.ask("¿Qué tal?", ["captchaia", "otraia"]);

  // Wait until the verification shows up, then watch what Iván sees for 20 s and solve it.
  let page = null;
  for (let i = 0; i < 60 && !page; i++) {
    await sleep(500);
    for (const p of w.ctx.pages()) {
      if (p.url().includes("captchaia.test") && (await p.locator("#solve").count().catch(() => 0))) page = p;
    }
  }
  say(!!page, `aparece la verificación en ${Math.round((Date.now() - t0) / 1000)} s`);
  const shownAt = Date.now();
  let samples = 0;
  let front = 0;
  let waitingSeen = 0;
  let otherSaysWhy = 0;
  while (Date.now() - shownAt < SOLVE_AFTER_S * 1000) {
    await sleep(1000);
    if (Date.now() - shownAt < 3000) continue; // the extension looks every 1.5 s
    samples++;
    if ((await w.frontTab())?.includes("captchaia.test")) front++;
    const ais = (await w.call("/api/estado")).body.ais;
    if (ais.find((x) => x.name === "captchaia")?.waiting === "challenge") waitingSeen++;
    if (!ais.find((x) => x.name === "otraia")?.waiting) otherSaysWhy++;
  }
  say(front === samples, `la pestaña de la verificación sigue delante mientras la resuelves: ${front} de ${samples} veces`);
  say(waitingSeen === samples, `la app sabe que ese chat te espera ("te espera"): ${waitingSeen} de ${samples} veces`);
  say(otherSaysWhy === samples, "el otro chat no aparece como si te esperase a ti");
  await page.locator("#solve").click(); // Iván solves it
  const solvedAt = Date.now();

  const events = await asking;
  const done = Object.fromEntries(events.filter((e) => e.type === "target_done").map((e) => [e.target, e]));
  const took = Math.round((Date.now() - t0) / 1000);
  say(!!done.captchaia?.ok && /hola/.test(done.captchaia.text),
    `llega la respuesta del chat con verificación: ok=${done.captchaia?.ok} ${JSON.stringify(done.captchaia?.text ?? done.captchaia?.error)} (${done.captchaia?.seconds} s)`);
  say(!!done.otraia?.ok && /hola/.test(done.otraia.text),
    `llega la respuesta del otro chat: ok=${done.otraia?.ok} ${JSON.stringify(done.otraia?.text ?? done.otraia?.error)} (${done.otraia?.seconds} s)`);
  say(took > LIMIT_S + SOLVE_AFTER_S - 5, `el tiempo resolviendo no cuenta: ${took} s en total con un límite de ${LIMIT_S} s`);
  say(Date.now() - solvedAt < 30000, `tras resolverla, todo termina en ${Math.round((Date.now() - solvedAt) / 1000)} s`);
  const after = (await w.call("/api/estado")).body.ais.find((x) => x.name === "captchaia");
  say(after && after.waiting === null && after.state === "lista", `después ya no espera y sigue lista: ${JSON.stringify(after && { waiting: after.waiting, state: after.state })}`);

  // The webllm window covered (by the app, say) or minimized while a chat writes: real chat pages
  // stop writing then. That time must not count either, and the app must say why it waits.
  // Headless Chromium never reports a covered window, so the page is told to report it
  // (document.hidden = true, as Chrome does for a covered window on Windows).
  const slow = await w.add(w.url("chat.lentaia.test", "/lento/"));
  const t1 = Date.now();
  const asking2 = w.ask("Cuéntame algo largo", ["lentaia"]);
  let writing = null;
  for (let i = 0; i < 40 && !writing; i++) {
    await sleep(250);
    for (const p of w.ctx.pages()) if (p.url().includes("lentaia.test") && (await p.locator(".msg.assistant").count().catch(() => 0))) writing = p;
  }
  const words = () => writing.evaluate(() => document.querySelector(".msg.assistant").innerText.split(/\s+/).filter(Boolean).length);
  for (let i = 0; i < 40 && (await words()) < 2; i++) await sleep(250); // cover it mid-answer
  await writing.evaluate(() => window.__setCovered(true));
  const coveredAt = Date.now();
  const wordsBefore = await words();
  let hiddenSeen = 0;
  let n = 0;
  while (Date.now() - coveredAt < SOLVE_AFTER_S * 1000) {
    await sleep(1000);
    if (Date.now() - coveredAt < 4000) continue; // the extension looks every 1.5 s
    n++;
    if ((await w.call("/api/estado")).body.ais.find((x) => x.name === "lentaia")?.waiting === "hidden") hiddenSeen++;
  }
  const wordsCovered = await words();
  await writing.evaluate(() => window.__setCovered(false));
  const slowDone = (await asking2).find((e) => e.type === "target_done");
  say(slow.status === "ok" && wordsCovered === wordsBefore && wordsBefore >= 2 && wordsBefore < 7,
    `con la ventanita tapada la web no escribe: ${wordsBefore} palabras al taparla, ${wordsCovered} ${SOLVE_AFTER_S} s después`);
  say(hiddenSeen === n, `la app dice que la ventanita está tapada: ${hiddenSeen} de ${n} veces`);
  say(!!slowDone?.ok && /del todo/.test(slowDone.text),
    `al volver a verse llega la respuesta entera: ok=${slowDone?.ok} ${JSON.stringify(slowDone?.text ?? slowDone?.error)} (${Math.round((Date.now() - t1) / 1000)} s en total, límite ${LIMIT_S} s)`);
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-40).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
