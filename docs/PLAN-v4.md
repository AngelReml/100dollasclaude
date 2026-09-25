# PLAN-v4 — El enrutador de webllm: un solo chat delante y comités de IAs detrás

Escrito el 25-sep-2026 con el método `experto-cowork-operativo`: las decisiones se toman con
evidencia fechada y la solución elegida es la más pequeña que funcione.
Actualizado el mismo día con las decisiones de Iván:
- se aprueba el uso indirecto de Claude;
- se añaden las APIs gratis;
- se confirman los 4 datos pendientes.

**La visión de fondo (en qué se convierte webllm y sus siete conceptos) está en `docs/VISION.md`.**

**Relación con PLAN-v3:**
- Siguen valiendo sus reglas de diseño (sección "Diseño: ultra intuitiva y estética"), su contrato y sus reglas de evidencia.
- Este plan cambia **qué se construye después** de lo ya hecho (3b, 7a, 7b y el arreglo de las verificaciones).
- La "Mesa de IAs" (fase 4 de PLAN-v3) pasa a ser el **modo experto** de lo que aquí se describe.

## Veredicto

**Combinación:** todo se programa dentro de webllm, en tu PC, y se añade una sola tarea programada en la nube.

- **Dentro de webllm se construyen:**
  - un **catálogo de IAs precargado**;
  - un **enrutador**, que decide cómo contestar;
  - un **motor de comités**: proponer, votar en número impar y fusionar;
  - una **pantalla de chat única**.
- **La tarea programada** revisa cada semana el catálogo, porque las webs de IA cierran, cambian de nombre o aparecen nuevas, y propone los cambios con pruebas.
- **No se instala nada del ecosistema Claude:** ni plugins, ni conectores MCP, ni skills nuevas.
- **No se usa el conector de GitHub de Mistral** para escribir código. El motivo está en "Riesgos".

## Lo que vas a tener (en cristiano)

1. **Una sola caja de chat**, como en cualquier IA. Escribes y recibes **una** respuesta.
2. **Por detrás, sin que tengas que hacer nada**, webllm decide cómo contestarte:
   - **Rápida:** una pregunta sencilla va a la IA que mejor lo hace en ese tipo de pregunta y que ahora está libre.
   - **Consejo:** varias IAs contestan y una los fusiona en una respuesta mejor, diciendo en qué coinciden y en qué no.
   - **Comité:** para decidir algo, 2 o 3 IAs proponen, un jurado de **3 IAs** vota sin saber quién escribió cada propuesta, y gana la mayoría. Con 3 votos nunca hay empate.
   - **Código:** una IA escribe el cambio en tu carpeta, se pasan los tests, el jurado revisa el cambio y, si lo rechaza, se corrige.
     - Tú ves el cambio en colores y decides: **Aceptar** o **Deshacer**.
     - Nunca se sube nada a GitHub sin ti.
   - **Investigar:** usa las IAs que buscan en internet y citan fuentes (Felo, Ask Brave, Kimi…).
3. **Debajo de cada respuesta, "Cómo se decidió"** (plegado, solo si quieres verlo):
   - quién propuso;
   - cómo votó el jurado (por ejemplo 2 a 1) y por qué;
   - qué opinaba el que perdió;
   - cuántos mensajes gastó de cada cuenta;
   - el **candado verde** del registro.
4. **Encima de la caja, un selector pequeño:** *Automático* (por defecto), *Rápida*, *Consejo*, *Comité*, *Código*. Por si quieres mandar tú.
5. **Todas las IAs de la lista ya vienen dentro.**
   - No tienes que pegar direcciones: cada una aparece en Inicio con un botón **Conectar**.
   - Conectar pide el permiso de Chrome para esa web, te deja entrar con tu cuenta y hace la prueba "pong". Todo en un paso.
   - "Añadir otra IA" sigue existiendo para las que salgan en el futuro.
6. **webllm aprende qué IA gana en qué:**
   - Cada vez que el jurado vota, y cada vez que tú pulsas 👍 o 👎, apunta qué IA ganó en ese tipo de pregunta.
   - Con el tiempo, el enrutador elige mejor solo.
   - En Ajustes ves la tabla con los datos reales.

**Lo que NO puede hacer nadie, tampoco webllm:**
- Entrar por ti con tu cuenta: las contraseñas las pones tú (regla dura 3).
- Saltarse las verificaciones (regla dura 2).

## Respuestas directas a lo que preguntaste

- **¿Faltó Brave?** Brave tiene dos cosas y no son iguales.
  - **Ask Brave** (en `search.brave.com`) es una web normal con chat y búsqueda, que usa el modelo abierto Qwen3. **Entra en el catálogo.**
  - **Brave Leo no se puede manejar, ni siquiera ahora que el Claude indirecto está aprobado.** Vive en una página interna del navegador Brave (`brave://leo-ai`), y ninguna extensión puede entrar en las páginas internas de un navegador.
  - **El sustituto:** el Claude Haiku gratis que tiene Leo también está en **Duck.ai**, gratis, sin cuenta y en una web normal. Duck.ai sí entra.
  - Ask Brave: confirmado que es gratis, sin cuenta y funciona en cualquier navegador.
- **Mistral y GitHub.** Es verdad, y **está confirmado que es gratis**: desde septiembre de 2025 los conectores de Le Chat, GitHub incluido, van en el plan gratuito. Con ellos puede leer y tocar repositorios. Una fuente de poca calidad dice que desde mayo de 2026 se llama "Vibe"; se ve al conectarla.
  - **Mistral entra en el catálogo** como una IA más: propone, critica y vota.
  - **Pero no le damos permiso para escribir en tu GitHub.** Eso haría que una web de fuera, fuera del guardián y del registro, tocara tu código.
  - En webllm, el código lo escribe **tu PC** (aider), con git para deshacer, con tests, y con tu **Aceptar**.
- **"Precargarlas todas".** Sí, y sin escribir direcciones. Queda un paso que nadie puede saltarse por ti: **entrar una vez con tu cuenta en cada una**. Por eso es un botón "Conectar" por IA y no una instalación de golpe.
- **"Escalar fuerte".** Escalar aquí significa:
  - más IAs;
  - comités más listos;
  - un enrutador que aprende.
  - **Todo para ti, en tu PC y con tus cuentas.**
  - Convertirlo en un servicio para otras personas sería automatizar cuentas de webs de terceros a gran escala. Casi todas lo prohíben en sus condiciones, así que ese salto solo sería viable con IAs **por API**. Este plan no da ese salto.

## Arquitectura recomendada

```
                         TÚ ── una caja de chat (pantalla "Chat")
                                         │
                ┌────────────────────────▼────────────────────────┐
                │  ENRUTADOR (nuevo, router.py)                     │
                │  1. clasifica: rápida / consejo / comité /        │
                │     código / investigar                           │
                │  2. elige IAs: catálogo + salud + presupuesto +   │
                │     puntuación aprendida                          │
                │  3. calcula cuántos mensajes gasta, antes de      │
                │     empezar                                       │
                └────────────────────────┬────────────────────────┘
                                         │ una "cadena" (Flow)
                ┌────────────────────────▼────────────────────────┐
                │  MOTOR DE CADENAS (ya existe, flows.py)           │
                │  + paso "jurado": respuestas anónimas y           │
                │    barajadas, votos impares, veredicto            │
                │  + paso "fusión": la mejor + lo útil del resto +  │
                │    los desacuerdos                                │
                │  registro encadenado + candado verde (ya existe)  │
                └───────┬──────────────────┬──────────────────┬───┘
                        │                  │                  │
        chats de tu Chrome           IAs por API          IAs de tu PC
        (puente + extensión;         (OmniRoute; rápidas, (LM Studio / Ollama;
        el catálogo: ~20 webs)       sin cuenta web: el    sin cuenta)
        → PROPONEN                   JURADO y el enrutador)
                        │
            aider + git + tests en TU carpeta (modo Código) → Aceptar / Deshacer
```

### Reparto de papeles (clave para que sea rápido y no queme cuentas)

- **Proponen las IAs más fuertes**, que suelen ser los chats web (Kimi, DeepSeek, Qwen, Mistral…). Son las que gastan mensajes de tus cuentas.
- **Votan las IAs por API** (z.ai GLM, groq gpt-oss, Nemotron y otras gratis de OpenRouter), y las de tu PC si son lo bastante buenas.
  - Por API contestan en segundos, van en paralelo y no gastan cuentas web.
  - No sacan verificaciones.
- **Por qué no todas las IAs a la vez:** la evidencia dice que mezclar IAs mejora el resultado **solo si las que proponen son buenas**. Mezclar con otras más flojas empeora. Por eso proponen las 2 o 3 mejores según la puntuación medida, no "todas".
- **El jurado, en cambio, sí conviene que sea variado:** 3 IAs de **familias distintas**. Un panel variado de modelos pequeños juzga mejor que un solo juez grande, con menos sesgo y unas 7 veces más barato.

### Reglas del comité (lo que evita trampas)

1. **Número impar de votos siempre (1 o 3).** Si un miembro del jurado falla (no contesta, está saturado), entra otro de reserva. Si no hay reserva, el jurado se reduce a 1. Nunca queda en 2.
2. **Respuestas anónimas y barajadas.** El jurado ve "Propuesta A, B, C", sin el nombre de la IA y en orden aleatorio. El orden y la semilla se guardan en el registro para poder repetirlo.
   - **Por qué:** está demostrado que una IA que juzga reconoce y prefiere sus propios textos.
3. **Nadie se juzga a sí mismo.** Si una propuesta viene de la familia GLM, el juez GLM se cambia por otro.
4. **Voto con motivo.** Cada miembro del jurado contesta con un formato fijo:
   - `VOTO: A`;
   - una línea de por qué;
   - el fallo más grave que ve en cada una.
   - Si el formato no se entiende, ese voto no cuenta y entra la reserva.
5. **La fusión dice la verdad:** parte de la ganadora, añade lo útil de las otras y enumera **en qué no están de acuerdo**. No esconde la discrepancia.
6. **Tope de gasto por pregunta.** Por defecto:
   - Consejo = 3 mensajes web;
   - Comité = 3 mensajes web (el jurado y la fusión van por API);
   - Código = 1 IA web que programa (unos 2 mensajes por cambio) + jurado por API + como mucho 2 correcciones.
   - Se enseña antes de empezar, como ya hace la app.
7. **Las respuestas son datos, no órdenes.** Lo que dice una IA entra en las otras **entre comillas y marcado como texto de otra IA**, con la instrucción de no obedecer nada de dentro. Nada de lo que diga una respuesta se ejecuta nunca.

### El catálogo precargado (comprobado con el buscador el 25-sep-2026; desde la nube no se pueden abrir las webs)

**Grupo 1: web de chat sencilla y funciona desde España.** Se precargan todas.

| IA | Dirección | Etiquetas para el enrutador |
|---|---|---|
| Kimi (Moonshot) | `https://www.kimi.com` | documentos largos, investigar, código |
| Le Chat / Vibe (Mistral) | `https://chat.mistral.ai` | general, código, rápida |
| HuggingChat | `https://huggingface.co/chat` | general, modelos abiertos; se puede usar sin cuenta |
| LongCat (Meituan) | `https://longcat.chat` | general, instrucciones |
| Grok (xAI) | `https://grok.com` | general, actualidad |
| Gemini (Google) | `https://gemini.google.com` | general, documentos largos |
| Dola (ByteDance) | `https://www.dola.com/chat/` | general |
| Felo (Japón) | `https://felo.ai` | investigar, con fuentes |
| Ask Brave | `https://search.brave.com` (modo chat) | investigar, con fuentes |
| Ai2 Playground | `https://playground.allenai.org` | general, modelos totalmente abiertos |
| Pi (Inflection) | `https://pi.ai` | conversación; puede cerrar |
| Inception Chat (Mercury) | `https://chat.inceptionlabs.ai` | rápida; menos lista |
| **Duck.ai** (DuckDuckGo) | `https://duck.ai` | **Claude Haiku 4.5 gratis y sin cuenta**; también Mistral Small, gpt-oss y Gemma. **Nunca elegir los GPT de OpenAI** |
| **Arena** (antes LMArena), chat directo | `https://arena.ai/direct` | elegir un modelo concreto, Claude incluido; lo que escribes puede publicarse para investigación: **nada privado** |
| **Perplexity** | `https://www.perplexity.ai` | investigar, con fuentes (gratis con su modelo propio) |
| Nous Chat | `https://chat.nousresearch.com` | Hermes 4; gratis |

**Grupo 2: se precargan marcadas "puede fallar"** (por su página complicada, por pocos mensajes o por una dirección sin confirmar):

| IA | Dirección | Por qué puede fallar |
|---|---|---|
| Venice | `https://venice.ai` | unos 10 mensajes gratis al día |
| Google AI Studio | `https://aistudio.google.com` | la página es complicada; Google puede usar lo que escribas |
| MiMo Studio (Xiaomi) | `https://aistudio.xiaomimimo.com` | pide cuenta Xiaomi; Xiaomi dice que es un escaparate de modelos, no un asistente |
| Poe | `https://poe.com` | solo unos 300 puntos al día (15-30 mensajes cortos); los Claude buenos no entran en el plan gratis |
| LingGuang (Ant Group) | `https://www.lingguang.com/chat` | puede pedir cuenta china |

**No se precargan:**
- **Agentes que hacen tareas, no chats:** MiniMax Agent, Manus y Genspark. No encajan en pregunta-respuesta, actúan por su cuenta en la web y abren otro frente de riesgo.
- **OpenRouter Chat:** su web deja elegir GPT y Claude. Sus modelos gratis se añaden mejor **por API**, vía OmniRoute, que es más rápido y no gasta cuentas web. Son buenos candidatos a jurado.
- **Siguen fuera:**
  - ChatGPT, directo o solo con GPT por dentro: Copilot;
  - Claude directo (`claude.ai`);
  - Brave Leo, porque no se puede manejar;
  - Sakana Fugu, que es solo API y de pago.
- **Bloqueadas por país:**
  - Sakana Chat (solo Japón);
  - Amazon Nova (solo Estados Unidos);
  - Doubao, Yuanbao, ERNIE e iFlytek (piden teléfono chino).
- **Cerradas en 2026:** Phind, Naver Clova X y StepFun internacional.

**Cómo se precarga sin quitarte seguridad:**
- El catálogo es un archivo del proyecto (en git).
- Cada IA aparece en Inicio como tarjeta **"Sin conectar"** con el botón **Conectar**.
- Ese botón hace el recorrido de "Añadir otra IA" con la dirección ya puesta: permiso de Chrome solo para esa web, entrar con tu cuenta y prueba "pong" por el guardián.
- Así Chrome solo da permiso a las webs que de verdad usas (mínimo privilegio).
- **Alternativa descartada:** meter las 22 webs en los permisos fijos de la extensión. Sería un solo aviso de Chrome, pero con acceso a webs que quizá nunca uses.

### Fuentes gratis por API comprobadas (25-sep-2026)

Las APIs son **el motor del jurado, del enrutador y del taller de código**:
- van rápido y en paralelo;
- saben usar herramientas;
- no gastan tus cuentas web ni sacan verificaciones.

Cada clave la crea Iván en la web del proveedor y la guarda en OmniRoute. **Nunca va a git.**

Límites cambiantes: cuando dos listas no coinciden, se dan las dos cifras.

| Proveedor | Qué es gratis | Modelos que interesan | Qué pide |
|---|---|---|---|
| **NVIDIA NIM** (build.nvidia.com) | unas 40 peticiones/min por modelo | **GLM-5.2 / GLM-5.3** (el mejor modelo abierto para programar), Nemotron | cuenta NVIDIA Developer + teléfono |
| **Mistral** (console.mistral.ai) | plan "Experiment": todos los modelos con límite; una lista comprobada en agosto dice **10 $/mes en créditos** | Mistral Medium/Large, **Codestral** (código) | nada (sin tarjeta) |
| **Groq** | 30/min; entre 250 y 1.000 al día según el modelo | gpt-oss-120b, **Qwen3.8-27B**, Kimi K2 | nada |
| **Google Gemini API** (AI Studio) | modelos Flash; desde abril los Pro ya no son gratis; límites bajos y cambiantes (de 20 a 1.500 al día según el modelo) | Gemini 3.x Flash | nada; condiciones propias en Europa |
| **OpenRouter** | modelos ":free": 20/min y 50 al día (1.000 al día tras una recarga única de 10 $) | Nemotron 3 Ultra, Ling 3.0, Gemma 4… | nada |
| **Z.ai** | GLM-4.7-Flash y GLM-4.6V-Flash gratis (ya lo usas) | GLM Flash | nada |
| **Ollama Cloud** | cuota por tiempo de GPU (cada 5 h y semanal) | **Kimi, DeepSeek V4 Pro, GLM-5.1**; los grandes gastan la cuota rápido | cuenta |
| **OpenCode Zen** | modelos gratis que van rotando | MiMo, MiniMax M2.5, Nemotron 3 Ultra | cuenta; pensado para el agente OpenCode |
| **Kilo Code** (pasarela) | 200 peticiones/hora (comprobado en agosto) | Nemotron 3 Ultra, Step 3.7 Flash | nada |
| **Cohere** | unas 1.000 llamadas/mes, uso no comercial | Command A+ | nada |
| **Cloudflare Workers AI** | 10.000 "neuronas"/día | Llama 3.3 70B, Mistral Small | cuenta |
| **Hugging Face** | 0,10 $/mes | modelos pequeños | cuenta |
| **OVHcloud AI Endpoints** (UE) | 2/min sin registrarse | Qwen3.5-397B, gpt-oss-120b | nada |
| **LLM7.io** | 10/min sin registrarse | gpt-oss-20b | nada |
| **SambaNova** | según la lista, 20 al día **o** 5 $ para 30 días | DeepSeek V3.1 | cuenta |
| Otros con uso justo | Aion Labs, AI21 (Jamba), Chutes, Glhf, Nscale, Agnes | variados | cuenta |

- **Con verificación china o de identidad real:** ModelScope y SiliconFlow (esta, desde mayo de 2026) y Alibaba Model Studio.
- **Créditos de una sola vez:**
  - DeepSeek: 5 millones de tokens;
  - xAI;
  - Fireworks: 1 $;
  - Nebius: 1 $;
  - Cerebras: 5 $ para 30 días, **solo con tarjeta**.
- **Gratis que se acabó en 2026:**
  - **GitHub Models** (cerrado el 30-jul);
  - **Gemini CLI** gratis (18-jun);
  - **Qwen Code** con cuenta gratis (15-abr);
  - **Cerebras** sin tarjeta (16-jul).
- **Claude por API** (unos 5 $ al registrarse) es Claude directo: sigue fuera.

## Procedimiento exacto (fases, cada una con prueba que ves)

Orden obligatorio: la **fase 0** va antes que todo. Después, **A → B → C → D → E → F → G → H**, e **I** al final. Cada fase tiene su PR.

| Fase | Qué se hace | Evidencia que se exige |
|---|---|---|
| **0. Prueba en vivo del PR #3** (ya fusionado) | Tú: ACTUALIZAR, pulsar ↻, verificación con Qwen y añadir Mistral | Tus capturas o tu "funciona / no funciona" en cada punto. Si algo falla, se arregla antes de seguir |
| **A2. APIs gratis** | Iván crea las claves (NVIDIA, Mistral, Groq, Gemini, OpenRouter, Ollama Cloud…) y las mete en OmniRoute; webllm las lista como fuentes "Por API" con su ficha (límites, herramientas) | Una prueba de ida y vuelta por proveedor (como las de z.ai y groq), con sus límites reales apuntados |
| **A. Catálogo precargado** | `catalog.yaml` con los grupos 1 y 2; tarjetas "Sin conectar"; **Conectar** en un paso; el diagnóstico de las que fallan se guarda para programar su soporte | pytest; prueba en Chromium con la extensión de verdad contra varias webs de mentira del catálogo; capturas. **Tú** conectas las que quieras y apuntamos cuáles pasan |
| **B. Chats a la vez (requisito de velocidad)** | Hoy los chats van de uno en uno. Se prueba en tu PC preguntar a 3 a la vez con la rotación de pestañas | Tus tiempos: de uno en uno contra a la vez. **Si a la vez no mejora o falla, se queda de uno en uno** y el comité tira más de las IAs por API |
| **C. Motor de comités** | Pasos "jurado" y "fusión" en `flows.py`; plantilla `comite`; voto impar garantizado; anonimato y barajado; reservas; tope de gasto | pytest: el empate es imposible, el jurado reserva entra, ningún texto del jurado lleva el nombre de la IA, el orden barajado se puede repetir, se para al llegar al tope. Más un comité real guardado con su candado |
| **D. Enrutador automático** | `router.py`: clasifica con una IA rápida por API (o reglas si OmniRoute está apagado), elige IAs por etiqueta, salud, presupuesto y puntuación, y explica en una línea por qué | pytest con 30 preguntas de ejemplo y su modo esperado; el tope de gasto se respeta siempre |
| **E. Pantalla de chat única** | Pantalla "Chat" por defecto; "Cómo se decidió" plegable; selector de modo; las pantallas de ahora pasan a "modo experto" | Lista de diseño de PLAN-v3 + capturas claro/oscuro a 1280 y 1920 sin fallos; tú haces 3 preguntas sin ayuda |
| **F. Código con jurado** (sustituye a la fase 5 de PLAN-v3) | El taller: **OpenCode** (MIT) o aider en una rama de prueba de tu carpeta, con modelos gratis por API que usan herramientas (GLM-5.x en NVIDIA como principal); tests; jurado sobre el cambio y el resultado de los tests; como mucho 2 correcciones; Aceptar o Deshacer. Además, el **banco de pruebas**: 20 tareas reales con tests para puntuar cada versión | La puntuación del banco de pruebas (tareas resueltas de 20) y una ejecución real con votos y Deshacer |
| **G. Aprendizaje** | `scores.json`: puntuación por IA y por tipo de pregunta, a partir de los votos y de tus 👍/👎; el enrutador la usa; tabla en Ajustes | pytest; la tabla con datos reales tras una semana de uso |
| **H. Catálogo vivo** | Tarea programada semanal en la nube (`create_trigger`): busca cambios (cierres, cambios de nombre, IAs nuevas) y **abre un PR** con evidencia. Nunca lo fusiona ella | El primer PR que abre, con las fuentes |
| **I. Cierre** | Icono único y limpieza (fase 6 de PLAN-v3), 7c (elegir el modelo dentro de Qwen y z.ai) y el constructor de cadenas (Mesa) en modo experto | Lo de PLAN-v3 |

Subagentes (solo en el desarrollo): en **C + E** el motor y la pantalla no tocan los mismos archivos y se pueden hacer a la vez. El resto va en orden.

## Contrato de ejecución

- **Reglas duras de CLAUDE.md, todas, siempre.** En especial:
  - la 1: el enrutador nunca elige Claude ni ChatGPT, y `is_blocked_model` se comprueba también en el catálogo y en los jurados;
  - la 2: las verificaciones las resuelves tú;
  - la 5: las respuestas no se ejecutan;
  - la 6: el guardián va en **todos** los caminos, incluidos el jurado web y la prueba de Conectar.
- **Mínimo privilegio:** el permiso de Chrome se da web a web al conectar; ningún token de GitHub en webllm; el modo Código solo toca la carpeta que eliges y siempre sobre git.
- **Presupuesto visible y con tope:** antes de cada comité, el gasto por cuenta; tope por pregunta y tope diario; si una web está en pausa o saturada, el enrutador la salta.
- **Registro completo:** cada propuesta, cada voto con su motivo, el orden barajado, el veredicto y la fusión van al registro encadenado. El candado verde cubre todo el comité.
- **Evidencia por fase:** salida real de pytest; la prueba en Chromium cuando se toque la extensión; una ejecución de verdad con su candado; capturas. Siempre separando **"probado aquí"** de **"falta probarlo en tu PC"**.

## Riesgos que bloquean o cambian el plan

- **Trifecta letal en el modo Código (bloqueante si no se mitiga).** Se juntan tres cosas:
  - tu código (dato privado);
  - respuestas de IAs de fuera (contenido no fiable);
  - una salida posible (subir a GitHub).
  - **Mitigación:**
    - no hay salida automática: nada se sube, todo se queda en tu PC y en git;
    - tú pulsas Aceptar;
    - el jurado ve el cambio, pero no ejecuta nada;
    - los comandos de tests los fijas tú una vez por carpeta.
  - **Por lo mismo, no se conecta el GitHub de Mistral.**
- **Inyección entre IAs.** Una respuesta puede traer frases del tipo "ignora lo anterior y…".
  - **Mitigación:** las respuestas entran siempre como texto citado; el jurado solo emite `VOTO: X` y una frase, y se ignora todo lo demás; y el caso tiene su test.
- **Cuentas.** Un comité multiplica los mensajes y más volumen trae más verificaciones y más riesgo de bloqueo. DeepSeek y z.ai prohíben el uso automático en sus condiciones.
  - **Mitigación:**
    - jurado y enrutador por API o en tu PC, sin gastar cuentas web;
    - topes de gasto;
    - el guardián de siempre;
    - "Rápida" por defecto para lo sencillo.
- **Lentitud.** Un chat web tarda de 20 a 120 s y hoy van de uno en uno. Un comité solo con chats web tardaría minutos.
  - **Mitigación:** la fase B, más el jurado por API en paralelo.
  - **Si la fase B falla**, el comité web se limita a 2 propuestas.
- **Calidad.** Mezclar IAs flojas empeora el resultado.
  - **Mitigación:** proponen solo las mejor puntuadas; el jurado es variado.
  - **Además:** se mide. Si el comité no gana a la mejor IA sola en tus 👍/👎, el enrutador usa menos el comité.
- **El catálogo se queda viejo** (este año ya cerraron tres).
  - **Mitigación:** la fase H, y la tarjeta enseña "no responde desde el día X".
- **Nivel en la matriz de riesgo del método:** bajo. No hay plugins ni MCP, y lo único nuevo en la nube es una tarea programada que solo abre PRs.

## Verificación antes de declarar "hecho"

- **Cada fase:**
  - el bloque de salida real de `pytest -q` en un entorno limpio;
  - la salida de la prueba en Chromium (`tests/extension/*.mjs`) si cambia la extensión;
  - el identificador de una ejecución real con `verify_run` en verde;
  - las capturas.
- **Nunca "funciona" basándose en el resumen de otra IA** (regla de Iván del 7-sep-2026): siempre la salida cruda.
- **Lo que depende de tu PC** (webs reales, tus cuentas, ventanas de Windows) se marca "pendiente de Iván" hasta que tú lo confirmes.

## Para Claude Code (cómo construirlo)

- **Catálogo:**
  - `src/webllm_agent/catalog.yaml` (en git) con `key, name, url, group (1|2), tags, notes, checked (fecha + fuente)`;
  - `config.py` lo carga como proveedores `kind: browser`, con estado `sin_conectar` hasta que Conectar pasa;
  - `custom_ais.json` sigue para los que añade Iván;
  - rutas `/api/catalogo` y `/api/conectar-catalogo`, que reutilizan `/api/anadir` con la URL fijada;
  - la extensión no cambia de modelo, porque ya acepta `site_config`.
- **Comités en `flows.py`:**
  - paso `jury` (lista de jurados, número de votos impar, reservas, `anonymize()`, `shuffle(seed)`, un analizador estricto de `VOTO:`);
  - paso `fuse`;
  - plantilla `comite`;
  - todo en el diario: el orden barajado, la semilla, los votos y los descartados.
- **`router.py`:**
  - `classify(msg) -> (modo, motivo)` con una IA por API y un respaldo por reglas;
  - `pick(modo, catálogo, salud, presupuesto, scores)`;
  - `budget(flow)`, que reutiliza `estimate_messages`.
- **`scores.py`:** Bradley-Terry o Elo por (IA, tipo), con olvido gradual; datos en `data/state/scores.json`.
- **App:**
  - pantalla `Chat` (ruta por defecto) con hilo de conversación, selector de modo y "Cómo se decidió";
  - la guía de primera vez se actualiza.
- **Tests, con los mismos patrones de ahora:**
  - servidor falso con comportamientos de jurado (`vote_a`, `vote_b`, `garbage`, `slow`);
  - extensión falsa para las propuestas;
  - `harness.mjs` para el catálogo en Chromium.
- **Recordatorio (CLAUDE.md):** los chats web van de uno en uno (`upstream_key("browser/x") == "browser"`). Solo se cambia tras la fase B en el PC de Iván.

## Fundamento canónico

- **Mezclar IAs mejora si proponen bien:** Wang et al., *Mixture-of-Agents Enhances LLM Capabilities*, arXiv 2406.04692, 7-jun-2024. Con solo modelos abiertos lograron un 65,1 % en AlpacaEval 2.0, frente al 57,5 % de GPT-4o. https://arxiv.org/abs/2406.04692
- **…pero la calidad pesa más que la variedad al proponer:** Li et al., *Rethinking Mixture-of-Agents* (Self-MoA), arXiv 2502.00674, febrero de 2025. https://arxiv.org/abs/2502.00674
- **Jurado variado mejor que un solo juez, con menos sesgo y unas 7 veces más barato:** Verga et al., *Replacing Judges with Juries* (PoLL), arXiv 2404.18796, abril de 2024. https://arxiv.org/abs/2404.18796
- **Las IAs que juzgan prefieren sus propios textos (de ahí el anonimato):** Panickssery, Bowman y Feng, NeurIPS 2024. https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html
- **Conectores de Le Chat (MCP, GitHub):** https://mistral.ai/news/le-chat-mcp-connectors-memories/ y el directorio comunitario https://github.com/rdmgator12/awesome-mistral-connectors (listado de 2-jul-2026; el nombre "Vibe" viene de aquí, fuente de poca calidad).
- **Ask Brave (Qwen3, web) y Brave Leo (dentro del navegador):** https://brave.com/ai/ · https://search.brave.com/help/ai · https://brave.com/leo/
- **Estado de cada IA del catálogo, búsquedas del 25-sep-2026** (desde la nube no se pueden abrir las webs; la fase A lo comprueba de verdad):
  - Kimi: https://en.wikipedia.org/wiki/Kimi_(chatbot)
  - HuggingChat: https://huggingface.co/chat/ · https://weavai.app/blog/en/2026/04/18/huggingchat-2026-review-free-open-source-ai-chat-guide/
  - LongCat: https://longcat.chat/
  - Pi: https://aitoolsdevpro.com/ai-tools/pi-guide/
  - Inception: https://chat.inceptionlabs.ai/
  - Venice: https://filmora.wondershare.com/video-editor-review/venice-ai-review.html
  - Google AI Studio: https://pricepertoken.com/endpoints/google-ai-studio/free
  - Dola: https://www.dola.com/chat/ · https://en.wikipedia.org/wiki/Doubao
  - Felo: https://felo.ai/blog/about-us/
  - Ai2 Playground: https://playground.allenai.org/
  - MiMo: https://mimo.xiaomi.com/
  - Nous Chat: https://www.aixploria.com/en/nous-chat-ai/
  - LingGuang: https://en.wikipedia.org/wiki/Lingguang
  - Sakana Chat, solo Japón: https://efficienist.com/sakana-ai-launches-free-sakana-chat-but-only-japan-gets-to-try-it/
  - Phind cerrado: https://www.aipedia.wiki/tools/phind/
  - Clova X cerrado: https://10wontips.blogspot.com/2026/02/naver-clova-x-and-naver-cue-shutting.html
  - StepFun internacional cerrado: https://en.wikipedia.org/wiki/StepFun
  - Amazon Nova, solo Estados Unidos: https://www.aboutamazon.com/news/innovation-at-amazon/amazon-nova-website-sdk
  - ERNIE: https://en.wikipedia.org/wiki/Ernie_Bot
  - Yuanbao: https://yangmao.ai/en/providers/yuanbao/
  - Manus: https://www.nocode.mba/articles/manus-ai-pricing
  - Genspark: https://www.eesel.ai/blog/genspark-ai-review
  - OpenRouter Chat: https://openrouter.ai/chat
- **Método:**
  - elegir lo más pequeño que funcione y automatizar después: https://claude.com/blog/subagents-in-claude-code ;
  - "trifecta letal": Simon Willison, 16-jun-2025;
  - tareas programadas: https://code.claude.com/docs/en/scheduled-tasks
- **Datos confirmados el 25-sep-2026 (antes pendientes):**
  - Nous Chat: `chat.nousresearch.com` — https://chat.nousresearch.com/
  - MiMo Studio: `aistudio.xiaomimimo.com`, con cuenta Xiaomi — https://xiaomiplanets.com/xiaomi-mimo-studio-ai/
  - Conector de GitHub de Mistral: gratis — https://venturebeat.com/ai/mistral-ai-just-made-enterprise-ai-features-free-and-thats-a-big-problem-for · https://help.mistral.ai/en/articles/393509-setting-up-my-first-connector
  - Ask Brave: gratis, sin cuenta y en cualquier navegador — https://brave.com/blog/ask-brave/
- **Claude indirecto y fuentes nuevas:**
  - Duck.ai — https://duckduckgo.com/duckduckgo-help-pages/duckai/chat-models
  - Arena — https://arena.ai/direct · https://en.wikipedia.org/wiki/LMArena
  - Poe — https://aisotools.com/poe-pricing
  - Leo en página interna — https://github.com/brave/brave-browser/issues/42817
- **APIs gratis:**
  - https://github.com/mnfst/awesome-free-llm-apis (con cada fila comprobada con una llamada real entre el 19 y el 21 de agosto de 2026)
  - https://github.com/open-free-llm-api/awesome-freellm-apis (actualizada el 25-sep-2026)
  - Mistral — https://pricepertoken.com/endpoints/mistral/free
  - Fin de GitHub Models — https://www.free-model.com/providers/github-models/
  - Gemini CLI — https://www.tembo.io/blog/gemini-cli-pricing
  - Qwen Code — https://inventivehq.com/blog/qwen-code-still-free-2026-shutdown
  - Cerebras — https://klymentiev.com/blog/free-llm-api
  - Ollama Cloud — https://hackup.ai/ai-plans/ollama/
  - OpenCode Zen — https://opencode.ai/docs/zen/
  - DeepSeek — https://pricepertoken.com/endpoints/deepseek/free
