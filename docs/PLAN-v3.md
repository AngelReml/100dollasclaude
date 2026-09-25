# PLAN v3 — webllm: inteligencia cruzada + aplicación de verdad

Fecha: 24-sep-2026. Hecho con la skill `experto-cowork-operativo`. Es un **plan**: todavía no hay código de esto.

## Cómo va (25-sep-2026)

| Fase | Estado | Qué falta |
|---|---|---|
| **1. Motor de cadenas** | **Hecho y probado con tests** (39 tests: plantillas, paralelo, reintentos, respaldo, candado). `webllm cadena` y `herramientas\probar-cadena.cmd` | La ejecución de verdad con tus chats: la haces tú con `probar-cadena` |
| 2. API de la app + eventos en directo | **En parte:** lo que necesitan Inicio, Preguntar e Historial (13 tests) | Rutas de cadenas para la Mesa y los eventos de una cadena larga |
| **3. App: Inicio, Preguntar, Historial** | **Hecho**, con guía de primera vez, modo claro y oscuro, capturas en `docs/capturas/fase3/` y revisión automática sin fallos | Tu prueba sin ayuda: doble clic en `WEBLLM` y una pregunta a todas |
| 4-6 | Sin empezar | — |

Diferencias con el plan, dichas claras:
- **Logos:** cada IA lleva un círculo de su color con su inicial, no el logo oficial.
- **Piezas del diseño todavía sin hacer**, porque ninguna pantalla de la fase 3 las usa: la `Línea de tiempo` (el avance de cada IA se ve en su tarjeta) y la `Ventana de confirmación`. Llegan con las fases 4 y 5.
- **Capturas de la guía:** son reales, de la página de extensiones de Chromium en español. Tu Chrome puede variar un poco.

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
