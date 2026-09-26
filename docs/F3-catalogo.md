# F3 — Todos los chats web, precargados (26-sep-2026)

**Resultado en la nube: todo lo que el plan pide probar aquí, bien.** Las 27 IAs del catálogo (sección 6 del plan) vienen precargadas en la app, y «Conectar varias» funciona de principio a fin con la extensión de verdad. **Desde la nube no se puede abrir ninguna web real**, así que cuántas funcionan con webllm solo se sabe en tu PC (abajo).

## Qué hay

- **Una pantalla nueva en la app: «Conectores»**, como «Ajustes → Conectores» de ChatGPT. Arriba salen tus chats conectados y debajo el resto, en tres grupos:
  - **Sin conectar**;
  - **No funcionan todavía**, con el motivo;
  - **No las quieres**.
- **Cada tarjeta** dice para qué sirve la IA y lo que conviene saber:
  - **«No privada»** en Arena y Google AI Studio;
  - **«Puede fallar»** y por qué, en las 6 del grupo 2;
  - si pide cuenta o no;
  - su tope si es más bajo: Venice, 10 al día; Poe, 15.
- **«Conectar varias»:**
  1. vienen todas marcadas, y desmarcas las que no quieras (quedan como «No la quiero», y puedes conectarlas cuando quieras);
  2. Chrome te pide permiso **una sola vez** para todas las marcadas;
  3. la ventanita de webllm las abre **de una en una**. Si una te pide entrar, **te la pone delante y te espera 3 minutos**: entras tú, porque webllm no escribe contraseñas. Si no entras, queda «Sin conectar» y pasa a la siguiente;
  4. cada una recibe un mensaje de prueba («pong»), que pasa por el guardián y cuenta en su tope del día;
  5. al final ves el resultado de cada una: «Conectada», «Sin conectar» o «No funciona todavía» con el motivo. El diagnóstico de la página se guarda para la autorreparación (F6);
  6. **Parar** suelta la que se está probando y no prueba más.
- **Solo las conectadas salen** en Open WebUI y en Preguntar.
- **Las no privadas** llevan el aviso en su nombre en Open WebUI («Arena (chat directo) (web, no privada)») y en su ficha. «Automático» y el Comité nunca las eligen por su cuenta: la regla ya está escrita y probada para cuando existan (F7, F8).
- **«Copiar el resumen»** (abajo del todo en Conectores) copia la tabla de las 27 con lo que pasó en tu PC. Pégamela y la apunto en `ESTADO.md` (es la salida de F3).
- **Si pegas en «+ Añadir otra IA» la dirección de una de la lista** (por ejemplo `chat.mistral.ai`), se conecta como la de la lista: con su nombre («Le Chat»), su tope y su privacidad.

## Dos decisiones mías que debes conocer

- **Google AI Studio sale como «no privada»**, igual que Arena. El plan solo marcaba así a Arena, pero su propia nota dice que «Google puede usar lo que escribas». Así, ni «Automático» ni el Comité la usarán solos. Si no estás de acuerdo, es un cambio de una línea en `catalog.yaml`.
- **Las 4 de siempre** (Qwen, DeepSeek, z.ai, Meta) están en el catálogo, pero se siguen conectando con su «Conectar» de siempre (comprobar la sesión), no con «Conectar varias».

## Cosas que la extensión (0.6.0) sabe hacer ahora

- **Una web que te manda a otra dirección para entrar** (Google, Microsoft, X…) se trata como «te pide entrar». webllm no lee esa página, ni tiene permiso para ello: espera a que vuelvas a la web del chat.
- **Una web que se ha mudado** a otra dirección que no es de acceso (por ejemplo, si Duck.ai te lleva a duckduckgo.com) no se queda esperando 3 minutos. Dice «te lleva a otra dirección (…)» y lo guarda para corregir la lista. Si la quieres ya, añádela con «+ Añadir otra IA» y esa dirección.

## Pruebas

| Qué | Resultado | Dónde |
|---|---|---|
| Las 27 del plan (4 + 17 + 6), direcciones https ya normalizadas, ninguna repetida | **Bien** | aquí (`tests/test_catalog.py`) |
| Ninguna pasa el bloqueo (`claude.ai`, `chatgpt.com`…), ni ninguna de las que el plan deja fuera | **Bien** | aquí |
| Cada IA tiene familia, etiquetas y para qué sirve; las del grupo 2, su motivo | **Bien** | aquí |
| Las no privadas nunca las eligen «Automático» ni el Comité | **Bien** (la regla, `catalog.eligible_for_auto`) | aquí |
| Topes propios: Venice 10, Poe 15; el guardián los aplica | **Bien** | aquí |
| «Conectar varias» en el servidor: un permiso, de una en una, cada resultado, el diagnóstico guardado, «No la quiero», sin permiso no se prueba nada, no entrar a tiempo, Parar, extensión antigua, Quitar | **Bien** (7 pruebas, `tests/test_conectores.py`) | aquí |
| **Con la extensión de verdad en Chromium** y 5 webs de prueba: **una sola petición de permiso** para las cinco; la primera conecta; la que pide entrar se pone delante, espera, **webllm no escribe nada** en la pantalla de acceso, y conecta cuando «entras»; la que te manda a otra dirección para entrar (como Google) te espera allí y conecta al volver; la que se ha mudado dice adónde lleva sin esperar; la que no tiene caja queda «No funciona todavía» con su diagnóstico; las conectadas contestan preguntas | **Bien** (13 de 13, `tests/extension/catalog_flow.mjs`) | aquí, en Chromium. El aviso de permiso de Chrome se simula (como en 7b) |
| Capturas en claro y oscuro, sin fallos de diseño | **Bien** (61 capturas, 0 problemas) | aquí (`docs/capturas/f3/`) |
| **Cuántas de las 27 funcionan de verdad** | **Falta** | tu PC |

## Para ti: cómo probarlo en tu PC

1. Doble clic en `ACTUALIZAR`.
2. En `chrome://extensions`, pulsa **↻** en «webllm puente». Debe poner **0.6.0**.
3. Abre la app (`WEBLLM`) → **Conectores** (en el menú de la izquierda).
4. Pulsa **Conectar varias**. Desmarca las que no quieras y pulsa **Conectar N**.
5. En la pestaña que se abre, pulsa **Permitir y conectar**, y en el aviso de Chrome, **Permitir** (una sola vez).
6. Deja la ventanita de webllm a la vista. Si una te pide entrar, entra tú en ella (tienes 3 minutos). Tarda más o menos 1 minuto por web.
7. Al terminar, pulsa **Copiar el resumen** (abajo del todo) y pégamelo. Con eso relleno la tabla de `ESTADO.md` y arreglo las que no funcionen.
8. Para que las nuevas reciban archivos e interruptores en Open WebUI, vuelve a hacer doble clic en `herramientas\poner-en-openwebui.cmd`. Sin eso también salen y responden.

**Riesgo para tus cuentas:** algunas webs prohíben en sus normas el uso automático. El guardián lo frena (una a la vez, 20 s entre mensajes, tope diario), pero no lo elimina.
