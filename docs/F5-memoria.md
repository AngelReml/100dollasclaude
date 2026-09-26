# F5 — Tu memoria en Obsidian (26-sep-2026)

**Resultado en la nube: hecho y probado, también en el Open WebUI de verdad (6 de 6).** Falta lo que solo se ve en tu PC: abrir Obsidian y ver la conversación de hace un minuto, y verla también desde el móvil si tu vault está en Drive.

## Tu decisión (26-sep-2026)

> «Quiero que escriban un vault, donde sea, pero quiero registro de chat principal y, en paralelo pero separado, cada respuesta por individual de cada IA […] con fecha como título.»

Así está hecho:
- **El vault puede estar donde quieras:** en tu PC o dentro de Google Drive.
- **Cada conversación** tiene su nota, que es el registro de chat principal.
- **Aparte, cada respuesta de cada IA** tiene su propio archivo, con la **fecha y la hora como título**.

## Qué hay nuevo

- **En la app, en el Inicio, la tarjeta «Memoria en Obsidian».** Escribes la carpeta de tu vault (por ejemplo `G:\Mi unidad\Obsidian` o `C:\Users\…\Obsidian`) y pulsas **«Encender la memoria»**. Desde ese momento, todo lo que preguntes se guarda ahí mientras ocurre.
- **Qué escribe y dónde.** Siempre dentro de una carpeta suya, `webllm`, para no tocar nunca tus notas:

  ```
  <tu vault>\webllm\
    Índice.md                                    todas las conversaciones, por proyecto
    Clientes 2026\2026-09-26 Plan de clientes.md una conversación (su carpeta = su carpeta en Open WebUI)
    Sin proyecto\2026-09-26 ¿Qué es la inflación.md
    Desde webllm\…                               lo que preguntas desde la app de webllm o con PREGUNTAR
    Respuestas\Qwen\2026-09-26 14.05.12 Qwen - ¿Qué es la inflación.md    cada respuesta, suelta
    Respuestas\z.ai\2026-09-26 14.06.40 z.ai - ¿Cuánto es 2 más 2.md
    Adjuntos\<pregunta>\informe.pdf              tus archivos y lo que generó un chat
    Comités\                                     los documentos del Comité (F7)
  ```

- **La nota de la conversación:**
  - lleva tus preguntas con fecha y hora;
  - lleva cada respuesta tal cual, con quién respondió, el modelo (si se sabe) y los segundos que tardó;
  - si una IA no respondió, lo dice («Sin respuesta. Lo has parado tú.»);
  - cada respuesta enlaza a su archivo suelto;
  - se rehace con cada respuesta, y lo avisa arriba: **lo que cambies en ella se pierde**.
- **El archivo de cada respuesta.** Su nombre empieza por la fecha y la hora, así se ordenan solos: `2026-09-26 14.05.12 Qwen - ¿Qué es la inflación.md`. Dentro lleva:
  - **arriba, las «propiedades»** que Obsidian enseña: fecha, IA, modelo, modos, proyecto, conversación, pregunta, registro y huella;
  - **la pregunta**;
  - **la respuesta, exactamente la del registro de webllm, letra por letra**.

  Se escribe **una vez** y webllm no lo vuelve a tocar: si le añades una nota tuya, se queda. Cada archivo es una respuesta completa con su pregunta, así que sirve tal cual para tu base de conversaciones en LM Studio.
- **El proyecto es la carpeta de Open WebUI** donde tienes la conversación. Una conversación sin carpeta va a «Sin proyecto».
- **El título es el de Open WebUI.** Si lo cambias, cambia dentro de la nota, pero el nombre del archivo se queda para que los enlaces de Obsidian no se rompan. El título provisional de Open WebUI («New Chat») no se usa: en su lugar va tu pregunta.
- **Se escribe mientras ocurre.** Tu pregunta está en la nota antes de que llegue la respuesta («esperando la respuesta…»).
- **Tus adjuntos y lo que genera un chat** (una página, un informe…) se copian a `Adjuntos`. Solo se copian si siguen teniendo la misma huella que apuntó el registro.
- **«Copiar también lo de antes».** Pasa al vault lo que preguntaste antes de encender la memoria (webllm lo tiene todo en su registro), cada pregunta en su conversación y en su orden. Pulsarlo dos veces no duplica nada.
- **«Reescribir todo».** Vuelve a escribir todo desde el registro, por si borraste algo de la carpeta `webllm` o la quieres como el primer día. Antes te avisa de que lo que cambiaste a mano en esos archivos se pierde.
- **Cambiar de carpeta.** La carpeta nueva recibe todo lo que webllm ya había escrito, sin enlaces rotos.

## Seguridad (lo que no se ve)

- **Un solo escritor, que nunca lee.**
  - webllm escribe; nunca abre una nota del vault ni mira qué hay en sus carpetas.
  - Lo único que comprueba es que **la carpeta del vault sigue existiendo**. Si la has movido o Drive está cerrado, no la vuelve a crear donde estaba.
  - Sabe lo que escribió por su propia lista, guardada en `data\state`.
- **Nunca frena una pregunta.**
  - Escribe en segundo plano: con un Drive lento, la respuesta llega igual de rápido.
  - Si la carpeta no está, la pregunta funciona igual y la tarjeta pone **«No puede escribir»** y por qué.
  - Cuando la carpeta vuelve, escribe lo que faltaba.
- **Nunca medio archivo.** Cada archivo se escribe aparte y se cambia de golpe, así Drive y Obsidian nunca ven una nota a medias.
- **Nada ejecuta lo que escribe una IA** (regla 5). Algunos complementos de Obsidian ejecutan código solos:
  - Templater, con «Trigger on new file creation» activado, ejecuta lo que va entre `<%` y `%>` en cada archivo nuevo;
  - Dataview ejecuta sus bloques `dataviewjs` y sus consultas `$=`.

  Una respuesta podría traer eso. webllm lo **desactiva de forma visible** en la copia del vault, lo dice en la propia nota y en sus propiedades («desactivado»), y el original sigue en su registro con la misma huella. El resto del código (python, etc.) queda igual.

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| Una conversación en una nota, escrita mientras ocurre, idéntica al registro (tablas, código, emoji, fórmulas) | **Bien** | aquí |
| **10 conversaciones seguidas, las 10 en el vault, idénticas al registro** (la salida de F5), y sus 10 respuestas sueltas | **Bien** | aquí |
| Cada respuesta de cada IA en su archivo, con la fecha como título, **byte a byte** igual al registro; tu nota en ese archivo se respeta; «Reescribir todo» lo devuelve | **Bien** | aquí |
| Títulos raros: CON, nul.txt, `a/b:c*?"<>\|#^[]%`, emoji, chino, 300 letras, «Tema» y «tema» | **Bien** | aquí |
| **Ni una lectura del vault:** vigiladas todas las formas de abrir para leer y de listar carpetas, con preguntas, adjuntos, Comité y cambio de carpeta | **Bien** | aquí |
| Drive cerrado: la pregunta sigue, la carpeta no se vuelve a crear, la app dice por qué, y al volver escribe lo que faltaba | **Bien** | aquí |
| Drive lento (3 s por archivo): la respuesta llega sin esperar | **Bien** | aquí |
| Lo que un complemento de Obsidian podría ejecutar queda desactivado, y el original se puede recuperar exacto | **Bien** | aquí |
| «Copiar también lo de antes»: Open WebUI, la app y PREGUNTAR, en su orden, sin duplicar; 60 preguntas escriben la lista de webllm pocas veces, no 60 | **Bien** | aquí |
| Un archivo ocupado un momento por otro programa (Windows no deja reemplazarlo): webllm lo reintenta y no da un falso fallo | **Bien** (simulado) | aquí |
| **Open WebUI de verdad:** una conversación en su carpeta «Clientes 2026» aparece en `webllm\Clientes 2026\` mientras Qwen escribe; «Detener» queda anotado; la respuesta suelta es idéntica al registro y a lo que enseña Open WebUI; una sin carpeta va a «Sin proyecto» | **Bien** (6 de 6) | aquí, en pantalla |
| La tarjeta de la app, en claro y oscuro | **Bien** (0 problemas de maquetación) | aquí |
| Obsidian abierto de verdad, y el móvil por Drive | **Falta** | tu PC |

Batería completa: **267 correctas, 0 fallos** (con Open WebUI de verdad y la extensión real en Chromium). Pruebas: `tests/test_vault.py` (14), `tests/openwebui/f5_checks.mjs` (6, dentro de `tests/test_openwebui_face.py`), `tests/test_openwebui_pipe.py` (la carpeta y el título que manda Open WebUI). Capturas: `docs/capturas/f5/` (33 a 36: la tarjeta apagada, guardando, «lo de antes» y «Reescribir todo») y `docs/capturas/f5/openwebui/`.

## Límites (dicho claro)

- **Obsidian no se puede abrir en la nube.** Los archivos son Markdown normal y los enlaces son relativos (`[texto](<../Respuestas/…>)`), que Obsidian entiende estén donde estén. Lo tienes que ver tú.
- **Drive:** webllm escribe en la carpeta; subirla a la nube y bajarla al móvil lo hace Google Drive, a su ritmo.
- **Lo que preguntas con la memoria apagada** no se escribe hasta que pulsas «Copiar también lo de antes».
- **Las conversaciones de antes de hoy** no saben su carpeta de Open WebUI: van a «Sin proyecto». Desde hoy, webllm lo apunta en su registro.
- **Si mueves una conversación a otra carpeta en Open WebUI,** su nota se queda donde nació, para no romper enlaces.
- **aider** (PROGRAMAR) no va al vault: sus mensajes son de programar, no conversaciones.
- **Imágenes o páginas de internet dentro de una respuesta** se cargan al abrir la nota, como en cualquier nota de Obsidian. webllm no las quita porque muchas son legítimas; lo que sí desactiva es lo que se ejecutaría solo.
- **Windows y el reintento:** «archivo ocupado» está simulado aquí; en Windows de verdad se verá en tu PC.

## Para ti: cómo probarlo en tu PC

1. Doble clic en `ACTUALIZAR`.
2. Doble clic en `herramientas\poner-en-openwebui.cmd`, para que Open WebUI mande la carpeta y el título de cada conversación.
3. En la app de webllm, en el Inicio, busca la tarjeta **«Memoria en Obsidian»**:
   - escribe la carpeta de tu vault;
   - pulsa **«Encender la memoria»**. Debe poner **«Guardando»**.
4. En Open WebUI, crea una carpeta (por ejemplo «Pruebas»), abre una conversación dentro y pregunta algo a Qwen.
5. En Obsidian, abre `webllm\Pruebas\…`:
   - debe estar la conversación, con tu pregunta y la respuesta;
   - y en `webllm\Respuestas\Qwen\` debe estar la respuesta suelta, con la fecha y la hora como título.
6. Si tu vault está en Drive, ábrelo desde el móvil y busca el mismo archivo.
7. Si quieres tu historial, pulsa **«Copiar también lo de antes»**.
8. Si algo sale distinto, mándame una captura de la tarjeta y `data\logs\bridge.log`.
