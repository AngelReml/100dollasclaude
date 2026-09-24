# PLAN v3 — webllm: inteligencia cruzada + aplicación de verdad

Fecha: 24-sep-2026. Hecho con la skill `experto-cowork-operativo`. Es un **plan**: todavía no hay código de esto.

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
| **3. App: Inicio, Preguntar e Historial** | Las 3 pantallas básicas y el botón "Pásasela a…" | Captura de la app funcionando en mi navegador; luego tú la abres con el icono |
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

## Decisiones que necesito de ti (recomendación ya puesta)

1. **App dentro de Chrome en modo aplicación** (recomendado) o programa aparte tipo Electron: más pesado, sin ventaja real.
2. **El juez, por defecto, una IA por API** (recomendado, no gasta cuentas de chat) o un chat web.
3. **Empezar por la fase 1** (motor) **y la 3** (Preguntar con "Pásasela a…") **a la vez**. Es lo que antes te da inteligencia cruzada usable.

## Fundamento

- Primitiva más pequeña y "empieza conversacional, automatiza después": skill `experto-cowork-operativo` (pluto.security 2026-04-29; claude.com/blog/subagents-in-claude-code).
- Subagentes solo para trabajo independiente y nunca editando el mismo archivo: ídem.
- Trifecta letal: Simon Willison, 2025-06-16.
- Estado actual verificado en este proyecto (24-sep-2026):
  - puente, extensión y panel funcionando;
  - "Programar con el chat z.ai: BIEN" visto por Iván;
  - 79 tests en verde;
  - commit `30903a8`.
