// PLAN-v5 F7 with the real extension and bridge (see harness.mjs): "seguir en la misma conversación", what the
// Committee needs (the role in turn 1, the problem in turn 2, in the same chat). The test page's /conversa/ mode
// gives each conversation its own address (/conversa/c/<id>) and restores it when that address is opened again;
// an address it does not know sends you to a new chat, like real sites do.
//   - two turns in the same chat: the second is typed in the conversation of the first, and its answer (not the
//     first one) is what comes back; the guard counts 2 messages;
//   - a conversation the page no longer has: nothing is typed anywhere, and it says why;
//   - an address of another site: refused, nothing typed;
//   - a page that takes 15 s to start answering and shows no "stop" button: the new answer is read, never the one
//     that was already on the page (with the previous extension the previous answer came back as the new one).
//   node tests/extension/conversation_flow.mjs      (prints one line per check, exits 1 on failure)
import { checks, sleep, startWorld } from "./harness.mjs";

const { say, failed } = checks();
let w = null;
const part = async (name, fn) => {
  try { await fn(); } catch (e) { say(false, `${name}: error: ${e && e.message ? e.message.split("\n")[0] : e}`); }
};
try {
  const site = (key, host, path) => (url) => ({ key, name: key[0].toUpperCase() + key.slice(1), by: "Prueba", url: url(host, path),
    group: "1", purpose: "prueba", family: "Prueba", tags: ["general"], account: "no", private: true });
  w = await startWorld({ limitS: 60, catalog: (url) => [site("conversa", "chat.conversa.test", "/conversa/")(url),
                                                        site("tarda", "chat.tarda.test", "/conversa/tarda/")(url)] });
  say(w.chrome, `la extensión ${w.version} se conecta al puente`);
  const conn = await w.call("/api/conectar-varias", { keys: ["conversa", "tarda"] });
  const addTab = w.ctx.pages().find((p) => p.url().includes("add.html")) ?? (await w.ctx.waitForEvent("page", { timeout: 15000 }));
  await addTab.waitForLoadState();
  await addTab.getByRole("button", { name: "Permitir y conectar" }).click();
  let b = conn.body;
  for (let i = 0; i < 240 && !["done", "failed"].includes(b.status); i++) { await sleep(500); b = (await w.call(`/api/conectar-varias/${b.batch_id}`)).body; }
  await addTab.close().catch(() => {});
  const page = (host) => w.ctx.pages().find((p) => p.url().includes(host));
  // the bridge's own endpoint (the one the Committee uses): webllm.continue_url = back to that conversation
  const ask = async (siteKey, content, extra = {}) => {
    const r = await fetch(`${w.api}/v1/chat/completions`, { method: "POST", headers: { Authorization: "Bearer demo-token", "Content-Type": "application/json" },
      body: JSON.stringify({ model: `browser/${siteKey}`, stream: false, messages: [{ role: "user", content }], webllm: extra }) });
    const body = await r.json();
    return { status: r.status, body, text: body.choices?.[0]?.message?.content ?? `(${body.error?.code}: ${body.error?.message})`,
             url: body.webllm?.url ?? null };
  };
  const users = (host) => page(host).evaluate(() => [...document.querySelectorAll(".msg.user")].map((x) => x.innerText));
  const count = async (siteKey) => ((await w.call("/api/estado")).body.ais.find((a) => a.name === siteKey) || {}).today;

  // 1. Two turns in the same chat.
  await part("dos turnos", async () => {
    const before = await count("conversa");
    const a = await ask("conversa", "Primera pregunta");
    const b2 = await ask("conversa", "Segunda pregunta", { continue_url: a.url });
    const p = page("chat.conversa.test");
    const seen = await users("chat.conversa.test");
    const after = await count("conversa");
    say(a.status === 200 && /\/conversa\/c\/\w+$/.test(a.url || "") && b2.status === 200 && b2.text === "Respuesta 2 a «Segunda pregunta»" &&
        p.url() === a.url && JSON.stringify(seen) === JSON.stringify(["Primera pregunta", "Segunda pregunta"]) && after - before === 2,
      `dos turnos en el mismo chat: «${a.text}» y luego «${b2.text}», en ${a.url?.replace(/^https:\/\/[^/]+/, "")}; en la página: ${JSON.stringify(seen)}; el guardián contó ${after - before}`);
  });

  // 2. A conversation the page no longer has: nothing typed anywhere.
  await part("conversación perdida", async () => {
    const lost = await ask("conversa", "Esto no debe escribirse", { continue_url: w.url("chat.conversa.test", "/conversa/c/noexiste") });
    const seen = await users("chat.conversa.test");
    say(lost.body.error?.code === "conversation_lost" && !seen.includes("Esto no debe escribirse"),
      `si la web ya no tiene la conversación, no se escribe nada y lo dice: ${lost.body.error?.code} — «${lost.body.error?.message?.slice(0, 110)}»`);
  });

  // 3. An address of another site: refused.
  await part("otra web", async () => {
    const other = await ask("conversa", "Tampoco esto", { continue_url: "https://chat.otra.test/c/1" });
    const seen = await users("chat.conversa.test");
    say(!!other.body.error && !seen.includes("Tampoco esto") && !w.ctx.pages().some((p) => p.url().includes("chat.otra.test")),
      `una dirección de otra web se rechaza sin abrirla ni escribir nada: ${other.body.error?.code}`);
  });

  // 4. Slow to start, no "stop" button: the new answer, never the previous one.
  await part("tarda en empezar", async () => {
    const a = await ask("tarda", "Uno");
    const t0 = Date.now();
    const b2 = await ask("tarda", "Dos", { continue_url: a.url });
    const s = Math.round((Date.now() - t0) / 1000);
    say(a.status === 200 && b2.text === "Respuesta 2 a «Dos»",
      `una web que tarda 15 s en empezar (como un modelo que piensa) y no enseña «parar»: se lee la respuesta nueva («${b2.text}», ${s} s), no la que ya estaba`);
  });
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed() && w) console.log(w.log.split("\n").slice(-40).join("\n"));
  await w?.close();
}
process.exitCode = failed() ? 1 : 0;
