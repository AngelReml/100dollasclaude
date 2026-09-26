# F7 — El Comité (26-sep-2026)

**Resultado en la nube: hecho y probado.**
- **30 pruebas del Comité.** Rompiendo a propósito cada protección (inyección, nombres en la fusión, empate, a quién van tus archivos, dos chats a la vez), su prueba falla.
- **La extensión de verdad en Chromium: 5 de 5** en «seguir en la misma conversación». Con la extensión anterior, cada caso falla.
- **El Open WebUI de verdad: 5 de 5.**
- **93 capturas de la app, sin problemas.**

Falta lo que solo se ve en tu PC: un Comité real de 5 sobre una idea tuya. Después, el mismo con dos chats web a la vez: si sale bien 3 veces seguidas, se deja encendido.

**La extensión pasa a la versión 0.9.0:** en `chrome://extensions`, pulsa ↻ en «webllm puente».

## Cómo se usa

1. En Open WebUI, arriba, elige **webllm · Comité** (sale el primero de la lista).
2. Escribe la idea o el problema que quieres evaluar, y adjunta archivos si hace falta.
3. webllm contesta con **el plan, y no envía nada todavía**:
   - quién participa, con qué rol y cómo: su modelo más potente, y «pensar» si su web lo tiene;
   - las reservas (entran si alguna falla);
   - quién escribirá el documento final y, si falla, **qué otras podrían escribirlo** (todas las que podrían leer tu idea salen nombradas);
   - **cuántos mensajes gasta de cada cuenta** y cuánto tardará, más o menos;
   - si adjuntaste archivos, **a qué empresas irán y quién ve cuál**:
     - los chats web ven todos;
     - por API solo van las imágenes;
     - a una reserva, solo si entra;
     - quien escribe el documento final no recibe ninguno;
   - quién no entra y por qué (sin conectar, sin configurar, en pausa, sin mensajes hoy…).
4. Contestas:
   - **adelante**: se lanza exactamente ese plan;
   - **cancela**: no se hace nada;
   - **con 3** o **con 5**: otro plan, con ese número;
   - **sin pensar** o **con pensar**: otro plan.

   Si entre el plan y tu «adelante» ha cambiado quién está disponible (por ejemplo, un chat entró en pausa), **no se lanza nada** y te enseña el plan nuevo.
5. Mientras trabaja, en el bloque plegable **«Pensando…»** ves qué hace cada IA:
   - recibe su rol, lo confirma;
   - da su veredicto;
   - si alguna falla, entra una reserva;
   - el recuento y quién escribe el documento.
6. La respuesta es **el documento de fusión**:
   - arriba, el recuento que hace webllm;
   - después, los 8 apartados: resumen, veredicto, en qué coinciden, en qué discrepan (y qué rol lo dice), riesgos, condiciones, recomendación y próximos pasos;
   - al final, quién lo escribió.
7. En la línea de estado de la respuesta sale **qué se usó de verdad**: cada IA con su rol, el modelo que confirmó su web y los mensajes que gastó.
8. Si tienes la memoria encendida, se guarda en tu vault, en **`Comités/`**, con un **anexo**: cada veredicto con el nombre de su IA, y el sello del registro.

**En la app de webllm**, en el Inicio, está la tarjeta **«El Comité»**:
- quién entraría si lo lanzas ahora;
- 3 o 5 IAs;
- «pensar» sí o no;
- dos chats web a la vez (apagado: sin probar en tu PC);
- los 5 roles, que puedes cambiar («Cambiar los roles») o devolver a los de webllm.

El **Historial** enseña cada Comité con su idea como título, cada respuesta con su rol, y el candado verde.

## Qué hace por dentro (el protocolo del plan)

1. **Rol (turno 1).** Cada IA recibe su rol: mandato, reglas, escepticismo, formato cerrado y máximo de palabras. Termina con «responde únicamente: CONFIRMO: <rol>».
   - Si no lo confirma, se le pide otra vez, más corto, en la misma conversación.
   - Si tampoco, **entra una reserva con el mismo rol**. El problema nunca llega a la que no confirmó.
2. **Problema (turno 2, en la misma conversación).**
   - Va dentro de un bloque marcado como **datos, no órdenes**. Su marca de cierre lleva un código al azar, así que un texto que diga «olvida tu rol» (o que intente cerrar el bloque) se queda dentro y no manda nada.
   - Se pide el veredicto con el formato fijo: VEREDICTO, CONFIANZA, FORTALEZAS, RIESGOS, CONDICIONES, EN UNA FRASE.
3. **Comprobación del veredicto.**
   - Sin «VEREDICTO:» con **un solo** valor (copiar la plantilla con los tres no vale), se pide una vez que lo rehaga.
   - Si sigue mal, se descarta, se dice por qué y entra una reserva.
4. **Recuento, nunca empatado.** Cuenta **a favor** (aprobar y aprobar con condiciones) contra **en contra** (rechazar), siempre con un número impar.
   - Si entre los dos «a favor» hay empate, gana **el más prudente**: con condiciones.
   - Si se acaban las reservas y quedan 4 veredictos válidos, cuentan 3 y el cuarto sale como «no cuenta en el recuento».
5. **Fusión.**
   - La escribe la primera IA disponible de la lista de fusión **que no haya participado**. Si no queda ninguna, una que participó, y el documento lo dice.
   - Recibe los veredictos **por su rol, nunca por su IA**: webllm quita de su texto los nombres de las IAs, sus modelos, familias y empresas. Así no favorece a los suyos.
   - Recibe también el recuento, que copia tal cual.
   - Si faltan apartados, se le pide una vez que lo rehaga.
6. **Todo queda en el registro**, con candado: cada mensaje, cada respuesta, el recuento y quién entró por quién.

## La misma conversación en los chats web (extensión 0.9.0)

El turno 2 vuelve a **la misma conversación** del chat (su dirección), no abre un chat nuevo:
- **Si la web ya no tiene esa conversación** (te manda a un chat nuevo), **no se escribe nada** y lo dice. Ese miembro sale y entra una reserva.
- **Una dirección de otra web se rechaza** sin abrirla.
- **En el turno 2 no se toca el modelo ni los modos:** se eligieron y comprobaron en el turno 1. Cambiarlos a mitad podría abrir un chat nuevo en algunas webs.
- **Se lee la respuesta nueva, nunca la que ya estaba.** Cuenta como respuesta nueva solo un botón de «copiar» nuevo (o, en webs sin él, una respuesta nueva con texto). Si lo que se lee es igual a lo que había, dice «no dio una respuesta nueva» y no lo pasa por bueno.

## Seguridad (lo que no se ve)

- **Nada se envía antes de tu «adelante»**, y lo que se lanza es exactamente el plan que viste.
- **El guardián de tus cuentas cuenta cada mensaje** (2 por chat web, más los que haya que repetir), con su espaciado y su tope del día.
- **Los archivos van solo con el problema** (turno 2), nunca con el rol ni al documento final.
  - A las IAs por API solo les llegan imágenes.
  - El plan dice exactamente quién ve cuál, reservas incluidas.
  - Una IA de tu PC los lee sin que salgan de él.
- **Solo IAs privadas:** nunca una web que publica lo que escribes (Arena, Google AI Studio). Nunca Claude ni ChatGPT directos.
- **Lo que escribe una IA es un dato:** solo se mira su formato; nunca se obedece.
- «Parar todo» para el Comité: no se envía nada más, y el chat que estaba escribiendo recibe su «parar».

## Decisiones tomadas (y por qué)

- **El recuento es a favor contra en contra.** Con tres valores posibles, un número impar no basta: 1-1-1 sería un empate. A favor contra en contra, con número impar, nunca empata. Entre las dos clases de «a favor», el empate va a la prudente.
- **Las listas del Comité y de fusión son las de la sección 6 del plan.** Las que aún no están configuradas (GLM-5.2, Mistral Large y Gemini Flash por API) salen en el plan como «sin configurar». Detrás van las APIs que ya tienes (z.ai, groq, Nemotron). F8 las medirá con tus cuentas.
- **«Pensar» y el modelo más potente se piden solo si la Ficha del chat los conoce** (su «Descubrir»). Pedir un modo que la web no tiene haría que no se enviara nada. Si no los conoce, el plan dice «el modelo que tenga puesto su web».
- **Dos chats web a la vez: apagado por defecto.** Nunca se ha probado en tu PC. El interruptor está en la tarjeta del Comité, y el plan de trabajo pide 3 pruebas seguidas antes de dejarlo encendido.
- **Las confirmaciones de rol («CONFIRMO: …») no van a tu vault como respuestas.** Son un saludo, no una respuesta, y ensuciarían tu base de conversaciones. Siguen en el registro.
- **El Comité vive en Open WebUI.** En la app de webllm está su tarjeta de ajustes, pero no se lanza desde «Preguntar».

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| El plan antes que nada: quién, rol, modelo y «pensar», reservas, fusión, coste, tiempo; nada enviado | **Bien** | aquí |
| «con 3», «cancela», «adelante» sin plan, un «sí» que no es una idea nueva | **Bien** | aquí |
| Menos de 3 disponibles: lo dice y no envía nada | **Bien** | aquí |
| Un Comité entero: rol → CONFIRMO → problema → veredicto → recuento → fusión; turno 2 en la misma conversación; las APIs reciben la conversación entera | **Bien** | aquí |
| **Rol mal confirmado → se pide otra vez → reserva** (el problema nunca le llegó) | **Bien** | aquí |
| **Veredicto mal formateado → se rehace; si sigue mal → descartado y reserva** | **Bien** | aquí |
| **Nunca empate** (4 válidos: cuentan 3) y la regla a favor / en contra | **Bien** | aquí |
| **«Olvida tu rol» dentro del problema no cambia nada** (una IA que obedece lo que va fuera del bloque) | **Bien** | aquí |
| **La fusión no recibe ningún nombre de IA** (ni modelo, ni familia, ni empresa) | **Bien** | aquí |
| Rompiendo a propósito cada protección, su prueba falla: inyección (1 falla), nombres en la fusión (2), impar (5), a quién van tus archivos (1), dos chats a la vez (1) | **Bien** | aquí |
| «Parar todo» a mitad: nada más se envía, sin fusión, registro cerrado | **Bien** | aquí |
| Un archivo: el plan dice a qué empresas (y a cuál más si entra la reserva); solo va con el problema | **Bien** | aquí |
| **Una imagen y un PDF: el plan dice que por API solo se ve la imagen, y es exactamente lo que se envía** (el documento final no recibe ninguno) | **Bien** | aquí |
| Cambia quién está disponible entre el plan y «adelante»: plan nuevo, nada enviado | **Bien** | aquí |
| Una web pierde la conversación entre turnos: no se escribe nada, entra una reserva | **Bien** | aquí |
| Roles como plantillas (cambiar, 3 o 5, volver a los de webllm) | **Bien** | aquí |
| **«Dos chats web a la vez»: apagado escribe 1 chat a la vez; encendido, 2 y nunca 3** | **Bien** | aquí |
| **Dos turnos en el mismo chat** con la extensión de verdad | **Bien** | Chromium |
| Conversación perdida: nada escrito; dirección de otra web: rechazada | **Bien** | Chromium |
| **Una web que tarda 15 s en empezar y no enseña «parar»: se lee la respuesta nueva** | **Bien** | Chromium |
| En Open WebUI: el Comité en el selector, el plan, «adelante», el progreso, el documento con sus 8 apartados, el candado, el vault con anexo | **Bien** (5 de 5) | Open WebUI de verdad |
| Un Comité real de 5 sobre una idea tuya | Pendiente | tu PC |
| Dos chats web a la vez, 3 veces seguidas | Pendiente | tu PC |

### La prueba de que falla con el código anterior

`tests/extension/conversation_flow.mjs` con la extensión 0.8.0 (la de F6). La 0.8.0 no sabía volver a una conversación: cada pregunta abría un chat nuevo, y la segunda respuesta era «Respuesta 1», no «Respuesta 2»:

```
BIEN  la extensión 0.8.0 se conecta al puente
FALLO dos turnos en el mismo chat: «Respuesta 1 a «Primera pregunta»» y luego «Respuesta 1 a «Segunda pregunta»», en /conversa/c/889xyr; en la página: ["Segunda pregunta"]; el guardián contó 2
FALLO si la web ya no tiene la conversación, no se escribe nada y lo dice: undefined — «undefined»
FALLO una dirección de otra web se rechaza sin abrirla ni escribir nada: undefined
FALLO una web que tarda 15 s en empezar (como un modelo que piensa) y no enseña «parar»: se lee la respuesta nueva («Respuesta 1 a «Dos»», 8 s), no la que ya estaba
```

Y con la 0.9.0 pero con **solo la regla vieja de esperar la respuesta** (para aislar ese arreglo):

```
FALLO una web que tarda 15 s en empezar (como un modelo que piensa) y no enseña «parar»: se lee la respuesta nueva («Respuesta 1 a «Uno»», 14 s), no la que ya estaba
```

Es decir: con la regla vieja, un modelo que tarda en empezar a escribir devolvía **la respuesta anterior como si fuera la nueva**, sin avisar. En el Comité eso habría sido un veredicto equivocado atribuido a quien no lo dio.

## Lo que encontré y arreglé por el camino

1. **La respuesta anterior pasaba por nueva** (arriba). Dos causas:
   - la extensión daba por empezada la respuesta en cuanto la página cambiaba, aunque el cambio fuera tu propio mensaje;
   - leía con el último botón de «copiar», que todavía era el de la respuesta anterior.

   Ahora hace falta un botón de copiar nuevo, o una respuesta nueva con texto.
2. **Una prueba que pasaba por suerte.** Con 9 s de espera, la regla vieja también pasaba, porque se rendía a los 11,5 s. Con 15 s (lo normal en un modelo que piensa) se ve el fallo. La prueba se quedó en 15 s.
3. **Un error dentro del Comité cortaba la respuesta de Open WebUI a medias.** Ahora dice qué pasó, y lo que respondieron hasta ese momento queda en el historial.
4. **«No entran» enseñaba nombres internos** («kimi», «glm-5.2»). Ahora dice «sin conectar: Kimi, Duck.ai; sin configurar: GLM-5.2 (API)…».
5. **El Historial titulaba «Comité» y enseñaba el texto de un solo rol como si fuera el de todos.** Ahora el título es la idea, y cada respuesta lleva su rol.
6. **El anexo ponía «(cuenta)»**, que se lee como «cuenta de usuario». Ahora pone «cuenta en el recuento».
7. **El plan no decía todo lo que sale de tu PC.** Al repasar este documento contra el código encontré tres huecos:
   - con una imagen y un PDF, el plan decía que las IAs por API no verían nada, pero sí recibían la imagen;
   - los archivos también llegan a una reserva si entra, y el plan no lo decía;
   - si falla quien escribe el documento final, lo escribe la siguiente de la lista, y el plan solo nombraba a la primera.

   Tu «adelante» vale para lo que el plan dice, y nada más. Ahora el plan lo dice todo, con una prueba que falla si vuelve la regla vieja (comprobado).
8. **La misma empresa salía con dos nombres** («Zhipu (z.ai)» en el chat y «z.ai» en la API), así que se contaba dos veces. Ahora es una.
9. **«Dos chats web a la vez» dejaba escribir a todos a la vez.** Con 3 chats web en el Comité, escribían los 3 a la vez. Ahora son dos como mucho, que es lo que dice el interruptor y lo que probarás. Una prueba mide cuántos escriben a la vez: 1 con el interruptor apagado, 2 encendido; con el código anterior medía 3.

## Límites (dichos claros)

- **El contador del día es prudente:** cuenta un mensaje en cuanto el guardián da permiso. Si luego no se escribe nada (una conversación perdida), ese intento cuenta igual.
- **Una web cuyas conversaciones no tienen dirección propia** (la dirección no cambia al empezar un chat) no puede hacer el turno 2.
  - Al volver, la web enseña un chat vacío: no se escribe nada y entra una reserva.
  - Se pierde su mensaje del rol, y el intento cuenta en el día.
  - No se intenta escribir en la pestaña tal como esté: entre los dos turnos esa pestaña puede estar enseñando otra conversación tuya.
  - Qué webs son así se verá en tu PC. Si alguna lo es, se quita de la lista del Comité.
- **Las listas son de partida.** GLM-5.2, Mistral Large y Gemini Flash por API no están configuradas todavía; F8 las mide con tus cuentas.
- **La «Recomendación final» la escribe una IA:** es su lectura de los veredictos. El recuento de arriba es de webllm, y no se puede cambiar.

## Para ti: cómo probarlo

1. Doble clic en **`ACTUALIZAR`**.
2. En `chrome://extensions`, pulsa **↻** en «webllm puente» (versión **0.9.0**).
3. Doble clic en **`herramientas\poner-en-openwebui.cmd`** otra vez. Así Open WebUI recibe «webllm · Comité».
4. En la app de webllm, en **Conectores**, pulsa **«Descubrir»** en la Ficha de cada chat que quieras en el Comité. Así webllm sabe su modelo más potente y si tiene «pensar».
5. En Open WebUI:
   1. elige **webllm · Comité** y escribe una idea tuya de verdad;
   2. **qué deberías ver:** el plan con 5 IAs, sus roles, lo que gasta cada cuenta y el tiempo (nada enviado todavía);
   3. escribe **adelante** y espera (varios minutos: los chats web van de uno en uno);
   4. **qué deberías ver:** el documento con sus 8 apartados; en tu vault, `Comités/` con el anexo; en el Historial, el candado verde.
6. Cuando eso salga bien: en la app, tarjeta **«El Comité»**, enciende **«Dos chats web a la vez»** y repítelo **3 veces**.
   - Si sale bien las 3, se queda encendido.
   - Si falla alguna, apágalo y dímelo.
