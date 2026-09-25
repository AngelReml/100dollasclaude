// Shared by the real-extension tests: everything real except Chrome's permission prompt and Iván.
// - tests/extension/fake_chat.html served over https under made-up *.test names;
// - the real bridge + app API (scripts/app_demo.py --sin-chrome, fake OmniRoute / LM Studio);
// - the real extension loaded in Chromium, pointed at that bridge. Chrome's "Allow" prompt cannot
//   be clicked by a script, so this copy of the extension already holds permission for
//   https://*.test/* (chrome.permissions.request then answers yes without asking, and the real
//   "Permitir y probar" click still goes through add.html).
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
const TOKEN = "demo-token";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** One line per check: "BIEN ..." or "FALLO ..."; `failed()` says how many failed. */
export function checks() {
  let failed = 0;
  const say = (ok, text) => {
    if (!ok) failed++;
    console.log(`${ok ? "BIEN " : "FALLO"} ${text}`);
  };
  return { say, failed: () => failed };
}

export async function startWorld({ port = Number(process.env.WEBLLM_TEST_PORT ?? 20197), limitS = 30 } = {}) {
  const tmp = mkdtempSync(join(tmpdir(), "webllm-ext-"));
  const api = `http://127.0.0.1:${port}`;
  const world = { tmp, api, log: "", bridge: null, ctx: null, site: null };

  world.close = async () => {
    await world.ctx?.close().catch(() => {});
    world.bridge?.kill();
    world.site?.close();
    rmSync(tmp, { recursive: true, force: true });
  };

  world.call = async (path, body) => {
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

  /** Ask like the app does (POST /api/preguntar, server-sent events); returns every event. */
  world.ask = async (prompt, to) => {
    const r = await fetch(`${api}/api/preguntar`, {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, to }),
    });
    return (await r.text()).split("\n").filter((l) => l.startsWith("data: ")).map((l) => JSON.parse(l.slice(6)));
  };

  try {
    // 1) A fake chat site over https (self-signed certificate made here, thrown away after).
    execFileSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=webllm-test",
      "-keyout", join(tmp, "key.pem"), "-out", join(tmp, "cert.pem")], { stdio: "ignore" });
    const page = readFileSync(join(here, "fake_chat.html"));
    const icon = readFileSync(join(root, "extension", "icon.png"));
    world.site = createServer({ key: readFileSync(join(tmp, "key.pem")), cert: readFileSync(join(tmp, "cert.pem")) }, (req, res) => {
      if (req.url === "/favicon.ico") {
        res.setHeader("Content-Type", "image/png");
        return res.end(icon);
      }
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.end(page);
    });
    await new Promise((r) => world.site.listen(0, "127.0.0.1", r));
    const sitePort = world.site.address().port;
    world.url = (host, path = "/") => `https://${host}:${sitePort}${path}`;

    // 2) The real bridge with the app API (no fake extension).
    if (await fetch(`${api}/health`).then(() => true, () => false)) throw new Error(`el puerto ${port} ya está ocupado`);
    world.bridge = spawn(python, [join(root, "scripts", "app_demo.py"), "--sin-chrome", "--port", String(port),
      "--data", join(tmp, "data"), "--limite", String(limitS)], { stdio: ["ignore", "pipe", "pipe"] });
    world.bridge.stdout.on("data", (d) => (world.log += d));
    world.bridge.stderr.on("data", (d) => (world.log += d));
    for (let i = 0; i < 60 && !(await fetch(`${api}/health`).then((r) => r.ok, () => false)); i++) await sleep(250);

    // 3) The real extension, pointed at that bridge.
    const ext = join(tmp, "extension");
    cpSync(join(root, "extension"), ext, { recursive: true });
    writeFileSync(join(ext, "config.json"), JSON.stringify({ bridge: `ws://127.0.0.1:${port}/ext`, token: TOKEN }));
    const manifest = JSON.parse(readFileSync(join(ext, "manifest.json"), "utf8"));
    manifest.host_permissions = [...manifest.host_permissions, "https://*.test/*"];
    writeFileSync(join(ext, "manifest.json"), JSON.stringify(manifest, null, 1));
    world.version = manifest.version;
    world.ctx = await chromium.launchPersistentContext(join(tmp, "profile"), {
      executablePath: exe,
      headless: true,
      // --no-proxy-server: the made-up *.test names must not go to a proxy from the environment.
      args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`, "--headless=new",
        "--host-resolver-rules=MAP *.test 127.0.0.1", "--ignore-certificate-errors", "--no-proxy-server"],
    });
    world.sw = world.ctx.serviceWorkers()[0] ?? (await world.ctx.waitForEvent("serviceworker", { timeout: 15000 }));
    world.chrome = false;
    for (let i = 0; i < 80 && !world.chrome; i++) {
      world.chrome = (await world.call("/api/estado")).body.chrome;
      if (!world.chrome) await sleep(250);
    }
  } catch (e) {
    await world.close();
    throw e;
  }

  /** Add one site the way Iván does: paste, click "Permitir y probar" in the tab Chrome opens. */
  world.add = async (address) => {
    const start = await world.call("/api/anadir", { url: address });
    if (start.status !== 200) return start.body;
    const tab = world.ctx.pages().find((p) => p.url().includes("add.html")) ?? (await world.ctx.waitForEvent("page", { timeout: 15000 }));
    await tab.waitForLoadState();
    await tab.getByRole("button", { name: "Permitir y probar" }).click();
    let st = start.body;
    for (let i = 0; i < 360 && st.status === "running"; i++) {
      await sleep(500);
      st = (await world.call(`/api/anadir/${st.add_id}`)).body;
    }
    return st;
  };

  /** The address of the tab in front in the small webllm window (what Iván sees). */
  world.frontTab = () =>
    world.sw.evaluate(async () => {
      const id = (await chrome.storage.local.get("window"))["window"];
      if (!id) return null;
      const [t] = await chrome.tabs.query({ windowId: id, active: true });
      return t ? t.url : null;
    });

  return world;
}
