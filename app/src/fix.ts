// Turns a failure code (src/webllm_agent/flows.py: error_code) into what Iván reads:
// what happened + what to do + the button that fixes it.

export type FixAction = "reanudar" | "conectar" | "guia" | "encender" | "encender_local" | "reintentar" | "otra";

export interface Problem {
  title: string;
  text: string;
  actions: FixAction[];
  /** Show what the AI's service said: its own words help when webllm has no better explanation. */
  said?: boolean;
}

export function problemFor(code: string, label: string, kind: "chat" | "api" | "local" = "chat", server = ""): Problem {
  // A chat that hits its message limit is paused by the bridge; an API limit is only temporary.
  if (code === "rate_limited" && kind === "chat") code = "paused";
  if (kind === "local" && (code === "unreachable" || code === "timeout")) {
    return code === "unreachable"
      ? {
          title: `${server || "El programa de IA de tu PC"} está apagado`,
          text: "Enciéndelo y vuelve a pedírselo. No gasta ninguna cuenta: funciona en tu PC.",
          actions: ["encender_local", "reintentar"],
        }
      : {
          title: `${label} tardó demasiado`,
          text: "Los modelos de tu PC pueden ir lentos la primera vez (se están cargando). Vuelve a intentarlo.",
          actions: ["reintentar"],
        };
  }
  switch (code) {
    case "login_required":
      return {
        title: `${label} no tiene la sesión abierta`,
        text: `Pulsa Conectar y entra con tu cuenta (o con una nueva) en la ventana que se abre. Luego vuelve a pedírselo.`,
        actions: ["conectar", "reintentar"],
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
        text: "Es el tope que pusimos para cuidar tu cuenta. Mañana vuelve sola, o pregúntaselo a otra IA.",
        actions: ["otra"],
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
        text: "No es cosa de tu cuenta: tiene demasiada gente. Prueba en un rato o pregúntaselo a otra IA.",
        actions: ["otra", "reintentar"],
        said: kind === "api",
      };
    case "rate_limited":
      return {
        title: `${label} ha llegado a su límite por ahora`,
        text: "Su servicio gratis limita cuántas preguntas acepta seguidas. Espera un rato antes de volver a preguntarle, o pregúntaselo a otra IA.",
        actions: ["otra", "reintentar"],
        said: true,
      };
    case "no_credit":
      return {
        title: `${label} se ha quedado sin crédito gratis`,
        text: "Su servicio pide saldo para seguir. Pregúntaselo a otra IA; si es un cupo diario, vuelve solo cuando se renueve.",
        actions: ["otra"],
        said: true,
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
        text: "Puede que la web vaya lenta. Vuelve a intentarlo o pregúntaselo a otra IA.",
        actions: ["reintentar", "otra"],
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
        actions: ["otra"],
        said: true,
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
        text: "Vuelve a intentarlo o pregúntaselo a otra IA. Si se repite, abre «Pruebas a fondo» desde Inicio.",
        actions: ["reintentar", "otra"],
        said: true,
      };
  }
}
