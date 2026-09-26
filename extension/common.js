// Shared by the service worker (importScripts), the "add a site" page and the
// tests (node): pure helpers, no chrome.* calls.
(function (root) {
  // Claude and ChatGPT stay out of webllm, whatever address is pasted.
  const BLOCKED_HOSTS = ["claude.ai", "anthropic.com", "chatgpt.com", "chat.openai.com", "openai.com"];

  function parseChatUrl(text) {
    let u;
    try { u = new URL(String(text || "").trim()); } catch (e) { return { ok: false, error: "bad_url" }; }
    if (u.protocol !== "https:") return { ok: false, error: "not_https" };
    const host = u.hostname.toLowerCase();
    if (BLOCKED_HOSTS.some((b) => host === b || host.endsWith("." + b))) return { ok: false, error: "blocked" };
    return { ok: true, url: u.origin + u.pathname.replace(/\/+$/, "/"), origin: u.origin, host };
  }

  // chat.mistral.ai -> "mistral"; www.perplexity.ai -> "perplexity".
  function siteKey(host, taken) {
    const parts = host.replace(/^(chat|www|app|web)\./, "").split(".");
    const base = (parts.length > 1 ? parts[parts.length - 2] : parts[0]).replace(/[^a-z0-9]/g, "") || "web";
    let key = base;
    for (let n = 2; (taken || []).includes(key); n++) key = base + "-" + n;
    return key;
  }

  function siteName(key) {
    const base = key.replace(/-\d+$/, "");
    return base.charAt(0).toUpperCase() + base.slice(1);
  }

  // A site nobody wrote selectors for: driver.js falls back to generic detection
  // (visible text box, "send" / "copy" / "stop" labels, Enter to send).
  function genericSite(name, url) {
    return { name, newChat: url, input: [], send: [], stop: [], copy: [], answer: [],
             loginUrl: "/auth|/login|/signin|/sign_in|/sign-in|/signup" };
  }

  // Buttons webllm never presses, whatever it is doing (PLAN-v5 D21), in the catalog's languages:
  // publishing, sharing, deleting, regenerating, deploying, paying, logging out, reporting.
  const FORBIDDEN_RE = new RegExp([
    "publish", "publicar", "publier", "veröffentlichen", "pubblica", "发布", "發佈", "公開", "공개",
    "share", "compartir", "partager", "teilen", "condividi", "分享", "共有", "공유",
    "delete", "borrar", "eliminar", "supprimer", "löschen", "elimina", "删除", "刪除", "削除", "삭제",
    "regenerat", "regenerar", "régénérer", "rigenera", "retry", "reintentar", "réessayer", "重新生成", "再生成", "重试",
    "deploy", "desplegar", "déployer", "bereitstellen", "部署", "デプロイ", "배포",
    "upgrade", "subscribe", "suscrib", "\\bpagar\\b", "\\bpay\\b", "\\bbuy\\b", "comprar", "acheter", "订阅", "升级", "購入",
    "log ?out", "sign ?out", "cerrar sesi[oó]n", "déconnexion", "退出登录", "ログアウト",
    "report", "denunciar", "signaler", "举报",
  ].join("|"), "i");

  // The modes Iván can switch on (Open WebUI's "+"), and how pages name them. Order matters:
  // "Deep research" is investigar, not buscar.
  const MODES = [
    ["investigar", /deep ?research|investigaci[oó]n|recherche approfondie|深度研究/i],
    ["constructor", /web ?dev|artifact|canvas|builder|constructor|slides|diapositivas|ok computer|全栈|网页开发/i],
    ["imagen", /image|imagen|dibuj|图像|图片|画像/i],
    ["pensar", /think|reason|razona|pensar|pensamiento|réfléchi|深度思考|思考|推理/i],
    ["buscar", /search|buscar|b[uú]squeda|internet|recherche|联网|搜索|検索/i],
  ];
  function modeOf(name) {
    const hit = MODES.find(([, re]) => re.test(String(name || "")));
    return hit ? hit[0] : null;
  }

  // "Qwen3.8-Max" and "qwen 3.8 max" are the same model name.
  function normName(s) {
    return String(s || "").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9.\u3040-\u30ff\u4e00-\u9fff]+/g, "");
  }

  root.WEBLLM_COMMON = { BLOCKED_HOSTS, parseChatUrl, siteKey, siteName, genericSite, FORBIDDEN_RE, MODES, modeOf, normName };
  if (typeof module !== "undefined") module.exports = root.WEBLLM_COMMON;
})(typeof self !== "undefined" ? self : globalThis);
