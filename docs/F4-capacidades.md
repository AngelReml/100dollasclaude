# F4 — Todo lo que sabe hacer cada chat, bajo tu control (26-sep-2026)

**Resultado en la nube: todo lo que el plan pide probar aquí, bien, con la extensión de verdad.** Queda lo que solo se puede ver en tu PC: si las webs de verdad (Qwen, z.ai, Kimi, DeepSeek) se dejan leer y manejar igual que la web de prueba.

## Qué hay nuevo

- **La ficha de cada chat.** En la app, cada chat tiene un botón **«Ficha: modelos y modos»**. Al pulsar **Descubrir**, webllm abre la web del chat, abre sus menús (el selector de modelos y el «+»), **los lee y los cierra**. No pulsa ninguna opción y no envía nada, así que no gasta mensajes. La ficha enseña:
  - **sus modelos, el más potente primero**. El orden sale de una tabla del catálogo, con su fuente y su fecha:
    - un modelo que la tabla no conoce sale «Nuevo, sin datos» y nunca se elige solo;
    - si dos empatan, pone **«Empate: dime cuál»** y no adivina;
    - con **«Este es el más potente»** eliges tú, y siempre puedes volver a la tabla;
    - **«Usar siempre el que tenga puesto su web»**: webllm no le cambia el modelo a ese chat. Es la salida si en una web no consigue confirmar el modelo que pone: sin ella, ese chat no enviaría nada. Un modelo elegido por su nombre en Open WebUI se sigue poniendo y comprobando;
  - **sus modos** junto a la caja (pensar, buscar…) y lo que hay en su **menú «+»**;
  - **qué archivos acepta**.
- **«Enséñame dónde está».** Si webllm no encuentra el selector de modelos o el «+», pulsas el botón y haces **un clic** en esa cosa, en la ventanita de webllm. Ese clic no hace nada en la web: solo le enseña dónde está. Se puede deshacer con «Olvidar lo que te enseñé».
- **En Open WebUI:**
  - **El selector de modelos** enseña los modelos de cada chat: «Qwen · <modelo> (web) — el más potente», y los demás. «Qwen (web)» a secas usa el más potente, y si no se sabe cuál es, el que tenga puesto su web (y lo dice).
  - **Cinco interruptores en el «+»:** Pensar más, Buscar en la web, Investigación profunda, Modo constructor, Crear imagen.
  - **Los archivos que adjuntas** van enteros a la web del chat y se suben **con su propio botón de subir**.
- **Antes de enviar, todo se comprueba en la página** (D21):
  - webllm pone el modelo y los modos y **lee en la página que han quedado puestos**;
  - sube los archivos y comprueba que **aparecen adjuntos, con la misma huella**;
  - si algo no cuadra, **no envía nada** y te dice qué pasó: «No se envió: Qwen no confirmó lo que pediste», «…ese modelo ya no está en Qwen», «…Qwen no tiene ese modo», «…el archivo no quedó adjunto».
- **Cada respuesta dice lo que se usó de verdad, leído en la web:**
  - «Respondió Qwen con el modelo «…» y el modo «…» (comprobado en su web)»;
  - a quién se subieron tus archivos: ««informe.pdf» se subió a Qwen (Alibaba), con la misma huella»;
  - si en la web había otro modo encendido que tú no pediste, **también lo dice**, porque webllm no lo quita a escondidas.
- **Lo que produce el chat:**
  - un archivo que la web genera (una página, un informe…) se guarda en `data\descargas\<pregunta>\` y la respuesta dice dónde. El candado verde del historial comprueba que nadie lo ha cambiado;
  - un enlace a un archivo de su web queda como enlace.
- **Botones prohibidos:** webllm nunca pulsa publicar, compartir, borrar, regenerar, desplegar, pagar, cerrar sesión ni denunciar. La regla está en inglés, español, francés, alemán, italiano, chino, japonés y coreano, y **todos** sus clics pasan por ella.
- **Modos caros:** la investigación profunda y el modo constructor suelen tener pocos usos al día en las webs, así que el guardián los cuenta aparte (5 al día por chat; se cambia en `data\config.yaml`, `expensive_daily_cap`).
- **El registro** guarda de cada respuesta: la IA, el modelo, los modos, los archivos (por su huella) y las descargas.

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| **Descubrir** lo lista todo (3 modelos, 3 opciones del «+», 2 modos, qué archivos acepta) **sin pulsar ninguna opción ni enviar nada**: la web de prueba anota cada clic y solo hay dos, los que abren los menús | **Bien** | aquí, extensión de verdad en Chromium |
| Modelo y modos puestos y **confirmados en la página**; con un selector que «no cambia», **no se envía nada** y dice por qué; una web sin subida de archivos: tampoco se envía nada | **Bien** | aquí, extensión de verdad |
| Un PDF, una imagen y un archivo de **20 MB** llegan a la web **con la misma huella** (viajan por partes) | **Bien** | aquí, extensión de verdad |
| «Publicar» y «Compartir» no se pulsan nunca | **Bien** | aquí, extensión de verdad, y la regla en 8 idiomas |
| Un archivo que genera la web se guarda, se enlaza y el candado lo vigila | **Bien** | aquí |
| «Enséñame»: sin él no encuentra el selector escondido; con un clic tuyo lo aprende, y ese clic no hace nada en la web | **Bien** | aquí, extensión de verdad |
| **Open WebUI + extensión de verdad:** el selector enseña «Completa · Modelo Ultra (web) — el más potente»; un PDF adjuntado **llega entero** a la web; el interruptor «Buscar en la web» **cambia el modo usado**; la respuesta lo dice | **Bien** (6 de 6) | aquí, en pantalla |
| Modos caros contados aparte; empates que no se adivinan; el más potente por defecto o el que eliges | **Bien** | aquí |
| Las 4 fichas de verdad (Qwen, z.ai, Kimi, DeepSeek) | **Falta** | tu PC |

Pruebas: `tests/extension/capabilities_flow.mjs` (14 de 14), `tests/openwebui/f4_checks.mjs` (6 de 6), `tests/test_forbidden.py`, y en `tests/test_gateway.py` las de archivos, modos, modelo, descargas y modos caros. Capturas: `docs/capturas/f4/` (la ficha, en claro y oscuro) y `docs/capturas/f4/openwebui/`.

## Límites (lo que no sé todavía, dicho claro)

- **Las webs de verdad no se pueden abrir desde la nube.** webllm busca lo que usan casi todos los chats: botones que abren menús y dicen «modelo» o el nombre de un modelo, interruptores marcados como tales, menús con opciones y la caja de subir archivos de la página. Una web que lo haga de otra forma dará «no encontré su selector» (entonces, «Enséñame») o «no se envió». **Nunca manda algo distinto de lo que pediste**, pero puede no poder usar un modo hasta que lo arreglemos.
- **«Enséñame» sirve para el selector de modelos, el «+» y el botón de adjuntar**, no todavía para un modo concreto. Si un modo no se deja poner, dímelo.
- **La tabla de potencia** solo tiene lo que dice el plan: Qwen 3.8, GLM-5.2 y Kimi K3. Lo demás sale «sin datos» hasta que tú lo marques o F8 lo mida.
- **Archivos:** se suben por la caja de subir de la propia web. Una web que solo acepte arrastrar y soltar dirá «el archivo no quedó adjunto». Límite: 50 MB por archivo y 100 MB por mensaje.
- **Descargas:**
  - se recogen los archivos que la web crea en la propia página;
  - las descargas que salen de sus servidores quedan como enlace;
  - webllm no pulsa botones de descarga desconocidos ni usa tu sesión para bajarse nada.
- **Parar** sigue sin pulsar el botón de parar de la web (se decide con la autorreparación, F6).
- **Open WebUI:** para ver los modelos de cada chat y los interruptores nuevos, vuelve a hacer doble clic en `herramientas\poner-en-openwebui.cmd` después de pulsar Descubrir.

## Para ti: cómo probarlo en tu PC

1. Doble clic en `ACTUALIZAR`.
2. En `chrome://extensions`, pulsa **↻** en «webllm puente». Debe poner **0.7.0**.
3. En la app de webllm, en el Inicio, en **Qwen**, pulsa **Ficha: modelos y modos** y luego **Descubrir**. Mira la ventanita de webllm: verás abrirse y cerrarse sus menús, sin escribir nada. **Compara la ficha con lo que ves en la web de Qwen:** modelos, modos y menú «+». Haz lo mismo con **z.ai, Kimi y DeepSeek**.
   - Si falta algo: «Enséñame dónde está».
   - Si pone «Empate» o no sabe cuál es el más potente, pulsa «Este es el más potente» en el que tú sepas.
4. Doble clic en `herramientas\poner-en-openwebui.cmd` (para los modelos y los interruptores nuevos).
5. En Open WebUI, elige **«Qwen · … — el más potente»**, adjunta un PDF y pregunta «Resume este PDF». Debajo del nombre debe poner «Respondió Qwen con el modelo «…» (comprobado en su web)» y ««tu.pdf» se subió a Qwen (Alibaba)».
6. **Modo constructor:** elige z.ai o Qwen, enciende **Modo constructor** en el «+» y pide «Hazme una web pequeña para una panadería». Puede tardar minutos. Lo que genere quedará en `data\descargas\` o como enlace, y la respuesta te dice dónde. webllm nunca pulsa publicar.
7. Si algo sale distinto, mándame `data\logs\bridge.log` y una captura de la ficha.
