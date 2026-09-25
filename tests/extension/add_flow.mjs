// "+ Añadir otra IA" end to end, with everything real except Chrome's permission prompt:
// the real bridge + app API (scripts/app_demo.py --sin-chrome), the real extension loaded in
// Chromium, and tests/extension/fake_chat.html served over https under made-up *.test names.
//   node tests/extension/add_flow.mjs      (prints one line per check, exits 1 on failure)
// Chrome's "Allow" prompt cannot be clicked by a script, so the copy of the extension used here
// already holds permission for https://*.test/* (then chrome.permissions.request answers yes
// without a prompt, and the real "Permitir y probar" click still goes through add.html).
import { execFileSync, spawn } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:https";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const require = createRequire(import.meta.url);
const { chromium } = require(join(root, "app", "node_modules", "playwright-core"));
const exe = process.env.PLAYWRIGHT_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const python = process.env.WEBLLM_PYTHON ?? "python3";
const port = Number(process.env.WEBLLM_TEST_PORT ?? 20197);
const TOKEN = "demo-token";
const api = `http://127.0.0.1:${port}`;
const tmp = mkdtempSync(join(tmpdir(), "webllm-add-"));
let failed = 0;
let bridge = null;
let ctx = null;
let log = "";

const say = (ok, text) => {
  if (!ok) failed++;
  console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = async (path, body) => {
  const r = await fetch(api + path, {
    method: body ? "POST" : "GET",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  try {
    return { status: r.status, body: JSON.parse(text) };
  } catch {
    throw new Error(`${path} respondió ${r.status}: ${text.slice(0, 200)}`);
  }
};

try {
  // 1) A fake chat site over https (self-signed certificate made here, thrown away after).
  execFileSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=webllm-test",
    "-keyout", join(tmp, "key.pem"), "-out", join(tmp, "cert.pem")], { stdio: "ignore" });
  const page = readFileSync(join(here, "fake_chat.html"));
  const icon = readFileSync(join(root, "extension", "icon.png"));
  const site = createServer({ key: readFileSync(join(tmp, "key.pem")), cert: readFileSync(join(tmp, "cert.pem")) }, (req, res) => {
    if (req.url === "/favicon.ico") {
      res.setHeader("Content-Type", "image/png");
      return res.end(icon);
    }
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.end(page);
  });
  await new Promise((r) => site.listen(0, "127.0.0.1", r));
  const sitePort = site.address().port;
  const url = (host, path = "/") => `https://${host}:${sitePort}${path}`;

  // 2) The real bridge with the app API (no fake extension).
  if (await fetch(`${api}/health`).then(() => true, () => false)) throw new Error(`el puerto ${port} ya está ocupado`);
  bridge = spawn(python, [join(root, "scripts", "app_demo.py"), "--sin-chrome", "--port", String(port), "--data", join(tmp, "data")], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  bridge.stdout.on("data", (d) => (log += d));
  bridge.stderr.on("data", (d) => (log += d));
  for (let i = 0; i < 60 && !(await fetch(`${api}/health`).then((r) => r.ok, () => false)); i++) await sleep(250);

  // 3) The real extension, pointed at that bridge.
  const ext = join(tmp, "extension");
  cpSync(join(root, "extension"), ext, { recursive: true });
  writeFileSync(join(ext, "config.json"), JSON.stringify({ bridge: `ws://127.0.0.1:${port}/ext`, token: TOKEN }));
  const manifest = JSON.parse(readFileSync(join(ext, "manifest.json"), "utf8"));
  manifest.host_permissions = [...manifest.host_permissions, "https://*.test/*"];
  writeFileSync(join(ext, "manifest.json"), JSON.stringify(manifest, null, 1));
  ctx = await chromium.launchPersistentContext(join(tmp, "profile"), {
    executablePath: exe,
    headless: true,
    args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`, "--headless=new",
      "--host-resolver-rules=MAP *.test 127.0.0.1", "--ignore-certificate-errors", "--no-proxy-server"],
  });
  const sw = ctx.serviceWorkers()[0] ?? (await ctx.waitForEvent("serviceworker", { timeout: 15000 }));
  let chrome = false;
  for (let i = 0; i < 80 && !chrome; i++) {
    chrome = (await call("/api/estado")).body.chrome;
    if (!chrome) await sleep(250);
  }
  say(chrome, `la extensión ${manifest.version} se conecta al puente`);

  // Adds one site the way Iván does: paste, click "Permitir y probar" in the tab Chrome opens.
  async function add(address) {
    const start = await call("/api/anadir", { url: address });
    if (start.status !== 200) return start.body;
    const tab = ctx.pages().find((p) => p.url().includes("add.html")) ?? (await ctx.waitForEvent("page", { timeout: 15000 }));
    await tab.waitForLoadState();
    await tab.getByRole("button", { name: "Permitir y probar" }).click();
    let st = start.body;
    for (let i = 0; i < 360 && st.status === "running"; i++) {
      await sleep(500);
      st = (await call(`/api/anadir/${st.add_id}`)).body;
    }
    return st;
  }
  const steps = (st) => st.steps.map((s) => `${s.ok ? "✓" : "✗"} ${s.text}`).join(" · ");

  // 4) A site that works.
  const ok = await add(url("chat.pruebaia.test"));
  say(ok.status === "ok" && ok.key === "pruebaia", `añadir ${ok.name}: ${ok.status} — ${steps(ok)}${ok.detail ? ` [${ok.detail.slice(0, 300)}]` : ""}`);
  const estado = (await call("/api/estado")).body;
  const ai = estado.ais.find((a) => a.name === "pruebaia");
  say(!!ai && ai.custom && ai.state === "lista", `aparece entre tus IAs: ${JSON.stringify(ai && { label: ai.label, custom: ai.custom, state: ai.state, icon: ai.icon, url: ai.url })}`);

  // 5) Ask it a question after the extension "forgot" the site (as after a Chrome restart):
  //    the bridge sends the site's name and address with the job.
  await sw.evaluate(() => delete self.WEBLLM_SITES.pruebaia);
  const r = await fetch(`${api}/api/preguntar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: "Responde solo con la palabra: pong", to: ["pruebaia"] }),
  });
  const events = (await r.text()).split("\n").filter((l) => l.startsWith("data: ")).map((l) => JSON.parse(l.slice(6)));
  const done = events.find((e) => e.type === "target_done");
  say(!!done?.ok && /pong/i.test(done.text), `pregunta a la IA añadida: ok=${done?.ok} texto=${JSON.stringify(done?.text)} (${done?.seconds} s)`);
  const after = (await call("/api/estado")).body.ais.find((a) => a.name === "pruebaia");
  say(after?.today === 2, `el guardián la cuenta: hoy ${after?.today} de ${after?.cap} (prueba + pregunta)`);

  // 6) Sites that cannot be used: nothing is saved, and the reason is plain.
  const nobox = await add(url("chat.sinbox.test", "/nobox/"));
  say(nobox.status === "failed" && nobox.error === "no_input", `sin caja de texto: ${nobox.error} — «${nobox.message}»`);
  const login = await add(url("chat.conlogin.test", "/login/"));
  say(login.status === "failed" && login.error === "login_required", `pide entrar: ${login.error} — «${login.message}»`);
  const names = (await call("/api/estado")).body.ais.map((a) => a.name);
  say(!names.includes("sinbox") && !names.includes("conlogin"), "las que fallan no se guardan");

  // 7) Remove it.
  const q = await call("/api/quitar", { ia: "pruebaia" });
  const gone = !(await call("/api/estado")).body.ais.some((a) => a.name === "pruebaia");
  say(q.status === 200 && gone, "quitar la IA añadida");
  site.close();
} catch (e) {
  say(false, `error: ${e && e.stack ? e.stack : e}`);
} finally {
  if (failed) console.log(log.split("\n").slice(-40).join("\n"));
  await ctx?.close().catch(() => {});
  bridge?.kill();
  rmSync(tmp, { recursive: true, force: true });
}
process.exitCode = failed ? 1 : 0;
