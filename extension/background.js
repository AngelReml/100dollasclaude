// webllm bridge extension (MV3 service worker).
// Connects to the local bridge (127.0.0.1, token from config.json), receives
// jobs {site, prompt}, drives that site's chat page in a dedicated window, and
// sends back the answer. It stops and tells you when a site shows a login page,
// a verification (CAPTCHA) or a limit; it never tries to get around them.
importScripts("sites.js");

const SITES = self.WEBLLM_SITES;
const HUMAN_WAIT_MS = 180000;
let ws = null;
let config = null;
let connecting = false;
const siteQueue = {};  // site -> promise chain (one job at a time per site)
const lastNotice = {}; // site+kind -> timestamp (avoid notification spam)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function loadConfig() {
  if (config) return config;
  const r = await fetch(chrome.runtime.getURL("config.json"));
  config = await r.json();
  return config;
}

async function connect() {
  if (connecting || (ws && ws.readyState <= 1)) return;
  connecting = true;
  try {
    const cfg = await loadConfig();
    // Only open the socket when the bridge is up: a refused WebSocket shows up
    // as a red "Errors" entry on chrome://extensions, a failed fetch does not.
    const health = cfg.bridge.replace(/^ws/, "http").replace(/\/ext$/, "/health");
    const up = await fetch(health, { cache: "no-store" }).then((r) => r.ok).catch(() => false);
    if (!up) return;
    const sock = new WebSocket(`${cfg.bridge}?token=${encodeURIComponent(cfg.token)}`);
    sock.onopen = () => sock.send(JSON.stringify({ type: "hello", sites: Object.keys(SITES), version: chrome.runtime.getManifest().version }));
    sock.onmessage = (ev) => onMessage(JSON.parse(ev.data));
    sock.onclose = () => { if (ws === sock) ws = null; };
    sock.onerror = () => {};
    ws = sock;
  } catch (e) {
    ws = null;
  } finally {
    connecting = false;
  }
}

function sendToBridge(obj) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
}

// Keep the service worker and the socket alive (Chrome 116+: WebSocket
// activity every <30 s keeps an extension service worker running).
setInterval(() => sendToBridge({ type: "ping" }), 20000);
chrome.alarms.create("webllm-keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => connect());
chrome.runtime.onStartup.addListener(() => connect());
chrome.runtime.onInstalled.addListener(() => connect());
connect();

function notify(site, kind, message) {
  const key = site + ":" + kind;
  const now = Date.now();
  if (lastNotice[key] && now - lastNotice[key] < 600000) return;
  lastNotice[key] = now;
  const name = (SITES[site] && SITES[site].name) || site;
  chrome.notifications.create({ type: "basic", iconUrl: "icon.png", title: `webllm · ${name}`, message, priority: 2 });
  sendToBridge({ type: "notice", site, kind, message });
}

// ---------------------------------------------------------------- tabs

// All chats live as tabs of ONE small webllm window in the bottom-right corner.
// It is created unfocused (it never steals your keyboard) and closes itself a
// minute after the last job.
const busy = new Set();      // sites with a job running
let closeTimer = null;
let rotateIndex = 0;

let windowPromise = null;   // one creation at a time: parallel jobs share it

function webllmWindow() {
  if (!windowPromise) windowPromise = findOrCreateWindow().finally(() => { windowPromise = null; });
  return windowPromise;
}

async function findOrCreateWindow() {
  const saved = (await chrome.storage.local.get("window"))["window"];
  if (saved) {
    try { return await chrome.windows.get(saved); } catch (e) { /* closed */ }
  }
  let left = 0, top = 0;
  try {
    const [d] = await chrome.system.display.getInfo();
    left = d.workArea.left + d.workArea.width - 640;
    top = d.workArea.top + d.workArea.height - 720;
  } catch (e) { /* default position */ }
  const win = await chrome.windows.create({ url: "about:blank", focused: false, state: "normal",
                                            width: 640, height: 720, left, top });
  await chrome.storage.local.set({ window: win.id, blank: win.tabs[0].id });
  return win;
}

async function siteTab(site) {
  const win = await webllmWindow();
  const key = "tab:" + site;
  const saved = (await chrome.storage.local.get(key))[key];
  if (saved) {
    try {
      const t = await chrome.tabs.get(saved);
      if (t && t.windowId === win.id) return t.id;
    } catch (e) { /* closed */ }
  }
  const tab = await chrome.tabs.create({ windowId: win.id, url: SITES[site].newChat, active: busy.size <= 1 });
  await chrome.storage.local.set({ [key]: tab.id });
  const blank = (await chrome.storage.local.get("blank"))["blank"];
  if (blank) { chrome.tabs.remove(blank).catch(() => {}); await chrome.storage.local.remove("blank"); }
  return tab.id;
}

// Chat pages only write the answer on screen in the visible tab, so while
// several chats work at once, show each of their tabs in turn.
setInterval(async () => {
  const sites = [...busy];
  if (!sites.length) return;
  rotateIndex = (rotateIndex + 1) % sites.length;
  const tabId = (await chrome.storage.local.get("tab:" + sites[rotateIndex]))["tab:" + sites[rotateIndex]];
  if (tabId) chrome.tabs.update(tabId, { active: true }).catch(() => {});
}, 2000);

function jobStarted(site) {
  busy.add(site);
  if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
}

function jobFinished(site) {
  busy.delete(site);
  if (busy.size || closeTimer) return;
  closeTimer = setTimeout(async () => {
    closeTimer = null;
    if (busy.size) return;
    const saved = (await chrome.storage.local.get("window"))["window"];
    if (saved) chrome.windows.remove(saved).catch(() => {});
    await chrome.storage.local.clear();
  }, 60000);
}

async function waitLoaded(tabId, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const t = await chrome.tabs.get(tabId);
    if (t.status === "complete") return true;
    await sleep(300);
  }
  return false;
}

// Chat pages stop writing the answer while their window is minimized or fully
// covered. We never force the window up; we only tell you once.
async function keepVisible(tabId, st, site) {
  if (!st || !st.hidden) return;
  let win = null;
  try { win = await chrome.windows.get((await chrome.tabs.get(tabId)).windowId); } catch (e) { return; }
  if (win.state === "minimized" || busy.size === 1) {
    notify(site, "hidden", "La ventanita de webllm está minimizada o tapada: las webs no terminan de escribir hasta que se vea. Déjala a la vista (puede estar pequeña en una esquina).");
  }
}

async function call(tabId, op, ...args) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: (o, a) => (window.__webllmDriver ? window.__webllmDriver[o](...a) : { __missing: true }),
      args: [op, args],
    });
    const out = res && res.result;
    if (out && out.__missing) {
      await chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", files: ["driver.js"] });
      continue;
    }
    return out;
  }
  throw new Error("driver could not be injected");
}

// ---------------------------------------------------------------- jobs

class JobError extends Error {
  constructor(code, detail) { super(code); this.code = code; this.detail = detail || ""; }
}

async function waitForHuman(site, tabId, what) {
  const tab = await chrome.tabs.get(tabId);
  await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
  await chrome.tabs.update(tabId, { active: true });
  notify(site, "challenge", `${SITES[site].name} pide una verificación (${what}). Resuélvela tú en la ventana que acabo de traer al frente; espero 3 minutos.`);
  const t0 = Date.now();
  while (Date.now() - t0 < HUMAN_WAIT_MS) {
    await sleep(2000);
    const st = await call(tabId, "state", SITES[site]);
    if (!st.challenge) return;
  }
  throw new JobError("challenge", what);
}

function checkBlocks(site, st) {
  if (st.banned) throw new JobError("banned", st.banned);
  if (st.siteBusy) throw new JobError("site_busy", st.siteBusy);
  if (st.rateLimited) throw new JobError("rate_limited", st.rateLimited);
  if (st.loginWall) throw new JobError("login_required", st.url);
}

async function runJob(job) {
  const site = SITES[job.site];
  if (!site) throw new JobError("unknown_site", job.site);
  const tabId = await siteTab(job.site);
  await chrome.tabs.update(tabId, { url: site.newChat });
  await sleep(800);
  await waitLoaded(tabId, 45000);

  // 1. wait for the chat box (or a login / verification page)
  let st;
  const t0 = Date.now();
  for (;;) {
    st = await call(tabId, "state", site);
    if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge); continue; }
    checkBlocks(job.site, st);
    if (st.input) break;
    if (Date.now() - t0 > 30000) throw new JobError("no_input", st.url);
    await sleep(1000);
  }

  // 2. type and send
  const ins = await call(tabId, "insert", site, job.prompt);
  if (!ins || !ins.ok) throw new JobError("insert_failed", JSON.stringify(ins));
  await sleep(500);
  const before = await call(tabId, "state", site);
  const snd = await call(tabId, "send", site);
  if (!snd || !snd.ok) throw new JobError("send_failed", JSON.stringify(snd));

  // 2b. make sure it really went out. A pop-up (age check, cookies, "new
  // feature"...) can swallow the click and leave the text in the box: then ask
  // the user to answer the pop-up and press send again once it is gone.
  const sendDeadline = Date.now() + HUMAN_WAIT_MS;
  let asked = false;
  for (let tries = 0; ; tries++) {
    await sleep(2500);
    st = await call(tabId, "state", site);
    if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge); continue; }
    checkBlocks(job.site, st);
    const stillThere = st.inputLen > 0 && st.inputLen >= before.inputLen * 0.5 && st.bodyLen <= before.bodyLen + 20;
    if (!stillThere) break;
    if (Date.now() > sendDeadline) throw new JobError("not_sent", "the text stayed in the chat box");
    if (st.overlay && !asked) {
      asked = true;
      const tab = await chrome.tabs.get(tabId);
      await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
      await chrome.tabs.update(tabId, { active: true });
      notify(job.site, "popup", `${site.name} ha sacado una ventana ("${st.overlay}"). Respóndela en la ventanita de webllm y sigo yo solo.`);
    }
    if (!st.overlay || tries % 3 === 2) await call(tabId, "send", site);
  }

  // 3. wait until the answer is complete
  const deadline = Date.now() + (job.timeout_ms || 300000);
  let lastSig = "";
  let stable = 0;
  let changed = false;
  while (Date.now() < deadline) {
    await sleep(1500);
    st = await call(tabId, "state", site);
    await keepVisible(tabId, st, job.site);
    if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge); continue; }
    checkBlocks(job.site, st);
    const sig = `${st.lastAnswerLen}:${st.bodyLen}:${st.copyCount}:${st.answerCount}`;
    if (sig !== lastSig) { lastSig = sig; stable = 0; changed = true; } else { stable++; }
    const newCopy = st.copyCount > before.copyCount;
    if (!st.generating && changed && ((newCopy && stable >= 1) || stable >= 5)) break;
  }
  if (Date.now() >= deadline) throw new JobError("timeout", `${Math.round((job.timeout_ms || 300000) / 1000)} s`);

  // 4. take the answer: the page's own copy button first, HTML as fallback
  await sleep(800);
  let out = await call(tabId, "capture", site);
  if (!out || !out.ok) out = await call(tabId, "fallback", site);
  if (!out || !out.ok || !out.text.trim()) {
    const d = await call(tabId, "diagnose", site).catch(() => null);
    throw new JobError("empty_answer", JSON.stringify({ out, diagnose: d }).slice(0, 6000));
  }
  out.modelName = st.modelName || null;
  return out;
}

async function handleJob(job) {
  const prev = siteQueue[job.site] || Promise.resolve();
  const run = prev.catch(() => {}).then(async () => {
    jobStarted(job.site);
    try {
      const out = await runJob(job);
      sendToBridge({ type: "result", id: job.id, ok: true, text: out.text, via: out.via, model_label: out.modelName });
    } catch (e) {
      const code = e instanceof JobError ? e.code : "extension_error";
      const detail = e instanceof JobError ? e.detail : String(e && e.message || e);
      const name = (SITES[job.site] && SITES[job.site].name) || job.site;
      if (code === "login_required") notify(job.site, code, `${name}: no hay sesión abierta. Entra con tu cuenta (o una nueva) en esa ventana y vuelve a pedirlo.`);
      if (code === "banned") notify(job.site, code, `${name}: la cuenta parece bloqueada. Crea otra, entra con ella en Chrome y haz doble clic en REANUDAR.`);
      if (code === "rate_limited") notify(job.site, code, `${name}: límite de mensajes alcanzado. Lo pauso; doble clic en REANUDAR cuando quieras seguir.`);
      if (code === "challenge") notify(job.site, code, `${name}: la verificación no se resolvió. Lo pauso; resuélvela y haz doble clic en REANUDAR.`);
      if (code === "site_busy") notify(job.site, code, `${name} está saturado ahora mismo (no es un límite de tu cuenta). Prueba en un rato o elige otro modelo en su web.`);
      if (code === "not_sent") notify(job.site, code, `${name}: el mensaje se quedó sin enviar (¿una ventana emergente?). Vuelve a pedirlo.`);
      sendToBridge({ type: "result", id: job.id, ok: false, error: code, detail });
    } finally {
      jobFinished(job.site);
    }
  });
  siteQueue[job.site] = run;
  return run;
}

async function handleDiagnose(msg) {
  try {
    const tabId = await siteTab(msg.site);
    await waitLoaded(tabId, 30000);
    const out = await call(tabId, "diagnose", SITES[msg.site]);
    sendToBridge({ type: "result", id: msg.id, ok: true, text: JSON.stringify(out, null, 1), via: "diagnose" });
  } catch (e) {
    sendToBridge({ type: "result", id: msg.id, ok: false, error: "extension_error", detail: String(e && e.message || e) });
  }
}

// "Conectar" in the app: bring the chat's tab forward so you can log in there.
// Only used when the page has no session (you must type in it), never for jobs.
async function handleShow(msg) {
  try {
    const tabId = await siteTab(msg.site);
    const tab = await chrome.tabs.get(tabId);
    await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
    await chrome.tabs.update(tabId, { active: true });
    sendToBridge({ type: "result", id: msg.id, ok: true, text: "", via: "show" });
  } catch (e) {
    sendToBridge({ type: "result", id: msg.id, ok: false, error: "extension_error", detail: String(e && e.message || e) });
  }
}

function onMessage(msg) {
  if (msg.type === "job") handleJob(msg);
  else if (msg.type === "diagnose") handleDiagnose(msg);
  else if (msg.type === "show") handleShow(msg);
}
