// Page-side driver, injected into the chat page's MAIN world by background.js.
// It only reads the page structure and types/clicks like a user would. It never
// reads cookies or storage, and it never touches CAPTCHAs: it only reports them.
(() => {
  if (window.__webllmDriver) return;

  const captured = [];

  // Record the text the page puts on the clipboard when its own "copy" button
  // is clicked: that is the exact markdown of the answer.
  const hookClipboard = () => {
    if (window.__webllmClipboardHooked) return;
    window.__webllmClipboardHooked = true;
    const cb = navigator.clipboard;
    if (cb && cb.writeText) {
      const orig = cb.writeText.bind(cb);
      cb.writeText = async (t) => {
        captured.push(String(t));
        try { return await orig(t); } catch (e) { return undefined; }
      };
    }
    if (cb && cb.write) {
      const origWrite = cb.write.bind(cb);
      cb.write = async (items) => {
        try {
          for (const it of items) {
            if (it.types.includes("text/plain")) captured.push(await (await it.getType("text/plain")).text());
          }
        } catch (e) { /* ignore */ }
        try { return await origWrite(items); } catch (e) { return undefined; }
      };
    }
    const origExec = document.execCommand.bind(document);
    document.execCommand = function (cmd, ...rest) {
      if (String(cmd).toLowerCase() === "copy") {
        const a = document.activeElement;
        const t = (a && "value" in a && a.value) || String(document.getSelection() || "");
        if (t) captured.push(t);
      }
      return origExec(cmd, ...rest);
    };
    window.addEventListener("copy", (e) => {
      let t = "";
      try { t = e.clipboardData ? e.clipboardData.getData("text/plain") : ""; } catch (err) { t = ""; }
      if (t) captured.push(t);
    });
  };
  hookClipboard();

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Really on screen: some size and not transparent (sites keep invisible
  // 0x0 / opacity-0 helper elements, e.g. z.ai's background verification).
  const visible = (el, minSize = 2) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width < minSize || r.height < minSize) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.display !== "none" && Number(st.opacity) > 0.05;
  };

  const labelOf = (el) => {
    const cls = typeof el.className === "string" ? el.className : (el.className && el.className.baseVal) || "";
    return [el.getAttribute("aria-label"), el.getAttribute("title"), el.getAttribute("data-testid"), cls, el.id]
      .filter(Boolean).join(" ");
  };

  const all = (sels) => {
    for (const s of sels || []) {
      try {
        const found = [...document.querySelectorAll(s)].filter((el) => visible(el));
        if (found.length) return found;
      } catch (e) { /* bad selector: try the next one */ }
    }
    return [];
  };

  const clickables = () => [...document.querySelectorAll("button,[role='button']")].filter((el) => visible(el));

  const findInput = (site) => {
    const bySite = all(site.input);
    if (bySite.length) return bySite[bySite.length - 1];
    const generic = [...document.querySelectorAll("textarea,[contenteditable='true'],input[type='text']")].filter((el) => visible(el));
    return generic.length ? generic[generic.length - 1] : null;
  };

  const SEND_RE = /send|enviar|submit|发送/i;
  const STOP_RE = /stop|detener|interrumpir|停止/i;
  const COPY_RE = /copy|copiar|复制/i;

  const findSend = (site) => {
    const bySite = all(site.send).map((el) => el.closest("button,[role='button']") || el);
    const cands = bySite.length ? bySite : clickables().filter((b) => SEND_RE.test(labelOf(b)));
    const enabled = cands.filter((b) => !b.disabled && b.getAttribute("aria-disabled") !== "true");
    return enabled.length ? enabled[enabled.length - 1] : null;
  };

  const isGenerating = (site) => {
    if (all(site.stop).length) return true;
    return clickables().some((b) => STOP_RE.test(labelOf(b)) && !/stop-?watch/i.test(labelOf(b)));
  };

  const inCode = (el) => !!el.closest("pre,code,[class*='code-block'],[class*='codeblock'],[class*='code-header']");

  const copyButtons = (site) => {
    const bySite = all(site.copy).map((el) => el.closest("button,[role='button']") || el);
    if (bySite.length) return bySite;
    return clickables().filter((b) => COPY_RE.test(labelOf(b)) && !/code/i.test(labelOf(b)) && !inCode(b));
  };

  const answers = (site) => all(site.answer);

  const overlays = () => [...document.querySelectorAll(
    "[role='dialog'],[aria-modal='true'],[role='alert'],[role='alertdialog'],[class*='modal' i],[class*='dialog' i],[class*='popup' i],[class*='toast' i],[class*='notification' i]"
  )].filter((el) => visible(el));

  const CHALLENGE_RE = /verify you are human|are you a robot|captcha|slide to verify|drag the slider|arrastra el control|desliza|verificaci[oó]n de seguridad|security check|unusual activity|actividad inusual|请完成验证|滑块|人机验证/i;
  const CHALLENGE_FRAME_RE = /captcha|challenges\.cloudflare\.com|hcaptcha|recaptcha|turnstile|geetest|arkoselabs/i;
  const RATE_RE = /too many (requests|messages)|rate limit|limit reached|reached (your|the) (daily |usage |message )?limit|try again later|demasiadas (solicitudes|peticiones)|has alcanzado (el|tu) l[ií]mite|server is busy|servidor (est[aá] )?ocupado|服务器繁忙|请求过于频繁|次数已达上限/i;
  const BAN_RE = /account (has been |is )?(suspended|banned|disabled|restricted)|cuenta (suspendida|bloqueada|inhabilitada)|账号(已)?被(封|禁)/i;
  const LOGIN_RE = /log in or sign up|sign in to (get started|continue)|please (log|sign) in|inicia sesi[oó]n para|请登录|登录后/i;

  const detectChallenge = () => {
    const frames = [...document.querySelectorAll("iframe")].filter((f) => visible(f, 30) && CHALLENGE_FRAME_RE.test(f.src || ""));
    if (frames.length) return "captcha (iframe)";
    const widgets = [...document.querySelectorAll(
      "[id*='captcha' i],[class*='captcha' i],[id^='nc_'],[class*='baxia' i],[class*='nc-container' i],[id*='aliyunCaptcha' i]"
    )].filter((w) => visible(w, 30));
    if (widgets.length) return "captcha (widget)";
    for (const o of overlays()) {
      const t = (o.innerText || "").slice(0, 600);
      if (CHALLENGE_RE.test(t)) return t.slice(0, 160);
    }
    return null;
  };

  const lastAnswerEl = (site) => {
    const a = answers(site);
    if (a.length) return a[a.length - 1];
    const cps = copyButtons(site);
    if (!cps.length) return null;
    // Walk up from the last copy button to the smallest block holding real text.
    let el = cps[cps.length - 1].parentElement;
    while (el && el !== document.body && (el.innerText || "").trim().length < 2) el = el.parentElement;
    return el;
  };

  const state = (site) => {
    const input = findInput(site);
    const loginUrl = site.loginUrl ? new RegExp(site.loginUrl, "i").test(location.pathname) : false;
    const passwordBox = [...document.querySelectorAll("input[type='password']")].some((el) => visible(el));
    const bodyText = (document.body && document.body.innerText) || "";
    const loginText = (site.loginText && new RegExp(site.loginText, "i").test(bodyText)) || (!input && LOGIN_RE.test(bodyText));
    let rate = null;
    let ban = null;
    for (const o of overlays()) {
      const t = (o.innerText || "").slice(0, 600);
      if (!rate && RATE_RE.test(t)) rate = t.slice(0, 200);
      if (!ban && BAN_RE.test(t)) ban = t.slice(0, 200);
    }
    const last = lastAnswerEl(site);
    const lastText = last ? (last.innerText || "") : "";
    if (!rate && lastText.length < 300 && RATE_RE.test(lastText)) rate = lastText.slice(0, 200);
    if (!ban && !input && BAN_RE.test(bodyText)) ban = (bodyText.match(BAN_RE) || [""])[0];
    const pop = overlays().map((o) => (o.innerText || "").trim()).find((t) => t.length > 0);
    const modelEl = all(site.modelLabel)[0];
    return {
      url: location.href,
      hidden: document.hidden,
      overlay: pop ? pop.slice(0, 80) : null,
      modelName: modelEl ? (modelEl.innerText || "").trim().slice(0, 60) : null,
      input: !!input,
      inputLen: input ? ("value" in input ? input.value.length : (input.innerText || "").length) : 0,
      generating: isGenerating(site),
      copyCount: copyButtons(site).length,
      answerCount: answers(site).length,
      lastAnswerLen: lastText.length,
      bodyLen: bodyText.length,
      challenge: detectChallenge(),
      loginWall: loginUrl || passwordBox || !!loginText,
      rateLimited: rate,
      banned: ban,
    };
  };

  const insert = (site, text) => {
    const el = findInput(site);
    if (!el) return { ok: false, error: "no_input" };
    el.focus();
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: el.value.length > 0, method: "value", len: el.value.length };
    }
    const sel = document.getSelection();
    sel.selectAllChildren(el);
    document.execCommand("delete");
    const ok = document.execCommand("insertText", false, text);
    return { ok: ok && (el.innerText || "").length > 0, method: "insertText", len: (el.innerText || "").length };
  };

  const send = (site) => {
    const b = findSend(site);
    if (b) {
      b.click();
      return { ok: true, method: "click" };
    }
    const el = findInput(site);
    if (!el) return { ok: false, error: "no_input" };
    for (const type of ["keydown", "keypress", "keyup"]) {
      el.dispatchEvent(new KeyboardEvent(type, { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    }
    return { ok: true, method: "enter" };
  };

  const capture = async (site) => {
    const cps = copyButtons(site);
    if (!cps.length) return { ok: false, error: "no_copy_button" };
    captured.length = 0;
    cps[cps.length - 1].click();
    for (let i = 0; i < 10 && !captured.length; i++) await sleep(150);
    const text = captured.length ? captured[captured.length - 1] : "";
    return text ? { ok: true, text, via: "copy-button" } : { ok: false, error: "copy_captured_nothing" };
  };

  // Fallback when the page has no usable copy button: rebuild markdown from
  // the last answer's HTML, skipping "thinking" blocks and UI chrome.
  const SKIP_RE = /think|reason|thought|toolbar|code-header|code-block-header|banner|copy/i;
  const toMarkdown = (node, depth = 0) => {
    if (node.nodeType === 3) return node.nodeValue;
    if (node.nodeType !== 1) return "";
    const el = node;
    const tag = el.tagName;
    if (["BUTTON", "SVG", "STYLE", "SCRIPT", "svg"].includes(tag)) return "";
    if (tag !== "PRE" && SKIP_RE.test(labelOf(el))) return "";
    const kids = () => [...el.childNodes].map((c) => toMarkdown(c, depth)).join("");
    switch (tag) {
      case "PRE": {
        const code = el.querySelector("code");
        const cls = (code && code.className) || el.className || "";
        const m = /language-([\w+#.-]+)/.exec(cls);
        const body = ((code || el).innerText || "").replace(/\n$/, "");
        return "\n```" + (m ? m[1] : "") + "\n" + body + "\n```\n";
      }
      case "CODE": return "`" + el.innerText + "`";
      case "BR": return "\n";
      case "P": return "\n" + kids() + "\n";
      case "H1": case "H2": case "H3": case "H4": case "H5": case "H6":
        return "\n" + "#".repeat(Number(tag[1])) + " " + kids().trim() + "\n";
      case "STRONG": case "B": return "**" + kids() + "**";
      case "EM": case "I": return "*" + kids() + "*";
      case "A": return "[" + kids() + "](" + (el.getAttribute("href") || "") + ")";
      case "UL": case "OL": {
        const items = [...el.children].filter((c) => c.tagName === "LI");
        return "\n" + items.map((li, i) => "  ".repeat(depth) + (tag === "OL" ? (i + 1) + ". " : "- ") +
          [...li.childNodes].map((c) => toMarkdown(c, depth + 1)).join("").trim()).join("\n") + "\n";
      }
      case "BLOCKQUOTE": return "\n" + kids().trim().split("\n").map((l) => "> " + l).join("\n") + "\n";
      case "TABLE": {
        const rows = [...el.querySelectorAll("tr")].map((tr) => "| " + [...tr.children].map((td) => (td.innerText || "").trim()).join(" | ") + " |");
        if (rows.length > 1) rows.splice(1, 0, rows[0].replace(/[^|]+/g, " --- "));
        return "\n" + rows.join("\n") + "\n";
      }
      case "DIV": return kids() + "\n";
      default: return kids();
    }
  };

  const fallback = (site) => {
    const el = lastAnswerEl(site);
    if (!el) return { ok: false, error: "no_answer_element" };
    const text = toMarkdown(el).replace(/\n{3,}/g, "\n\n").trim();
    return text ? { ok: true, text, via: "dom" } : { ok: false, error: "empty_answer" };
  };

  // Structure-only summary used to fix selectors remotely (no text content of
  // the conversation beyond short labels, no cookies, no storage).
  const diagnose = (site) => {
    const d = (el) => ({ tag: el.tagName, id: el.id || undefined, label: labelOf(el).slice(0, 120), text: (el.innerText || "").trim().slice(0, 30) });
    return {
      url: location.href,
      title: document.title,
      state: state(site),
      inputs: [...document.querySelectorAll("textarea,[contenteditable='true'],input")].filter((el) => visible(el)).map(d).slice(-6),
      clickables: clickables().map(d).slice(-40),
      answerCandidates: [...document.querySelectorAll("[class*='markdown' i],[class*='answer' i],[class*='response' i],[class*='assistant' i],[class*='message' i]")]
        .filter((el) => visible(el)).map((el) => ({ tag: el.tagName, label: labelOf(el).slice(0, 100), textLen: (el.innerText || "").length })).slice(-12),
      overlays: overlays().map((o) => (o.innerText || "").trim().slice(0, 120)).slice(-5),
    };
  };

  window.__webllmDriver = { state, insert, send, capture, fallback, diagnose };
})();
