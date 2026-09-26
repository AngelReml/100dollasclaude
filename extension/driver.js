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
  // Also for the clicks defined before the capabilities section below (send, copy).
  const FORBIDDEN_RE_EARLY = (window.WEBLLM_COMMON && window.WEBLLM_COMMON.FORBIDDEN_RE) || /publish|publicar|share|compartir|delete|borrar|regenerat|deploy/i;

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

  // PLAN-v5 F6, layer 1: text boxes of every usual kind. Rich editors (contenteditable "plaintext-only" or
  // "", role="textbox") first, like textareas; plain inputs (also without a type) only if there is nothing else.
  const BOX_SEL = "textarea,[contenteditable]:not([contenteditable='false']),[role='textbox']";
  const LINE_SEL = "input[type='text'],input:not([type])";
  const editable = (el) => !!el && (el.matches(BOX_SEL) || el.matches(LINE_SEL)) && el.type !== "password";
  const findInput = (site) => {
    const bySite = all(site.input);
    if (bySite.length) return bySite[bySite.length - 1];
    for (const sel of [BOX_SEL, LINE_SEL]) {
      const generic = [...document.querySelectorAll(sel)].filter((el) => visible(el) && !el.closest("nav,aside,[role='navigation']"));
      if (generic.length) return generic[generic.length - 1];
    }
    return null;
  };

  // The names chat pages give these buttons, in the catalog's languages.
  const SEND_RE = /send|enviar|envoyer|senden|invia|submit|发送|發送|送出|送信|전송|보내기/i;
  // Whole words only, and only in a button's own name (aria-label, title, test id, short text):
  // class names are not names (a "nonstop-toggle" is not a stop button), and a false "stop"
  // would make webllm wait for an answer that is already finished.
  const STOP_RE = /(^|[^a-zà-ÿ])(stop|detener|parar|interrumpir|arr[êe]ter|stopper|anhalten|stoppen|interrompi|fermare|ferma)([^a-zà-ÿ]|$)|停止|中止|중지|정지/i;
  const COPY_RE = /copy|copiar|copier|kopieren|copia|复制|複製|拷贝|コピー|복사/i;

  const nameOf = (el) => {
    const text = (el.innerText || "").trim();
    return [el.getAttribute("aria-label"), el.getAttribute("title"), el.getAttribute("data-testid"),
      text.length <= 40 ? text : ""].filter(Boolean).join(" ");
  };
  // Inside the window: pages often park a finished "stop" button off-screen instead of removing it.
  const onScreen = (el) => {
    const r = el.getBoundingClientRect();
    return r.right > 0 && r.bottom > 0 && r.left < window.innerWidth && r.top < window.innerHeight;
  };
  const isEnabled = (b) => !b.disabled && b.getAttribute("aria-disabled") !== "true";

  const findSend = (site) => {
    const bySite = all(site.send).map((el) => el.closest("button,[role='button']") || el);
    const cands = bySite.length ? bySite : clickables().filter((b) => SEND_RE.test(labelOf(b) + " " + nameOf(b)));
    const enabled = cands.filter((b) => !b.disabled && b.getAttribute("aria-disabled") !== "true");
    return enabled.length ? enabled[enabled.length - 1] : null;
  };

  // The "stop" button that says an answer is being written, or null.
  const stopButton = (site) =>
    all(site.stop).find(onScreen) || clickables().find((b) => onScreen(b) && isEnabled(b) && STOP_RE.test(nameOf(b))) || null;
  const isGenerating = (site) => !!stopButton(site);

  const inCode = (el) => !!el.closest("pre,code,[class*='code-block'],[class*='codeblock'],[class*='code-header']");

  const copyButtons = (site) => {
    const bySite = all(site.copy).map((el) => el.closest("button,[role='button']") || el);
    if (bySite.length) return bySite;
    return clickables().filter((b) => COPY_RE.test(labelOf(b) + " " + nameOf(b)) && !/code|código/i.test(labelOf(b)) && !inCode(b));
  };

  const answers = (site) => all(site.answer);

  const overlays = () => [...document.querySelectorAll(
    "[role='dialog'],[aria-modal='true'],[role='alert'],[role='alertdialog'],[class*='modal' i],[class*='dialog' i],[class*='popup' i],[class*='toast' i],[class*='notification' i]"
  )].filter((el) => visible(el));

  const CHALLENGE_RE = /verify you are human|are you a robot|captcha|slide to verify|drag the slider|arrastra el control|desliza|verificaci[oó]n de seguridad|security check|unusual activity|actividad inusual|请完成验证|滑块|人机验证/i;
  const CHALLENGE_FRAME_RE = /captcha|challenges\.cloudflare\.com|hcaptcha|recaptcha|turnstile|geetest|arkoselabs/i;
  // Limits of YOUR account (pause the site) vs the site being overloaded (just retry later).
  const RATE_RE = /too many (requests|messages)|rate limit|limit reached|reached (your|the) (daily |usage |message )?limit|demasiadas (solicitudes|peticiones)|has alcanzado (el|tu) l[ií]mite|请求过于频繁|次数已达上限/i;
  const BUSY_RE = /at capacity|server is busy|servers? (are|is) (busy|overloaded)|overloaded|temporarily unavailable|servidor (est[aá] )?(ocupado|saturado)|服务器繁忙/i;
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

  // Sites without selectors (added from the app): usual markers of an AI message.
  // querySelectorAll is in document order, so the last match is the innermost
  // element of the last message.
  const GENERIC_ANSWER = "[data-message-author-role='assistant'],[data-role='assistant'],[class*='assistant' i]," +
    "[class*='markdown' i],[class*='response' i],[class*='answer' i],[class*='bot-message' i],[class*='ai-message' i]," +
    "[data-testid*='assistant' i],[data-testid*='bot-message' i],[class*='prose' i],[class*='respuesta' i],[class*='reponse' i]";
  const genericAnswers = () => [...document.querySelectorAll(GENERIC_ANSWER)].filter((el) =>
    visible(el) && (el.innerText || "").trim() && !el.querySelector("textarea,input,[contenteditable='true']"));

  const lastAnswerEl = (site) => {
    const a = answers(site);
    if (a.length) return a[a.length - 1];
    const cps = copyButtons(site);
    if (!cps.length) {
      if ((site.answer || []).length) return null;
      const g = genericAnswers();
      return g.length ? g[g.length - 1] : null;
    }
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
    let busy = null;
    for (const o of overlays()) {
      const t = (o.innerText || "").slice(0, 600);
      if (!busy && BUSY_RE.test(t)) busy = t.slice(0, 200);
      if (!rate && RATE_RE.test(t)) rate = t.slice(0, 200);
      if (!ban && BAN_RE.test(t)) ban = t.slice(0, 200);
    }
    const last = lastAnswerEl(site);
    const lastText = last ? (last.innerText || "") : "";
    if (!busy && lastText.length < 300 && BUSY_RE.test(lastText)) busy = lastText.slice(0, 200);
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
      rateLimited: busy ? null : rate,
      siteBusy: busy,
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
    if (b && !FORBIDDEN_RE_EARLY.test(nameOf(b))) {
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
    if (FORBIDDEN_RE_EARLY.test(nameOf(cps[cps.length - 1]))) return { ok: false, error: "forbidden" };
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
      stop: (() => { const b = stopButton(site); return b ? { ...d(b), name: nameOf(b).slice(0, 80) } : null; })(),
    };
  };

  // ------------------------------------------------ what each chat can do (PLAN-v5 F4, D21, D22)
  // Loaded with common.js in this same (page) world: forbidden buttons, modes, model names.
  const C = window.WEBLLM_COMMON || {};
  const FORBIDDEN_RE = C.FORBIDDEN_RE || /publish|publicar|share|compartir|delete|borrar|regenerat|deploy/i;
  const norm = C.normName || ((x) => String(x || "").toLowerCase());
  const forbidden = (el) => FORBIDDEN_RE.test(nameOf(el)) || FORBIDDEN_RE.test((el.innerText || "").slice(0, 80));
  // Every click webllm makes goes through here: a forbidden button is never pressed, whatever asked for it.
  const safeClick = (el) => {
    if (!el || forbidden(el)) return false;
    el.click();
    return true;
  };
  window.__webllmSafeClick = safeClick;

  const MODEL_RE = /model|modelo|modèle|模型|モデル/i;
  const FAMILY_RE = /qwen|glm|deepseek|kimi|gpt|claude|gemini|llama|mistral|grok|hermes|olmo|mercury|sonar|mimo|longcat|seed|ling/i;
  const PLUS_RE = /^\+$|attach|adjuntar|upload|subir|more|más|tools|herramientas|añadir|add|joindre|添加|上传|附件|追加/i;
  const OPTION_SEL = "[role='menuitem'],[role='menuitemradio'],[role='menuitemcheckbox'],[role='option']";
  const hasPopup = (el) => el.hasAttribute("aria-haspopup") || el.hasAttribute("aria-expanded");
  const optionName = (el) => (nameOf(el) || (el.innerText || "").trim().split("\n")[0]).slice(0, 80);
  const isChecked = (el) => ["true", "mixed"].includes(el.getAttribute("aria-checked")) || el.getAttribute("aria-selected") === "true" ||
    el.getAttribute("aria-pressed") === "true" || el.getAttribute("data-state") === "checked" || el.getAttribute("data-state") === "on";
  const visibleOptions = () => [...document.querySelectorAll(OPTION_SEL)].filter((el) => visible(el));

  const modelButton = (site) => {
    const bySite = all(site.modelButton);
    if (bySite.length) return bySite[0].closest("button,[role='button']") || bySite[0];
    const cands = clickables().filter((b) => hasPopup(b) && !forbidden(b));
    return cands.find((b) => MODEL_RE.test(nameOf(b))) || cands.find((b) => FAMILY_RE.test((b.innerText || "").slice(0, 60))) || null;
  };
  const plusButton = (site) => {
    const bySite = all(site.plusButton);
    if (bySite.length) return bySite[0].closest("button,[role='button']") || bySite[0];
    const model = modelButton(site);
    return clickables().find((b) => b !== model && hasPopup(b) && !forbidden(b) && PLUS_RE.test(nameOf(b) || (b.innerText || "").trim())) || null;
  };
  const modeToggles = () => [...document.querySelectorAll("button[aria-pressed],[role='switch'],[role='checkbox']:not(input)")]
    .filter((el) => visible(el) && !forbidden(el) && !el.closest("[role='menu'],[role='listbox']"));

  const closeMenu = async (trigger) => {
    for (const target of [document.activeElement, document.body, document]) {
      target && target.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
    }
    await sleep(250);
    if (visibleOptions().length && trigger && trigger.getAttribute("aria-expanded") === "true") {
      safeClick(trigger); // a toggle that does not listen to Escape: the same trigger closes it
      await sleep(250);
    }
    return !visibleOptions().length;
  };

  // Open a menu, read its options, close it. Never presses an option.
  const readMenu = async (trigger) => {
    if (!trigger || !safeClick(trigger)) return { ok: false, options: [] };
    let opts = [];
    for (let i = 0; i < 8 && !opts.length; i++) { await sleep(150); opts = visibleOptions(); }
    const options = opts.map((el) => ({ name: optionName(el), selected: isChecked(el), forbidden: forbidden(el) }))
      .filter((o) => o.name);
    const closed = await closeMenu(trigger);
    return { ok: true, options, closed };
  };

  // The chat's card: its models, its modes, its "+" menu, what files it takes. Read-only: menus are opened,
  // read and closed; no option is pressed and nothing is sent.
  const discover = async (site) => {
    const mb = modelButton(site);
    const pb = plusButton(site);
    const models = mb ? await readMenu(mb) : { ok: false, options: [] };
    const plus = pb ? await readMenu(pb) : { ok: false, options: [] };
    const files = [...document.querySelectorAll("input[type='file']")].map((i) => ({ accept: i.getAttribute("accept") || "", multiple: i.multiple }));
    return {
      ok: true,
      url: location.href,
      model_button: mb ? optionName(mb) : null,
      current_model: mb ? ((mb.innerText || "").trim().split("\n")[0] || optionName(mb)).slice(0, 80) : null,
      models: models.options.filter((o) => !o.forbidden).map((o) => ({ name: o.name, selected: o.selected })),
      plus: plus.options.filter((o) => !o.forbidden).map((o) => o.name),
      modes: modeToggles().map((el) => ({ name: nameOf(el).slice(0, 60) || (el.innerText || "").trim().slice(0, 60), on: isChecked(el),
        mode: C.modeOf ? C.modeOf(nameOf(el) || el.innerText) : null })),
      files,
      closed: (models.closed !== false) && (plus.closed !== false),
    };
  };

  // Put this model in the page's selector and confirm it on the page (D21: what you see is what is used).
  const chooseModel = async (site, wanted) => {
    const mb = modelButton(site);
    if (!mb) return { ok: false, error: "no_model_button" };
    const want = norm(wanted);
    const shows = () => norm((mb.innerText || "") + " " + nameOf(mb)).includes(want);
    if (shows()) return { ok: true, model: wanted, already: true };
    if (!safeClick(mb)) return { ok: false, error: "forbidden" };
    let opts = [];
    for (let i = 0; i < 8 && !opts.length; i++) { await sleep(150); opts = visibleOptions(); }
    const hit = opts.find((el) => norm(optionName(el)) === want) || opts.find((el) => norm(optionName(el)).includes(want));
    if (!hit) {
      const names = opts.map(optionName);
      await closeMenu(mb);
      return { ok: false, error: "model_not_found", options: names };
    }
    if (!safeClick(hit)) { await closeMenu(mb); return { ok: false, error: "forbidden" }; }
    await sleep(500);
    if (visibleOptions().length) await closeMenu(mb);
    for (let i = 0; i < 6; i++) {
      if (shows()) return { ok: true, model: wanted };
      await sleep(250);
    }
    return { ok: false, error: "not_confirmed", shows: ((mb.innerText || "").trim() || nameOf(mb)).slice(0, 80) };
  };

  // Switch a mode on or off and confirm it on the page: a toggle next to the box, or an item of the "+" menu.
  const setMode = async (site, mode, on = true) => {
    const direct = modeToggles().find((el) => C.modeOf && C.modeOf(nameOf(el) || el.innerText) === mode);
    if (direct) {
      if (isChecked(direct) !== on && !safeClick(direct)) return { ok: false, error: "forbidden" };
      for (let i = 0; i < 6; i++) {
        if (isChecked(direct) === on) return { ok: true, mode, name: nameOf(direct).slice(0, 60), via: "toggle" };
        await sleep(200);
      }
      return { ok: false, error: "not_confirmed", mode };
    }
    const pb = plusButton(site);
    if (!pb || !safeClick(pb)) return { ok: false, error: "mode_not_found", mode };
    let opts = [];
    for (let i = 0; i < 8 && !opts.length; i++) { await sleep(150); opts = visibleOptions(); }
    const item = opts.find((el) => C.modeOf && C.modeOf(optionName(el)) === mode);
    if (!item) { await closeMenu(pb); return { ok: false, error: "mode_not_found", mode, options: opts.map(optionName) }; }
    const name = optionName(item);
    if (isChecked(item) !== on && !safeClick(item)) { await closeMenu(pb); return { ok: false, error: "forbidden" }; }
    await sleep(400);
    // Confirmed when the page shows it: the item checked (menu still open) or a chip with its name.
    const confirmed = () => {
      const again = visibleOptions().find((el) => optionName(el) === name);
      if (again) return isChecked(again) === on;
      const chip = [...document.querySelectorAll("button,span,div")].some((el) => visible(el) && !el.children.length &&
        (el.innerText || "").trim() === name);
      return chip === on;
    };
    for (let i = 0; i < 6; i++) {
      if (confirmed()) { if (visibleOptions().length) await closeMenu(pb); return { ok: true, mode, name, via: "menu" }; }
      await sleep(250);
    }
    if (visibleOptions().length) await closeMenu(pb);
    return { ok: false, error: "not_confirmed", mode };
  };

  // Files travel into the page in parts (big ones too), then go in through the page's own file input,
  // with their sha256 checked here, and must then show on the page.
  const fileParts = (window.__webllmFileParts = window.__webllmFileParts || {});
  const fileChunk = (key, index, b64) => {
    (fileParts[key] = fileParts[key] || [])[index] = b64;
    return { ok: true };
  };
  const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const fromB64 = (b64) => {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  };
  const acceptsType = (input, meta) => {
    const acc = (input.getAttribute("accept") || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
    if (!acc.length) return true;
    const ext = "." + (meta.name.split(".").pop() || "").toLowerCase();
    return acc.some((a) => a === ext || a === meta.type || (a.endsWith("/*") && meta.type.startsWith(a.slice(0, -1))));
  };
  const attach = async (site, metas) => {
    const inputs = [...document.querySelectorAll(site.fileInput && site.fileInput.length ? site.fileInput.join(",") : "input[type='file']")];
    const out = [];
    const byInput = new Map();
    for (const meta of metas) {
      const parts = fileParts[meta.key] || [];
      if (parts.length !== meta.parts || parts.some((x) => x === undefined)) return { ok: false, error: "file_incomplete", name: meta.name };
      const chunks = parts.map(fromB64);
      const file = new File(chunks, meta.name, { type: meta.type || "application/octet-stream" });
      const sha = hex(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()));
      delete fileParts[meta.key];
      if (sha !== meta.sha256) return { ok: false, error: "file_changed", name: meta.name };
      const input = inputs.find((i) => acceptsType(i, meta));
      if (!input) return { ok: false, error: inputs.length ? "file_type_refused" : "no_file_input", name: meta.name };
      if (!byInput.has(input)) byInput.set(input, []);
      byInput.get(input).push(file);
      out.push({ name: meta.name, sha256: sha, size: file.size });
    }
    // An input that takes several files gets them all at once (setting it again would replace them);
    // one that takes a single file gets them one after the other, like choosing them one by one.
    const put = (input, files) => {
      const dt = new DataTransfer();
      files.forEach((f) => dt.items.add(f));
      input.files = dt.files;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    };
    for (const [input, files] of byInput) {
      if (input.multiple) put(input, files);
      else for (const f of files) { put(input, [f]); await sleep(400); }
    }
    // They must show on the page (a chip with the name) before anything is sent.
    const stem = (n) => n.slice(0, Math.min(n.length, 18));
    for (let i = 0; i < 30; i++) {
      const text = document.body.innerText || "";
      const titles = [...document.querySelectorAll("[title],[aria-label]")].map((el) => (el.getAttribute("title") || "") + " " + (el.getAttribute("aria-label") || "")).join(" ");
      const missing = out.filter((f) => !text.includes(stem(f.name)) && !titles.includes(stem(f.name)));
      if (!missing.length) return { ok: true, files: out };
      await sleep(300);
    }
    return { ok: false, error: "file_not_shown", files: out };
  };

  // What the chat produced in its last answer: files made in the page (blob:/data:) come back whole;
  // other file links stay links (webllm does not fetch them with your session).
  const downloads = async (site) => {
    const el = lastAnswerEl(site);
    const scope = el ? (el.closest("[class*='message' i],[class*='answer' i],[class*='assistant' i]") || el) : null;
    const anchors = scope ? [...scope.querySelectorAll("a[href]")].filter((a) => a.hasAttribute("download") || /^(blob|data):/.test(a.getAttribute("href"))) : [];
    const out = [];
    for (const a of anchors.slice(0, 10)) {
      const href = a.getAttribute("href");
      const name = (a.getAttribute("download") || (a.innerText || "").trim() || "archivo").slice(0, 120);
      if (/^(blob|data):/.test(href)) {
        try {
          const blob = await (await fetch(href)).blob();
          if (blob.size > 25 * 1024 * 1024) { out.push({ name, url: null, too_big: blob.size }); continue; }
          const b64 = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1] || ""); r.onerror = rej; r.readAsDataURL(blob); });
          out.push({ name, type: blob.type || "application/octet-stream", b64 });
        } catch (e) { out.push({ name, url: null, error: String(e && e.message || e).slice(0, 120) }); }
      } else {
        out.push({ name, url: a.href });
      }
    }
    return { ok: true, files: out };
  };

  // "Enséñame dónde está": Iván clicks the thing webllm could not find. That click does nothing on the page;
  // webllm keeps a way to find the element again.
  const selectorFor = (el) => {
    const unique = (sel) => { try { return document.querySelectorAll(sel).length === 1; } catch (e) { return false; } };
    const q = (v) => v.replace(/"/g, '\\"');
    if (el.id && unique("#" + CSS.escape(el.id))) return "#" + CSS.escape(el.id);
    for (const attr of ["data-testid", "aria-label", "title", "name"]) {
      const v = el.getAttribute(attr);
      if (v && unique(`${el.tagName.toLowerCase()}[${attr}="${q(v)}"]`)) return `${el.tagName.toLowerCase()}[${attr}="${q(v)}"]`;
    }
    const path = [];
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const same = n.parentElement ? [...n.parentElement.children].filter((c) => c.tagName === n.tagName) : [n];
      path.unshift(n.tagName.toLowerCase() + (same.length > 1 ? `:nth-of-type(${same.indexOf(n) + 1})` : ""));
    }
    return "body > " + path.join(" > ");
  };
  // ------------------------------------------------ self-repair (PLAN-v5 F6)
  const SKIP_AREA = "nav,aside,[role='navigation'],[role='complementary'],[data-webllm-teach],[data-webllm-observe]";
  const short = (v, n) => (v ? String(v).trim().replace(/\s+/g, " ").slice(0, n) || undefined : undefined);
  const classesOf = (el) => (typeof el.className === "string" ? el.className : "").trim().split(/\s+/).filter(Boolean);
  const matches = (sel, el) => { try { return [...document.querySelectorAll(sel)].includes(el); } catch (e) { return false; } };
  // A selector that finds this element and the ones like it (the next answers), not just this one.
  const general = (el) => {
    const tag = el.tagName.toLowerCase();
    for (const attr of ["data-testid", "data-role", "data-message-author-role"]) {
      const v = el.getAttribute(attr);
      const sel = v && `${tag}[${attr}="${v.replace(/"/g, '\\"')}"]`;
      if (sel && matches(sel, el)) return sel;
    }
    const cls = classesOf(el).filter((c) => /^[A-Za-z_][\w-]*$/.test(c)).slice(0, 4);
    const sel = cls.length ? tag + cls.map((c) => "." + CSS.escape(c)).join("") : "";
    return sel && matches(sel, el) ? sel : selectorFor(el);
  };
  // The message an element belongs to: going up until the next level is the list of messages.
  const messageOf = (el) => {
    let m = el.nodeType === 1 ? el : el.parentElement;
    while (m && m.parentElement && m.parentElement !== document.body) {
      const withText = [...m.parentElement.children].filter((c) => (c.innerText || "").trim());
      if (withText.length >= 2) break;
      m = m.parentElement;
    }
    return m;
  };
  // What webllm typed, found on the page: the innermost element holding it (Iván's message). Its text never
  // leaves the page; only "this block is / is after your message" does.
  const yourMessage = (sent) => {
    const probe = String(sent || "").trim().slice(0, 40);
    if (!probe) return null;
    const holders = [...document.querySelectorAll("body *")].filter((el) => !editable(el) && !el.closest(SKIP_AREA) &&
      (el.innerText || "").includes(probe) && ![...el.children].some((c) => (c.innerText || "").includes(probe)));
    return holders.length ? holders[holders.length - 1] : null;
  };

  // The page's x-ray, for an AI to point at the text box, the send button or the answer: numbered candidates
  // with what the site wrote on them (tags, classes, short labels of controls, sizes, positions). Never the text
  // of the conversation (answers are only their length), never a password field, never what was typed.
  const xray = (site, sent) => {
    const probe = String(sent || "").trim();
    const mine = yourMessage(sent);
    const out = { url: location.origin + location.pathname, candidates: [] };
    const seen = new Set();
    const leaks = (v) => !!probe && !!v && ((v.length >= 8 && probe.includes(v)) || v.includes(probe.slice(0, 12)));
    const add = (el, kind) => {
      if (seen.has(el) || out.candidates.length >= 90) return;
      seen.add(el);
      const r = el.getBoundingClientRect();
      const text = el.innerText || "";
      const c = { n: out.candidates.length, kind, tag: el.tagName.toLowerCase(), role: short(el.getAttribute("role"), 30),
        testid: short(el.getAttribute("data-testid"), 60), id: short(el.id, 60), classes: short(classesOf(el).join(" "), 100),
        x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
      if (kind === "box") {
        Object.assign(c, { type: short(el.getAttribute("type"), 20), contenteditable: short(el.getAttribute("contenteditable"), 20),
          placeholder: short(el.getAttribute("placeholder") || el.getAttribute("aria-placeholder") || el.getAttribute("data-placeholder"), 60),
          label: short(el.getAttribute("aria-label"), 60) });
      } else if (kind === "button") {
        Object.assign(c, { label: short(el.getAttribute("aria-label"), 60), title: short(el.getAttribute("title"), 60),
          text: text.trim().length <= 24 ? short(text, 24) : undefined, disabled: !isEnabled(el) || undefined,
          icon_only: !text.trim() || undefined });
      } else {
        Object.assign(c, { text_len: text.trim().length, children: el.childElementCount,
          is_your_message: !!(mine && (el === mine || el.contains(mine))) || undefined,
          after_your_message: !!(mine && !el.contains(mine) && (mine.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) || undefined });
      }
      for (const k of ["label", "title", "text", "placeholder", "testid", "id", "classes"]) if (leaks(c[k])) delete c[k];
      for (const k of Object.keys(c)) if (c[k] === undefined) delete c[k];
      // where to find it again: kept by webllm, never shown to the AI (which answers with numbers only)
      c.sel = selectorFor(el);
      c.general = kind === "block" ? general(el) : c.sel;
      out.candidates.push(c);
    };
    const inArea = (el) => !el.closest(SKIP_AREA);
    [...document.querySelectorAll(BOX_SEL + "," + LINE_SEL)].filter((el) => visible(el) && inArea(el) && editable(el)).slice(-8)
      .forEach((el) => add(el, "box"));
    clickables().filter(inArea).slice(-45).forEach((el) => add(el, "button"));
    [...document.querySelectorAll("div,article,section")].filter((el) => {
      if (!visible(el) || !inArea(el) || el.querySelector(BOX_SEL + "," + LINE_SEL) || el.closest("button,[role='button']")) return false;
      const t = (el.innerText || "").trim();
      if (!t) return false;
      // the same text one block down (a div inside a div): keep only the inner one; <strong>, <p>… are not blocks
      const only = el.children.length === 1 && el.children[0].matches("div,article,section") ? el.children[0] : null;
      return !(only && ((only.innerText || "").trim().length === t.length));
    }).slice(-30).forEach((el) => add(el, "block"));
    return out;
  };

  // A repair (layer 3) or a lesson (layer 4), tried on the page as it is, sending nothing: is the text box a
  // text box, the send button a button (and not a forbidden one), the answer a message that is not Iván's?
  const tryPatch = (patch, sent) => {
    const mine = yourMessage(sent);
    const probe = String(sent || "").trim().slice(0, 40);
    const checks = {};
    for (const [key, sels] of Object.entries(patch || {})) {
      let found = [];
      let bad = false;
      for (const sel of Array.isArray(sels) ? sels : []) {
        try { found = [...document.querySelectorAll(sel)].filter((el) => visible(el)); } catch (e) { bad = true; break; }
        if (found.length) break;
      }
      const el = found[found.length - 1];
      if (bad) checks[key] = { ok: false, why: "not_a_selector" };
      else if (!el) checks[key] = { ok: false, why: "not_found" };
      else if (key === "input") checks[key] = editable(el) ? { ok: true } : { ok: false, why: "not_a_text_box" };
      else if (["send", "copy", "stop"].includes(key)) {
        const b = el.closest("button,[role='button']");
        checks[key] = !b ? { ok: false, why: "not_a_button" } : forbidden(b) ? { ok: false, why: "forbidden" } : { ok: true };
      } else if (key === "answer") {
        const t = (el.innerText || "").trim();
        checks[key] = !t ? { ok: false, why: "empty" }
          : el.querySelector(BOX_SEL + "," + LINE_SEL) ? { ok: false, why: "holds_the_box" }
          : (probe && t.includes(probe)) || (mine && (el === mine || el.contains(mine))) ? { ok: false, why: "is_your_message" }
          : mine && !(mine.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) ? { ok: false, why: "before_your_message" }
          : { ok: true, length: t.length };
      } else checks[key] = { ok: false, why: "unknown" };
    }
    return { ok: Object.keys(checks).length > 0 && Object.values(checks).every((c) => c.ok), checks };
  };

  // "Parar": the site's own stop button, if an answer is being written (never a forbidden one).
  const pressStop = (site) => {
    const b = stopButton(site);
    if (!b) return { ok: false, error: "no_stop_button" };
    return safeClick(b) ? { ok: true, name: nameOf(b).slice(0, 60) } : { ok: false, error: "forbidden" };
  };

  // Observer mode (PLAN-v5 F6): Iván writes in his own tab; webllm only looks (no clicks, no typing).
  const observe = (site) => {
    const input = findInput(site);
    const typed = !input ? "" : ("value" in input && input.tagName !== "DIV" ? input.value : input.innerText) || "";
    const last = lastAnswerEl(site);
    return { url: location.href, typed: String(typed).slice(0, 20000), generating: isGenerating(site), hidden: document.hidden,
             copyCount: copyButtons(site).length, answerCount: answers(site).length, lastAnswerLen: last ? (last.innerText || "").length : 0,
             bodyLen: ((document.body && document.body.innerText) || "").length, challenge: detectChallenge(),
             stop: !!window.__webllmStopObserving };
  };
  // A visible mark while webllm records this tab, with a way to stop it (it also stops from the extension icon).
  const observeBadge = (on) => {
    document.querySelectorAll("[data-webllm-observe]").forEach((n) => n.remove());
    window.__webllmStopObserving = false;
    if (!on) return { ok: true };
    const bar = document.createElement("div");
    bar.setAttribute("data-webllm-observe", "1");
    bar.style.cssText = "position:fixed;z-index:2147483647;right:12px;bottom:12px;background:#1f2937;color:#fff;font:600 14px system-ui;" +
      "padding:8px 10px 8px 14px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);display:flex;gap:10px;align-items:center";
    const label = document.createElement("span");
    label.textContent = "● webllm está registrando esta conversación";
    const stopBtn = document.createElement("button");
    stopBtn.textContent = "Dejar de registrar";
    stopBtn.style.cssText = "font:600 14px system-ui;border:0;border-radius:8px;padding:6px 10px;cursor:pointer";
    stopBtn.onclick = (e) => { e.stopPropagation(); window.__webllmStopObserving = true; label.textContent = "webllm ya no registra"; stopBtn.remove(); };
    bar.append(label, stopBtn);
    document.body.appendChild(bar);
    return { ok: true };
  };

  const teach = (what, text, waitMs = 180000) => new Promise((resolve) => {
    const bar = document.createElement("div");
    bar.setAttribute("data-webllm-teach", "1");
    bar.style.cssText = "position:fixed;z-index:2147483647;left:50%;top:12px;transform:translateX(-50%);background:#3a55d6;color:#fff;" +
      "font:600 17px system-ui;padding:12px 18px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);pointer-events:none";
    bar.textContent = "webllm: " + text;
    document.body.appendChild(bar);
    const done = (out) => { document.removeEventListener("click", onClick, true); bar.remove(); clearTimeout(timer); resolve(out); };
    const onClick = (e) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      // The answer: the whole message Iván clicked in, and a selector that finds the next ones too.
      if (what === "answer") {
        const msg = messageOf(e.target);
        return done({ ok: true, what, selector: general(msg), name: "" });
      }
      const el = (what === "input" ? e.target.closest(BOX_SEL + "," + LINE_SEL) : null) ||
        e.target.closest("button,[role='button'],a,input,textarea,[contenteditable]:not([contenteditable='false']),[role='textbox'],[role='menuitem'],[role='option']") || e.target;
      done({ ok: true, what, selector: selectorFor(el), name: optionName(el) });
    };
    document.addEventListener("click", onClick, true);
    const timer = setTimeout(() => done({ ok: false, what, error: "timeout" }), waitMs);
  });

  // The modes that are on right now (a toggle next to the box, or a chip a menu left), whoever put them.
  const activeModes = () => modeToggles().filter(isChecked).map((el) => nameOf(el).slice(0, 60) || (el.innerText || "").trim().slice(0, 60));

  window.__webllmDriver = { state, insert, send, capture, fallback, diagnose, discover, chooseModel, setMode, fileChunk, attach, downloads, teach,
    activeModes, xray, tryPatch, pressStop, observe, observeBadge };
})();
