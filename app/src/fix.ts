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
    case "no_input":
      return {
        title: `No encontré la caja de texto de ${label}`,
        text: "Su web ha cambiado. En su Ficha, pulsa «Enséñame esta web» (3 clics); o enciende «Reparar solas con IA». No se envió nada.",
        actions: ["otra"],
      };
    case "empty_answer":
      return {
        title: `${label} contestó, pero no pude leer su respuesta`,
        text: "Su web ha cambiado. La respuesta sigue en su ventanita: en su Ficha, pulsa «Enséñame esta web» (3 clics); o enciende «Reparar solas con IA».",
        actions: ["otra"],
      };
    case "conversation_lost":
      return {
        title: `${label} ya no tenía la conversación de antes`,
        text: "Su web abrió un chat nuevo, así que no se escribió nada. Vuelve a empezar la pregunta.",
        actions: ["reintentar", "otra"],
      };
    case "bad_continue_url":
      return {
        title: `No se abrió esa conversación de ${label}`,
        text: "La dirección no era de su web, así que ni se abrió ni se escribió nada.",
        actions: ["otra"],
      };
    case "no_new_answer":
      return {
        title: `${label} no dio una respuesta nueva`,
        text: "En su web seguía la respuesta de antes. Mira su ventanita; si se quedó a medias, pregunta otra vez.",
        actions: ["reintentar", "otra"],
      };
    case "not_confirmed":
      return {
        title: `No se envió: ${label} no confirmó lo que pediste`,
        text: "webllm puso el modelo o el modo en su web, pero la página no lo confirmó, así que no mandó nada. Vuelve a intentarlo o elige otro modelo. Si pasa siempre con el modelo, en su Ficha pulsa «Usar siempre el que tenga puesto su web».",
        actions: ["reintentar", "otra"],
      };
    case "model_not_in_page":
      return {
        title: `No se envió: ese modelo ya no está en ${label}`,
        text: "Su selector no lo tiene. En Conectores, pulsa Descubrir para ver sus modelos de hoy.",
        actions: ["otra"],
      };
    case "mode_not_in_page":
      return {
        title: `No se envió: ${label} no tiene ese modo`,
        text: "Quita ese interruptor o pregúntaselo a otro chat.",
        actions: ["otra"],
      };
    case "file_not_attached":
      return {
        title: `No se envió: el archivo no quedó adjunto en ${label}`,
        text: "Su web no lo aceptó así. Pregúntaselo a otro chat o arrástralo tú en su ventana.",
        actions: ["otra"],
      };
    case "forbidden":
      return {
        title: `No se envió: iba a pulsar un botón prohibido en ${label}`,
        text: "webllm nunca pulsa publicar, compartir, borrar ni nada parecido. Dímelo para revisar esa web.",
        actions: [],
      };
    case "expensive_cap":
      return {
        title: `${label} ya ha usado hoy sus modos caros`,
        text: "La investigación profunda y el modo constructor se cuentan aparte (5 al día). Mañana vuelven.",
        actions: ["otra"],
      };
    case "cancelled":
      return {
        title: "Lo has parado tú",
        text: "Si ya se había enviado, la web puede haber contestado igualmente; pregunta otra vez cuando quieras.",
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
