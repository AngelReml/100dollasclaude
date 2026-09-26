// webllm bridge extension (MV3 service worker).
// Connects to the local bridge (127.0.0.1, token from config.json), receives
// jobs {site, prompt}, drives that site's chat page in a dedicated window, and
// sends back the answer. It stops and tells you when a site shows a login page,
// a verification (CAPTCHA) or a limit; it never tries to get around them.
importScripts("common.js", "sites.js");

const SITES = self.WEBLLM_SITES;
const { genericSite, parseChatUrl } = self.WEBLLM_COMMON;
const HUMAN_WAIT_MS = 300000;  // how long a verification or pop-up waits for you (each time)
const JOB_HARD_CAP_MS = 29 * 60000; // no job runs longer, whatever it waits for (the bridge gives up at 30)
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

// ---------------------------------------------------------- waiting for you

// While a chat waits for you (a verification, a pop-up) its tab stays in front,
// so the other chats are hidden and cannot write either: that time does not
// count against any job's time limit. The bridge hears about it (job_alive) and
// keeps waiting too, and the app shows "te espero" instead of an error.
const needsHuman = new Map(); // site -> "challenge" | "popup" | "hidden" (first one stays in front)
const runningJob = {};        // site -> id of the job it is doing for the bridge
let humanSince = 0;
let humanTotal = 0;

function humanMs() {
  return humanTotal + (humanSince ? Date.now() - humanSince : 0);
}

function humanStart(site, kind) {
  if (!needsHuman.size) humanSince = Date.now();
  needsHuman.set(site, kind);
  beat(site);
}

function humanEnd(site) {
  if (!needsHuman.delete(site)) return;
  if (!needsHuman.size && humanSince) {
    humanTotal += Date.now() - humanSince;
    humanSince = 0;
  }
  beat(site);
}

// A stopwatch that pauses while you are needed.
function jobClock() {
  const t0 = Date.now();
  const h0 = humanMs();
  return () => Date.now() - t0 - (humanMs() - h0);
}

function beat(site) {
  if (runningJob[site]) sendToBridge({ type: "job_alive", id: runningJob[site], site, waiting: needsHuman.get(site) || null });
}
setInterval(() => Object.keys(runningJob).forEach(beat), 10000);

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
// several chats work at once, show each of their tabs in turn. A chat that
// needs you (verification, pop-up) stays in front until you are done.
setInterval(async () => {
  const sites = needsHuman.size ? [needsHuman.keys().next().value] : [...busy];
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
// covered (by the app's window, for example). We never force the window up: we
// tell you (a notice, and the app says "te espera") and that time does not count
// against the time limit. Returns true while the chat's own tab is in front but
// cannot be seen. A tab hidden only because another chat's tab is in front (the
// rotation) is not "covered".
async function coveredWindow(tabId, st, site) {
  let covered = false;
  if (st && st.hidden) {
    try { covered = (await chrome.tabs.get(tabId)).active; } catch (e) { covered = false; }
  }
  if (covered && needsHuman.get(site) !== "hidden") {
    humanStart(site, "hidden");
    notify(site, "hidden", "La ventanita de webllm está minimizada o tapada: las webs no terminan de escribir hasta que se vea. Déjala a la vista (puede estar pequeña en una esquina).");
  } else if (!covered && needsHuman.get(site) === "hidden") {
    humanEnd(site);
  }
  return covered;
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
      await chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", files: ["common.js", "driver.js"] });
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

// "Parar" (Open WebUI's stop button, or "Parar todo"): the bridge names the job; it stops at the next look.
const cancelled = new Set();
function stillWanted(job) {
  if (job && cancelled.has(job.id)) throw new JobError("cancelled", "parado por Iván");
}

async function waitForHuman(site, tabId, what, job) {
  humanStart(site, "challenge");
  try {
    const tab = await chrome.tabs.get(tabId);
    await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
    await chrome.tabs.update(tabId, { active: true });
    notify(site, "challenge", `${SITES[site].name} pide una verificación (${what}). Resuélvela tú en la ventana que acabo de traer al frente; te espero 5 minutos.`);
    const t0 = Date.now();
    while (Date.now() - t0 < HUMAN_WAIT_MS) {
      await sleep(2000);
      stillWanted(job);
      const st = await call(tabId, "state", SITES[site]);
      if (!st.challenge) return;
    }
    throw new JobError("challenge", what);
  } finally {
    humanEnd(site);
  }
}

function checkBlocks(site, st) {
  if (st.banned) throw new JobError("banned", st.banned);
  if (st.siteBusy) throw new JobError("site_busy", st.siteBusy);
  if (st.rateLimited) throw new JobError("rate_limited", st.rateLimited);
  if (st.loginWall) throw new JobError("login_required", st.url);
}

async function runJob(job) {
  const jobStart = Date.now();
  const site = SITES[job.site];
  if (!site) throw new JobError("unknown_site", job.site);
  const tabId = await siteTab(job.site);
  await chrome.tabs.update(tabId, { url: site.newChat });
  await sleep(800);
  await waitLoaded(tabId, 45000);

  // 1. wait for the chat box (or a login / verification page)
  let st;
  const boxClock = jobClock();
  for (;;) {
    stillWanted(job);
    st = await call(tabId, "state", site);
    if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge, job); continue; }
    checkBlocks(job.site, st);
    if (st.input) break;
    if (boxClock() > 30000) throw new JobError("no_input", st.url);
    await sleep(1000);
  }

  // 1b. what Iván chose (PLAN-v5 D21/D22): the model, the modes and the files, each one put through the
  //     page's own controls and confirmed there. If the page does not confirm it, nothing is sent.
  const used = { model: null, modes: [], files: [], modes_on: [] };
  const want = job.want || {};
  if (want.model) {
    stillWanted(job);
    const r = await call(tabId, "chooseModel", site, want.model);
    if (!r || !r.ok) {
      throw new JobError(r && r.error === "model_not_found" ? "model_not_in_page" : "not_confirmed",
        JSON.stringify({ what: "model", wanted: want.model, ...(r || {}) }).slice(0, 2000));
    }
    used.model = r.model;
  }
  for (const mode of want.modes || []) {
    stillWanted(job);
    const r = await call(tabId, "setMode", site, mode, true);
    if (!r || !r.ok) {
      throw new JobError(r && r.error === "mode_not_found" ? "mode_not_in_page" : "not_confirmed",
        JSON.stringify({ what: "mode", wanted: mode, ...(r || {}) }).slice(0, 2000));
    }
    used.modes.push({ mode, name: r.name });
  }
  if ((job.files || []).length) {
    const got = incoming[job.id] || {};
    for (const f of job.files) {
      const parts = got[f.key] || [];
      for (let i = 0; i < f.parts; i++) {
        stillWanted(job);
        if (parts[i] === undefined) throw new JobError("file_incomplete", f.name);
        await call(tabId, "fileChunk", f.key, i, parts[i]);
      }
    }
    const r = await call(tabId, "attach", site, job.files.map((f) => ({ key: f.key, name: f.name, type: f.type, sha256: f.sha256, parts: f.parts })));
    if (!r || !r.ok) throw new JobError(r && r.error ? r.error : "file_not_attached", JSON.stringify(r || {}).slice(0, 2000));
    used.files = r.files;
  }
  used.modes_on = await call(tabId, "activeModes", site);  // what is really on when it is sent

  // 2. type and send
  stillWanted(job);
  const ins = await call(tabId, "insert", site, job.prompt);
  if (!ins || !ins.ok) throw new JobError("insert_failed", JSON.stringify(ins));
  await sleep(500);
  const before = await call(tabId, "state", site);
  const snd = await call(tabId, "send", site);
  if (!snd || !snd.ok) throw new JobError("send_failed", JSON.stringify(snd));

  // 2b. make sure it really went out. A pop-up (age check, cookies, "new
  // feature"...) can swallow the click and leave the text in the box: then ask
  // the user to answer the pop-up and press send again once it is gone.
  const sendClock = jobClock();
  let askedAt = 0;
  try {
    for (let tries = 0; ; tries++) {
      await sleep(2500);
      stillWanted(job);
      st = await call(tabId, "state", site);
      if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge, job); continue; }
      checkBlocks(job.site, st);
      const stillThere = st.inputLen > 0 && st.inputLen >= before.inputLen * 0.5 && st.bodyLen <= before.bodyLen + 20;
      if (!stillThere) break;
      if (sendClock() > 90000 || (askedAt && Date.now() - askedAt > HUMAN_WAIT_MS)) {
        throw new JobError("not_sent", "the text stayed in the chat box");
      }
      if (st.overlay && !askedAt) {
        askedAt = Date.now();
        humanStart(job.site, "popup");
        const tab = await chrome.tabs.get(tabId);
        await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
        await chrome.tabs.update(tabId, { active: true });
        notify(job.site, "popup", `${site.name} ha sacado una ventana ("${st.overlay}"). Respóndela en la ventanita de webllm y sigo yo solo.`);
      }
      if (!st.overlay || tries % 3 === 2) await call(tabId, "send", site);
    }
  } finally {
    if (askedAt) humanEnd(job.site);
  }

  // 3. wait until the answer is complete (time spent on a verification does not count)
  // A "stop" button already there before sending is not an answer being written (a page that
  // never hides it, or a button that only looks like one): then it says nothing about the end.
  // And once the page has put a new "copy" button and nothing has changed for 12 s, the answer
  // is finished even if something still looks like "stop" (Iván's Meta, 2026-09-25).
  const stopMeansNothing = !!before.generating;
  const limit = job.timeout_ms || 300000;
  const answerClock = jobClock();
  let lastSig = "";
  let stable = 0;
  let changed = false;
  while (answerClock() < limit) {
    await sleep(1500);
    stillWanted(job);
    if (Date.now() - jobStart > JOB_HARD_CAP_MS) break;
    st = await call(tabId, "state", site);
    if (await coveredWindow(tabId, st, job.site)) continue;
    if (st.challenge) { await waitForHuman(job.site, tabId, st.challenge, job); continue; }
    checkBlocks(job.site, st);
    const sig = `${st.lastAnswerLen}:${st.bodyLen}:${st.copyCount}:${st.answerCount}`;
    if (sig !== lastSig) { lastSig = sig; stable = 0; changed = true; } else { stable++; }
    const newCopy = st.copyCount > before.copyCount;
    const writing = st.generating && !stopMeansNothing;
    if (changed && !writing && ((newCopy && stable >= 1) || stable >= 5)) break;
    if (changed && newCopy && stable >= 8) break;
  }
  if (answerClock() >= limit || Date.now() - jobStart > JOB_HARD_CAP_MS) {
    // What the page looked like at the end: the evidence to fix this site (it goes to bridge.log).
    const d = await call(tabId, "diagnose", site).catch(() => null);
    throw new JobError("timeout", JSON.stringify({ limit_s: Math.round(limit / 1000), stop_before_send: stopMeansNothing,
                                                    state: st, diagnose: d }).slice(0, 6000));
  }

  // 4. take the answer: the page's own copy button first, HTML as fallback
  await sleep(800);
  let out = await call(tabId, "capture", site);
  if (!out || !out.ok) out = await call(tabId, "fallback", site);
  if (!out || !out.ok || !out.text.trim()) {
    const d = await call(tabId, "diagnose", site).catch(() => null);
    throw new JobError("empty_answer", JSON.stringify({ out, diagnose: d }).slice(0, 6000));
  }
  out.modelName = st.modelName || null;
  out.used = used;
  const made = await call(tabId, "downloads", site).catch(() => null);
  out.downloads = made && made.ok ? made.files : [];
  return out;
}

async function handleJob(job) {
  const prev = siteQueue[job.site] || Promise.resolve();
  const run = prev.catch(() => {}).then(async () => {
    jobStarted(job.site);
    runningJob[job.site] = job.id;
    beat(job.site);
    try {
      const out = await runJob(job);
      sendToBridge({ type: "result", id: job.id, ok: true, text: out.text, via: out.via, model_label: out.modelName,
                     used: out.used, downloads: out.downloads });
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
      delete runningJob[job.site];
      delete incoming[job.id];
      cancelled.delete(job.id);
      humanEnd(job.site);
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

// Files for a job arrive in parts before the job (big ones too): job id -> file key -> parts.
const incoming = {};
function onFilePart(msg) {
  const job = (incoming[msg.job] = incoming[msg.job] || {});
  (job[msg.key] = job[msg.key] || [])[msg.n] = msg.data;
}

// "Descubrir" (PLAN-v5 F4): open the chat, read its card (models, modes, "+" menu, files) and close every
// menu again. Nothing is pressed but the menus' own buttons, and nothing is sent.
function inQueue(site, fn) {
  const prev = siteQueue[site] || Promise.resolve();
  const run = prev.catch(() => {}).then(async () => {
    jobStarted(site);
    try { return await fn(); } finally { jobFinished(site); }
  });
  siteQueue[site] = run;
  return run;
}
function handleDiscover(msg) {
  return inQueue(msg.site, async () => {
    try {
      const site = SITES[msg.site];
      if (!site) throw new JobError("unknown_site", msg.site);
      const tabId = await siteTab(msg.site);
      await chrome.tabs.update(tabId, { url: site.newChat });
      await sleep(800);
      await waitLoaded(tabId, 45000);
      let st;
      for (const t0 = Date.now(); ; ) {
        st = await call(tabId, "state", site);
        if (st.challenge) throw new JobError("challenge", st.challenge);
        if (st.loginWall) throw new JobError("login_required", st.url);
        if (st.input || Date.now() - t0 > 30000) break;
        await sleep(1000);
      }
      if (!st.input) throw new JobError("no_input", st.url);
      const card = await call(tabId, "discover", site);
      sendToBridge({ type: "result", id: msg.id, ok: true, text: JSON.stringify(card), via: "discover" });
    } catch (e) {
      sendToBridge({ type: "result", id: msg.id, ok: false, error: e instanceof JobError ? e.code : "extension_error",
                     detail: e instanceof JobError ? e.detail : String(e && e.message || e) });
    }
  });
}

// "Enséñame dónde está": the chat comes to the front with a banner; Iván's next click there does nothing
// on the page and tells webllm where that thing is.
function handleTeach(msg) {
  return inQueue(msg.site, async () => {
    try {
      const tabId = await siteTab(msg.site);
      await waitLoaded(tabId, 30000);
      humanStart(msg.site, "teach");
      const tab = await chrome.tabs.get(tabId);
      await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
      await chrome.tabs.update(tabId, { active: true });
      const out = await call(tabId, "teach", msg.what, msg.text, Number(msg.wait_ms) || 180000);
      sendToBridge({ type: "result", id: msg.id, ok: !!(out && out.ok), text: JSON.stringify(out || {}), via: "teach",
                     error: out && out.ok ? undefined : (out && out.error) || "teach_failed" });
    } catch (e) {
      sendToBridge({ type: "result", id: msg.id, ok: false, error: "extension_error", detail: String(e && e.message || e) });
    } finally {
      humanEnd(msg.site);
    }
  });
}

// Sites you added from the app are not in sites.js: the bridge sends their
// name and address with every message, and driver.js detects them generically.
function ensureSite(msg) {
  if (msg.site && !SITES[msg.site] && msg.site_config && parseChatUrl(msg.site_config.url).ok) {
    SITES[msg.site] = genericSite(msg.site_config.name, parseChatUrl(msg.site_config.url).url);
  }
  // What Iván showed with "Enséñame dónde está" goes first, before the site's own and the generic rules.
  const patch = msg.site_patch;
  if (msg.site && SITES[msg.site] && patch && typeof patch === "object") {
    for (const k of ["modelButton", "plusButton", "fileInput", "input", "send", "copy", "answer"]) {
      const sels = Array.isArray(patch[k]) ? patch[k].filter((x) => typeof x === "string" && x.length < 300) : [];
      if (sels.length) SITES[msg.site][k] = [...new Set([...sels, ...(SITES[msg.site][k] || [])])];
    }
  }
}

// ------------------------------------------------------- add a site from the app

// 1) The app asks: open our own page, where you click "Permitir y probar".
async function handleAddSite(msg) {
  const p = parseChatUrl(msg.url);
  if (!p.ok) {
    sendToBridge({ type: "result", id: msg.id, ok: false, error: p.error });
    return;
  }
  const q = new URLSearchParams({ add_id: msg.add_id, key: msg.key, name: msg.name, url: p.url });
  const tab = await chrome.tabs.create({ url: chrome.runtime.getURL("add.html?" + q), active: true });
  await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
  sendToBridge({ type: "result", id: msg.id, ok: true, text: "", via: "add" });
}

// A page on another address where you log in (accounts.google.com, login.live.com, …/signin).
const LOGIN_PAGE = /^(accounts|login|auth|signin|sso|id|account|passport)\.|\/(log-?in|sign-?in|signup|auth|oauth|sso)(\/|$|\?)/i;

// "Conectar varias" (PLAN-v5 F3): ONE page, ONE Chrome permission prompt for every marked site.
async function handleAddMany(msg) {
  const sites = (msg.sites || []).filter((s) => s && s.key && parseChatUrl(s.url).ok);
  if (!sites.length || sites.length !== (msg.sites || []).length) {
    sendToBridge({ type: "result", id: msg.id, ok: false, error: "bad_url" });
    return;
  }
  const q = new URLSearchParams({ batch: msg.batch_id, sites: JSON.stringify(sites.map((s) => ({ key: s.key, name: s.name, url: s.url }))) });
  const tab = await chrome.tabs.create({ url: chrome.runtime.getURL("add.html?" + q), active: true });
  await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
  sendToBridge({ type: "result", id: msg.id, ok: true, text: "", via: "add_many" });
}

// One site of "Conectar varias" (permission already granted): the same check as "+ Añadir otra IA",
// but a site that asks Iván to log in waits for him (wait_login_s) instead of failing at once.
function handleAddCheck(msg) {
  sendToBridge({ type: "result", id: msg.id, ok: true, text: "", via: "add_check" });
  testSite({ add_id: msg.add_id, key: msg.key, name: msg.name, url: parseChatUrl(msg.url).url, waitLoginS: Number(msg.wait_login_s) || 0 });
}

function addProgress(addId, step, ok, text) {
  sendToBridge({ type: "add_progress", add_id: addId, step, ok, text });
}

async function favicon(tabId) {
  try {
    const t = await chrome.tabs.get(tabId);
    if (!t.favIconUrl || !/^https:/.test(t.favIconUrl)) return null;
    const r = await fetch(t.favIconUrl);
    const type = r.headers.get("content-type") || "";
    if (!r.ok || !/^image\//.test(type)) return null;
    const buf = new Uint8Array(await r.arrayBuffer());
    if (buf.length > 60000) return null;
    let bin = "";
    for (let i = 0; i < buf.length; i += 8192) bin += String.fromCharCode(...buf.subarray(i, i + 8192));
    return `data:${type.split(";")[0]};base64,${btoa(bin)}`;
  } catch (e) {
    return null; // the icon lives on another domain, or there is none: the app draws a letter
  }
}

// 2) Permission granted: open the site and find its text box, reporting every step.
//    Then the bridge sends the test message like any other one (through its account guard).
async function testSite(m) {
  const done = (ok, extra) => sendToBridge({ type: "add_done", add_id: m.add_id, ok, ...extra });
  SITES[m.key] = genericSite(m.name, m.url);
  addProgress(m.add_id, "permission", true, "Permiso concedido");
  addProgress(m.add_id, "open", null, "Abriendo la web…");
  let tabId = null;
  jobStarted(m.key);
  try {
    tabId = await siteTab(m.key);
    await chrome.tabs.update(tabId, { url: m.url });
    await sleep(800);
    await waitLoaded(tabId, 45000);
    const origin = new URL(m.url).origin;
    // A site that sends you to another address to log in (Google, Microsoft…): webllm has no permission
    // there and must not read that page anyway; it counts as "asks you to log in".
    // Another address that is not a login page means the chat has moved: webllm has no permission
    // there, so it says so (with the new address) instead of waiting for a login that is not coming.
    const look = async () => {
      const t = await chrome.tabs.get(tabId);
      let where = null;
      try { where = new URL(t.url || t.pendingUrl || ""); } catch (e) { where = null; }
      if (where && where.origin !== origin && /^https?:$/.test(where.protocol)) {
        return LOGIN_PAGE.test(where.hostname + where.pathname) ? { loginWall: true, url: t.url } : { moved: t.url };
      }
      return call(tabId, "state", SITES[m.key]);
    };
    let st;
    const t0 = Date.now();
    for (;;) {
      if (cancelled.has(m.add_id)) return done(false, { error: "cancelled" });
      st = await look();
      if (st.moved || st.challenge || st.loginWall || st.input || Date.now() - t0 > 20000) break;
      await sleep(1000);
    }
    addProgress(m.add_id, "open", true, "Web abierta");
    if (st.moved) return done(false, { error: "moved", detail: String(st.moved).slice(0, 300) });
    if ((st.challenge || st.loginWall) && m.waitLoginS > 0) {
      // Show it to Iván and wait: he logs in (or solves the verification) himself; webllm never types
      // credentials and never touches a verification.
      const kind = st.challenge ? "challenge" : "login";
      humanStart(m.key, kind);
      try {
        const tab = await chrome.tabs.get(tabId);
        await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
        await chrome.tabs.update(tabId, { active: true });
        const mins = Math.max(1, Math.round(m.waitLoginS / 60));
        const minutes = mins === 1 ? "1 minuto" : `${mins} minutos`;
        addProgress(m.add_id, "login", null, st.challenge
          ? `Te espera: resuelve la verificación en la ventanita de webllm (hasta ${minutes})`
          : `Te espera: entra con tu cuenta en la ventanita de webllm (hasta ${minutes})`);
        notify(m.key, kind, `${m.name} te pide ${st.challenge ? "una verificación" : "entrar con tu cuenta"}. Hazlo tú en la ventana de webllm; te espero ${minutes}.`);
        const t1 = Date.now();
        while ((st.challenge || st.loginWall || !st.input) && Date.now() - t1 < m.waitLoginS * 1000) {
          await sleep(2000);
          if (cancelled.has(m.add_id)) return done(false, { error: "cancelled" });
          st = await look().catch(() => ({ loginWall: true }));
        }
      } finally {
        humanEnd(m.key);
      }
      if (!st.challenge && !st.loginWall && st.input) addProgress(m.add_id, "login", true, "Has entrado");
    }
    if (st.challenge || st.loginWall) {
      const tab = await chrome.tabs.get(tabId);
      await chrome.windows.update(tab.windowId, { focused: true, state: "normal" });
      await chrome.tabs.update(tabId, { active: true });
      return done(false, { error: st.challenge ? "challenge" : "login_required", detail: String(st.challenge || st.url) });
    }
    if (!st.input) {
      const d = await call(tabId, "diagnose", SITES[m.key]).catch(() => null);
      return done(false, { error: "no_input", detail: JSON.stringify(d).slice(0, 6000) });
    }
    addProgress(m.add_id, "input", true, "Caja de texto: encontrada");
    sendToBridge({ type: "add_ready", add_id: m.add_id, icon: await favicon(tabId) });
  } catch (e) {
    const code = e instanceof JobError ? e.code : "extension_error";
    done(false, { error: code, detail: e instanceof JobError ? e.detail : String(e && e.message || e) });
  } finally {
    jobFinished(m.key);
    cancelled.delete(m.add_id);
  }
}

chrome.runtime.onMessage.addListener((m) => {
  if (!m || !m.add_id) return;
  if (m.type === "add_test") testSite(m);
  else if (m.type === "add_denied") sendToBridge({ type: "add_done", add_id: m.add_id, ok: false, error: "permission_denied" });
  else if (m.type === "add_cancel") sendToBridge({ type: "add_done", add_id: m.add_id, ok: false, error: "cancelled" });
});
chrome.runtime.onMessage.addListener((m) => {
  if (m && m.type === "add_many_permission" && m.batch_id) sendToBridge({ type: "add_many_permission", batch_id: m.batch_id, ok: !!m.ok });
});

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
  if (msg.type === "cancel") { cancelled.add(msg.id); return; }
  ensureSite(msg);
  if (msg.type === "add_site") handleAddSite(msg);
  else if (msg.type === "add_many") handleAddMany(msg);
  else if (msg.type === "file_part") onFilePart(msg);
  else if (msg.type === "discover") handleDiscover(msg);
  else if (msg.type === "teach") handleTeach(msg);
  else if (msg.type === "add_check") handleAddCheck(msg);
  else if (msg.type === "job") handleJob(msg);
  else if (msg.type === "diagnose") handleDiagnose(msg);
  else if (msg.type === "show") handleShow(msg);
}
