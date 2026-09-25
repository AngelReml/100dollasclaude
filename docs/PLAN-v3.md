# PLAN v3 — webllm: inteligencia cruzada + aplicación de verdad

Fecha: 24-sep-2026. Hecho con la skill `experto-cowork-operativo`. Es un **plan**: todavía no hay código de esto.

## Cómo va (25-sep-2026)

| Fase | Estado | Qué falta |
|---|---|---|
| **1. Motor de cadenas** | **Hecho y probado con tests** (39 tests: plantillas, paralelo, reintentos, respaldo, candado). `webllm cadena` y `herramientas\probar-cadena.cmd` | La ejecución de verdad con tus chats: la haces tú con `probar-cadena` |
| 2. API de la app + eventos en directo | **En parte:** lo que necesitan Inicio, Preguntar e Historial (13 tests) | Rutas de cadenas para la Mesa y los eventos de una cadena larga |
| **3. App: Inicio, Preguntar, Historial** | **Hecho**, con guía de primera vez, modo claro y oscuro, capturas en `docs/capturas/fase3/` y revisión automática sin fallos | Tu prueba sin ayuda: doble clic en `WEBLLM` y una pregunta a todas |
| **3b. Arreglos tras tu prueba** | **Hecho** (25-sep, tarde): botón único **Conectar** que se pone en verde solo, guía que solo sale si falta algo, IAs en un desplegable agrupado. Capturas en `docs/capturas/3b-7a/` | Pulsar ↻ en la extensión (pasa a 0.4.0) y probar **Conectar** con un chat sin sesión |
| **7a. Modelos de tu PC** | **Hecho**: LM Studio y Ollama salen solos en "En tu PC", sin los modelos de embeddings, con botón **Encender** si están apagados. Una pregunta a la vez por programa. 9 tests con un LM Studio de mentira | Ver en la app la respuesta de tu `qwen2.5-1.5b-instruct` |
| **7b. Añadir una IA por su dirección** | **Hecho** (25-sep, noche): "Añadir otra IA" en Inicio y en el desplegable, permiso solo para esa web, prueba de verdad ("pong") paso a paso por el guardián, icono de la web, "Quitar". Extensión 0.5.0. Probado en Chromium con la extensión y el puente de verdad contra una web de chat de mentira (`tests/extension/add_flow.mjs`). Capturas en `docs/capturas/7b/` | Pulsar ↻ en la extensión (0.5.0) y añadir una web de verdad |
| **Arreglo: respuestas perdidas tras una verificación** (fallo que vio Iván) | **Hecho** (25-sep, noche): el tiempo esperando a Iván (verificación, ventana emergente, ventanita tapada) no cuenta; la pestaña que le necesita no rota; el puente espera mientras la extensión dice que sigue; la app ya no cuelga antes; "Te espera" y "En cola" en las tarjetas. `tests/extension/captcha_flow.mjs` falla con el código anterior y pasa con el nuevo | Preguntar a todas y resolver una verificación de Qwen |
| 4-6, 7c | Sin empezar (siguiente: 4) | — |

Diferencias con el plan, dichas claras:
- **Logos:** cada IA lleva un círculo de su color con su inicial, no el logo oficial.
- **Piezas del diseño todavía sin hacer**, porque ninguna pantalla de la fase 3 las usa: la `Línea de tiempo` (el avance de cada IA se ve en su tarjeta) y la `Ventana de confirmación`. Llegan con las fases 4 y 5.
- **Capturas de la guía:** son reales, de la página de extensiones de Chromium en español. Tu Chrome puede variar un poco.
- **7b, diferencias con lo escrito abajo:**
  - Las IAs añadidas se guardan en `data/state/custom_ais.json`, no en `data/config.yaml`. Ese archivo está en git y `ACTUALIZAR` chocaría con él.
  - La extensión no las guarda en `chrome.storage`: el puente le manda el nombre y la dirección con cada mensaje. Así un Chrome recién abierto también las conoce.
  - No hay pantalla de Ajustes todavía, así que el botón está en Inicio y en el desplegable.
  - El mensaje de envío de prueba lo manda el puente, no la extensión, para que pase por el guardián de cuentas (regla dura 6).
- **Los chats de tu Chrome se preguntan de uno en uno** (el motor de cadenas los trata como un solo origen). La extensión y el puente permiten varios a la vez, rotando pestañas, pero eso no está probado en tu PC. Queda así hasta probarlo.

## Lo que pidió Iván tras probar la app (25-sep-2026) — va ANTES de la fase 4

Iván ha probado la app en su PC: le gusta, "limpia y preciosa". El orden de trabajo pasa a ser:
**3b → 7a → 7b → 4 → 5 → 6 → 7c.**

### 3b. Arreglos de lo que ha probado

1. **"Abrir" no conecta, y "Comprobar" sí (fallo real).**
   - **Causa**, en `Bienvenida.tsx` y `ui/Fix.tsx`:
     - "Abrir" hace `window.open(url)`, que abre la web en una pestaña normal y no avisa a la app de nada;
     - el estado solo cambia al pulsar "Comprobar", que abre el chat en la ventanita de webllm.
   - **Arreglo:** un solo botón, **"Conectar"**, por cada chat. Al pulsarlo:
     - abre ese chat en la ventanita de webllm (vía la extensión, como hace `/api/comprobar`);
     - si no hay sesión, trae esa ventanita al frente para que Iván entre ahí;
     - vuelve a mirar sola cada 3 s, hasta 3 min, y el círculo se pone verde sin más clics.
   - Se quita el `window.open` a la pestaña normal.
   - **Prueba:** un test con la extensión de mentira pasando de `sin_sesion` a `lista`, y una captura con el verde sin segundo clic.
2. **La guía de primera vez le sobra.**
   - No se abre sola si Chrome ya está conectado y hay al menos un chat listo.
   - Hay un botón **"Saltar"** visible en cada paso.
   - Se puede volver a ver desde Ajustes ("Ver la guía otra vez").
3. **Las IAs, en un desplegable.** En vez de la fila de chips, un único botón **"IAs: 3 elegidas ▾"** que abre una lista con casillas:
   - agrupada en **"Chats en tu Chrome"**, **"IAs por API"** y **"En tu PC"** (locales, ver 7a);
   - cada IA con su logo, su semáforo y el motivo corto si no está lista;
   - con atajos arriba: "Todas las listas", "Solo las que no gastan cuenta", "Ninguna";
   - recuerda la última elección y se maneja con teclado (Radix `Popover` / `DropdownMenu`);
   - es el mismo componente que usarán las tarjetas de la Mesa (fase 4).

### 7a. Modelos locales (LM Studio y Ollama)

- **Verificado en el PC de Iván el 25-sep-2026:**
  - el servidor de LM Studio **está encendido** en `http://127.0.0.1:1234/v1`;
  - la CLI está en `%USERPROFILE%\.lmstudio\bin\lms.exe` y `lms server status` dice "running on port 1234";
  - `GET /v1/models` devuelve `qwen2.5-1.5b-instruct` más dos modelos de embeddings;
  - una llamada real a `/v1/chat/completions` con `qwen2.5-1.5b-instruct` respondió en 8,6 s, carga incluida.
- **Ollama** está instalado, pero su servidor (`http://127.0.0.1:11434/v1`) estaba apagado.
- **Qué se construye:**
  1. Una nueva "puerta" `local` en `config.py`, junto a `omniroute` y `bridge`.
     - Descubre sola los servidores locales conocidos: LM Studio en :1234 y Ollama en :11434, más los que Iván añada en Ajustes.
     - Lista sus modelos con `GET /v1/models` y **quita los de embeddings** (ids con `embed`).
     - Cada modelo es una IA del grupo **"En tu PC"**, con el nombre "LM Studio · qwen2.5-1.5b-instruct".
  2. **Sin guardián de cuentas**, porque no hay cuenta. Sí una llamada a la vez por servidor, porque el PC es uno, y un tiempo de espera largo.
  3. **Si el servidor está apagado**, se usa el patrón "qué pasó + botón":
     - "LM Studio está apagado · [Encender LM Studio]", que ejecuta `lms server start`;
     - para Ollama, `ollama serve`, lanzado sin atarse al proceso.
  4. Van directas a su servidor, sin pasar por OmniRoute.
- **Prueba:**
  - tests con el servidor de mentira haciendo de LM Studio: lista de modelos, filtro de embeddings y servidor apagado;
  - en vivo, Iván ve en la app la respuesta de su modelo de LM Studio.

### 7b. Añadir una IA nueva pegando su dirección

**Lo que ve Iván:**
- En el desplegable de IAs, y en Ajustes, hay **"+ Añadir otra IA"**. Pega la dirección de un chat (por ejemplo `https://chat.mistral.ai`) y pulsa **"Probar"**.
- La app le va contando en humano lo que encuentra: "Abriendo la web… Caja de texto: encontrada… Enviando una prueba… Respuesta leída ✔".
- Si funciona, la IA queda añadida con su nombre y su icono (el de la web), y ya puede usarla en Preguntar y en la Mesa.

**Cómo se hace:**
1. **Bloqueos (regla dura).**
   - Se rechazan `claude.ai`, `anthropic.com`, `chatgpt.com`, `chat.openai.com`, `openai.com` y cualquier dirección que no sea `https`.
   - Mensaje: "Claude y ChatGPT no se usan con webllm, así que esta dirección no se puede añadir."
2. **Permiso mínimo.**
   - El manifiesto gana `optional_host_permissions: ["https://*/*"]`, pero **no se concede nada por adelantado**.
   - Al añadir una web, la extensión abre su propia página `add.html?url=…` con un botón **"Permitir y probar"**.
   - Ese botón pide a Chrome permiso solo para ese dominio (`chrome.permissions.request`). Chrome enseña su propio aviso e Iván pulsa "Permitir".
3. **Prueba automática de la web**, con la detección genérica que ya tiene `driver.js`:
   - busca la caja de texto, el botón de enviar (o Enter), el botón de copiar o, si no lo hay, el texto de la respuesta, y el botón de parar;
   - envía "Responde solo con la palabra: pong";
   - si la respuesta capturada contiene "pong", la guarda.
   - Si sale el login o una verificación, se aplica la regla de siempre: Iván entra o la resuelve en esa ventanita y pulsa "Probar otra vez". Nunca se salta un CAPTCHA.
4. **Guardado.**
   - La extensión guarda la configuración de la web en `chrome.storage.local`, junto a las de `sites.js`.
   - El servidor añade la IA a `data/config.yaml` (`kind: browser`, `gateway: bridge`, `model: browser/<nombre>`, `url`).
   - `SITES` en `bridge.py` deja de ser una lista fija y se lee de la configuración.
   - El guardián de cuentas se aplica solo.
5. **Honestidad si una web no se deja.** Se dice exactamente qué falló ("no encontré la caja de texto", "no hay botón de copiar: leeré el texto de la página") y, si nada funciona: "Esta web no se deja manejar todavía · [Enviar diagnóstico]". No se promete que cualquier web funcione: se prueba y se dice.

**Prueba:**
- tests del registro dinámico de IAs, del bloqueo de dominios y del guardado;
- una página de chat de prueba servida en local para la detección genérica;
- en vivo, Iván añade una web nueva y le hace una pregunta.

### 7c. Elegir el modelo dentro de Qwen y z.ai

Esto lo pidió Iván el 24-sep. La extensión ya lee qué modelo respondió (`modelLabel`); falta **elegirlo**:
- La extensión lee las opciones del menú de modelos de la web y, antes de enviar, elige la que Iván haya marcado.
- En la app sale un segundo desplegable, "Modelo", al lado de esa IA.
- Si el modelo potente llega a su límite, la web suele cambiar de modelo sola. Iván lo vio el 24-sep: "gastó los tokens de un modelo, cambió de modelo y respondió". La app lo enseña: "Respondió con X porque Y estaba agotado".

## Veredicto

**Combinación.** Se construye como código en este mismo proyecto:
- una sesión de desarrollo por fases;
- subagentes solo para piezas que no dependen unas de otras (el motor y la pantalla);
- ninguna skill, plugin ni conector MCP nuevo.

No hace falta nada nuevo del ecosistema Claude: todo vive dentro de webllm, en tu PC.

## Qué vas a tener al final (en cristiano)

**Un solo icono**, "webllm", en el escritorio. Al hacer doble clic:
- se enciende todo lo necesario;
- se abre una ventana propia con aspecto de programa (Chrome en modo aplicación, sin pestañas ni barra de direcciones).

**Seis pantallas:**

1. **Inicio.** Un semáforo por cada pieza y cada IA: conectada, en pausa, sin sesión o saturada. Cada una con su botón para arreglarla.
2. **Preguntar.** Escribes una vez y eliges destinatarios con un clic.
   - Las respuestas salen en columnas.
   - Cada respuesta tiene botones: **"Pásasela a…"** (se la mandas a otra IA), **"Que la critique…"** y **"Copiar"**.
3. **Mesa de IAs (la inteligencia cruzada).** Montas una "cadena" con tarjetas.
   - En cada tarjeta dices **a quién** va y **qué mensaje**.
   - El mensaje puede incluir **respuestas de tarjetas anteriores**, eligiéndolas de una lista, sin escribir código.
   - Pulsas **Ejecutar** y ves cada paso en directo. Al final queda toda la cadena guardada.
   - Hay plantillas listas, para no empezar de cero:
     - **Consejo + juez:** la misma pregunta a varias IAs; otra compara las respuestas y escribe la mejor, diciendo en qué coinciden y en qué no.
     - **Reparto + integración:** un mensaje distinto a cada IA (por ejemplo "Qwen investiga el mercado", "DeepSeek los números", "z.ai los riesgos") y otra IA lo une todo en un informe.
     - **Debate:** A responde, B le busca fallos, A corrige. Tú eliges cuántas vueltas.
     - **Cadena:** lo que dice A entra en B y lo que dice B entra en C (por ejemplo: idea → plan → revisión).
     - **Programar con revisión:** una IA cambia el código, otra revisa el cambio y, si ve un fallo, la primera lo corrige.
4. **Programar.**
   - Eliges la carpeta con el explorador de Windows, eliges la IA y escribes qué quieres.
   - Ves el cambio en colores (rojo lo quitado, verde lo añadido) y el resultado de los tests.
   - Botón **"Deshacer"**.
5. **Historial.**
   - Todo lo que has hecho, con buscador.
   - Cada cadena con un **candado verde** si nadie la ha tocado; es la verificación del diario encadenado que ya existe.
   - Botón para exportar.
6. **Ajustes.**
   - IAs activas y su modelo, límites diarios.
   - "Reanudar", "Diagnosticar", "Probar todo" (el panel de ahora pasa aquí).

**Antes de ejecutar una cadena**, la app te dice **cuántos mensajes gastará de cada cuenta**. Así un debate de 3 vueltas con 3 IAs no te funde el límite sin avisar.

## Diseño: ultra intuitiva y estética (obligatorio, no opcional)

La regla de oro es que **Iván la use sin ayuda y sin leer instrucciones**. Si una pantalla necesita un manual, está mal diseñada y se rehace.

**Principios:**

1. **Una acción principal por pantalla.** Un botón grande de color claramente destacado ("Preguntar", "Ejecutar cadena", "Programar"). Lo demás, discreto.
2. **Cero jerga.** Nada de "token", "endpoint", "SSE", "HTTP 503" ni "provider". Se dice "IA", "cadena", "conectada", "saturada, prueba en un rato".
3. **Los errores nunca se enseñan en crudo.** Siempre en formato **qué pasó + qué hacer + botón que lo arregla**. Por ejemplo: "Qwen no tiene sesión abierta · [Abrir Qwen para entrar]".
4. **El estado se entiende de un vistazo.** Cada IA con su logo y su color, y un semáforo que usa color, icono y palabra a la vez (que no dependa solo del color).
5. **Todo se ve avanzar.** Una línea de tiempo con cada paso de la cadena: esperando, escribiendo, respondida, fallo. Los mensajes son humanos ("DeepSeek está escribiendo…") y hay un cronómetro.
6. **Nada da miedo.** "Deshacer" en todo lo que cambie archivos, confirmación solo en lo irreversible, y aviso de gasto de mensajes antes de ejecutar.
7. **Pantallas vacías que enseñan.** Cuando no hay nada, se muestra un ejemplo y un botón "Probar este ejemplo", no un hueco en blanco.
8. **Primera vez guiada.**
   - Un asistente de 3 pasos al abrirla por primera vez:
     1. instalar la extensión, con capturas;
     2. comprobar sesiones, abriendo cada web con un botón;
     3. hacer la primera pregunta a todas.
   - Cada paso se pone en verde solo.
9. **Estética cuidada y coherente.**
   - Un sistema de diseño único: colores, tipografía, espaciado, esquinas redondeadas y sombras suaves.
   - Modo claro y oscuro, animaciones sutiles de menos de 200 ms, iconos de un mismo estilo.
   - Aspecto de aplicación moderna, no de página de pruebas.
10. **Accesible.** Buen contraste (nivel AA), se maneja con teclado, textos de al menos 15 px y botones grandes.

**Piezas del sistema de diseño**, reutilizables en todas las pantallas:
- básicas: `Botón`, `Tarjeta`, `Semáforo`, `Chip de IA` (logo, nombre y estado);
- de conversación: `Tarjeta de respuesta` (texto con formato, modelo usado, tiempo, y los botones Pásasela a / Critícala / Copiar), `Tarjeta de paso` (para la Mesa);
- de ayuda y avisos: `Línea de tiempo`, `Aviso` (arriba a la derecha, que desaparece solo), `Ventana de confirmación`, `Pantalla vacía`, `Asistente de primera vez`.

**Tecnología para la estética:**
- React + Vite + TypeScript + Tailwind CSS;
- componentes accesibles con Radix/shadcn-ui;
- iconos Lucide y la tipografía Inter, incluida en el proyecto.

El resultado compilado se guarda en el repo, así que tu PC nunca necesita instalar ni compilar nada.

**Cómo se comprueba que es intuitiva y estética (criterio de "hecho" de cada pantalla):**
- **Capturas** de cada pantalla en modo claro y oscuro, a 1280 y 1920 px de ancho, sin cortes ni textos solapados.
- Revisión con esta lista: una acción principal, cero jerga, errores con botón de arreglo, pantalla vacía con ejemplo, se usa con teclado.
- **Prueba final con Iván**, sin ayuda. Tiene que:
  1. hacer una pregunta a todas;
  2. ejecutar la plantilla "Consejo + juez";
  3. pasar una respuesta a otra IA;
  4. deshacer un cambio de código.

  Si se atasca en algo, esa pantalla se rediseña.

## Arquitectura recomendada

```
[icono webllm] → WEBLLM.cmd → enciende OmniRoute + servidor webllm → abre la app (chrome --app)

servidor webllm (un solo proceso, 127.0.0.1:20130)
  ├── puente con la extensión (lo que ya funciona)
  ├── MOTOR DE CADENAS (nuevo): ejecuta los pasos, en paralelo si no dependen uno de otro
  ├── API de la app + eventos en directo (nuevo)
  └── sirve la app (nuevo: React compilado, sin internet)

extensión de Chrome (la de ahora) · OmniRoute (APIs) · aider (programar) · diario encadenado
```

- **Motor de cadenas** (`src/webllm_agent/flows.py`).
  - Cada cadena es un archivo JSON con sus pasos.
  - Cada paso lleva: destinatario(s), plantilla de mensaje con huecos del tipo `{{paso1.respuesta}}`, modo (una IA, varias, juez, repetir N vueltas) y qué hacer si falla (esperar, probar otra IA o parar).
  - Todo pasa por el guardián de cuentas que ya existe. Cada respuesta va al diario encadenado.
- **La app** (`app/`, React + Vite + TypeScript).
  - Se compila una vez y el resultado se guarda en el proyecto. Tú no instalas nada.
  - La sirve el mismo servidor. Funciona sin internet, salvo los chats de las IAs.
- **Por qué Chrome en modo aplicación y no Electron:** ya tienes Chrome, no hay que instalar otro programa de 150 MB, se ve como una ventana propia y la extensión ya vive ahí.
- **Qué NO se instala:** ni plugins, ni conectores MCP, ni servicios en la nube. Las cuentas y los datos se quedan en tu PC.

## Procedimiento exacto (fases, cada una con prueba que ves)

| Fase | Qué se hace | Cómo lo compruebas tú (evidencia) |
|---|---|---|
| **1. Motor de cadenas** | Motor, plantillas de mensaje, pasos en paralelo o en fila, reintentos, guardado, diario | Ejecuto de verdad "Reparto + integración" con 2 chats y 1 IA por API. Te enseño la cadena guardada y su candado verde |
| **2. API de la app + eventos en directo** | Rutas para estado, preguntar, cadenas, historial y programar; avisos en directo | Tests automáticos en verde, y una cadena que se ve avanzar paso a paso |
| **3. App: Inicio, Preguntar e Historial** | Sistema de diseño (colores, piezas reutilizables, modo claro y oscuro) + las 3 pantallas básicas + el botón "Pásasela a…" + asistente de primera vez | Capturas de cada pantalla en claro y oscuro y la lista de diseño cumplida; luego tú la abres con el icono y haces una pregunta sin ayuda |
| **4. App: Mesa de IAs** | Constructor de tarjetas, 5 plantillas, aviso de cuántos mensajes gastará | Ejecuto cada plantilla de verdad y lo ves en pantalla |
| **5. App: Programar** | Elegir carpeta, pedir el cambio, ver colores y tests, deshacer, revisión por otra IA | Una IA de tu Chrome arregla el proyecto de prueba, otra lo revisa y ves el antes y el después |
| **6. Icono único y limpieza** | WEBLLM.cmd con icono, Ajustes, guía, y los .cmd viejos a `herramientas\` | Tú haces doble clic en el icono y completas una cadena sin ayuda |

Las fases 1 y 3 se pueden hacer a la vez con dos subagentes: una es el motor y la otra la pantalla, y no tocan los mismos archivos. El resto va en orden.

## Contrato de ejecución

- **Permisos mínimos.**
  - El servidor solo escucha en `127.0.0.1` y usa su clave.
  - La app no guarda cookies ni contraseñas de las webs; eso sigue en tu Chrome.
  - Nada de Claude ni ChatGPT como destino.
- **La IA nunca ejecuta nada por su cuenta.**
  - Las respuestas se tratan como texto no fiable.
  - El motor no ejecuta código ni comandos que venga de una respuesta.
  - Programar solo cambia archivos de la carpeta que tú eliges, y siempre con git para poder deshacer.
- **Protección de cuentas.**
  - Siguen el espaciado, el tope diario y las pausas.
  - Las cadenas largas avisan de cuánto gastan antes de empezar.
  - Si una web se satura, la cadena prueba otra IA o espera. Nunca insiste contra un bloqueo.
- **Evidencia obligatoria por fase:** tests en verde con su salida real, una ejecución de verdad guardada en el historial con su candado, y una captura de pantalla de la app. Nada de "ya funciona" sin prueba.

## Riesgos que cambian el plan

1. **"Trifecta letal", en la pantalla Programar.**
   - Se juntan tus archivos privados, respuestas de IAs (contenido no fiable) y un canal de salida (las webs de chat). Mandar tu código a esas webs es justo el objetivo, pero significa que ese código sale de tu PC.
   - **Mitigación:** solo se manda la carpeta que eliges. Nunca los archivos `.env`, contraseñas o claves: se bloquean por defecto con `.aiderignore`. Y la app lo avisa la primera vez.
2. **Gasto de cuentas.**
   - La inteligencia cruzada multiplica los mensajes.
   - **Mitigación:** el aviso de gasto antes de ejecutar. Además, por defecto el papel de **juez** lo hace una IA por API (z.ai, groq o Nemotron), que no quema cuentas de chat.
3. **CAPTCHAs.** Con más volumen salen más. Se mantiene "te aviso y lo resuelves tú". Si Qwen los pide demasiado, sale de las plantillas por defecto.
4. **Textos largos en los chats.** Pasarle 4 respuestas largas a un juez puede superar lo que admite la caja de texto de una web. **Mitigación:** para el juez, IA por API con memoria larga; y si no hay más remedio, se recorta con aviso.
5. **Las webs cambian.** Se mantiene "Diagnosticar" y la reparación con el registro del servidor.

Nivel de riesgo (según la skill): esto es código local tuyo con acceso a tus archivos y a internet, es decir, **alto**. Se controla con los puntos de arriba, sin instalar plugins ni conectores de terceros.

## Verificación antes de decir "hecho"

- `python -m pytest -q` con la salida real (hoy: 79 tests en verde).
- Una ejecución real de cada plantilla guardada en `data/runs/`, con `journal verify` dando OK.
- Capturas de la app en cada fase.
- La prueba final la haces tú: doble clic en el icono y una cadena completa.

## Decisiones tomadas por Iván (24-sep-2026)

1. **App dentro de Chrome, en modo aplicación** (`chrome --app=http://127.0.0.1:20130`), no Electron.
2. **El juez, por defecto, es una IA por API** (z.ai GLM, groq o Nemotron vía OmniRoute), no un chat web.
3. **Se empieza por la fase 1 (motor) y la 3 (Preguntar con "Pásasela a…")**.
4. **Ultra intuitiva y estética**: la sección de diseño de arriba es obligatoria en cada pantalla.
5. **Quien programa es Claude Code desde GitHub.** Lee la sección siguiente.

## Para Claude Code (programando desde GitHub, sin acceso al PC de Iván)

- **Lee primero `CLAUDE.md`** (reglas del proyecto) y `docs/ESTADO.md` (qué funciona hoy).
- **Qué NO tienes en la nube:**
  - el Chrome de Iván con la extensión;
  - OmniRoute (`http://127.0.0.1:20128`), sus claves (`~/.omniroute/.env`) y `data/` (diario, token del puente);
  - las sesiones de las webs.
- **Qué SÍ puedes comprobar:** `python -m pytest -q`. Hay un servidor OpenAI de mentira (`tests/conftest.py`) y una extensión de mentira sobre un WebSocket real (`tests/test_bridge.py`). Todo lo nuevo se prueba igual: sin red y con estos dobles.
- **Nunca declares "funciona en vivo"** sin evidencia del PC de Iván.
  - En cada PR, separa "probado con tests (salida pegada)" de "pendiente de probar en el PC de Iván".
  - La prueba en vivo la hace Iván: con el panel / "Probar todo", o con la nueva app.
- **La app compilada se guarda en el repo** (`src/webllm_agent/static/app/`). El PC de Iván no debe necesitar `npm` para usarla; solo para quien programa.
- **Forma de trabajar:**
  - una rama y un PR por fase, con la lista de comprobación de diseño y los tests;
  - no romper lo que ya funciona (puente, extensión, `webllm ask`, diario, guardián);
  - si tocas `extension/`, sube `version` en `manifest.json`: Iván tendrá que pulsar la flecha ↻ en `chrome://extensions`.
- **Después de cada PR fusionado**, Iván hace doble clic en `ACTUALIZAR.cmd` en su PC, que baja los cambios de GitHub.

## Fundamento

- Primitiva más pequeña y "empieza conversacional, automatiza después": skill `experto-cowork-operativo` (pluto.security 2026-04-29; claude.com/blog/subagents-in-claude-code).
- Subagentes solo para trabajo independiente y nunca editando el mismo archivo: ídem.
- Trifecta letal: Simon Willison, 2025-06-16.
- Estado actual verificado en este proyecto (24-sep-2026):
  - puente, extensión y panel funcionando;
  - "Programar con el chat z.ai: BIEN" visto por Iván;
  - 79 tests en verde;
  - commit `30903a8`.
