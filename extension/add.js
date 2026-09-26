// "Add a site" page: asks Chrome for permission on that one site (it needs a
// click here, Chrome requires it), then lets the service worker test the site.
// With ?batch= ("Conectar varias", PLAN-v5 F3): the list of sites and ONE permission request for all.
const q = new URLSearchParams(location.search);
if (q.get("batch")) {
  manySites(q.get("batch"));
} else {
  oneSite();
}

function manySites(batchId) {
  const $ = (id) => document.getElementById(id);
  const say = (text, cls) => { $("msg").textContent = text; $("msg").className = cls || ""; };
  let sites = [];
  try { sites = JSON.parse(q.get("sites") || "[]"); } catch (e) { sites = []; }
  sites = sites.filter((s) => s && WEBLLM_COMMON.parseChatUrl(s.url).ok);
  $("one").hidden = true;
  $("many").hidden = false;
  $("go").textContent = "Permitir y conectar";
  $("count").textContent = sites.length === 1 ? sites[0].name : `${sites.length} IAs`;
  for (const s of sites) {
    const li = document.createElement("li");
    li.textContent = s.name;
    const u = document.createElement("span");
    u.className = "u";
    u.textContent = WEBLLM_COMMON.parseChatUrl(s.url).url;
    li.appendChild(u);
    $("list").appendChild(li);
  }
  const origins = [...new Set(sites.map((s) => WEBLLM_COMMON.parseChatUrl(s.url).origin + "/*"))];
  if (!origins.length) {
    $("go").disabled = true;
    say("No hay ninguna dirección válida.", "bad");
  }
  $("go").addEventListener("click", async () => {
    $("go").disabled = true;
    let granted = false;
    try {
      granted = await chrome.permissions.request({ origins }); // ONE prompt for all of them
    } catch (e) {
      granted = false;
    }
    chrome.runtime.sendMessage({ type: "add_many_permission", batch_id: batchId, ok: granted });
    if (!granted) {
      say("No diste permiso, así que webllm no las conecta. Puedes cerrar esta pestaña y volver a intentarlo desde la app.", "bad");
      return;
    }
    say("Permiso concedido. Sigue en la app de webllm; esta pestaña se cierra sola.", "ok");
    setTimeout(() => window.close(), 2500);
  });
  $("cancel").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "add_many_permission", batch_id: batchId, ok: false });
    window.close();
  });
}

function oneSite() {
  const addId = q.get("add_id");
  const key = q.get("key");
  const name = q.get("name") || "esta IA";
  const parsed = WEBLLM_COMMON.parseChatUrl(q.get("url"));
  const $ = (id) => document.getElementById(id);
  const say = (text, cls) => { $("msg").textContent = text; $("msg").className = cls || ""; };

  $("name").textContent = name;
  $("url").textContent = parsed.ok ? parsed.url : q.get("url") || "";
  if (!parsed.ok) {
    $("go").disabled = true;
    say("Esta dirección no se puede añadir.", "bad");
  }

  $("go").addEventListener("click", async () => {
    $("go").disabled = true;
    let granted = false;
    try {
      granted = await chrome.permissions.request({ origins: [parsed.origin + "/*"] });
    } catch (e) {
      granted = false;
    }
    if (!granted) {
      say("No diste permiso, así que webllm no puede usar esta web. Puedes volver a pulsar el botón.", "bad");
      $("go").disabled = false;
      chrome.runtime.sendMessage({ type: "add_denied", add_id: addId });
      return;
    }
    say("Permiso concedido. La prueba sigue en la app de webllm; esta pestaña se cierra sola.", "ok");
    chrome.runtime.sendMessage({ type: "add_test", add_id: addId, key, name, url: parsed.url });
    setTimeout(() => window.close(), 2500);
  });

  $("cancel").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "add_cancel", add_id: addId });
    window.close();
  });
}
