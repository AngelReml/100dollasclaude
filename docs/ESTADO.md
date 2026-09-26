# ESTADO — webllm-agent (26-sep-2026)

> 🚧 **EN CONSTRUCCIÓN.**
> - La pieza principal ya está hecha: **tu Chrome escribe en los chats de IA como si fueran una API**, y aider programa con ellos.
> - Qué está probado:
>   - el funcionamiento completo, con una extensión de prueba;
>   - la parte que escribe y lee la página, en z.ai real;
>   - z.ai, groq y Nemotron por API.
> - Falta probarlo con la extensión de verdad en tu Chrome (paso 1).

## Cómo funciona (en corto)

```
tú / aider / webllm ask ──► puente (127.0.0.1:20130) ──► extensión en TU Chrome ──► chat de Qwen / DeepSeek / z.ai / Meta
                                                                                  (escribe, espera y copia la respuesta)
```

- **Tu Chrome:** usa tu perfil de siempre y tus sesiones abiertas. No hay que copiar cookies ni claves.
- **Ventanas:** cada chat se abre en su propia ventana de Chrome, con una conversación nueva en cada envío.
- **Captura de la respuesta:** se usa el botón "copiar" de la propia web, así llega el texto exacto, con código y todo.

## Los mandamientos (todo con doble clic en la carpeta del proyecto)

1. **`1 - INSTALAR (solo una vez)`.** Abre Chrome en la página de extensiones y te dice los 3 clics que hay que hacer.
2. **`2 - PROBAR TODO`.** Hace una prueba real de cada cosa y pone **BIEN** o **MAL**.
   - Si algo sale MAL, te dice qué hacer en la misma línea.
   - Tarda unos minutos y verás ventanas de Chrome escribiendo solas.
3. **`PREGUNTAR`.** Escribe tu pregunta, deja una línea vacía y pulsa Enter.
   - Luego pulsa Enter para mandarla a todas, o escribe el nombre de una IA.
4. **`PROGRAMAR`.**
   - Arrastra la carpeta de tu proyecto a la ventana y elige la IA con un número.
   - Pide los cambios en lenguaje normal.
   - Deshacer: `/undo`. Salir: `/exit`.
   - Cada cambio queda guardado con git. Si pregunta algo, responde `y` (sí) o `n` (no).
   - Cada cambio gasta 2 mensajes del chat.
5. **`REANUDAR`.** Quita las pausas cuando ya has entrado con una cuenta nueva o has resuelto una verificación.
6. **Deja a la vista la ventanita de webllm** (pequeña, abajo a la derecha). Puede estar en una esquina, pero no minimizada ni tapada del todo.
   - Si queda tapada, las webs no escriben la respuesta. La app te lo dice en la tarjeta del chat ("Te espera") y la respuesta sigue sola cuando se vuelve a ver.
7. **Si un chat te echa, te banea o pide verificación,** sale un aviso de Windows que te dice qué hacer.
   - **Sin sesión:** entra y repite.
   - **Verificación:** la resuelves tú en esa ventana y el envío sigue solo.
   - **Baneo o límite:** entra con otra cuenta y haz doble clic en `REANUDAR`.
8. **Protección automática:** 1 mensaje a la vez por chat, 20 s entre mensajes, 150 al día. Nunca se salta una verificación.
9. **Todo queda apuntado** en `data/runs/`. Los comandos avanzados están en `herramientas\`.

## Novedades del 26-sep-2026 (PLAN-v5, fase F6: webs que se reparan solas, y seguir tú en la web)

- **Cuando una web cambia de diseño, webllm lo arregla solo, sin enviar nada para probar:**
  1. primero busca la caja y los botones en más idiomas y con las cajas modernas;
  2. si no los encuentra, una IA por API (z.ai, o la que elijas) señala dónde están con números de una lista de la página, **sin ver tu conversación**;
  3. webllm lo prueba en la página, y si vale lo guarda en la Ficha de ese chat, con fecha y **«Deshacer»**;
  4. si nada de eso basta, **«Enséñame esta web»**: tres clics tuyos (caja, enviar, respuesta).
- **Una pregunta nunca se envía dos veces:** si faltaba la caja, no se había enviado; si faltaba la respuesta, se vuelve a leer.
- **Comprobación diaria** (Conectores → «Webs que cambian»): webllm abre cada chat conectado y mira que siga bien, sin enviar nada. También con «Comprobar ahora».
- **«Parar» pulsa también el botón de parar de la web.**
- **«Continuar en la web»**, bajo cada respuesta de un chat web (en Open WebUI y en la app):
  - abre esa conversación en tu Chrome;
  - lo que escribas allí a mano queda en la misma conversación (historial y vault), marcado como tuyo;
  - al volver a Open WebUI, tu siguiente pregunta lo lleva consigo, y la respuesta te lo dice.
- **«Registrar esta conversación»:** en el icono de la extensión, para un chat que abriste tú. Solo si tú lo pulsas, y con «Dejar de registrar».
- **Probado aquí:** la extensión de verdad en Chromium, **16 de 16**; con la extensión anterior, cada caso falla. **El Open WebUI de verdad, 5 de 5.** Y 32 pruebas de código nuevas.
- **Falta tu PC:** seguir en la web de Kimi una conversación empezada en webllm, y volver a probar las webs del catálogo que «No funcionan todavía». Guía en `docs/F6-reparacion.md`.
- **Qué hacer:**
  1. `ACTUALIZAR`;
  2. ↻ en «webllm puente» en `chrome://extensions` (**versión 0.8.0**);
  3. `herramientas\poner-en-openwebui.cmd` otra vez (trae el botón «Continuar en la web»).

## Novedades del 26-sep-2026 (PLAN-v5, fase F5: tu memoria en Obsidian)

- **En la app, en el Inicio, la tarjeta «Memoria en Obsidian».** Escribes la carpeta de tu vault (donde quieras: en tu PC o en Drive) y pulsas «Encender la memoria».
- **Lo que escribe, siempre dentro de su carpeta `webllm`:**
  - una nota por conversación, en la carpeta de su proyecto (la carpeta de Open WebUI donde la tengas);
  - y aparte, como pediste, **cada respuesta de cada IA en su propio archivo, con la fecha y la hora como título** (`Respuestas\Qwen\2026-09-26 14.05.12 Qwen - ¿Qué es la inflación.md`), idéntica al registro.
- **Se escribe mientras ocurre** y **nunca lee nada del vault.** Si Drive está cerrado, la pregunta sigue funcionando y la tarjeta te lo dice; al volver, escribe lo que faltaba.
- **«Copiar también lo de antes»** pasa tu historial al vault. **«Reescribir todo»** lo rehace desde el registro.
- Lo que un complemento de Obsidian podría ejecutar solo (Templater, Dataview) queda desactivado en la copia.
- **Probado aquí:** 14 pruebas de la memoria (incluidas 10 conversaciones seguidas idénticas al registro y ni una lectura del vault) y **6 de 6 en el Open WebUI de verdad**.
- **Falta tu PC:** abrir Obsidian y ver la conversación de hace un minuto (y en el móvil, si el vault está en Drive). Guía en `docs/F5-memoria.md`.
- **Qué hacer:**
  1. `ACTUALIZAR`;
  2. `herramientas\poner-en-openwebui.cmd` otra vez;
  3. en la app, tarjeta «Memoria en Obsidian» → tu carpeta → «Encender la memoria».

## Novedades del 26-sep-2026 (PLAN-v5, fase F4: todo lo que sabe hacer cada chat, bajo tu control)

- **Cada chat tiene su «Ficha»** (en la app, en su tarjeta):
  - «Descubrir» abre sus menús, los lee y los cierra, sin pulsar opciones ni enviar nada;
  - enseña sus modelos (el más potente primero, o «Empate: dime cuál»), sus modos, su menú «+» y qué archivos acepta;
  - si falta algo, **«Enséñame dónde está»**: un clic tuyo en la web.
- **En Open WebUI:**
  - salen los modelos de cada chat («Qwen · … — el más potente»);
  - hay cinco interruptores en el «+»: pensar, buscar, investigación profunda, modo constructor e imagen;
  - los archivos que adjuntas se suben a la web con su propio botón.
- **Antes de enviar, todo se comprueba en la página.** Si el modelo, un modo o un archivo no quedan puestos, **no se envía nada** y te dice qué pasó.
- **Cada respuesta dice lo que se usó de verdad** (modelo, modos, a quién se subieron tus archivos). Lo que genera el chat se guarda en `data\descargas\`.
- **Nunca** pulsa publicar, compartir, borrar, regenerar, desplegar ni pagar (en 8 idiomas).
- **Probado aquí con la extensión de verdad:**
  - 14 de 14 en la web de prueba, incluido un archivo de 20 MB con la misma huella;
  - 6 de 6 en Open WebUI con la extensión de verdad detrás.
- **Falta tu PC:** que las fichas de Qwen, z.ai, Kimi y DeepSeek coincidan con lo que ves. Guía en `docs/F4-capacidades.md`.
- **Qué hacer:**
  1. `ACTUALIZAR`;
  2. ↻ en «webllm puente» (debe poner **0.7.0**);
  3. Ficha → Descubrir en tus chats;
  4. `herramientas\poner-en-openwebui.cmd` otra vez.

## Novedades del 26-sep-2026 (PLAN-v5, fase F3: todos los chats web, precargados)

- **En la app hay una pantalla nueva, «Conectores»,** con las 27 IAs de chat web de la lista del plan. Las que no están conectadas no salen en Open WebUI ni en Preguntar.
- **«Conectar varias»:**
  - vienen todas marcadas y desmarcas las que no quieras;
  - Chrome pide permiso una sola vez;
  - se abren de una en una;
  - si una pide entrar, te la pone delante y te espera 3 minutos. Entras tú: webllm no escribe contraseñas;
  - cada una recibe un «pong» por el guardián;
  - al final ves el resultado de cada una con el motivo.
- **Probado aquí con la extensión de verdad** (13 de 13): un solo permiso; conecta; espera a que entres (también si te manda a otra dirección para entrar, como Google); dice adónde lleva una web mudada; guarda el diagnóstico de la que no tiene caja.
- **Falta lo importante, y solo puede ser en tu PC:** cuántas de las 27 funcionan de verdad. Guía en `docs/F3-catalogo.md`. Al terminar, pulsa **Copiar el resumen** en Conectores y pégamelo: con eso relleno esta tabla.
- **Qué hacer:**
  1. `ACTUALIZAR`;
  2. ↻ en «webllm puente» (debe poner **0.6.0**);
  3. app → **Conectores** → **Conectar varias**.

**Catálogo en tu PC** (se rellena con tu resumen):

| IA | En tu PC |
|---|---|
| Qwen, DeepSeek, z.ai, Meta AI | las de siempre |
| Kimi, Le Chat, HuggingChat, LongCat, Grok, Gemini, Dola, Felo, Ask Brave, Ai2 Playground, Pi, Inception Chat, Duck.ai, Arena (no privada), Perplexity, Nous Chat, Copilot | pendiente |
| Venice, Google AI Studio (no privada), MiMo Studio, Poe, LingGuang, You.com (grupo «puede fallar») | pendiente |

## Novedades del 26-sep-2026 (PLAN-v5, fase F2: webllm, la única conexión de Open WebUI)

- **La salida de F2 se cumple en la nube.** Desde Open WebUI responden una IA web, una por API y una de tu PC, y el registro de webllm tiene las tres. Detalle y tu guía: `docs/F2-pasarela.md`.
- **Parar:**
  - el cuadrado «Detener» de Open WebUI corta la espera al momento;
  - **«Parar todo»** en el Inicio de la app para todo lo que esté en marcha, venga de Open WebUI o de la app;
  - una pregunta parada que aún esperaba turno no se envía nunca.
  - Ojo: webllm no pulsa el botón de parar de cada web (eso llega en F4). Si la pregunta ya se envió, la web puede terminar su respuesta en la ventanita, pero no se usa.
- **Herramientas:** las IAs por API pueden usar herramientas de Open WebUI (probado con una que da la hora). Open WebUI **te pide permiso antes** de cada uso. Tras «Permitir» queda una ruedita «Preparando…» girando: es un fallo de Open WebUI, la respuesta está completa.
- **Nada se cambia solo:** si una IA falla, se dice y no se pregunta a otra. Cada respuesta por API o de tu PC dice qué modelo respondió.
- **Tope diario por API:** como mucho 300 preguntas al día a cada una (`data/config.yaml`, `api_daily_cap`). Los chats siguen con 150. Las de tu PC, sin tope. La app y Open WebUI enseñan los mismos números.
- **Claves:** una prueba revisa que ninguna clave vaya a GitHub. No las he pasado al almacén de claves de Windows: webllm no tiene claves propias que mover (explicado en `docs/F2-pasarela.md`).
- **Qué hacer:**
  1. `ACTUALIZAR`;
  2. ↻ en «webllm puente» en `chrome://extensions` (debe poner **0.5.2**);
  3. de nuevo `herramientas\poner-en-openwebui.cmd`;
  4. las pruebas de la guía.

## Novedades del 26-sep-2026 (PLAN-v5, fase F1: Open WebUI como cara)

- **Todo lo que se puede probar en la nube, bien.** Open WebUI 0.11.4 muestra tus IAs de webllm en su selector y les pregunta a través de webllm, con el guardián de tus cuentas y el registro de siempre.
  - Las respuestas largas (6 minutos) no se cortan.
  - Los archivos llegan enteros.
  - El interruptor "Pensar más" llega a webllm.
  - "Te espera" se ve sin abrir nada.
- **Los resultados y tu guía paso a paso están en `docs/F1-cara.md`.** Resumen de la guía:
  1. instala Open WebUI Desktop;
  2. activa "Enable API Keys" en Administración → Ajustes → General;
  3. crea una clave;
  4. doble clic en `herramientas\poner-en-openwebui.cmd`.
- **Aún no:**
  - los archivos y los modos llegan a webllm, pero todavía no se pasan a las webs (fase F4). La respuesta lo dice a la vista;
  - la prueba de una herramienta con permiso (comprobación 5) llega con F2 (hecha: ver arriba).

## Novedades del 26-sep-2026 (PLAN-v5, fase F0)

**Una vez, después de ACTUALIZAR:** la extensión cambia a la versión **0.5.1**. Abre `chrome://extensions` y pulsa la flecha ↻ en "webllm puente".

1. **Meta respondía y la app seguía "Esperando".**
   - **Lo que pasaba:** webllm da una respuesta por terminada cuando desaparece el botón de "parar" del chat. Si la web deja en pantalla algo que parece ese botón, webllm espera para siempre.
   - **Arreglado de cuatro formas, porque no sé cuál de ellas le pasa a tu Meta:**
     - un "Detener" que se queda después de responder: si ya está el botón "Copiar" y nada cambia en 12 segundos, la respuesta está terminada;
     - un "Detener" escondido fuera de la pantalla: ya no cuenta;
     - un botón que solo tiene la palabra "stop" en su nombre interno: ya no cuenta;
     - un botón "Detener" que ya estaba antes de preguntar: no dice nada de la respuesta, así que no cuenta.
   - **Si aun así se queda esperando,** webllm apunta en `data/logs/bridge.log` cómo era la página en ese momento. Con eso se arregla sin adivinar.
   - **Probado aquí:** una web de prueba con cada uno de los 4 casos, con la extensión de verdad en Chromium.
     - Con la extensión anterior fallan los 4.
     - Con la nueva llegan las 4 respuestas (entre 8 y 18 segundos).
2. **"Nemotron no pudo responder", y los límites de z.ai por API.**
   - **Lo que pasaba:** cuando un servicio por API decía "límite" con su propio código (OpenRouter pone un número como 429, z.ai los suyos como 1302), la app no lo entendía y ponía el mensaje general "no pudo responder".
   - **Ahora la tarjeta dice qué pasó:**
     - "ha llegado a su límite por ahora", "se ha quedado sin crédito gratis" o "está saturada";
     - **lo que respondió el servicio**, palabra por palabra;
     - y un botón **"Preguntar a …"** con otra IA que esté lista. Solo pasa si lo pulsas tú.
   - **Qué no sé:** la causa exacta de tu fallo de Nemotron. La próxima vez la tarjeta enseñará lo que dijo el servicio.
   - Capturas: `docs/capturas/f0/` (la 19 y la 20 son este caso).

**Para ti, cómo probarlo (es la prueba de F0):**
1. `ACTUALIZAR`, y ↻ en "webllm puente" en `chrome://extensions`.
2. Abre webllm y haz **3 veces seguidas "Preguntar a todas"** con una pregunta cualquiera.
3. **Lo que debes ver:** cada chat responde, o su tarjeta dice claramente por qué no. Ninguno se queda "Esperando" con la respuesta ya escrita en su web.
4. Si Meta (u otro) se queda esperando, mándame `data/logs/bridge.log`.

## Novedades del 25-sep-2026, noche

**Una vez, después de ACTUALIZAR:** la extensión cambia a la versión **0.5.0**. Abre `chrome://extensions` y pulsa la flecha ↻ en "webllm puente".

1. **Arreglado: las respuestas que se perdían tras resolver una verificación.**
   - **Lo que pasaba:**
     - el tiempo que tardabas en resolver la verificación contaba como si el chat tardara en contestar;
     - la app dejaba de esperar a los 7 minutos, antes que el resto de webllm;
     - mientras resolvías la verificación, la ventanita cambiaba de pestaña cada 2 segundos;
     - si la ventanita quedaba tapada (por la propia app, por ejemplo), la web dejaba de escribir y el reloj seguía corriendo.
   - **Ahora:**
     - el tiempo que un chat te espera no cuenta;
     - la pestaña que te necesita se queda delante;
     - cada verificación te espera 5 minutos;
     - la respuesta llega sola al terminar, sin volver a preguntar.
   - **En la app,** la tarjeta de ese chat dice **"Te espera"** y qué hacer:
     - resolver la verificación;
     - responder la ventana emergente;
     - o dejar la ventanita a la vista.
   - **Los demás chats** dicen **"En cola"** hasta que les toca, en vez de un reloj que corría sin haber enviado nada. Se preguntan de uno en uno, como hasta ahora.
2. **"Añadir otra IA".** En Inicio (sección *Tus IAs*) y al final del desplegable de IAs.
   - Pegas la dirección de una web de chat en la que tengas cuenta, por ejemplo `https://chat.mistral.ai`, y pulsas **Probar y añadir**.
   - Chrome abre una pestaña "Añadir … a webllm". Pulsa **Permitir y probar** y luego **Permitir** en el aviso de Chrome. El permiso es solo para esa web.
   - webllm la abre, busca la caja de texto y le manda una prueba ("pong"). La app te enseña cada paso con ✓ o ✗.
   - La prueba gasta 1 mensaje de esa web y pasa por la protección de siempre.
   - **Si contesta:** queda entre tus IAs, con su icono.
   - **Si no:** te dice por qué, no guarda nada y tienes **Probar otra vez** y **Copiar diagnóstico**.
   - Claude y ChatGPT no se pueden añadir.
   - Las IAs que añades se pueden **Quitar** desde su tarjeta en Inicio. Tu cuenta en esa web no se toca.

| Qué | Probado aquí | Falta probarlo en tu PC |
|---|---|---|
| Verificación en mitad de una pregunta a todas | Sí, en Chromium con la extensión y el puente de verdad y una web de chat de mentira con una verificación resuelta a los 20 s. Con el código de antes, el mismo test falla igual que te pasó a ti | Preguntar a todas y resolver una verificación de Qwen |
| Ventanita tapada | Sí, pero simulado. Se le dice a la página que no se ve, como hace Chrome en Windows con una ventana tapada, porque el Chromium sin pantalla de la nube no lo hace solo | Tapar la ventanita con la app mientras un chat escribe y ver el aviso |
| Añadir otra IA | Sí, en Chromium con la extensión y el puente de verdad: añadir, preguntarle, una web sin caja de texto, otra que pide entrar, quitar. Lo único simulado es tu clic en "Permitir" del aviso de Chrome | Añadir una web de verdad (por ejemplo Mistral) y preguntarle |
| Todo lo demás | 166 tests en verde; 41 capturas en `docs/capturas/7b/` sin fallos de diseño | — |

## Novedades del 25-sep-2026, tarde (lo que pediste tras probar la app)

1. **Un solo botón, "Conectar", por cada chat.**
   - Abre el chat en la ventanita de webllm y, si no tienes la sesión abierta, la trae al frente.
   - Entras ahí con tu cuenta y la app lo ve sola: mira cada 3 segundos, hasta 3 minutos, y se pone en verde sin que vuelvas a pulsar.
   - No envía ningún mensaje.
2. **La guía de primera vez ya no sale** si Chrome está conectado y tienes algún chat listo. Para verla: Inicio → **Ver la guía otra vez**.
3. **Las IAs, en un desplegable.** En Preguntar hay un solo botón, "IAs: N elegidas":
   - al abrirlo salen agrupadas en *Chats en tu Chrome*, *IAs por API* y *En tu PC*;
   - arriba tienes atajos: *Todas las listas*, *Solo las que no gastan cuenta* y *Ninguna*;
   - recuerda tu última elección.
4. **Los modelos de tu PC (LM Studio y Ollama).**
   - Salen solos en el grupo *En tu PC*, por ejemplo "LM Studio · qwen2.5-1.5b-instruct". Los modelos de "embeddings" no salen, porque no sirven para chatear.
   - No gastan ninguna cuenta.
   - Si el programa está apagado, tienes el botón **Encender LM Studio** (o **Encender Ollama**).

**Una vez, después de ACTUALIZAR:** la extensión cambia a la versión 0.4.0. Abre `chrome://extensions` y pulsa la flecha ↻ en "webllm puente". `ACTUALIZAR` te lo recuerda.

| Qué | Probado aquí (con dobles de prueba) | Falta probarlo en tu PC |
|---|---|---|
| Conectar | Sí: la extensión de mentira "entra" 6 s después y el círculo se pone verde solo; 3 tests | Pulsar Conectar en un chat sin sesión y entrar |
| Desplegable de IAs | Sí: capturas y uso completo con teclado | — |
| LM Studio / Ollama | Sí: un LM Studio de mentira, 9 tests; un Ollama "instalado pero apagado" sale en gris | Ver la respuesta de tu `qwen2.5-1.5b-instruct` en la app |
| Todo lo demás | 144 tests en verde | — |

## Novedades del 25-sep-2026 (programado por Claude Code desde GitHub)

1. **La app de webllm.** Doble clic en **`WEBLLM`**: se enciende todo y se abre una ventana propia.
   - **Inicio:** un semáforo por cada pieza y cada IA, con el botón que arregla cada problema.
   - **Preguntar:** escribes una vez, eliges a quién con un clic y ves las respuestas una al lado de otra. En cada respuesta tienes **Pásasela a…**, **Que la critique…** y **Copiar**.
   - **Historial:** todo lo que has preguntado, con buscador, **candado verde** si nadie lo ha tocado y botón **Exportar**.
   - **Guía de primera vez:** 3 pasos que se ponen en verde solos.
   - Modo claro y oscuro (abajo a la izquierda). Capturas en `docs/capturas/fase3/`.
2. **Cadenas de IAs (el motor de la futura "Mesa de IAs").** Doble clic en **`herramientas\probar-cadena`**:
   - DeepSeek y z.ai (chat) hacen cada uno una parte de un encargo;
   - z.ai por API lo une todo en un informe;
   - al final te dice si el registro tiene el **candado verde**.
   - Gasta 1 mensaje de cada chat. Antes de empezar te dice cuánto gastará y puedes cancelar.

| Qué | Probado aquí (en la nube, con dobles de prueba) | Falta probarlo en tu PC |
|---|---|---|
| App: Inicio, Preguntar, Historial, guía | Sí: servidor de verdad con una extensión y un OmniRoute de mentira; 26 capturas revisadas; uso con teclado | Abrirla con `WEBLLM` y hacer una pregunta sin ayuda |
| Cadenas | Sí: 39 tests, incluido "Reparto + integración" con 2 chats de mentira y 1 IA por API | `herramientas\probar-cadena` con tus chats de verdad |
| Todo lo anterior sigue igual | 132 tests en verde | — |

## Novedades del 24-sep-2026 (tarde)

- **El panel de pruebas está en http://127.0.0.1:20130.** `2 - PROBAR TODO` lo abre.
- **Verificado por Iván en su Chrome:**
  - z.ai y DeepSeek responden;
  - **"Programar con el chat z.ai": BIEN.** Una IA de su Chrome arregló el código de prueba.
- **Una sola ventanita** en una esquina, con una pestaña por IA, que se cierra sola al terminar.
- **"Saturada"** ya no pausa la IA. Ventanas emergentes (como la de la edad en Qwen): te avisa y espera.
- **Pendiente:**
  - Qwen: CAPTCHAs y la ventana de la edad;
  - Meta: repetir la prueba con la versión 0.3.0 de la extensión.
- **Siguiente paso:** `docs/PLAN-v3.md` (Mesa de IAs y aplicación de verdad). Lo programará Claude Code desde GitHub.
- **Para bajar lo que suba Claude Code:** doble clic en **`ACTUALIZAR`**.

## Qué está comprobado (24-sep-2026)

| Pieza | Estado | Prueba |
|---|---|---|
| Puente local | OK | Se enciende solo; `/health` y `/v1/models` responden; 17 tests propios |
| Extensión: escribir, enviar, esperar y copiar | OK en z.ai real, sin cuenta | Prueba de ida y vuelta byte a byte: 185 de 185 caracteres idénticos por el botón "copiar" |
| Extensión: aviso de CAPTCHA | OK | Qwen sin cuenta mostró un CAPTCHA deslizante; se detecta y no se toca |
| Extensión: página oculta | Resuelto | Se detectó que z.ai se para si está oculta; ahora la ventana se trae al frente |
| aider → puente → extensión | OK (extensión de prueba) | `python tests/bridge_aider_check.py`: test de rojo a verde, con commit |
| `webllm ask` a chats del navegador y a APIs a la vez | OK (tests) | 76 tests en verde |
| z.ai por API (GLM-4.7-Flash) | OK | Prueba de ida y vuelta 10/10 |
| groq, Nemotron gratis | OK | Prueba de ida y vuelta 5/5 cada uno |
| **Extensión de verdad en tu Chrome** | **PENDIENTE** | Hace falta `1 - INSTALAR` y después `2 - PROBAR TODO` |
| Qwen, DeepSeek y Meta con tu sesión | **PENDIENTE** | Los selectores de Qwen, DeepSeek y Meta son una primera versión; se ajustan con `puente diagnosticar` si fallan |

## Riesgos

- **Cuentas.** Las webs pueden banear el uso automático (DeepSeek y z.ai lo prohíben en sus términos). Lo aceptaste; la protección lo frena, pero no lo evita.
- **Las webs cambian.** Si cambia la página de un chat, puede dejar de encontrar la caja de texto o el botón. Se ve en el aviso y se arregla con `diagnosticar`.
- **Ventanas ocultas.** Si minimizas las ventanas de chat, pueden pararse (ver mandamiento 6).
- **z.ai por API** tiene límite de velocidad: devolvió 429 tras unas 15 peticiones seguidas. Si sale gratis de verdad: [FALTA DATO], míralo en tu cuenta de z.ai.

## Dónde está cada cosa

- **Lo que usas:**
  - `LEEME - EMPIEZA AQUI.txt`: la guía corta.
  - `WEBLLM`: la app.
  - Los otros archivos de doble clic, en la carpeta principal.
- **Por dentro:**
  - `extension/`: la extensión de Chrome.
  - `src/webllm_agent/bridge.py`: el puente.
  - `src/webllm_agent/selftest.py`: PROBAR TODO.
  - `src/webllm_agent/flows.py`: el motor de cadenas.
  - `app/`: la app (lo que se compila va a `src/webllm_agent/static/app/`).
  - `herramientas\`: los comandos avanzados.
- **Configuración y registros:**
  - `data/config.yaml`: nombres, orden, límites.
  - `data/runs/`: el registro de cada envío.
- **Vía antigua por cookies de OmniRoute** (`docs/proveedores-web.md`): ya no hace falta. OmniRoute solo se usa para las IAs por API.
