# F6 — Webs que se reparan solas, y seguir tú en la web (26-sep-2026)

**Resultado en la nube: hecho y probado con la extensión de verdad en Chromium (16 de 16) y en el Open WebUI de verdad (5 de 5).** El mismo recorrido con la extensión anterior (0.7.0) falla en cada caso. Falta lo que solo se ve en tu PC: seguir en la web de Kimi una conversación empezada en webllm, y volver a probar las webs del catálogo que quedaron «No funciona todavía».

**La extensión pasa a la versión 0.8.0:** en `chrome://extensions`, pulsa ↻ en la tarjeta «webllm puente».

## Qué hay nuevo

### 1. Cuando una web cambia, webllm lo arregla, de la forma más barata a la más humana

1. **Detección general, más amplia.** Encuentra la caja de texto, el botón de enviar, el de parar y el de copiar en más idiomas (español, inglés, francés, alemán, italiano, portugués, chino, japonés y coreano) y con las cajas modernas que usan las webs nuevas. Muchas webs funcionan sin configurar nada. En las pruebas, una web en francés con una caja moderna funciona a la primera.
2. **Ajustes por web** (`sites.js`), como hasta ahora.
3. **Reparación con IA.** Cuando webllm no encuentra la caja o no puede leer la respuesta:
   1. la extensión saca una **radiografía** de la página: una lista numerada de cajas, botones y bloques con lo que la web puso en ellos (tipo, clases, nombres cortos de sus botones, tamaño, posición);
      - **sin el texto de tu conversación**: de una respuesta solo va su longitud y si viene «después de tu mensaje»;
      - sin contraseñas, cookies ni lo que hayas escrito;
   2. una IA por API (la que elijas; por defecto z.ai) contesta **solo con números** de esa lista;
      - cualquier otra cosa se rechaza y no se usa: código, selectores, texto, un número que no existe, un botón donde se pedía una caja, o tu propio mensaje donde se pedía la respuesta;
   3. webllm **lo prueba en la página, sin enviar nada**:
      - ¿hay exactamente una caja visible?
      - ¿el bloque elegido contiene la respuesta que ya está en la página, y no tu mensaje?
   4. **si pasa, se guarda como arreglo de esa web**, con fecha y quién lo hizo, y el trabajo sigue;
      - si faltaba la caja, **tu pregunta se envía entonces, una sola vez** (antes no se había enviado nada);
      - si faltaba la respuesta, **se vuelve a leer, nunca se vuelve a enviar**;
      - la respuesta te lo dice: «La web de X había cambiado y webllm no encontraba …: z.ai señaló dónde está, se comprobó en la página sin enviar nada y queda guardado en su Ficha».
4. **«Enséñame esta web (3 clics)».** En la Ficha de ese chat (y en «Conectores», en las webs que «No funcionan todavía»):
   - webllm te pide tres clics en su ventana: en la caja de texto, en el botón de enviar y en la última respuesta;
   - tus clics no hacen nada en la web, y cada uno se prueba en la página antes de guardarse.

**En la Ficha de cada chat, «Arreglos de esta web»:** cada arreglo con su fecha, qué arregla y quién lo hizo («tú» o «una IA (z.ai)»). **«Deshacer»** en cada uno y «Deshacer todos». Deshacer vale desde la siguiente pregunta.

**En «Conectores», la tarjeta «Webs que cambian»:**
- **Comprobación diaria.** Una vez al día, cuando no estás preguntando nada, webllm abre cada chat conectado y mira que siga todo en su sitio. **No envía nada.** «Comprobar ahora» la hace en el momento. Si a una web le falta la caja, la repara ahí mismo (sin enviar nada).
- **«Reparar solas con IA».** Encendida o apagada, y qué IA ayuda. Solo pueden ayudar IAs por API o de tu PC, privadas y nunca un chat web. Apagada, webllm te dice qué pasó y te pide los 3 clics.

**«Parar» pulsa también el botón de parar de la web**, para que deje de escribir. Pasa por la misma protección que el resto de clics, y nunca pulsa «publicar», «compartir», «borrar» ni «regenerar».

### 2. Seguir tú en la web, y que quede registrado

- **«Continuar en la web».** Está bajo cada respuesta de un chat web:
  - en Open WebUI, junto a los botones de la respuesta;
  - en la app, en «Preguntar» y en el «Historial».

  Al pulsarlo:
  - abre **esa conversación exacta** en una pestaña normal de tu Chrome, no en la ventanita de webllm;
  - en la página aparece la marca **«● webllm está registrando esta conversación»**, con **«Dejar de registrar»**;
  - en la app, en el Inicio, aparece «Registrando tu conversación con X», con el mismo botón.
- **Lo que escribes allí queda en la misma conversación:**
  - cada mensaje tuyo y la respuesta de la IA se guardan, marcados «Escrita por ti en la web de X»;
  - van al historial y a la misma nota de tu vault («## Tú, en la web de X»);
  - webllm solo mira: no pulsa nada ni escribe nada en esa pestaña;
  - nota tu mensaje en el momento de enviarlo (Enter o el botón de enviar), así que un texto pegado y enviado al instante también cuenta;
  - espera a que la respuesta termine con las mismas reglas que sus trabajos, y la lee de la página.
- **Volver a Open WebUI y seguir desde donde lo dejaste.** Open WebUI no tiene lo que escribiste en la web. Por eso webllm lo añade a tu siguiente pregunta de esa conversación:
  - va en su sitio (después de la respuesta desde la que seguiste) y a la IA que elijas;
  - la respuesta lo dice: «Con tu pregunta van también los 2 mensajes que escribiste directamente en la web de Qwen, con sus respuestas».
- **«Registrar esta conversación»:** si abres tú un chat sin pasar por webllm, pulsa el icono de la extensión.
  - Solo en webs de tu catálogo a las que diste permiso.
  - Solo la pestaña que tú marcas, y nunca a escondidas: la marca está en la página.
  - «Dejar de registrar» lo para, en el icono o en la propia marca.
- **Si webllm está cerrado mientras escribes en la web**, tus turnos esperan en Chrome y se guardan al abrirlo. La conversación sigue siendo la misma aunque cierres y abras webllm.
- **Tus mensajes escritos a mano cuentan en el contador del día de ese chat**, solo para informarte; no esperan ni se frenan.
- **En el Historial** salen como «En la web», con lo que escribiste, la respuesta y lo que tardó la web (medido desde que pulsaste Enter).

## Seguridad (lo que no se ve)

- **La IA que repara nunca ve tu conversación**, y lo que contesta nunca se ejecuta ni se usa como instrucción. Solo elige números de una lista; lo que se guarda lo escribió la propia página. La prueba en Chromium lo comprueba: lo que recibió la IA no contiene tu pregunta, ni la respuesta, ni los títulos de la barra lateral.
- **Probar un arreglo no envía nada.** Y una pregunta nunca se envía dos veces.
- **Nunca se salta una verificación** (regla 2): si la página pide una, webllm te espera como siempre.
- **El modo observador** solo funciona en webs con permiso y en pestañas que tú marcas. Nunca lee campos de contraseña: solo la caja del chat.
- **Todo queda apuntado:** cada reparación, guardada o no, en `data\state\reparaciones.jsonl`; cada arreglo, con su historia, en `data\state\patches\<web>.json`; cada turno escrito a mano, como una pregunta más en `data\runs\`, con su candado.

## Decisiones tomadas (y por qué)

- **«Parar» pulsa el botón de parar de la web** (estaba pendiente). Sin eso, la web seguía escribiendo aunque webllm ya no escuchara.
- **La IA contesta números, no selectores.** El plan decía «selectores en JSON, nunca código». Esto es más estricto: un selector escrito por una IA podría apuntar a cualquier cosa, y un número solo puede apuntar a algo que la página ya enseñó.
- **La reparación con IA viene encendida.** Nunca ve tu conversación y todo se puede deshacer. Si no la quieres, apágala en «Conectores».
- **Seguir desde donde lo dejaste = lo que escribiste en la web va con tu siguiente pregunta.** webllm sigue abriendo una conversación nueva en cada envío (como hasta ahora) con todo el hilo dentro, así que vale para cualquier IA que elijas. Escribir dentro de la misma conversación de la web es otra pieza, que el plan pone en F7 (el Comité la necesita).

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| Capa 1: una web en francés, con caja moderna, se conecta sin ayuda | **Bien** | Chromium |
| Capa 3: una web cuyas respuestas no se podían leer se conecta gracias a la reparación; la prueba se envió una sola vez | **Bien** | Chromium |
| Una IA que contesta con código: rechazada, nada guardado, nada reenviado | **Bien** | Chromium y aquí |
| El arreglo en la Ficha con fecha y quién; la siguiente pregunta ya no pregunta a ninguna IA | **Bien** | Chromium |
| «Deshacer» vale al momento; con la reparación apagada no se pregunta a ninguna IA y te dice qué pasó | **Bien** | Chromium y aquí |
| Reparada tras una pregunta real: se lee, se envió una vez, y la IA no vio ni la pregunta, ni la respuesta, ni la barra lateral | **Bien** | Chromium |
| Capa 4, «Enséñame» con 3 clics: tus clics no envían nada y la web pasa a funcionar | **Bien** | Chromium |
| «Parar» pulsa el botón de parar de la web | **Bien** | Chromium |
| Comprobación diaria: abre cada chat y no envía nada; repara una caja perdida | **Bien** | Chromium y aquí |
| «Continuar en la web» + **2 turnos escritos a mano** en la misma conversación y en la misma nota del vault | **Bien** | Chromium |
| «Registrar esta conversación» desde el icono de la extensión, y «Dejar de registrar» | **Bien** | Chromium |
| Un turno escrito con webllm cerrado: se guarda en Chrome y llega al historial al volver a conectar | **Bien** | Chromium |
| En Open WebUI: el botón bajo la respuesta de un chat web (no bajo una IA por API), abre la conversación, y lo escrito en la web va con tu siguiente pregunta | **Bien** | Open WebUI de verdad |
| Un chat que abriste tú y registras: todos sus turnos quedan en una sola conversación | **Bien** | aquí |
| Un error largo de la página ya no se lee como «saturada» | **Bien** (falla con el código anterior) | aquí |
| Pantallas de la app: claro/oscuro × 1280/1920, 87 capturas, 0 problemas de diseño | **Bien** | `docs/capturas/f6/` |
| Open WebUI: las 4 capturas del botón | **Bien** | `docs/capturas/f6/openwebui/` |
| El mismo recorrido de Chromium con la extensión anterior (0.7.0) | **Falla en cada caso** (abajo) | Chromium |
| Una web de verdad que cambia de diseño | Pendiente | tu PC |

### El registro de un arreglo (simulado)

La salida de F6 pide el registro de un arreglo automático real o, si ninguna web cambia durante la prueba, del simulado. Este es el simulado, tal como lo apuntó la prueba en Chromium (la IA del demo eligió el bloque número 4 de la radiografía; se probó en la página sin enviar nada y quedó guardado en la Ficha con fecha y quién):

```
BIEN  capa 3: la web cuyas respuestas no se podían leer se conecta gracias a la reparación (guardada, IA zai, eligió {"answer":4}); el «pong» se envió una sola vez
BIEN  el arreglo queda en su ficha, con fecha y quién lo hizo: {"index":0,"when":"2026-09-26 12:07:58","what":"la respuesta","by":"una IA (z.ai)","why":"no podía leer la respuesta","active":true,"undone":null}
```

El real saldrá en tu PC, en `data\state\reparaciones.jsonl`, la primera vez que una web cambie.

### La prueba de que cada caso falla con el código anterior

`tests/extension/repair_flow.mjs` con `WEBLLM_EXTENSION_DIR` apuntando a la extensión 0.7.0 (la de F5):

```
BIEN  la extensión 0.7.0 se conecta al puente
FALLO capa 1: una web en francés con caja moderna («Envoyer», «Copier la réponse») se conecta sin ayuda (no_funciona)
FALLO capa 3: la web cuyas respuestas no se podían leer se conecta gracias a la reparación (undefined, IA undefined, eligió undefined); el «pong» se envió una sola vez
FALLO una IA que responde con código: rechazada («undefined»), nada guardado, nada reenviado; la web queda «no_funciona»
FALLO el arreglo queda en su ficha, con fecha y quién lo hizo: undefined
FALLO la siguiente pregunta ya funciona sin preguntar a ninguna IA: «(model_not_found: No conozco esta IA: rara.)»
FALLO deshacer: error: Cannot read properties of undefined (reading 'index')
FALLO reparada otra vez tras una pregunta: se lee, en la página hay 1 mensaje tuyo (se envió una vez) y la respuesta lo dice: «undefined…»
FALLO la IA solo vio la estructura de la página: ni la pregunta, ni la respuesta, ni los títulos privados de la barra lateral (fugas: [])
FALLO enséñame: error: locator.click: Target page, context or browser has been closed
FALLO «Parar» pulsa también el botón de parar de la web (clics en la página: ["Send message"])
FALLO la comprobación diaria abre cada chat conectado y no envía nada: 
FALLO observador: error: Cannot read properties of null (reading 'locator')
FALLO registrar: error: page.goto: net::ERR_FILE_NOT_FOUND at chrome-extension://…/popup.html?tab=1060182687
```

Con la extensión 0.8.0, el mismo guion da 16 BIEN y ningún FALLO. La primera línea («se conecta al puente») pasa con las dos: no es un caso de F6.

## Lo que encontré y arreglé por el camino

Las pruebas y las capturas sacaron seis fallos antes de que llegaran a ti:
1. **Un error de una web se leía como «está saturada».** El diagnóstico de la página era tan largo que se comía el código del error. Ahora el código va primero y el diagnóstico largo queda solo en el registro.
2. **El observador perdía un mensaje pegado y enviado al instante.** Solo miraba la caja cada segundo y medio. Ahora nota tu mensaje justo al enviarlo, y empieza a escuchar antes de poner la marca «registrando».
3. **En un chat que abrías tú, cada turno era una conversación distinta.** Ahora todos los turnos de esa pestaña van a la misma.
4. **En Open WebUI, pulsar el botón tapaba la línea «Respondió Qwen…»** de esa respuesta (la que dice qué se usó de verdad). Ahora solo sale un aviso.
5. **En el Historial, un turno escrito a mano ponía «Cadena» y «Respondió en 0 s».** Ahora pone «En la web» y el tiempo medido.
6. **«Enséñame esta web» salía también en webs que se han cambiado de dirección**, donde tres clics no arreglan nada. Ahora solo sale cuando el problema es la página.

## Lo que no está hecho

- **Proponer los arreglos que funcionan como cambio de `sites.js`** (el plan dice «pueden proponerse», con tu aprobación). Hoy cada arreglo vive en tu PC, en la Ficha de esa web. Llevarlos a `sites.js` para todos queda para más adelante.
- **Escribir dentro de la misma conversación de la web** desde webllm: llega en F7.
- **Lo que solo se ve en tu PC** (abajo).

## Para ti: cómo probarlo

1. Doble clic en **`ACTUALIZAR`**.
2. En `chrome://extensions`, pulsa **↻** en «webllm puente» (versión **0.8.0**).
3. Doble clic en **`herramientas\poner-en-openwebui.cmd`** otra vez. Así Open WebUI recibe el botón «Continuar en la web».
4. **Seguir en la web:**
   1. en Open WebUI pregunta algo a **Kimi** (o a cualquier chat web);
   2. bajo la respuesta, pulsa **«Continuar en la web»** (el icono de la flecha saliendo de un cuadro);
   3. se abre esa conversación en tu Chrome, con la marca «webllm está registrando…»;
   4. escribe allí dos mensajes a mano;
   5. **qué deberías ver:** en el Historial de la app y en la nota de tu vault, tus dos mensajes («Escrita por ti en la web de Kimi») y sus respuestas;
   6. vuelve a Open WebUI y pregunta otra cosa en la misma conversación: bajo la respuesta pondrá «Con tu pregunta van también los 2 mensajes que escribiste directamente en la web de Kimi…».
5. **Webs que no funcionaban:**
   1. en la app, **Conectores** → las que dicen «No funciona todavía» → **«Conectar»** otra vez;
   2. si alguna sigue sin funcionar, pulsa **«Enséñame esta web»** y haz los 3 clics que te pide.
   3. Apúntame cuántas funcionan ahora. En su Ficha verás si lo arregló una IA o tú.
6. **Comprobación diaria:** Conectores → tarjeta «Webs que cambian» → **«Comprobar ahora»**. Deberías ver «N de N bien».
