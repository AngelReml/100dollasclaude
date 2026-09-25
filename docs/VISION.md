# VISIÓN — En qué se convierte webllm

> **Nota (25-sep-2026):** el plan vigente es `docs/PLAN-v5.md` (Open WebUI como cara, webllm como motor, Comité obligatorio, memoria de un solo escritor, webs que se reparan solas). Donde este documento no coincida, manda PLAN-v5.

Escrito el 25-sep-2026, a partir de lo que Iván imagina. Este documento dice **hacia dónde va** webllm.
El **cómo y en qué orden** está en `docs/PLAN-v4.md`, y las reglas de diseño y de evidencia en `docs/PLAN-v3.md`.

## El norte, en una frase

**Un taller de programación de nivel frontera, hecho con IAs gratis, que se acerque a la fiabilidad de Claude Code y sepa cuándo pensar mucho y cuándo contestar rápido.**
Es para Iván y funciona en su PC. No es un producto comercial.

## Qué significa "nivel frontera" aquí (sin engañarnos)

- **Dónde estamos, septiembre de 2026:**
  - el mejor modelo abierto en la prueba de programación más dura resuelve cerca del **62 %** de las tareas (GLM-5.2 y Qwen3.8-Flash-Next);
  - el mejor modelo cerrado ronda el **80 %**.
  - La diferencia es real, pero ya no es un abismo. Además, **GLM-5.2 se puede usar gratis** por la API de NVIDIA.
- **La fiabilidad de Claude Code no sale solo del modelo.** Sale de tres cosas juntas:
  1. un **buen taller**: herramientas para leer el proyecto, editar archivos y pasar tests;
  2. un **modelo fuerte**;
  3. **comprobar cada cambio**: tests, revisión y pasos pequeños.
- webllm puede competir en la 1 y en la 3, y juntar varios modelos para acercarse en la 2.
- **Lo que sí es alcanzable:** tareas bien definidas y con tests que se resuelven con una fiabilidad **cercana** a Claude Code, más despacio pero gratis.
- **Lo que costará más:** trabajos largos y ambiguos, en los que el mejor modelo cerrado sigue ganando.
- **Cómo se sabe si nos acercamos:** con un **banco de pruebas propio**. Son 20 tareas reales de Iván en un proyecto de prueba, y cada versión de webllm se puntúa contra ellas. Cuenta el número, no la impresión.

## Los siete conceptos (el modelo mental de todo webllm)

Todo lo que se construya debe encajar en uno de estos siete. Si algo no encaja, sobra.

### 1. Fuentes: dónde vive la inteligencia

Cada IA es una **fuente** con una ficha: qué tal lo hace (medido), velocidad, cuánto cuesta (mensajes o créditos), riesgo para la cuenta y si sabe usar herramientas.

| Tipo de fuente | Ejemplos | Para qué sirve mejor |
|---|---|---|
| **Chats web con tus cuentas** (la extensión) | Kimi, DeepSeek, Qwen, Mistral, Duck.ai (Claude Haiku), Arena… | **Consultores:** los modelos más potentes gratis. Son lentos, gastan mensajes de tu cuenta y pueden pedir verificaciones |
| **APIs gratis** (OmniRoute) | GLM-5.x en NVIDIA, Mistral, Groq, Gemini, OpenRouter y OpenCode Zen (modelos gratis) | **El motor del taller y del jurado:** rápidas, en paralelo y con herramientas; sin cuentas web ni verificaciones |
| **Tu PC** (LM Studio / Ollama) | los modelos que tengas | Tareas pequeñas y privadas, sin límites de nadie |

### 2. Habilidades: las formas de trabajar, cada una con su receta y su precio

Una habilidad es una **receta con nombre**: qué pasos, qué papeles, qué comprobaciones y **cuánto cuesta**.
Como dice Iván: el comité es caro, así que es una habilidad que se usa **cuando merece la pena**, no siempre.

| Habilidad | Receta | Coste típico | Cuándo |
|---|---|---|---|
| **Rápida** | 1 fuente, la mejor para ese tipo de pregunta | 1 mensaje | Casi siempre |
| **Consejo** | 3 proponen; 1 fusiona y dice en qué discrepan | 3 web + 1 API | Opiniones, ideas, textos importantes |
| **Comité** | 2-3 proponen; jurado **impar** anónimo de familias distintas; veredicto con motivos | 2-3 web + 3-4 API | Decisiones: "¿A o B?", arquitectura, compras |
| **Debate** | A responde, B busca fallos, A corrige (N vueltas) | 2N | Afinar un plan o un argumento |
| **Investigar** | fuentes que buscan y citan (Felo, Ask Brave, Kimi…) + fusión con enlaces | 2-3 | Datos actuales |
| **Programar** | el taller: plan → cambio → tests → jurado revisa el cambio → corrección (como mucho 2) → Aceptar | 1 web o API por cambio + jurado por API | Código |
| **Revisar código** | jurado sobre un cambio ya hecho | 3 API | Antes de aceptar algo |
| **Depurar** | reproducir el fallo con un test → proponer 2-3 arreglos → quedarse con el que pasa los tests | variable | Errores |

- **El futuro de este concepto:** Iván podrá **guardar una forma de trabajar como habilidad nueva** sin programar (por ejemplo "Consejo de 3 chinos + juez Mistral"), y el enrutador la usará cuando toque.

### 3. Enrutador: el director

- Para cada mensaje elige **habilidad + fuentes**, dentro del presupuesto, y explica por qué en una línea.
- Por defecto funciona en *Automático*; Iván siempre puede forzar una habilidad.
- Aprende de los votos del jurado, de los tests y de los 👍/👎 de Iván.

### 4. Taller: las manos que tocan el código

- Es un agente de programación de verdad que lee el proyecto, edita archivos, pasa los tests y hace commits en git.
- **No se reinventa:** se enchufa uno abierto y probado.
  - Hoy es **aider**, que ya funciona con webllm.
  - El candidato a principal es **OpenCode** (licencia MIT; es la alternativa abierta de referencia a Claude Code y funciona con cualquier modelo).
- webllm pone **el cerebro** (enrutador + comités) y **la verificación** (tests, jurado, registro).
- **Siempre en una rama de prueba y en tu PC.** Nada se sube solo a GitHub, y se pulsa **Aceptar / Deshacer**.

### 5. Memoria: lo que aprende

- **Puntuaciones:** qué fuente gana en qué tipo de tarea, medido.
- **Memoria de cada proyecto:** convenciones, decisiones tomadas y cómo se pasan sus tests. Así no hay que repetirlo cada vez.
- **Registro encadenado con candado verde:** qué se preguntó, quién dijo qué y quién votó qué. Ya existe.

### 6. Guardián: los límites que nunca se saltan

- Protección de cuentas: espaciado, tope diario y pausa si hay límite.
- Presupuesto por pregunta y por día.
- Las respuestas de las IAs **son datos, nunca órdenes**: nada de lo que dicen se ejecuta sin pasar por el taller, los tests y tu Aceptar.
- **Claude y ChatGPT, directamente, no** (`claude.ai`, `chatgpt.com`).
- **Servicios que usan Claude o GPT por dentro, sí.** Aprobado por Iván el 25-sep-2026: Duck.ai, Poe, Perplexity, Arena, Copilot…
  - Dentro de ellos se puede elegir cualquier modelo, también los GPT.
- Las verificaciones (CAPTCHA) siempre las resuelve Iván.

### 7. Interfaz: una sola conversación

- Una caja de chat.
- Debajo de cada respuesta, **"Cómo se decidió"**.
- En Ajustes, las fuentes, las habilidades, las puntuaciones y el presupuesto.
- El resto de pantallas (Preguntar, Mesa, Historial) queda como **modo experto**.

## Horizontes (qué se puede tener y cuándo tiene sentido)

| Horizonte | Qué tienes | Condición para pasar al siguiente |
|---|---|---|
| **H1: el enrutador** (PLAN-v4, fases A-E) | Catálogo de unas 20 webs + APIs gratis, habilidades Rápida/Consejo/Comité/Investigar, chat único | Tus 👍 dicen que el comité gana a una IA sola cuando se usa |
| **H2: el taller** (PLAN-v4, fases F-G + banco de pruebas) | Programar con jurado sobre OpenCode o aider, memoria de proyecto, puntuaciones | El banco de 20 tareas sube versión a versión; se mide la distancia a Claude Code |
| **H3: habilidades tuyas** | Guardar tus propias formas de trabajar, catálogo que se actualiza solo (tarea semanal) | Usas habilidades propias sin ayuda |
| **H4: trabajo nocturno supervisado** | Encargas una tarea larga por la noche; el taller trabaja en una rama de prueba y por la mañana tienes un informe, los tests y el cambio para **Aceptar** | Nunca se fusiona nada sin ti; el registro lo demuestra |

## Qué NO va a ser (para no perder el norte)

- **No es un producto para otros.** Automatizar cuentas web de terceros a escala choca con sus condiciones. Si algún día se abre a otros, será solo con APIs.
- **No es "todas las IAs a la vez para todo".** Eso gasta cuentas, tarda y, según la evidencia, puede **empeorar** el resultado si entran IAs flojas.
- **No es un agente que actúe solo en internet ni en tu GitHub.** Las manos se quedan en tu PC, sobre git, con tests y con tu Aceptar.

## Fundamento

- **Distancia entre modelos abiertos y cerrados (septiembre de 2026):**
  - https://www.morphllm.com/swe-bench-pro
  - https://www.morphllm.com/best-ai-model-for-coding
  - https://llm-stats.com/benchmarks/swe-bench-verified
- **Taller abierto de referencia:**
  - https://www.openhands.dev/blog/open-source-ai-coding-agents
  - https://pinggy.io/blog/best_open_source_cli_coding_agents/
- **Mezclar IAs y jurados:** ver "Fundamento canónico" en `docs/PLAN-v4.md` (Mixture-of-Agents, Self-MoA, PoLL y la preferencia por sus propios textos).
- **APIs gratis y fuentes web con Claude dentro:** ver la tabla "Fuentes gratis comprobadas" en `docs/PLAN-v4.md`.
