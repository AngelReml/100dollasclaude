# F1 — Open WebUI como cara de webllm (26-sep-2026)

**Resultado en la nube: Open WebUI pasa todo lo que se puede probar aquí.** Falta tu prueba en el PC (abajo) para decidirlo del todo, como dice el plan (PLAN-v5, D1 y F1).

Probado con Open WebUI **0.11.4** (21-sep-2026, la última que había) instalado en la nube, contra la demostración de webllm: el puente, la pasarela y el registro de verdad, con un Chrome y un OmniRoute de mentira.

## Las 12 comprobaciones

| # | Qué | Resultado | Dónde |
|---|---|---|---|
| 1 | Salen los modelos de webllm en el selector | **Bien**: las 8 IAs, con nombres claros ("Qwen (web)", "z.ai (API)"…) | aquí, en pantalla |
| 2 | La respuesta llega por partes | **Bien**: primero los avisos y después el texto | aquí, en pantalla |
| 3 | Una respuesta de 6 minutos no se corta | **Bien**: llegó entera a los 365 s | aquí, en pantalla |
| 4 | Llega a webllm el identificador de la conversación | **Bien**: el mismo en Open WebUI y en el registro de webllm | aquí |
| 5 | Una herramienta MCP (la hora) pide permiso y funciona | **Pendiente, en F2**: necesita que las IAs por API puedan usar herramientas a través de webllm (es una tarea de F2). La aprobación ya queda activada por el instalador | aquí, en F2 |
| 6 | Tu servidor MCP de terminal funciona con `mcpo` | Falta | tu PC |
| 7 | Tu SKILL.md de prompt-forge se importa y se usa | **El mecanismo, bien**: una skill de prueba elegida con «$» llega a la IA dentro de sus instrucciones. Falta con tu prompt-forge | aquí y tu PC |
| 8 | Desde el móvil, por Tailscale | Falta | tu PC |
| 9 | En español, y los avisos de webllm a la vista | **Bien**: la interfaz está en español; "te espera: resuelve la verificación…" se ve sin abrir nada; el bloque plegable "Pensando durante…" guarda lo que pasó | aquí, en pantalla |
| 10 | Prueba sin guía (6 cosas a la primera) | Falta | tu PC |
| 11 | El interruptor "Pensar más" sale en el "+" y llega a webllm | **Bien**: sale en el botón de integraciones de la caja de texto y webllm recibe el modo "pensar" | aquí, en pantalla |
| 12 | Los archivos llegan enteros a webllm | **Bien**: un PDF y una imagen llegan con la **misma huella** (sha256) que los originales. Y al terminar sigue a la vista que la IA todavía no los ha visto (pasarlos a las webs es la fase F4) | aquí, en pantalla |

Capturas: `docs/capturas/f1/` (del 01 al 10).

## Lo que se ha construido para esto

- **La pasarela de webllm** (`/gw/v1`, en el mismo puente de siempre): Open WebUI habla solo con webllm. Cada pregunta pasa por el mismo motor que la app, así que se aplican:
  - el guardián de tus cuentas;
  - el registro con candado verde;
  - el historial (sale como "Desde Open WebUI");
  - los mismos mensajes de error en español.
- **La "pipe" de webllm** (`openwebui/webllm_pipe.py`): la función que Open WebUI ejecuta para mostrar tus IAs como modelos y mandarles la conversación, los archivos de ese mensaje y los modos.
- **El interruptor "Pensar más"** (`openwebui/webllm_modo_pensar.py`).
- **El instalador** (`scripts/openwebui_setup.py`, con doble clic en `herramientas\poner-en-openwebui.cmd`). Deja Open WebUI así:
  - cada IA de webllm recibe tus archivos enteros (Open WebUI no los lee ni los indexa por su cuenta);
  - las tareas de fondo que gastarían mensajes de tus chats (etiquetas, sugerencias, resúmenes) están apagadas;
  - los títulos de las conversaciones los pone webllm con tus primeras palabras, sin preguntar a ninguna IA;
  - las sugerencias, en español;
  - el modelo "Arena" de Open WebUI, oculto;
  - la aprobación de herramientas, disponible.

## Trampas que encontré y quedaron resueltas

- **Mensajes gastados sin que lo pidas.** Open WebUI manda por detrás, al mismo modelo, peticiones para inventar el título, las etiquetas y las sugerencias. Con un chat web, cada pregunta tuya gastaría 2 o 3 mensajes más de tu cuenta.
  - La pipe las responde ella misma.
  - Aunque llegaran, webllm las rechaza para los chats web.
  - Y el instalador las apaga.
- **El aviso escondido.** "Qwen te espera" quedaba dentro del bloque plegado. Ahora sale en la línea de estado, a la vista.
- **Las claves de API vienen apagadas** en Open WebUI. Sin activarlas no se puede crear la clave que usa el instalador. Por eso son los pasos 3 y 4 de abajo.
- **Una conversación vacía se mandaba igual.** Con solo espacios, el puente mandaba al chat la instrucción final sin pregunta. Arreglado también para aider.

## Para ti: cómo probarlo en tu PC

1. **Instala Open WebUI Desktop:** `winget install OpenWebUI.OpenWebUI` en una ventana de comandos, o su instalador (github.com/open-webui/desktop).
2. **Ábrelo y crea tu usuario.** El primero que se crea es el administrador.
3. **Activa las claves de API:** tu nombre (abajo a la izquierda) → **Administración** → **Ajustes** → **General** → activa **"Enable API Keys"**. Esa opción sale en inglés: Open WebUI no la tiene traducida. Guarda.
4. **Crea la clave:** tu nombre → **Ajustes** → **Cuenta** → **Claves de la API** → **Crear Nueva Clave**. Cópiala.
5. Con **webllm abierto**, doble clic en **`herramientas\poner-en-openwebui.cmd`**, pega la clave y pulsa Enter.
   - Encuentra Open WebUI solo (la aplicación de escritorio usa `http://localhost:8080`).
   - Debe terminar en "Listo".
6. En Open WebUI, arriba, elige **"Qwen (web)"** y pregunta algo.
   - **Lo que debes ver:** "Pensando…" mientras Qwen escribe en la ventanita de webllm, y después la respuesta.
   - Si pide una verificación, arriba sale "Qwen te espera: resuelve la verificación en la ventanita de webllm".
7. **Las comprobaciones que solo puedes hacer tú:**
   - **6:** tu servidor MCP de terminal a través de `mcpo`;
   - **7:** importa tu SKILL.md de prompt-forge (Espacio de trabajo → Skills) y úsalo escribiendo «$» en la caja;
   - **8:** chatea desde el móvil con datos (Tailscale Serve; la guía llega en F10);
   - **10:** sin mirar ninguna guía, haz estas 6 cosas y apunta cuáles te salen a la primera:
     1. empezar una conversación;
     2. elegir un modelo;
     3. adjuntar un archivo;
     4. parar una respuesta;
     5. encontrar una conversación antigua;
     6. aprobar una herramienta (esta, cuando llegue F2).

**Regla de decisión (PLAN-v5):** Open WebUI se queda si pasan la 1, la 2, la 3, la 10, la 11 y la 12, y de las demás falla como mucho una. Hoy pasan todas las que se pueden probar aquí. La 10 es tuya.

## Cómo se repite esta prueba (para quien programe)

```bash
# Open WebUI en un entorno aparte (Python 3.11): uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python open-webui
DATA_DIR=... OFFLINE_MODE=true DEFAULT_LOCALE=es-ES ENABLE_OLLAMA_API=false ENABLE_OPENAI_API=false \
  .venv/bin/open-webui serve --port 20210
python scripts/app_demo.py --port 20199 --data DIR
python scripts/openwebui_setup.py --openwebui http://127.0.0.1:20210 --clave <token del administrador de prueba> \
  --webllm http://127.0.0.1:20199 --webllm-token demo-token
OW_EMAIL=... OW_PASSWORD=... WEBLLM_DATA=DIR OUT=... node tests/openwebui/f1_checks.mjs [--largo]
```

Fuentes:
- Open WebUI 0.11.4, su propio código: las funciones "pipe", los filtros con interruptor (`self.toggle`), `__files__` y `metadata.user_message`, `file_context`, `filterIds`, `tool_approval_mode`, `ENABLE_API_KEYS` (apagado por defecto).
- La dirección de la aplicación de escritorio (`localhost:8080`): tech-insider.org/open-webui-setup-2026. Por si no es esa, el instalador también prueba 3000 y 8081.
