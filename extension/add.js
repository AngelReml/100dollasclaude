// "Add a site" page: asks Chrome for permission on that one site (it needs a
// click here, Chrome requires it), then lets the service worker test the site.
const q = new URLSearchParams(location.search);
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
