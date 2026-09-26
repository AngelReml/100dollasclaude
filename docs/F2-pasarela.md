# F2 — webllm, la única conexión de Open WebUI (26-sep-2026)

**Resultado en la nube: la salida de F2 se cumple aquí.** Desde Open WebUI responden una IA web (Qwen), una por API (z.ai) y una de tu PC (LM Studio), y el registro de webllm tiene las tres. Falta tu prueba en el PC (abajo): aquí el Chrome, OmniRoute y LM Studio son de mentira. El puente, la pasarela, el guardián y el registro sí son los de verdad.

Probado con Open WebUI **0.11.4** instalado desde cero en la nube (`tests/test_openwebui_face.py`: las 10 comprobaciones de F1 y las 8 de F2, todas **BIEN**).

## Lo que pedía el plan y cómo quedó

| Qué | Resultado | Dónde |
|---|---|---|
| Lista de modelos con su ficha, en español y agrupados | **Bien, con un límite.** Primero los chats web, luego las APIs y luego tu PC: «Qwen (web)», «z.ai (API)», «LM Studio · … (tu PC)». Cada una lleva una ficha con lo que gasta, cómo va y su tope diario. Es la misma cifra que enseña la app: chats 150 al día, APIs 300. **El límite:** la ficha es igual para todas las del mismo tipo. La de cada IA (para qué sirve, contexto, modelos) llega con el catálogo (F3) y sus capacidades (F4). «webllm · Comité» y «webllm · Automático» **no salen todavía**: saldrán cuando funcionen (F7 y F8), nada a la vista que no funcione | aquí |
| Los avisos de webllm, en el bloque de razonamiento | **Bien**: «Preguntando a Qwen…», «te espera: resuelve la verificación…». Lo que tienes que ver sí o sí (qué respondió, archivos no usados) queda en la línea de estado, sin abrir nada | aquí, en pantalla (F1) |
| Las APIs pasan sus herramientas tal cual | **Bien**: un servidor MCP de prueba (la hora) sale en el «+». La IA por API pide usarlo, **Open WebUI te pide permiso** (Permitir / Denegar) y solo después se usa. La respuesta dice lo que dijo («Son las 10:30») y el registro guarda la petición y el resultado | aquí, en pantalla |
| Cada respuesta dice qué IA y qué modelo la dio | **Bien por API y en tu PC**: «Respondió z.ai con zai/glm-4.7-flash.», «Respondió LM Studio · qwen2.5-1.5b-instruct.». **En los chats web**, el modelo solo se dice cuando la web lo enseña (Meta, desde F0). Leerlo en todas y no enviar si no se puede confirmar es F4 | aquí, en pantalla |
| Si una IA falla, no se cambia sola por otra | **Bien**: si falla, se dice por qué y no se pregunta a ninguna otra. Solo si tú le pones una «reserva» en la configuración se usa, y se dice en directo y al final («Respondió el respaldo … en lugar de …») | aquí |
| Señales de vida en las respuestas largas | **Bien**: cada 10 s, sin mezclarse con la respuesta. Una de 6 minutos llegó entera (F1) | aquí |
| Se agrupa por conversación | **Bien**: el identificador de la conversación de Open WebUI queda en el registro de webllm (F1, comprobación 4) | aquí, en pantalla (F1) |
| **Parar** | **Bien, en tres sitios.** (1) El botón «Detener» de Open WebUI corta la respuesta de un chat web en 4 s, webllm lo apunta como «parado por ti» y la siguiente pregunta a esa IA va normal. (2) **«Parar todo»** en el Inicio de la app de webllm para todas las preguntas en curso, las de Open WebUI y las de la app, y dice qué paró («Parado: 1 pregunta y 1 chat de la ventanita»). (3) Una pregunta que aún esperaba turno no se envía nunca. La extensión 0.5.2 deja de manejar y de leer la página en cuanto se para (probado con la extensión de verdad en Chromium). **Lo que no hace:** pulsar el botón de parar *de la web*. Si la pregunta ya se había enviado, la web puede terminar de escribir su respuesta en la ventanita; webllm ya no la recoge. Pulsar ese botón solo cuando esté identificado con certeza en cada web es trabajo de F4 | aquí, en pantalla |
| Límite de gasto por fuente | **Bien**: cada IA por API, como mucho 300 preguntas al día (`api_daily_cap` en `data/config.yaml`; una sola IA puede tener el suyo con `daily_cap`). Cuenta cada llamada, reservas incluidas. Al llegar al tope no se envía nada y se dice en español. Los chats web siguen con su guardián (150 al día). Los modelos de tu PC no tienen tope: son gratis | aquí |
| Las claves al almacén de claves de Windows | **No lo he hecho, y es a propósito.** webllm no guarda ninguna clave propia en el proyecto. La de OmniRoute es un archivo del propio OmniRoute, que la necesita ahí. El token del puente lo lee la extensión de Chrome, y una extensión no puede leer ese almacén. Pasarlas no quitaría ninguna copia del disco. En su lugar, una prueba revisa cada archivo que iría a GitHub (el repositorio es público) buscando claves, y comprueba que las carpetas privadas (`data/`, `extension/config.json`) están excluidas. Si algún día webllm guarda una clave propia, irá al almacén | aquí |

Capturas: `docs/capturas/f2/openwebui/` (Open WebUI: 01 herramienta en el «+», 02 pide permiso, 03 respuesta con la herramienta, 04–06 Detener y la pregunta siguiente, 07 tu PC responde) y `docs/capturas/f2/` (app: «Parar todo» en claro y oscuro). Revisión de diseño de las 50 capturas de la app: 0 problemas (`revision.json`).

## Un fallo de Open WebUI que verás (no es de webllm)

Con el permiso por herramienta activado, **después de «Permitir» queda un «Preparando hora_hora_actual…» con la ruedita girando**, aunque la respuesta ya ha llegado bien (captura 03). Es un fallo de Open WebUI 0.11.4: en ese modo no apunta el resultado de la herramienta en su lista. Lo comprobé enviándole exactamente lo mismo sin pedir permiso: así sale bien. Ignora la ruedita: la respuesta y el registro de webllm están completos. Prefiero dejarte el permiso activado (nada se usa sin tu clic) a esconder la ruedita.

## Lo que se ha construido para esto

- **La pasarela para las APIs y tu PC**: la respuesta llega a trozos según se escribe, y las herramientas van y vuelven tal cual. Las que contestan todo de golpe (LM Studio) también funcionan.
- **Parar de verdad:** cada pregunta lleva una etiqueta hasta la extensión. Parar corta solo esa pregunta, nunca la de otra conversación. Una pregunta parada mientras esperaba turno no se envía. El motor de cadenas también sabe parar: la llamada en curso acaba como «parada por ti», no se prueban reservas ni pasos siguientes, y el registro se cierra con su candado.
- **El tope diario por API** (`budget.py`), con los mismos números en la app y en Open WebUI.
- **La prueba de claves** (`tests/test_secrets.py`).
- **La extensión 0.5.2** (desde F0 hasta aquí): obedece «parar» al momento.

## Trampas que encontré y quedaron resueltas

- **Parar no llegaba a Chrome.** Al cortar la conexión, el servidor mataba la tarea antes de poder avisar a la extensión. Ahora primero avisa y luego corta.
- **«Parar todo» no paraba las preguntas de la app a una IA por API.** Solo cortaba los chats de Chrome. Ahora para todo, y una prueba lo demuestra: falla sin el arreglo y pasa con él.
- **Un error a mitad de respuesta se perdía** (y con una versión intermedia, el pipe de Open WebUI se rompía). Ahora Open WebUI lo recibe, lo enseña y lo guarda en la conversación.
- **La pregunta siguiente a una parada tardaba 3 minutos en la demo.** No era webllm: Open WebUI manda la conversación entera y el truco de la demo «(demo: 3 minutos)» seguía en ella. La demo ya solo mira la última pregunta y obedece «parar» como la extensión de verdad.

## Para ti: cómo probarlo en tu PC

1. Doble clic en `ACTUALIZAR`.
2. En Chrome, abre `chrome://extensions` y pulsa **↻** en la tarjeta «webllm puente». Debe poner **0.5.2**.
3. Si ya pusiste webllm en Open WebUI (F1), vuelve a hacer doble clic en `herramientas\poner-en-openwebui.cmd` con tu clave: actualiza el pipe sin duplicar nada.
4. En Open WebUI, **una conversación nueva con cada una** de estas tres. En todas, pregunta «¿Qué es la inflación?»:
   - «Qwen (web)» → debe responder, y en «Pensando…» pone «Preguntando a Qwen…»;
   - «z.ai (API)» → debe responder, y debajo del nombre pone «Respondió z.ai con …»;
   - una de «(tu PC)» (LM Studio encendido) → debe responder, y pone «Respondió LM Studio · ….».
5. **Parar:** pregunta a Qwen algo largo («Escribe un cuento de 2000 palabras») y pulsa el cuadrado (Detener) a los pocos segundos. Open WebUI deja de esperar al momento. En la ventanita de webllm, la web de Qwen quizá termine su respuesta (webllm ya no la recoge ni la usa). Luego pregúntale otra cosa: debe responder normal, sin esperar a la anterior.
6. **Parar todo:** con una pregunta larga en marcha, abre la app de webllm (`WEBLLM`), pulsa **Parar todo** en el Inicio. Debe decir «Parado: 1 pregunta…».
7. En la app → Historial: salen las preguntas de Open WebUI («Desde Open WebUI»), con su candado verde.

Si algo sale distinto, mándame `data\logs\bridge.log`.

## Cómo se repite esta prueba (para quien programe)

```bash
python -m pytest -q                                   # todo (sin Open WebUI se salta solo su prueba)
WEBLLM_OPENWEBUI_PY=/ruta/.venv/bin/python python -m pytest -q tests/test_openwebui_face.py   # Open WebUI desde cero, F1 + F2
node app/scripts/screenshots.mjs docs/capturas/f2 20199   # la app, con python scripts/app_demo.py --port 20199
```
