# F8 — «Automático» (26-sep-2026)

**Resultado en la nube: hecho y probado.**
- **50 pruebas de «Automático».** Rompiendo a propósito cada protección, su prueba falla.
- **El Open WebUI de verdad: __OWUI__.**
- **__CAPTURAS__ capturas de la app, sin problemas.**
- **Todas las pruebas del proyecto juntas: __TOTAL__.**

Falta lo que solo se ve en tu PC:
- **Tus 10 preguntas de prueba**, 2 de cada tipo, marcando si eligió bien. Es la salida del plan: **9 de 10 bien elegidas**.
- **Encender las APIs de la tabla** que aún no tienes (GLM-5.2, Qwen3.8-27B, Codestral, Gemini Flash). Hasta entonces, «Automático» usa las reservas.

**La extensión no cambia** en esta fase: no hace falta pulsar ↻.

## Qué es y cómo se usa

1. En Open WebUI, arriba, elige **webllm · Automático**.
   - Está justo después de los chats web y del Comité.
   - **Nunca es el de partida:** un chat nuevo se abre con el mismo modelo que antes.
2. Pregunta como siempre. **La primera línea de la respuesta dice qué IA eligió y por qué**, por ejemplo:
   > **Automático** eligió **Kimi** para «Código» (dice «script», dice «python»). Antes en su lista: GLM-5.2 (API), sin configurar; Qwen3.8-27B (Groq), sin configurar; Codestral (API), sin configurar.
3. **Si la IA elegida falla**, te lo dice como cualquier otra, con esa misma primera línea delante.
   - **No pregunta a otra sin ti.**
   - Si falló por estar saturada o sin sesión, vuelve a enviar la pregunta: «Automático» se la salta 15 minutos y usa la siguiente de la lista.
4. **Una idea para evaluar** va al **Comité**, que enseña su plan y espera tu «adelante» (nada se envía antes).
   - Con un plan esperando, «adelante», «cancela», «con 3»… van al Comité.
   - Si en vez de eso haces otra pregunta, el plan se descarta y la primera línea lo dice.
5. **Si no hay ninguna disponible**, no envía nada y te dice cuál falta y qué hacer.
6. **En la app de webllm** (Inicio → «Que webllm elija la IA») ves:
   - las reglas, en su orden;
   - qué elegiría ahora para cada tipo de pregunta, y por qué se salta las anteriores;
   - «Probar con tus preguntas»;
   - «Las IAs por API».
7. **En el Historial**, cada pregunta hecha con «Automático» dice qué eligió y por qué, y lleva el candado verde.

## Las reglas (están en un archivo y se ven en la app)

No aprende ni adivina: lee **tu última pregunta** y lo que adjuntas, y prueba estos pasos en orden. El primero que encaja decide.

1. Si dice «mi idea», «esta idea», «es buena idea», «merece la pena», «pros y contras», «evalúa mi»… → **Evaluar una idea**.
2. Si adjuntas un archivo de código (.py, .js, .html…) → **Código**.
3. Si adjuntas un archivo de texto (PDF, Word…) → **Documento largo**.
4. Si lleva código escrito (un bloque ``` o algo con forma de código, como «TypeError» o «def f(x):») → **Código**.
5. Si tu mensaje pasa de 8.000 caracteres → **Documento largo**.
6. Si dice «código», «programa», «script», «python», «error de compilación»… → **Código**.
7. Si dice «este documento», «este pdf», «resume este»… → **Documento largo**.
8. Si dice «fuentes», «busca en internet», «noticias», «qué tiempo hace», «cotización»… → **Investigar con fuentes**.
9. Si no, y sigues una conversación de código, documento o investigación → **el mismo tipo** («sigue la conversación»).
10. Si no → **Pregunta rápida**.

Lo que va con la pregunta (un archivo, código escrito, un texto muy largo) pesa más que una palabra suelta. Así, «Resume este PDF sobre cómo programar en python» con un PDF es un documento, no código.

## La tabla

| Tipo | Primero | Reservas (plan) | Añadidas (lo que ya tienes, sin medir) |
|---|---|---|---|
| Código | GLM-5.2 (API) | Qwen3.8-27B (Groq) → Codestral (API) → Kimi (web) | gpt-oss-120b (Groq) → DeepSeek (web) → Qwen (web) |
| Pregunta rápida | Qwen3.8-27B (Groq) | GLM Flash (z.ai) → Gemini Flash (API) | gpt-oss-120b (Groq) → Qwen (web) |
| Documento largo | Gemini Flash (API, 1 millón de tokens) | Kimi (web) | Qwen (web) → DeepSeek (web) |
| Investigar con fuentes | Felo (web) | Ask Brave → Perplexity → Kimi (web) | — |
| Evaluar una idea | webllm · Comité | — (el Comité lleva sus reservas dentro) | — |

**«Disponible»** quiere decir todo esto a la vez:
- conectada o configurada;
- sin pausa y por debajo de su tope de hoy;
- bien en su última comprobación, y sin fallar (saturada o sin sesión) en los últimos 15 minutos;
- privada;
- capaz de recibir lo que va con la pregunta: un PDF solo va a un chat web que sepa subir archivos, y una imagen solo a una IA que vea imágenes.

## Las fichas de las IAs por API

| IA | Quién la sirve | Para qué | Ve imágenes | Gratis | Lo que escribes |
|---|---|---|---|---|---|
| GLM-5.2 | NVIDIA NIM | programar | no se sabe | unas 40 por minuto | **sin comprobar**: NVIDIA lo guarda 30 días; no queda claro si entrena |
| Qwen3.8-27B | Groq | rápido, código | no se sabe | 30 por minuto; 250-1.000 al día | **no entrena** (contrato de Groq, 4.2) |
| Codestral | Mistral | código | no | plan «Experiment» | **entrena si no lo apagas** |
| Mistral Large | Mistral | general | no se sabe | plan «Experiment» | **entrena si no lo apagas** |
| Gemini Flash | Google | documentos largos, imágenes | sí | 20-1.500 al día, cambiante | **no entrena en Europa** |
| GLM Flash (la que tienes) | z.ai | rápido; arregla las webs (F6) | no | gratis | **sin comprobar**: las fuentes se contradicen |
| gpt-oss-120b (la que tienes) | Groq | general, código | no | 30 por minuto | **no entrena** |
| Nemotron (la que tienes) | OpenRouter, gratis | general | no se sabe | 50 al día | **puede entrenar** |

**Cómo se enciende una:**
1. Crea su clave en la web del proveedor.
2. Ponla en OmniRoute.
3. En webllm: **Inicio → Automático → Las IAs por API → Buscar en OmniRoute → Encender**.
   - Se hace una llamada corta de prueba, que cuenta en su día.
   - El nombre del modelo sale siempre de la lista de OmniRoute, nunca inventado.
   - Nunca se ofrece uno prohibido (Claude, ChatGPT o Codex).
   - Desde ese momento está también en el selector de Open WebUI.

## Lo que encontré sobre tu privacidad (y lo que cambia)

Tu regla (D21) es que nada sale de tu PC sin un gesto tuyo, y que «Automático» y el Comité nunca usan solos una web que publica o usa lo que escribes. Al hacer las fichas miré qué hace cada proveedor gratis con lo que escribes:

- **Mistral (plan gratis):** usa lo que escribes para entrenar si no lo apagas.
  - Codestral y Mistral Large no se usan solos hasta que lo apagues en su consola (Admin → Privacy → «Anonymous improvement data») y pulses **«Ya lo apagué»**.
- **Nemotron** (OpenRouter, gratis): OpenRouter avisa de que quien sirve sus modelos gratis suele guardar lo que escribes para entrenar.
  - **Esto cambia algo que ya usabas:** en F7, Nemotron era uno de los 5 del Comité. Ahora ni el Comité ni «Automático» lo usan solos.
  - Si te parece bien, pulsa **«Permitir»** en su ficha y vuelve a entrar. Elegido por ti, arriba, se usa igual que siempre.
- **Groq:** su contrato dice que no puede entrenar con lo que escribes sin tu permiso.
- **Gemini (API):** en Europa, Google trata lo gratis como lo de pago y no usa lo que escribes para mejorar sus productos.
  - **Consecuencia que decides tú:** la misma regla de Google vale para **Google AI Studio** (la web).
  - El catálogo la tiene marcada como «no privada» justo por «Google puede usar lo que escribas». En Europa no sería así. No la he cambiado: si quieres, la marco como privada.
- **z.ai y NVIDIA:** sin comprobar (las fuentes se contradicen o no lo dicen claro). Se usan, y su ficha lo dice. Si prefieres que no, pulsa **«No dejar que la usen solos»**.

**Fuentes:** las condiciones de cada proveedor, citadas por el buscador el 26-sep-2026. Sus propias páginas no se pueden abrir desde la nube (salen bloqueadas), así que no las he leído enteras. Cada ficha lleva el enlace a su web por si quieres comprobarlo.

## Probar con tus preguntas (la salida de F8)

En la app: **Inicio → Automático → «Probar con tus preguntas»**.
1. Salen 10 preguntas de ejemplo, 2 de cada tipo. **Cámbialas por preguntas tuyas de verdad**: si las escribo yo, acertar no demuestra nada.
2. **«Ver qué elegiría»:** para cada una sale el tipo, la IA y por qué. **No se envía nada a ninguna IA.**
3. Marca cada una **Bien** o **Mal** y **Guarda la prueba**. La tarjeta enseña «Tu prueba: X de 10».
4. **La meta del plan es 9 de 10.** Si falla alguna, dime cuál: se ajusta la regla en el archivo y se vuelve a probar.

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| **Cada tipo tiene primero y reserva** (el Comité, con las suyas dentro) | **Bien** | aquí |
| **Nada de la tabla apunta a una IA prohibida**, y de la lista de OmniRoute nunca se ofrece una | **Bien** | aquí |
| **Ninguna regla usa una web no privada** (Arena, AI Studio), ni una API que puede entrenar sin tu permiso | **Bien** | aquí |
| Las reglas en orden y en español; una tabla rota se rechaza | **Bien** | aquí |
| Cada ficha dice de dónde salen sus datos y qué pasa con lo que escribes | **Bien** | aquí |
| 14 preguntas de muestra, cada una con su tipo y su porqué (incluidas «Dame una idea para cenar» y «¿Qué tiempo hace?») | **Bien** | aquí |
| Sin señales, sigue la conversación (nunca vuelve al Comité) | **Bien** | aquí |
| La primera disponible; cada una saltada dice por qué (sin configurar, en pausa, falló hace 2 min…) | **Bien** | aquí |
| Un PDF nunca va por API; una imagen solo a una IA que ve imágenes | **Bien** | aquí |
| **La primera línea**: con y sin streaming, antes de las primeras palabras de una API que escribe en directo, y delante de un error | **Bien** | aquí |
| **La IA nunca ve las primeras líneas de «Automático»** en la conversación, y el registro guarda sus palabras, no las de webllm | **Bien** | aquí |
| **Si la elegida falla, no se pregunta a otra** | **Bien** | aquí |
| Una idea → plan del Comité (nada enviado); «cancela» va al Comité; otra pregunta descarta el plan | **Bien** | aquí |
| Nadie disponible: no se envía nada y dice qué hacer | **Bien** | aquí |
| Encender una API desde la lista de OmniRoute (con su llamada de prueba), apagarla; un modelo que no está en la lista se rechaza sin llamar a nada | **Bien** | aquí |
| «Ya lo apagué» / «Permitir» / volver a lo que dice la ficha | **Bien** | aquí |
| Tu prueba: qué elegiría para cada pregunta sin enviar nada; tus marcas se guardan | **Bien** | aquí |
| El Historial dice qué eligió y por qué (y nada si elegiste tú) | **Bien** | aquí |
| Open WebUI: «Automático» no tiene interruptores del «+» ni el botón «Continuar en la web» | **Bien** | aquí |
| **En el Open WebUI de verdad:** en el selector y no es el de partida; una pregunta de código con su primera línea y su registro; «sigue la conversación»; una idea → plan del Comité, nada enviado | **__OWUI_CORTO__** | Open WebUI de verdad |
| Tus 10 preguntas, 9 de 10 bien | Pendiente | tu PC |
| Encender GLM-5.2, Qwen3.8-27B, Codestral y Gemini Flash desde tu OmniRoute | Pendiente | tu PC |

Rompiendo a propósito una protección, su prueba falla:
- sin la regla de privacidad;
- con un PDF enviado por API;
- con una palabra pesando más que un archivo;
- sin la primera línea en el streaming de una API, en un error o sin streaming;
- con la IA viendo la primera línea.

## Lo que encontré y arreglé por el camino

1. **«Dame una idea para cenar» iba al Comité** (la señal «una idea» era demasiado amplia). Quitada: ahora evalúa «mi idea», «esta idea», «merece la pena»…
2. **«¿Qué tiempo hace hoy en Madrid?» iba a una IA por API**, que se lo habría inventado. Ahora va a «Investigar con fuentes», con las señales de actualidad (tiempo, cotización, última hora).
3. **Una palabra suelta pesaba más que un archivo** («python» dentro de una pregunta sobre un PDF). Ahora el orden de las reglas está escrito paso a paso, y lo que va con la pregunta decide antes.
4. **Un «no» escrito sin comillas en el archivo se leía como «falso».** El lector ya lo entiende.
5. **Un botón decía «Usar nvidia/z-ai/glm-5.2».** Ahora dice «Encender», y debajo cómo se llama en OmniRoute.
6. **El aviso de mensajes del día decía «el Comité»** también cuando preguntaba «Automático». Ahora habla de quien pregunta.

## Decisiones (y por qué)

- **Reglas escritas y a la vista, sin aprendizaje** (D7). Así sabes siempre por qué eligió lo que eligió, y una regla mala se arregla en el archivo.
- **Si la elegida falla, no se pasa sola a otra** (D21, punto 1): tu pregunta no va a una segunda empresa sin un gesto tuyo. Volver a enviarla es ese gesto, y entonces se salta la que falló.
- **Añadí reservas que ya tienes** (gpt-oss-120b, DeepSeek, Qwen) detrás de las del plan. Sin ellas, hoy «Automático» casi nunca tendría a quién preguntar. Salen marcadas como «añadidas» en el archivo y en la app, y tu prueba dirá si valen.
- **«Automático» no tiene los interruptores del «+»** (pensar, buscar…): son de cada chat, y no sabría a cuál aplicarlos.
- **Una pregunta sin señales sigue el tipo de la conversación**, salvo después del Comité.
- **Las fichas de las APIs dicen lo que se sabe y lo que no**, con su fuente. Lo no comprobado lo dice.

## Límites (dichos claros)

- **Son reglas de palabras: a veces se equivocarán.** Por ejemplo, «programa de televisión» cuenta como código. Para eso es tu prueba. Una elección mala es barata: responde otra IA buena, y la primera línea te lo dice.
- **Solo lee tu última pregunta** (y sus archivos), más «sigue la conversación».
- **Por API solo van imágenes;** un PDF va a un chat web.
- **Cada pregunta a un chat web abre un chat nuevo en su web** (D10). Si sigues hablando de un documento con Kimi, el archivo no vuelve a subirse solo. Esto ya pasaba antes de F8.
- **Las primeras de la tabla necesitan claves que aún no tienes.** Hasta entonces, «Automático» usa las reservas.

## Para ti: cómo probarlo

1. Doble clic en **`ACTUALIZAR`**.
2. Doble clic en **`herramientas\poner-en-openwebui.cmd`**. Así Open WebUI recibe «webllm · Automático».
3. **(Recomendado)** Crea las claves que faltan y ponlas en OmniRoute:
   - build.nvidia.com: GLM-5.2;
   - console.groq.com (ya la tienes): Qwen3.8-27B;
   - aistudio.google.com: Gemini Flash;
   - console.mistral.ai: Codestral. Apaga antes «Anonymous improvement data».
4. En webllm: **Inicio → Automático → Las IAs por API → Buscar en OmniRoute → Encender** cada una.
5. Decide **Nemotron**: «Permitir» o dejarlo como está.
6. **«Probar con tus preguntas»:**
   1. escribe 10 preguntas tuyas, 2 de cada tipo;
   2. pulsa «Ver qué elegiría»;
   3. marca cada una y guarda.

   **Qué deberías ver:** «Tu prueba: X de 10». Si no llega a 9, dime cuáles fallaron.
7. En Open WebUI, elige **webllm · Automático** y pregunta de verdad. **Qué deberías ver:** la primera línea con la IA elegida y el porqué.
