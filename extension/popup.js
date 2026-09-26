// The extension's icon (PLAN-v5 F6, observer mode): "Registrar esta conversación" in a chat Iván opened
// himself, and "Dejar de registrar". Only on chats webllm has permission for; never without his click.
const msg = document.getElementById("msg");
const btn = document.getElementById("toggle");

function show(r) {
  if (!r || !r.ok) { msg.textContent = "No pude mirar esta pestaña."; btn.hidden = true; return; }
  if (!r.site) { msg.textContent = "Esta web no es un chat conectado a webllm. Conéctala antes desde la app de webllm."; btn.hidden = true; return; }
  if (!r.allowed) { msg.textContent = `webllm no tiene permiso en ${r.site}. Conéctala desde la app de webllm.`; btn.hidden = true; return; }
  btn.hidden = false;
  if (r.on) {
    msg.textContent = `webllm está registrando esta conversación de ${r.site}: cada mensaje tuyo y cada respuesta van a tu historial` +
      (r.connected ? "." : " (webllm está apagado: se guardará cuando lo abras).");
    btn.textContent = "Dejar de registrar";
    btn.className = "stop";
  } else {
    msg.textContent = `Si registras esta conversación de ${r.site}, cada mensaje que escribas y cada respuesta irán a tu historial de webllm (y a tu memoria en Obsidian). webllm no pulsa ni escribe nada aquí.`;
    btn.textContent = "Registrar esta conversación";
    btn.className = "";
  }
}

// Opened as the icon's popup it looks at the tab in front; opened as popup.html?tab=N (tests), at that tab.
const tab = Number(new URLSearchParams(location.search).get("tab")) || null;
chrome.runtime.sendMessage({ type: "popup", action: "look", tab }, show);
btn.onclick = () => chrome.runtime.sendMessage({ type: "popup", action: "toggle", tab }, show);
