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

  root.WEBLLM_COMMON = { BLOCKED_HOSTS, parseChatUrl, siteKey, siteName, genericSite };
  if (typeof module !== "undefined") module.exports = root.WEBLLM_COMMON;
})(typeof self !== "undefined" ? self : globalThis);
