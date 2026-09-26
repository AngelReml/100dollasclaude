"""What Iván reads when an AI fails outside the app (in Open WebUI, through the gateway).

The same "qué pasó + qué hacer" as the app (app/src/fix.ts: problemFor), in plain Spanish.
tests/test_gateway.py checks that every code the app knows has a text here too.
"""

from __future__ import annotations

# code -> (title, what to do). "{ai}" is the AI's name.
PROBLEMS: dict[str, tuple[str, str]] = {
    "login_required": ("{ai} no tiene la sesión abierta",
                       "Abre el panel de webllm, pulsa Conectar y entra con tu cuenta en la ventana que se abre. "
                       "Luego vuelve a preguntar."),
    "paused": ("{ai} está en pausa para proteger tu cuenta",
               "Cuando hayas entrado con otra cuenta o resuelto la verificación, reanúdala en el panel de webllm."),
    "cooldown": ("{ai} está en pausa para proteger tu cuenta",
                 "Cuando hayas entrado con otra cuenta o resuelto la verificación, reanúdala en el panel de webllm."),
    "challenge": ("{ai} pidió una verificación y nadie la resolvió",
                  "Resuélvela en la ventanita de webllm y reanúdala en el panel de webllm."),
    "banned": ("{ai} está en pausa para proteger tu cuenta",
               "La cuenta parece bloqueada. Entra con otra y reanúdala en el panel de webllm."),
    "daily_cap": ("{ai} ya ha gastado los mensajes de hoy",
                  "Es el tope que pusimos para cuidar tu cuenta. Mañana vuelve sola, o pregúntaselo a otra IA."),
    "busy": ("Ya había otro envío a {ai}",
             "Solo se manda un mensaje a la vez a cada IA. Vuelve a intentarlo en un momento."),
    "site_busy": ("{ai} está saturada ahora mismo",
                  "No es cosa de tu cuenta: tiene demasiada gente. Prueba en un rato o pregúntaselo a otra IA."),
    "overloaded": ("{ai} está saturada ahora mismo",
                   "No es cosa de tu cuenta: tiene demasiada gente. Prueba en un rato o pregúntaselo a otra IA."),
    "rate_limited": ("{ai} ha llegado a su límite por ahora",
                     "Espera un rato antes de volver a preguntarle, o pregúntaselo a otra IA."),
    "no_credit": ("{ai} se ha quedado sin crédito gratis",
                  "Su servicio pide saldo para seguir. Pregúntaselo a otra IA; si es un cupo diario, "
                  "vuelve solo cuando se renueve."),
    "bridge_unavailable": ("Chrome no está conectado",
                           "Abre Chrome y comprueba que la extensión webllm está instalada y encendida."),
    "extension_disconnected": ("Chrome no está conectado",
                               "Abre Chrome y comprueba que la extensión webllm está instalada y encendida."),
    "not_sent": ("El mensaje no llegó a enviarse",
                 "Una ventana emergente tapó la caja de {ai}. Ciérrala en la ventanita de webllm y vuelve a preguntar."),
    "timeout": ("{ai} tardó demasiado en contestar",
                "Puede que la web vaya lenta. Vuelve a intentarlo o pregúntaselo a otra IA."),
    "unreachable": ("Las IAs por API están apagadas",
                    "El programa que las conecta (OmniRoute) no está encendido. Enciéndelo desde el panel de webllm."),
    "unauthorized": ("{ai} no acepta la clave",
                     "La clave guardada en OmniRoute no vale o ha caducado. Revísala en el panel de OmniRoute."),
    "offline": ("webllm no responde", "Cierra esta ventana y vuelve a abrir webllm con su icono."),
    # PLAN-v5 F4 (D21): what Iván chose could not be put or confirmed on the chat's page, so nothing was sent
    "not_confirmed": ("No se envió: {ai} no confirmó lo que pediste",
                      "webllm puso el modelo o el modo en su web, pero la página no lo confirmó, así que no mandó "
                      "nada. Vuelve a intentarlo o elige otro modelo. Si pasa siempre con el modelo, en su Ficha "
                      "(webllm) pulsa «Usar siempre el que tenga puesto su web»."),
    "model_not_in_page": ("No se envió: ese modelo ya no está en {ai}",
                          "Su selector no lo tiene. En webllm → Conectores, pulsa Descubrir para ver sus modelos de hoy."),
    "mode_not_in_page": ("No se envió: {ai} no tiene ese modo",
                         "Quita ese interruptor del «+» o pregúntaselo a otro chat."),
    "file_not_attached": ("No se envió: el archivo no quedó adjunto en {ai}",
                          "Su web no lo aceptó así. Pregúntaselo a otro chat o arrástralo tú en su ventana."),
    "forbidden": ("No se envió: iba a pulsar un botón prohibido en {ai}",
                  "webllm nunca pulsa publicar, compartir, borrar ni nada parecido. Dímelo para revisar esa web."),
    "expensive_cap": ("{ai} ya ha usado hoy sus modos caros",
                      "La investigación profunda y el modo constructor se cuentan aparte (5 al día). Mañana vuelven."),
    # PLAN-v5 F6: the page changed and neither the repair nor a lesson could fix it (yet)
    "no_input": ("No encontré la caja de texto de {ai}",
                 "Su web ha cambiado. En la app de webllm, en su Ficha, pulsa «Enséñame esta web» (3 clics); o enciende "
                 "«Reparar solas con IA». No se envió nada."),
    "empty_answer": ("{ai} contestó, pero no pude leer su respuesta",
                     "Su web ha cambiado. La respuesta sigue en su ventanita: en la app de webllm, en su Ficha, pulsa "
                     "«Enséñame esta web» (3 clics); o enciende «Reparar solas con IA»."),
    "cancelled": ("Lo has parado tú", "Si ya se había enviado, la web puede haber contestado igualmente; "
                                      "pregunta otra vez cuando quieras."),
    "task_for_web_chat": ("Petición interna rechazada",
                          "Open WebUI quería usar {ai} para una tarea interna (un título, unas etiquetas). "
                          "webllm no gasta mensajes de tus cuentas en eso."),
}
DEFAULT = ("{ai} no pudo responder", "Vuelve a intentarlo o pregúntaselo a otra IA.")


# Codes whose text already says everything: the service's own words would only repeat webllm's.
OWN_TEXT = frozenset({"login_required", "paused", "cooldown", "bridge_unavailable", "extension_disconnected",
                      "not_confirmed", "model_not_in_page", "mode_not_in_page", "file_not_attached", "forbidden",
                      "expensive_cap", "no_input", "empty_answer"})


def problem_text(code: str, ai: str, said: str = "") -> str:
    """One paragraph: what happened, what to do, and (when it helps) what the service answered."""
    title, todo = PROBLEMS.get(code, DEFAULT)
    out = f"{title.format(ai=ai)}. {todo.format(ai=ai)}"
    said = " ".join((said or "").split())
    if said and code not in OWN_TEXT:
        out += f" Lo que respondió: «{said[:200]}{'…' if len(said) > 200 else ''}»"
    return out


# While a chat waits for Iván (the extension reports it every 10 s). In Open WebUI it shows on the
# one-line status above the answer, so it must fit in one line (about 90 characters).
WAITING_SHORT: dict[str, str] = {
    "challenge": "{ai} te espera: resuelve la verificación en la ventanita de webllm. Después sigue sola.",
    "popup": "{ai} ha sacado una ventana: respóndela en la ventanita de webllm y sigo solo.",
    "hidden": "La ventanita de webllm está tapada: déjala a la vista para que {ai} pueda escribir.",
    # PLAN-v5 F6: not waiting for Iván; webllm itself is fixing its way around a changed page
    "repair": "La web de {ai} ha cambiado: la estoy arreglando, sin enviar nada. Después sigo.",
}
# The app's longer words for the same moments (app/src/screens/Preguntar.tsx: waitingText).
WAITING: dict[str, str] = {
    "challenge": "{ai} pide una verificación. Resuélvela en la ventanita de webllm (ya la he puesto delante). "
                 "Te espero hasta 5 minutos; después la respuesta llega sola, no hace falta volver a preguntar.",
    "popup": "{ai} ha sacado una ventana. Respóndela en la ventanita de webllm y sigo yo solo.",
    "hidden": "La ventanita de webllm está tapada o minimizada, y {ai} no escribe la respuesta mientras no se vea. "
              "Déjala a la vista (pequeña en una esquina vale): la respuesta sigue sola.",
    "repair": "La web de {ai} ha cambiado y no encontraba lo que necesita. La estoy arreglando sin enviar nada; "
              "no tienes que hacer nada.",
}
