# PLAN-v5 — webllm: el motor de IAs detrás de una cara tipo Claude

**Fecha:** 25-sep-2026. Sale de la lluvia de ideas con Iván y de la crítica de 5 IAs (Qwen, DeepSeek, z.ai, Meta y groq).

**Sustituye a PLAN-v4.**
- `docs/VISION.md` sigue valiendo en los conceptos. Donde no coincida con este plan, manda este plan.
- `docs/PLAN-v3.md` sigue siendo la referencia de las reglas de diseño y de evidencia.

**Qué significa "sin errores" aquí.** Ningún plan garantiza cero fallos. Este los reduce con cinco cosas:
1. cada fase tiene una **puerta de entrada** (qué tiene que estar probado antes de empezar);
2. cada fase tiene una **salida medible** (qué salida real demuestra que está hecha);
3. los cambios son pequeños, con un PR por fase;
4. hay tests automáticos y una prueba en tu PC;
5. todo se puede deshacer: la cara nueva es un programa aparte y la app actual de webllm no se tira.

---

## 1. Decisiones cerradas

| # | Decisión | Por qué (evidencia) |
|---|---|---|
| D1 | **La cara es Open WebUI Desktop**, y webllm es **el motor**. Open WebUI habla con webllm como con cualquier proveedor de IA. **Plan B: LibreChat.** **Plan C: la app propia de webllm.** | Open WebUI se instala en Windows con un instalador o con `winget`, sin Docker. Ya trae: conectores MCP nativos, **aprobación de herramientas antes de ejecutarlas** (v0.11.1, agosto de 2026), skills con el mismo formato SKILL.md, y una guía oficial para usarlo desde el móvil con Tailscale. LibreChat también tiene MCP, skills y aprobaciones, pero pide Docker o Node 24 + MongoDB: demasiado peso. Hacerlo nosotros desde cero es lo que las 4 críticas puntuaron con 4/10 |
| D2 | **Todo pasa por webllm.** Open WebUI tiene **una sola conexión**: webllm. Chats web, APIs, modelos de tu PC y skills de webllm aparecen como "modelos" en su selector | Así webllm es el único que escribe el registro y la memoria, y aplica el guardián y el presupuesto a todo |
| D3 | **El núcleo funciona sin ningún chat web.** Las APIs gratis y los modelos de tu PC son la base; los chats web son un extra valioso | La extensión es la pieza más frágil (4 de 5 críticas) |
| D4 | **El Comité es obligatorio y es la pieza central**, con el protocolo de Iván (sección 2). Aparece en el selector como **"webllm · Comité"** | Decisión de Iván |
| D5 | **Memoria con un solo escritor.** webllm guarda todo en su registro local y lo **copia en un solo sentido** al vault de Obsidian, que está en una carpeta sincronizada con Google Drive. **Nunca se lee de vuelta desde Drive** | Obsidian + Drive en ambos sentidos = conflictos (5 de 5 críticas). Es la idea de Meta |
| D6 | **Un solo formato de "acción"** (el estándar `tool_calls`) para todas las IAs. Open WebUI enseña la tarjeta **Permitir/Denegar**. Con los chats web, webllm hace de intérprete: menú en texto → petición → `tool_calls` | Es la idea de z.ai: una tarjeta, un registro, un código |
| D7 | **Ficha de capacidades por cada IA y modelo**, y **"Automático" con reglas escritas y a la vista**, afinadas antes de entregarlo. Siempre puedes elegir tú el modelo. **Sin aprendizaje automático** | Idea de DeepSeek; decisión de Iván |
| D8 | **Claves de las APIs en el almacén de claves de Windows** (Administrador de credenciales), nunca en archivos del proyecto | 4 de 5 críticas |
| D9 | **Botón "Parar todo"**, registro del sistema, límites de gasto por fuente y un "contrato de fallo" (qué pasa si algo se cae a mitad) | 5 de 5 críticas |
| D10 | **Chats web sin memoria entre proyectos:** modo temporal donde exista (o memoria desactivada en tu cuenta) y chat nuevo en cada trabajo. El Comité sigue en la misma conversación solo entre el rol y el problema | Crítica de z.ai: la memoria de los chats web mezcla proyectos |
| D11 | **El registro se llama "auditable"**, no "a prueba de manipulaciones". Más adelante, el sello del registro se podrá guardar en GitHub | Crítica de z.ai |
| D12 | **Móvil con Tailscale Serve** (HTTPS privado), sin abrir el PC a internet. Primero solo chatear y leer; encargar trabajos, después | Guía oficial de Open WebUI + crítica de z.ai |
| D13 | **Taller de código:** OpenCode con permiso "preguntar" antes de editar o ejecutar, en una rama de prueba (git worktree), con **modo simulación** y los **tests como juez**. Nunca sube nada solo a GitHub | Críticas de Meta y Qwen |
| D14 | **Se aplazan:** imágenes, vídeo y audio; plugins; enrutador que aprende; pedir trabajos desde el móvil | 5 de 5 críticas |
| D15 | **Primeras skills:** el Comité (de webllm) y tu **prompt-forge** (tu SKILL.md). Después, experto-cowork y "experto GPT" | Suposición: confírmala o cámbiala |
| D16 | **Seguir tú una conversación directamente en la web queda registrado** (modo observador, sección 3) | Petición de Iván: de 8 respuestas te gusta una y quieres seguir hablando con esa IA en su propia web |
| D17 | **Webs que se reparan solas** ante cambios de diseño o webs nuevas raras, en 4 capas y sin saltarse nunca un bloqueo anti-bot (sección 3) | Petición de Iván + la crítica número 1 de todas: la fragilidad de la extensión |
| D18 | **Interfaz ultraintuitiva = la estándar de los chats de IA** (ChatGPT, Claude): conversaciones a la izquierda, selector de modelo arriba, caja de texto abajo con adjuntar, respuesta que se escribe en directo, tarjeta Permitir/Denegar. **webllm no inventa pantallas ni botones nuevos en la conversación**: todo lo suyo entra por piezas que ese estándar ya tiene (sección "La cara") | Petición de Iván. Refuerza D1: el diseño de Open WebUI sigue el de ChatGPT, así que lo que ya sabes usar funciona igual |
| D19 | **Claude y GPT por dentro de otros servicios, aprobados** (Duck.ai, Poe, Perplexity, Arena, Copilot…), y dentro de ellos se puede elegir cualquier modelo. **Siguen fuera:** `claude.ai` y `chatgpt.com` directos, y tus suscripciones de Claude, ChatGPT o Codex a través de OmniRoute | Decisión de Iván (25-sep-2026). Da al Comité una familia más (OpenAI), y el jurado es mejor con familias distintas |
| D20 | **Todas las IAs con chat web que hemos encontrado vienen precargadas** (catálogo de la sección 6): no escribes ninguna dirección. Lo único que nadie puede hacer por ti es **entrar una vez con tu cuenta** en las que la pidan (regla dura 3). Chrome da permiso solo a las que dejas marcadas | Petición de Iván: "quiero tenerlas todas". Mínimo privilegio: nada de permisos fijos para 27 webs que quizá no uses |

### La cara (D18): cómo se ve todo lo de webllm sin salir del estándar

| Lo de webllm | Dónde aparece | Igual que en |
|---|---|---|
| Elegir IA, modelo o "Automático" | El selector de modelo de arriba, con nombres claros en español y agrupados: "Qwen 3.8 (web)", "GLM-4.7 rápido (API)", "webllm · Automático" | El selector de modelo de ChatGPT o Claude |
| El Comité | Un "modelo" más: "webllm · Comité". Escribes la idea y la respuesta es el documento de fusión | Elegir un modelo "que piensa más" |
| El progreso del Comité (roles, veredictos, recuento) | El bloque plegable de razonamiento, encima de la respuesta | El "Pensando…" plegable de ChatGPT o Claude |
| Una web te espera (verificación, ventana tapada) o se acabó una cuota | Una línea dentro de ese mismo bloque, en español: qué pasó y qué hacer | Los avisos dentro de la respuesta |
| Acciones (GitHub, tu terminal) | La tarjeta Permitir/Denegar | La aprobación de herramientas de Claude |
| Skills (Comité, prompt-forge) | La lista de skills de Open WebUI | Las skills de Claude |
| Conectar tus cuentas de chats web | El panel de webllm (la app actual), abierto desde un enlace, como si fuera "Ajustes → Conectores" | Los conectores en Ajustes |

- **En español.** Si la traducción de Open WebUI no convence, se corrige; se comprueba en F1.
- **Lo que no uses no se ve.** Las funciones que no se usan se desactivan en la administración de Open WebUI, y los modelos que no quieres ver se ocultan.
- **Cuando haya duda de diseño, gana lo que hacen ChatGPT y Claude**, no una idea nueva.

---

## 2. El Comité

### Qué es

Sirve para **evaluar ideas**.
- Cada IA recibe un **rol**, confirma que lo ha entendido, recibe **el problema** y da **su veredicto**.
- Luego, **la IA más potente disponible en ese momento** junta todos los veredictos en **un único documento de fusión**.
- Ese documento es lo que Iván usa.

### Participantes

- **Número impar:** 3 o 5 (5 por defecto). Los veredictos cuentan como votos y así nunca hay empate.
- **Quién entra:** los primeros disponibles de la lista del Comité (sección 6). Se prefieren familias de modelos distintas.
- **Roles por defecto para evaluar ideas:**
  1. **Arquitecto técnico:** ¿se puede construir y mantener?
  2. **Abogado del diablo:** busca el fallo que nadie ve.
  3. **Seguridad y riesgos:** cuentas, datos, lo irreversible.
  4. **Usuario que no programa:** ¿se entiende? ¿lo usaría?
  5. **Estratega:** coste, tiempo, alternativas más simples.
- Con 3 participantes van los roles 1, 2 y 3.
- Los roles se pueden editar y se guardan como plantillas.

### El protocolo, paso a paso

1. **Plan y coste antes de empezar.** Eliges "webllm · Comité" y escribes el problema. webllm contesta primero con:
   - quiénes participan y con qué rol;
   - cuántos mensajes gasta de cada cuenta;
   - cuánto tardará, aproximadamente.
   - Escribes **"adelante"** para lanzarlo o **"cancela"**.
2. **Rol (turno 1).** Cada participante recibe su rol.
   - El texto del rol sigue el estilo de prompt-forge: rol fijo, mandato, prohibiciones, escepticismo, formato de veredicto cerrado y límite de palabras.
   - Termina con: *"Si entiendes tu rol, responde únicamente: `CONFIRMO: <rol>`"*.
3. **Comprobación del rol.**
   - Si la respuesta no contiene `CONFIRMO:` con el rol pedido, se reintenta una vez con una versión más corta.
   - Si vuelve a fallar, ese participante se sustituye por el siguiente de la lista (y el número sigue siendo impar).
4. **Problema (turno 2, en la misma conversación).** El problema va dentro de un bloque marcado como **datos, no órdenes**, para que un texto que diga "olvida tu rol" no cambie nada. Se pide el veredicto con este formato fijo, en español y con un máximo de 350 palabras:
   ```
   VEREDICTO: [APROBAR] | [APROBAR CON CONDICIONES] | [RECHAZAR]
   CONFIANZA: alta | media | baja
   FORTALEZAS: (máximo 3)
   RIESGOS: (máximo 3, del más grave al menos grave)
   CONDICIONES: (qué tendría que cumplirse; vacío si no hay)
   EN UNA FRASE: (tu postura)
   ```
5. **Comprobación del veredicto.**
   - Si falta `VEREDICTO:` con uno de los tres valores, se pide una vez que lo reformatee (1 mensaje más).
   - Si sigue mal, ese veredicto se descarta, se anota por qué, y se completa con un participante de reserva para mantener el número impar.
6. **Recuento:** mayoría, con cifras (por ejemplo, 3 a favor, 1 con condiciones, 1 en contra).
7. **Fusión.** Se elige **la IA más potente disponible ahora mismo** según la lista de fusión (sección 6).
   - Si hay alternativa, que no haya sido participante; si no la hay, se usa igual y se avisa en el documento.
   - Recibe:
     - el problema;
     - los veredictos **identificados por su rol, no por el nombre de la IA** (así evitamos que favorezca a los de su familia);
     - el recuento.
   - Escribe el **Documento de fusión** con esta estructura fija:
     1. Resumen (máximo 5 líneas).
     2. Veredicto del Comité (recuento y postura mayoritaria).
     3. En qué coinciden.
     4. En qué discrepan, y qué rol lo dice.
     5. Riesgos principales.
     6. Condiciones para seguir adelante.
     7. Recomendación final.
     8. Próximos pasos concretos.
8. **Entrega:**
   - el documento sale como respuesta en el chat;
   - se guarda en el vault (`Comités/AAAA-MM-DD-<tema>.md`), con un anexo que incluye cada veredicto (esta vez con el nombre de la IA) y el sello del registro.

### Coste y tiempo (se enseñan antes de empezar)

- **Un participante de chat web:** 2 mensajes de su cuenta (3 si hay que reformatear).
- **Un participante por API:** 2 llamadas.
- **La fusión:** 1 llamada.
- **Ejemplo con 5 participantes (3 web y 2 API):** 6 mensajes web, 4 llamadas de API y 1 de fusión.
- **Tiempo:**
  - los chats web van hoy de uno en uno, así que 3 chats × 2 turnos ≈ 3 a 6 minutos;
  - las APIs van en paralelo y tardan segundos;
  - si en F6 se confirma que dos chats pueden ir a la vez, baja.

### Lo que necesita por dentro

- **Conversación en dos turnos en los chats web.** Hoy cada trabajo abre un chat nuevo. Hace falta un modo "seguir en la misma conversación":
  - la extensión devuelve la dirección del chat tras el turno 1;
  - el turno 2 vuelve a esa dirección.
  - El guardián cuenta los 2 mensajes.
- **Cadena de dos pasos por participante** en el motor de cadenas (`flows.py`), con validación, reintento, reserva, recuento y fusión.

---

## 3. Seguir tú una conversación y webs que no se rompen

### Modo observador: sigues tú en la web y webllm lo registra

- **Botón "Continuar en la web"** en cada respuesta de un chat web.
  - Abre **esa conversación exacta** en una pestaña normal de tu Chrome, no en la ventanita de webllm, que se cierra sola cuando termina los trabajos.
  - Esa pestaña queda **"en observación"**: cada mensaje que escribes y cada respuesta de la IA entran en el mismo hilo (registro y vault), marcados como "escrito por Iván directamente".
- **Cómo funciona:** es la misma maquinaria de ahora, pero en pasivo.
  1. La extensión detecta tu envío (Enter o el botón de enviar de la caja, que ya sabe encontrar).
  2. Espera a que termine la respuesta con la misma detección de sus trabajos.
  3. La lee con el botón "copiar" de la web o, si no hay, del texto de la página.
- **Si abres tú un chat sin pasar por webllm:** en las webs del catálogo con permiso, el icono de la extensión tiene **"Registrar esta conversación"**. Solo se registra lo que tú decides: nunca a escondidas.
- **Límites:**
  - solo webs con permiso concedido;
  - nunca campos de contraseña;
  - tus mensajes cuentan en el contador del día, solo para informarte, pero no se frenan: los escribes tú, no la automatización.
- **Después** puedes volver a webllm y seguir desde donde lo dejaste, porque se guarda la dirección de la conversación.

### Auto-reparación: 4 capas, de la más barata a la más humana

1. **Detección genérica** (ya existe). Encuentra la caja de texto, el botón de enviar, el de parar, el de copiar y la respuesta por rasgos comunes: nombres de accesibilidad y etiquetas en varios idiomas, español incluido (lo de Meta). Muchas webs funcionan sin configurar nada.
2. **Ajustes por web** (ya existen, en `sites.js`). Solo cuando la detección genérica no basta.
3. **Reparación con IA.** Cuando un paso falla (no encuentra la caja, la respuesta "nunca termina" o no puede leerla):
   1. la extensión saca una **radiografía** de la página: lista de botones, cajas y candidatos a respuesta, sin contraseñas ni cookies;
   2. una IA por API propone **selectores**: solo datos en JSON, **nunca código**;
   3. webllm los **prueba en la página de verdad sin enviar nada**: ¿encuentra exactamente una caja visible? ¿el candidato a respuesta contiene la última respuesta que ya conocemos?
   4. si pasan, se guardan como **"parche"** de esa web (con fecha y reversible) y el trabajo sigue; si no, se pasa a la capa 4.
4. **"Enséñame".** webllm te pide tres clics: uno en la caja de texto, otro en el botón de enviar y otro en la última respuesta. Con eso aprende esa web, sea la que sea.

**Además:**
- una **comprobación diaria** de cada web conectada, sin enviar nada, para detectar cambios antes de que te afecten;
- los parches que funcionan pueden proponerse como PR para `sites.js`, siempre con tu aprobación.

**Límites:**
- **Ninguna capa se salta una verificación ni un bloqueo anti-bot** (regla dura 2): si una web los pone, webllm para y te avisa.
- Un rediseño muy radical puede necesitar la capa 4. Si una web no se deja manejar de ninguna forma, webllm te dice exactamente qué pasa. No se promete que todas las webs funcionen.
- Los selectores que propone una IA se tratan como datos: se validan (formato, longitud, que el navegador los acepte) y **nunca se ejecutan como código**.

---

## 4. Arquitectura

```
 Móvil (Tailscale, HTTPS privado) ─┐
                                   ▼
 ┌──────────────── Open WebUI Desktop (la cara) ────────────────┐
 │ chat · conversaciones · carpetas/proyectos · selector de       │
 │ modelo · skills (SKILL.md) · conectores MCP · aprobación de    │
 │ herramientas                                                   │
 └───────────────┬──────────────────────────────────┬────────────┘
                 │ una sola conexión (OpenAI)        │ herramientas MCP
                 ▼                                   ▼
 ┌──────────── webllm (el motor, 127.0.0.1:20130) ─┐   GitHub MCP · tu MCP de
 │ /v1/models: todas las fuentes + skills           │   terminal (vía mcpo) ·
 │ /v1/chat/completions: guardián · presupuesto ·   │   (más, después)
 │   fichas · "Automático" · intérprete de          │
 │   herramientas para chats web · Comité · Parar   │
 │ registro auditable ──► copia a Obsidian (vault   │
 │   en carpeta de Drive)                           │
 │ app actual = panel de control (Conectar,         │
 │   "Te espera", estado)                           │
 └──┬──────────────────┬──────────────────┬────────┘
    ▼                  ▼                  ▼
 chats web          APIs gratis        tu PC
 (extensión)        (OmniRoute)        (LM Studio / Ollama)
```

---

## 5. Fases

Cada fase tiene:
- **Puerta:** qué tiene que ser verdad antes de empezar.
- **Qué se hace.**
- **Probado aquí:** en la nube, con salida real.
- **En tu PC:** lo que haces tú.
- **Salida:** la condición medible para darla por cerrada.

### F0 — Estabilizar lo que ya existe

- **Puerta:** ninguna.
- **Qué:**
  - **Meta:** con tu `diagnostico-meta.txt`, arreglar cómo detecta webllm que Meta ha terminado. La sospecha es un botón "Detener" que no desaparece, porque tu Meta está en español. Añadir los nombres en español a `sites.js`.
  - **Nemotron:** ver en el registro por qué falló.
  - **z.ai por API:** cuando llega a su límite de mensajes, que la tarjeta lo diga claro y ofrezca otra IA.
- **Probado aquí:** una página de prueba que imita el caso (un botón "Detener" que no desaparece) y falla con el código actual y pasa con el arreglo; pytest completo.
- **En tu PC:** 3 veces seguidas "Preguntar a todas".
- **Salida:** en las 3, cada chat responde o dice claramente por qué no. Ninguno se queda "Esperando" con la respuesta ya escrita.

### F1 — Prueba de la cara (decide D1 con datos)

- **Puerta:** F0 cerrada.
- **Qué:** conectar Open WebUI a webllm y pasar esta lista de 10 comprobaciones:
  1. Salen los modelos de webllm en el selector.
  2. La respuesta llega por partes (streaming).
  3. Una petición de 6 minutos no se corta (webllm manda señales de vida mientras espera).
  4. Con `ENABLE_FORWARD_USER_INFO_HEADERS` activado, llega a webllm el identificador de la conversación (`X-OpenWebUI-Chat-Id`), que hace falta para la memoria.
  5. Una herramienta MCP inofensiva (la hora) pide aprobación y funciona.
  6. Tu servidor MCP local de terminal funciona a través de `mcpo`.
  7. Se importa tu SKILL.md de prompt-forge y se usa.
  8. Desde el móvil con datos (no wifi), por Tailscale Serve, se chatea.
  9. La interfaz sale en español, y un aviso de webllm (texto de razonamiento) se ve en el bloque plegable, encima de la respuesta.
  10. **Prueba sin guía:** sin instrucciones, haces 6 cosas: empezar una conversación, elegir un modelo, adjuntar un archivo, parar una respuesta, encontrar una conversación antigua y aprobar una herramienta. Se apunta cuáles te salen a la primera.
- **Probado aquí:** las comprobaciones 1 a 5 y 9, con Open WebUI instalado en la nube (pip, Python 3.11) contra el webllm de demostración. Con la salida de cada comprobación y capturas.
- **En tu PC:**
  - instalar Open WebUI Desktop (`winget install OpenWebUI.OpenWebUI` o el instalador);
  - las comprobaciones 6 a 8 y 10;
  - una guía paso a paso con capturas.
- **Salida:**
  - queda Open WebUI si pasan la 1, la 2, la 3 y la 10 (con las 6 cosas a la primera, o con lo que falle arreglado cambiando nombres u ocultando funciones), y de las demás falla como mucho una;
  - si no, se prueba LibreChat con la misma lista; si tampoco, Plan C (la app propia, con el mismo diseño estándar).
  - La decisión, con la lista rellena, se apunta en `docs/ESTADO.md`.

### F2 — webllm como pasarela única

- **Puerta:** F1 decidida.
- **Qué:**
  - `/v1/models` lista cada fuente y cada modelo con su **ficha** (herramientas, contexto, velocidad, coste, para qué sirve) y las skills de webllm ("webllm · Comité", "webllm · Automático"), con nombres claros en español y agrupados (D18).
  - Los avisos de webllm (una web te espera, una cuota agotada) van en el bloque de razonamiento de la respuesta.
  - Las APIs pasan sus herramientas tal cual.
  - Señales de vida en las respuestas largas.
  - Se agrupa por el identificador de conversación.
  - El botón **Parar todo**.
  - Límites de gasto por fuente.
  - Las claves se mueven al almacén de claves de Windows.
- **Probado aquí:**
  - tests de la lista de modelos y de sus fichas;
  - streaming con señales de vida;
  - un aviso de "te espera" llega como texto de razonamiento, no mezclado con la respuesta;
  - Parar cancela un trabajo en curso (extensión falsa);
  - ninguna clave en el disco del proyecto (test que busca claves en el repositorio).
- **En tu PC:** en Open WebUI eliges una IA web, una por API y una de tu PC, y las tres responden; "Parar" corta una respuesta.
- **Salida:** las 3 responden desde Open WebUI y el registro las tiene todas.

### F3 — Todas las IAs con chat web, precargadas

- **Puerta:** F2.
- **Qué:**
  - `catalog.yaml` en el proyecto (en git) con las 27 IAs del catálogo (sección 6). Para cada una: dirección, para qué sirve, familia de modelo, si pide cuenta, si es privada, límite diario propio y fecha de la última comprobación.
  - Qwen, DeepSeek, z.ai y Meta pasan también al catálogo, con sus ajustes de `sites.js`.
  - En el panel de webllm ("Ajustes → Conectores", D18) cada IA es una tarjeta **"Sin conectar"** con **Conectar**. Arriba está **"Conectar varias"**:
    1. vienen todas marcadas, como pediste, y desmarcas las que no quieras;
    2. Chrome pide permiso **una sola vez**, solo para las webs marcadas;
    3. la ventana de webllm las abre de una en una. Si una pide entrar, te la enseña y espera hasta 3 minutos (la contraseña la pones tú: regla dura 3). Si no entras, queda "Sin conectar" y pasa a la siguiente;
    4. cada una recibe la prueba "pong" a través del guardián (1 mensaje).
  - **Resultado por IA:** "Conectada", "No funciona todavía" (con el motivo y el diagnóstico guardado para F5) o "Sin conectar".
  - **Solo las conectadas salen en el selector de Open WebUI** (D18: lo que no usas no se ve).
  - **El guardián vale para todas.** Las de pocos mensajes gratis (Venice, Poe) llevan en el catálogo un límite diario más bajo.
  - **Las no privadas** (Arena publica lo que escribes) no las usan nunca "Automático" ni el Comité. Solo se usan si las eliges tú, y su nombre en el selector lo avisa.
- **Probado aquí:**
  - tests del catálogo:
    - todas las direcciones son https y ninguna se repite;
    - ninguna pasa el bloqueo (`claude.ai`, `chatgpt.com`);
    - cada IA tiene familia y etiquetas;
    - las no privadas quedan fuera de "Automático" y del Comité;
  - Chromium con la extensión de verdad y 3 webs de prueba del catálogo:
    - una conecta a la primera;
    - otra pide entrar y conecta cuando "entras";
    - otra no tiene caja y queda "No funciona todavía" con su diagnóstico;
    - una sola petición de permiso para las tres (el aviso de Chrome se simula, como en 7b);
  - capturas del panel en claro y oscuro.
  - Desde la nube no se abre ninguna web real, así que cuántas funcionan solo se sabe en tu PC.
- **En tu PC:** "Conectar varias" con las que quieras.
- **Salida:**
  - la tabla del catálogo rellena en `docs/ESTADO.md`, con cada IA como "conectada", "no funciona todavía y por qué" o "no la quiero";
  - cada IA conectada responde desde Open WebUI.

### F4 — Memoria en Obsidian (un solo escritor)

- **Puerta:** F2.
- **Qué:**
  - Carpeta del vault configurable (dentro de tu carpeta de Google Drive).
  - Un archivo Markdown por conversación, en su carpeta de proyecto.
  - Se escribe mientras ocurre.
  - Documentos del Comité en `Comités/`.
  - Un índice.
  - Solo escribe: **nunca lee** del vault.
- **Probado aquí:** tests que comparan el archivo con el registro, escritura a mitad de una conversación y caracteres raros en los títulos. Uno comprueba que no hay ni una lectura del vault.
- **En tu PC:** abres Obsidian y ves la conversación de hace un minuto; desde el móvil, en Drive, ves el mismo archivo.
- **Salida:** 10 conversaciones seguidas, las 10 en el vault, idénticas al registro.

### F5 — Webs que se reparan solas y modo observador

- **Puerta:** F2, F3 y F4.
- **Qué:** lo de la sección 3:
  - detección genérica ampliada (etiquetas en varios idiomas);
  - radiografía de la página;
  - reparación con IA con prueba en vivo y sin enviar nada;
  - parches por web, con fecha y reversibles;
  - "Enséñame" con 3 clics;
  - comprobación diaria;
  - "Continuar en la web" y "Registrar esta conversación" (modo observador).
  - Con cambio de versión de la extensión.
- **Probado aquí:** Chromium con la extensión de verdad y varias versiones de la web de prueba:
  - clases y etiquetas cambiadas → la capa 1 o la 3 lo resuelven;
  - una propuesta de IA con código dentro → rechazada;
  - "Enséñame" con clics simulados;
  - el observador registra 2 turnos escritos "a mano" en la página.
  - Cada caso falla con el código anterior y pasa con el nuevo.
- **En tu PC:**
  - una conversación que empieza en webllm y sigues en la web de Kimi: aparece entera en el vault;
  - las webs del catálogo que en F3 quedaron "No funciona todavía", probadas otra vez.
- **Salida:** la conversación completa en el vault; el recuento de webs del catálogo que ahora funcionan gracias a la capa 1, a la 3 o a la 4 (apuntado en `docs/ESTADO.md`), y el registro de un arreglo automático real (o, si ninguna web cambia durante la prueba, del simulado).

### F6 — El Comité

- **Puerta:** F2, F3, F4 y F5.
- **Qué:** todo lo de la sección 2:
  - modo "seguir en la misma conversación" en la extensión (con cambio de versión);
  - plantillas de rol;
  - validaciones, reintento y reserva;
  - recuento impar;
  - fusión por lista;
  - plan y coste con "adelante";
  - progreso en el bloque plegable de razonamiento (D18);
  - documento en el chat y en el vault;
  - dos chats web a la vez, desactivado por defecto: hoy van de uno en uno y `CLAUDE.md` pide una prueba en vivo antes de cambiarlo.
- **Probado aquí:**
  - tests con la extensión falsa y la API falsa: rol bien confirmado; rol mal confirmado → reintento → reserva; veredicto mal formateado; empate imposible; inyección en el problema ("olvida tu rol") sin efecto; la fusión no recibe nombres de IA;
  - Chromium con la extensión de verdad: dos turnos en el mismo chat de la web de prueba.
- **En tu PC:** un Comité real con 5 participantes sobre una idea tuya. Después, el mismo Comité con dos chats a la vez: si sale bien 3 veces seguidas, se deja activado.
- **Salida:** documento de fusión completo con sus 8 apartados, recuento impar, anexo con los 5 veredictos y candado verde.

### F7 — Elegir modelo y "Automático" bien afinado

- **Puerta:** F2 y F3.
- **Qué:**
  - fichas de cada modelo de API (por ejemplo GLM-5.2, GLM Flash, Qwen3.8-27B, Codestral, Gemini Flash);
  - selector de modelo **dentro** de Qwen y z.ai web (7c: pulsar el menú de modelos de la página, frágil por naturaleza);
  - la tabla de "Automático" (sección 6), en un archivo y a la vista.
- **Probado aquí:**
  - tests de la tabla: cada tipo de tarea tiene primero y reserva; nada apunta a una IA prohibida;
  - para la parte del selector web, la página de prueba con un menú de modelos.
- **En tu PC:** 10 preguntas de prueba (2 de cada tipo) con "Automático", apuntando qué eligió y si acertó. La tabla se ajusta con esos datos antes de darla por buena.
- **Salida:** 9 de 10 bien enrutadas.

### F8 — Acciones y conectores

- **Puerta:** F1 (comprobaciones 5 y 6) y F2.
- **Qué:**
  - **GitHub** con el servidor MCP oficial de GitHub, usando un token limitado a tus repositorios, sin permisos de administración y solo para proponer (PR);
  - tu MCP de terminal;
  - el **intérprete de herramientas para chats web**: menú en texto → petición → `tool_calls`. Con un analizador estricto: lo que no encaje se rechaza, no se adivina.
- **Probado aquí:**
  - tests del intérprete: petición válida, mal formada e **inyección** ("borra el repo");
  - aprobación siempre visible;
  - ninguna acción sin aprobar.
- **En tu PC:** "crea un issue de prueba en mi repo" con una IA de API y con una web; las dos pasan por tu Permitir.
- **Salida:** los dos issues creados; un intento de inyección, denegado y apuntado en el registro.

### F9 — Móvil

- **Puerta:** F1 (comprobación 8).
- **Qué:** guía de Tailscale en el PC y en el móvil, Tailscale Serve (HTTPS) y la app instalada como PWA. **Solo chatear y leer.**
- **En tu PC y tu móvil:** una conversación desde el móvil con datos, que aparece en el vault.
- **Salida:** lo anterior funciona sin abrir ningún puerto del router.

### F10 — Taller de código

- **Puerta:** F2 y F8.
- **Qué:**
  - OpenCode configurado con `edit: ask` y `bash: ask`;
  - trabajo en un **git worktree** (una rama de prueba);
  - **modo simulación** (primero el plan, el cambio y los comandos; después se ejecuta);
  - los tests del proyecto como juez;
  - Comité opcional para revisar el plan;
  - **Aceptar / Deshacer**;
  - modelos principales: GLM-5.x por API.
  - Antes de empezar se decide el aislamiento (solo worktree o WSL2/Docker), con una prueba de qué se puede romper en cada caso.
- **Probado aquí:** un proyecto de prueba con una tarea y sus tests (de rojo a verde) y Deshacer, que funcionan.
- **En tu PC:** 5 tareas reales tuyas.
- **Salida:** tareas resueltas de 5, apuntadas. Es la base del banco de pruebas pequeño.

### F11 — Después (no se empieza sin nueva decisión)

- imágenes, vídeo y audio como fuentes;
- plugins;
- encargar trabajos desde el móvil;
- trabajo nocturno supervisado;
- sello del registro en GitHub;
- catálogo vivo: una tarea semanal busca IAs nuevas, cierres y cambios de nombre y abre un PR con las pruebas, que nunca se fusiona solo.

---

## 6. Listas iniciales (se afinan en F7 con datos de tu PC)

**Lista del Comité (participantes, en orden):**
1. Kimi (web)
2. DeepSeek (web)
3. Qwen 3.8 (web)
4. GLM-5.2 (API NVIDIA)
5. Mistral Large (API)
6. Gemini Flash (API)
7. Duck.ai · Claude Haiku (web)
8. z.ai chat (web)
9. Duck.ai o Copilot · GPT (web): el modelo GPT que ofrezcan, comprobado en F7 (D19)

**Lista de fusión ("la más potente disponible"):**
1. GLM-5.2 (API)
2. Kimi K3 (web)
3. DeepSeek (web)
4. Qwen 3.8 (web)
5. Mistral Large (API)
6. Gemini Flash (API)

"Disponible" = lista, sin pausa, por debajo de su límite de gasto y respondiendo en su última comprobación.

**Tabla de "Automático" (primero → reserva):**

| Tipo | Primero | Reservas |
|---|---|---|
| Código | GLM-5.2 (API) | Qwen3.8-27B (Groq) → Codestral (API) → Kimi (web) |
| Pregunta rápida | Qwen3.8-27B (Groq) | GLM Flash (API) → Gemini Flash (API) |
| Documento largo | Gemini Flash (API, 1M) | Kimi (web) |
| Investigar con fuentes | Felo (web) | Ask Brave (web) → Perplexity (web) → Kimi (web) |
| Evaluar una idea | **webllm · Comité** | — |

Estas listas se basan en pruebas públicas de septiembre de 2026 y en la tabla de APIs gratis de PLAN-v4. Son un punto de partida: **F7 las mide con tus cuentas antes de darlas por buenas.**

### Catálogo: todas las IAs con chat web (se precargan en F3)

Comprobado con el buscador entre el 24 y el 25 de septiembre de 2026. Desde la nube no se pueden abrir estas webs: si cada una funciona con webllm solo se sabe en tu PC, en F3.

**Las que ya usas (4):**

| IA | Dirección |
|---|---|
| Qwen (Alibaba) | `https://chat.qwen.ai` |
| DeepSeek | `https://chat.deepseek.com` |
| z.ai (Zhipu, GLM) | `https://chat.z.ai` |
| Meta AI | `https://www.meta.ai` |

**Grupo 1: chat sencillo y funciona desde España (17).**

| IA | Dirección | Para qué | Nota |
|---|---|---|---|
| Kimi (Moonshot) | `https://www.kimi.com` | documentos largos, investigar, código | |
| Le Chat (Mistral) | `https://chat.mistral.ai` | general, código, rápida | su conector de GitHub no se activa (sección 9) |
| HuggingChat (Hugging Face) | `https://huggingface.co/chat` | general, modelos abiertos | sin cuenta |
| LongCat (Meituan) | `https://longcat.chat` | general, instrucciones | |
| Grok (xAI) | `https://grok.com` | general, actualidad | |
| Gemini (Google) | `https://gemini.google.com` | general, documentos largos | |
| Dola (ByteDance) | `https://www.dola.com/chat/` | general | |
| Felo (Japón) | `https://felo.ai` | investigar, con fuentes | |
| Ask Brave | `https://search.brave.com` (modo chat) | investigar, con fuentes | sin cuenta; la dirección exacta del modo chat se ve al conectar |
| Ai2 Playground | `https://playground.allenai.org` | general, modelos totalmente abiertos | |
| Pi (Inflection) | `https://pi.ai` | conversación | apenas la mantienen; puede cerrar |
| Inception Chat (Mercury) | `https://chat.inceptionlabs.ai` | muy rápida | menos lista |
| Duck.ai (DuckDuckGo) | `https://duck.ai` | Claude Haiku 4.5, GPT (D19), Mistral Small, gpt-oss, Gemma | sin cuenta |
| Arena, chat directo | `https://arena.ai/direct` | elegir un modelo concreto, Claude incluido | **no privada:** lo que escribes puede publicarse |
| Perplexity | `https://www.perplexity.ai` | investigar, con fuentes | gratis con su modelo propio |
| Nous Chat | `https://chat.nousresearch.com` | Hermes 4 | |
| Copilot (Microsoft) | `https://copilot.microsoft.com` | general, actualidad; GPT por dentro (D19) | sin cuenta; con cuenta de Microsoft, más mensajes |

**Grupo 2: se precargan marcadas "puede fallar" (6).**

| IA | Dirección | Por qué puede fallar |
|---|---|---|
| Venice | `https://venice.ai` | unos 10 mensajes gratis al día |
| Google AI Studio | `https://aistudio.google.com` | página complicada; Google puede usar lo que escribas |
| MiMo Studio (Xiaomi) | `https://aistudio.xiaomimimo.com` | pide cuenta Xiaomi; es un escaparate de modelos, no un asistente |
| Poe | `https://poe.com` | unos 300 puntos al día (15 a 30 mensajes cortos) |
| LingGuang (Ant Group) | `https://www.lingguang.com/chat` | puede pedir cuenta china |
| You.com | `https://you.com` | la empresa se centra ahora en sus APIs; el chat gratis puede desaparecer |

**Total: 27** (4 + 17 + 6).

**No se precargan, y por qué:**
- **Agentes que hacen tareas, no chats:** MiniMax Agent, Manus y Genspark. Actúan por su cuenta en la web; no encajan en pregunta-respuesta.
- **OpenRouter Chat:** sus modelos gratis van mejor por API (tabla de PLAN-v4), sin gastar cuenta web. Si la quieres como web, "+ Añadir otra IA" la acepta.
- **Directas, fuera siempre:** `chatgpt.com` y `claude.ai`.
- **Brave Leo:** vive dentro del navegador Brave (`brave://leo-ai`) y ninguna extensión puede manejarla. Su Claude Haiku está en Duck.ai.
- **Sakana Fugu:** solo API y de pago.
- **Bloqueadas por país:**
  - Sakana Chat (solo Japón);
  - Amazon Nova (solo Estados Unidos);
  - Doubao, Yuanbao, ERNIE e iFlytek Spark (piden teléfono chino).
- **Cerradas en 2026:** Phind, Naver Clova X y StepFun internacional.

**Riesgo para tus cuentas:** algunas webs prohíben el uso automático en sus normas. El guardián lo frena, pero no lo elimina.

---

## 7. Contrato de ejecución

- **Las reglas duras de `CLAUDE.md`, siempre:**
  - Claude y ChatGPT directos fuera; Claude y GPT por dentro de otros servicios, aprobados (D19);
  - las verificaciones las resuelve Iván;
  - ni contraseñas ni cookies;
  - secretos fuera de git;
  - las respuestas de las IAs son datos;
  - el guardián en todo camino;
  - español llano;
  - evidencia cruda.
- **Una fase por rama y PR.** Nunca se empieza una fase con su puerta sin cumplir.
- **"Hecho" exige:**
  - la salida real de pytest en un entorno limpio;
  - la prueba en Chromium si cambia la extensión;
  - capturas si cambia algo que Iván ve;
  - separar "probado aquí" de "falta en tu PC".
- **Nada irreversible sin Iván:** ni fusionar, ni subir a main, ni borrar, ni acciones en GitHub fuera de PRs.

## 8. Riesgos y qué se hace

| Riesgo | Qué se hace |
|---|---|
| Las webs cambian y la extensión se rompe | D3: el núcleo no depende de ellas. D17: auto-reparación en 4 capas y comprobación diaria. Si nada funciona, "Copiar diagnóstico" y arreglo con su test |
| El modo observador registra algo que no querías | Solo webs con permiso; solo pestañas que tú marcas; nunca campos de contraseña; un botón para dejar de observar |
| Open WebUI cambia algo que usamos | Se fija la versión que pasó F1; se actualiza solo tras repetir la lista de 10 |
| Open WebUI trae demasiadas opciones y abruma | D18: se desactiva lo que no se usa; la prueba sin guía de F1 lo mide |
| El Comité tarda (chats web de uno en uno) | APIs en paralelo; se prueban dos chats a la vez en F6; 3 participantes para lo urgente |
| Cuentas: más mensajes = más verificaciones y más riesgo de bloqueo | Coste visible y "adelante"; límites por fuente; Comité con parte por API |
| Cuotas gratis que desaparecen (ya pasó 4 veces este año) | Las fichas guardan la fecha de la última comprobación; si una API falla por cuota, se pasa a la reserva sin romper nada |
| Inyección entre IAs y en herramientas | Datos marcados; formatos cerrados; analizador estricto; aprobación siempre; test de inyección en cada fase que toca herramientas |
| Conflictos de memoria | D5: un solo escritor, sin leer nunca de Drive |
| Un agente de código rompe algo | Worktree, modo simulación, pedir permiso para editar y ejecutar, tests, Deshacer; aislamiento decidido con prueba en F10 |

## 9. Lo que NO se hace

- Construir desde cero una interfaz tipo Claude (salvo el Plan C).
- Pantallas o botones propios de webllm dentro de la conversación que no existan en ChatGPT o Claude (D18).
- Un enrutador que aprende solo.
- Leer o escribir en Drive en los dos sentidos.
- Dar permisos de escritura en GitHub a webs de terceros (el conector de Mistral).
- Imágenes, vídeo, audio o plugins antes de F11.

## 10. Preguntas abiertas (no frenan F0 ni F1)

1. ¿Las primeras skills son el Comité y prompt-forge? (D15)
2. ¿Los 5 roles por defecto del Comité te valen, o quieres otros?
3. ¿Dónde está (o estará) tu vault de Obsidian dentro de Google Drive?

## Fuentes

- **Open WebUI:**
  - escritorio: https://github.com/open-webui/desktop
  - aprobaciones (v0.11.1): https://openwebui.com/blog/v0-11-1-the-model-learns-to-stop-and-ask
  - MCP: https://docs.openwebui.com/features/extensibility/mcp/
  - mcpo: https://github.com/open-webui/mcpo
  - skills: https://docs.openwebui.com/features/workspace/skills/
  - Tailscale: https://docs.openwebui.com/ecosystem/computer/phone-and-remote/tailscale/
  - identificador de conversación: https://github.com/open-webui/open-webui/pull/15813
- **LibreChat:**
  - instalación: https://www.librechat.ai/docs/local
  - sin instalador de escritorio: https://github.com/LibreChat-AI/librechat.ai/pull/758
  - skills: https://www.librechat.ai/docs/features/skills
  - aprobaciones: https://github.com/danny-avila/LibreChat/pull/13942
- **OpenCode, permisos:** https://opencode.ai/docs/permissions/
- **Catálogo de chats web:**
  - las fuentes de cada IA, en la tabla del catálogo de PLAN-v4 y en la conversación con Iván del 24 y 25 de septiembre de 2026;
  - Copilot gratis y sin cuenta: https://support.microsoft.com/en-us/microsoft-365-copilot/what-s-the-difference-between-microsoft-copilot-free-and-copilot-in-microsoft-365 y https://medhacloud.com/blog/microsoft-copilot-free
  - You.com, ahora centrada en APIs: https://en.wikipedia.org/wiki/You.com y https://aiproductivity.ai/pricing/you/
- **Crítica de las 5 IAs:** conversación con Iván del 25-sep-2026. Su criba está resumida en las decisiones D3, D5, D6, D7, D8, D9, D10, D11, D13 y D14.
