// Turns a failure code (src/webllm_agent/flows.py: error_code) into what Iván reads:
// what happened + what to do + the button that fixes it.

export type FixAction = "reanudar" | "abrir" | "guia" | "encender" | "reintentar" | "comprobar";

export interface Problem {
  title: string;
  text: string;
  actions: FixAction[];
}

export function problemFor(code: string, label: string, kind: "chat" | "api" = "chat"): Problem {
  // A chat that hits its message limit is paused by the bridge; an API limit is only temporary.
  if (code === "rate_limited" && kind === "chat") code = "paused";
  switch (code) {
    case "login_required":
      return {
        title: `${label} no tiene la sesión abierta`,
        text: `Entra en ${label} con tu cuenta (o con una nueva) y vuelve a pedírselo.`,
        actions: ["abrir", "reintentar"],
      };
    case "paused":
    case "cooldown":
    case "challenge":
    case "banned":
      return {
        title: `${label} está en pausa para proteger tu cuenta`,
        text: "Cuando hayas entrado con otra cuenta o resuelto la verificación, reanúdala.",
        actions: ["reanudar"],
      };
    case "daily_cap":
      return {
        title: `${label} ya ha gastado los mensajes de hoy`,
        text: "Es el tope que pusimos para cuidar tu cuenta. Mañana vuelve sola, o pregunta a otra IA.",
        actions: [],
      };
    case "busy":
      return {
        title: `Ya había otro envío a ${label}`,
        text: "Solo se manda un mensaje a la vez a cada IA. Vuelve a intentarlo en un momento.",
        actions: ["reintentar"],
      };
    case "site_busy":
    case "overloaded":
      return {
        title: `${label} está saturada ahora mismo`,
        text: "No es cosa de tu cuenta: tiene demasiada gente. Prueba en un rato o pregunta a otra IA.",
        actions: ["reintentar"],
      };
    case "rate_limited":
      return {
        title: `${label} ha llegado a su límite por ahora`,
        text: "Espera un rato antes de volver a preguntarle, o pregunta a otra IA.",
        actions: ["reintentar"],
      };
    case "bridge_unavailable":
    case "extension_disconnected":
      return {
        title: "Chrome no está conectado",
        text: "Abre Chrome y comprueba que la extensión webllm está instalada y encendida.",
        actions: ["guia", "reintentar"],
      };
    case "not_sent":
      return {
        title: "El mensaje no llegó a enviarse",
        text: `Una ventana emergente tapó la caja de ${label}. Ciérrala en la ventanita de webllm y vuelve a pedirlo.`,
        actions: ["reintentar"],
      };
    case "timeout":
      return {
        title: `${label} tardó demasiado en contestar`,
        text: "Puede que la web vaya lenta. Vuelve a intentarlo.",
        actions: ["reintentar"],
      };
    case "unreachable":
      return {
        title: "Las IAs por API están apagadas",
        text: "El programa que las conecta (OmniRoute) no está encendido.",
        actions: ["encender"],
      };
    case "unauthorized":
      return {
        title: `${label} no acepta la clave`,
        text: "La clave guardada en OmniRoute no vale o ha caducado. Revísala en el panel de OmniRoute.",
        actions: [],
      };
    case "offline":
      return {
        title: "webllm no responde",
        text: "Cierra esta ventana y vuelve a abrir webllm con su icono.",
        actions: [],
      };
    default:
      return {
        title: `${label} no pudo responder`,
        text: "Vuelve a intentarlo. Si se repite, abre «Pruebas a fondo» desde Inicio.",
        actions: ["reintentar"],
      };
  }
}
