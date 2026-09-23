# ESTADO — webllm-agent v2 (24-sep-2026)

> 🚧 **EN CONSTRUCCIÓN.** Hoy funciona con IAs por API: z.ai (GLM-4.7-Flash), groq y OpenRouter gratis.
> Qwen, DeepSeek y Meta AI todavía **no están conectadas**: faltan los pasos
> de la sección "Lo que tienes que hacer tú".

## Los mandamientos

1. **Primero enciende OmniRoute.** Doble clic en `start-omniroute.cmd`. Se queda en una ventana minimizada llamada "OmniRoute". Para apagarlo: `stop-omniroute.cmd`.
2. **Para preguntar a tus IAs:** doble clic en `preguntar.cmd`.
   - Escribe la pregunta y deja una línea vacía.
   - Elige `todas` o el nombre de una IA.
3. **Desde la terminal**, en la carpeta del proyecto:
   - `webllm.cmd ask "tu pregunta" --to todas`
   - `webllm.cmd ask "tu pregunta" --to qwen` (o `deepseek`, `zai`, `meta`, `groq`, `nemotron`)
   - `webllm.cmd status`: qué IAs hay, cuáles están en pausa y cuántos envíos llevas hoy.
4. **Cada envío queda apuntado** en `data/runs/<fecha-hora>/`: tu pregunta, cada respuesta y un diario encadenado. Para comprobar que nadie lo ha tocado: `webllm.cmd journal verify --all`.
5. **Para que una IA cambie código en una carpeta:**
   - abre una terminal en esa carpeta;
   - ejecuta `"C:\Users\angel\Desktop\proyectos ia\minimax3 coding\aider-omniroute.cmd"`;
   - pide el cambio en lenguaje normal.
   Cada cambio se guarda con git, así que se deshace con `/undo`. Si aider quiere ejecutar un comando de terminal, **siempre te pregunta antes**.
6. **Si una IA web se pone en pausa**, `webllm` te dice por qué y qué paso repetir en el panel. Cuando lo arregles: `webllm.cmd guard clear <nombre>`.
7. **Nunca** pases Claude ni ChatGPT/Codex por aquí: `webllm` los rechaza aunque lo pidas.

## Qué funciona hoy (comprobado el 24-sep-2026)

| Pieza | Estado | Prueba |
|---|---|---|
| OmniRoute 3.8.50 en 127.0.0.1:20128 | OK | `/v1/models` HTTP 200 (1218 modelos); arranca y para con los .cmd |
| Ruta por defecto `webllm-default` (GLM-4.7-Flash → groq → Nemotron gratis) | OK. Contesta z.ai; si z.ai dice "demasiadas peticiones", salta sola a groq | Prueba de ida y vuelta 3/3 (2 las contestó z.ai y 1 groq, tras un 429 de z.ai) |
| z.ai `glm-4.7-flash` | OK (entre 1,4 y 23 s) | Prueba de ida y vuelta 10/10 (24-sep-2026) |
| groq `openai/gpt-oss-120b` | OK | Prueba de ida y vuelta 5/5 |
| OpenRouter `nemotron-3-super-120b-a12b:free` | OK (tarda entre 7 y 18 s) | Prueba de ida y vuelta 5/5 |
| OpenRouter `glm-5.2:free` | Inestable: 3 de 5, dos 429 por saturación | Desactivado en `data/config.yaml` |
| aider 0.86.2 + OmniRoute | OK | En el repo de prueba, el test pasa de rojo a verde con commit |
| `webllm ask --to todas` | OK: 2/2 respondieron | Registro verificado |
| Tests automáticos | 59 de 59 | `python -m pytest -q` |

La "prueba de ida y vuelta" pide a la IA que devuelva un bloque con trampas (tabuladores, espacios al final, ñ/€, comillas y acentos graves) y lo compara byte a byte. Cada prueba va sin caché, sin "memoria" y sin compresión de OmniRoute, para que cuente como una llamada real.

## Qué está bloqueado y por qué

| Pieza | Estado | Qué falta |
|---|---|---|
| Qwen web | BLOQUEADO POR IVÁN | Pegar la cookie en el panel (punto 4 de la lista) |
| DeepSeek web | BLOQUEADO POR IVÁN | Pegar el userToken (punto 3) |
| Meta AI web | BLOQUEADO POR IVÁN | Pegar `ecto_1_sess` y el token `ecto1:` (punto 5) |
| z.ai GLM-4.7-Flash | **CONECTADO** el 24-sep-2026 | Falta confirmar que no gasta saldo: mira el consumo en tu cuenta de z.ai. OmniRoute no lo muestra ("No quota information available"): [FALTA DATO] |
| DeepSeek API (de pago) | DESCARTADO | Sin saldo (decidido el 24-sep-2026); fuera de la ruta por defecto |
| Límites nativos de OmniRoute para las webs + interruptor anti-reintento | Preparado | Se aplican con `python scripts/apply_web_limits.py --apply` cuando existan las conexiones |
| Plan B (extensión de Chrome) | No hace falta | Ninguna IA ha fallado por diseño. El diseño está en `docs/plan-b.md` |

## Lo que tienes que hacer tú

Las claves y las sesiones son como contraseñas: Claude no puede copiarlas ni pegarlas
aunque se lo pidas. Lo que sí hace es dejártelo en "copiar y pegar" con enlaces directos.

1. ~~Entrar al panel de OmniRoute~~ **HECHO** (24-sep-2026).
2. ~~z.ai~~ **HECHO** (24-sep-2026): conexión `zai` activa y prueba de ida y vuelta 10/10.
   Solo te queda mirar en tu cuenta de z.ai que el consumo de GLM-4.7-Flash sale a 0.
3. **DeepSeek.** Es el más fácil:
   1. En tu Chrome normal, entra en https://chat.deepseek.com con tu cuenta.
   2. Pulsa **F12** y elige la pestaña **Console**.
   3. Si Chrome te avisa de que no dejes pegar, escribe `allow pasting` y pulsa Enter.
   4. Pega esta línea y pulsa Enter: `copy(localStorage.getItem("userToken"))`. No sale nada, pero la sesión ya está copiada.
   5. Abre http://127.0.0.1:20128/dashboard/providers/deepseek-web?action=add-api-key, pega con Ctrl+V, pulsa **Check token** y guarda.
4. **Qwen:**
   1. En tu Chrome normal, entra en https://chat.qwen.ai con tu cuenta.
   2. Pulsa **F12**, elige la pestaña **Network** y pulsa **F5** para recargar.
   3. Haz clic en la **primera fila** de la lista (se llama como la página, `chat.qwen.ai` o `/`).
   4. A la derecha, en **Headers**, baja hasta **Request Headers** y busca la línea **cookie:**.
   5. Haz clic derecho sobre su valor → **Copy value**.
   6. Abre http://127.0.0.1:20128/dashboard/providers/qwen-web?action=add-api-key, pega, pulsa **Check cookie** y guarda.
5. **Meta AI.** Si tu cuenta de Meta es la del negocio, usa otra para Meta AI. Aquí se pegan dos cosas juntas.
   1. Entra en https://www.meta.ai con tu cuenta y pulsa **F12**.
   2. Pestaña **Application** → a la izquierda **Cookies** → `https://www.meta.ai` → fila **ecto_1_sess**. Copia su **Value**.
   3. Pestaña **Network** → pulsa el filtro **WS** → pulsa **F5** → haz clic en la fila **clippy** → pestaña **Payload**. Copia el valor de **Authorization** (empieza por `ecto1:`).
   4. Abre http://127.0.0.1:20128/dashboard/providers/muse-spark-web?action=add-api-key y escribe en el cuadro, en una sola línea: `ecto_1_sess=` + lo primero + `; ` + lo segundo. Queda así: `ecto_1_sess=AAAA...; ecto1:BBBB...`
   5. Pulsa **Check cookie** y guarda.
6. ~~¿Apagar el reintento tras un 429?~~ **RESUELTO SIN APAGARLO PARA TODOS.**
   - OmniRoute tiene un interruptor por conexión (`disableCooling`). Con él, esa conexión deja de reintentar tras un 429 y devuelve el error enseguida.
   - Se pondrá **solo en Qwen, DeepSeek y Meta**, con `scripts/apply_web_limits.py --apply`, en cuanto existan esas conexiones.
   - El reintento general sigue encendido, así que Hermes, Shinobi y las IAs por API no pierden nada.
7. ~~DeepSeek API de pago~~ **NO**: se ha quitado de la ruta por defecto.
8. **Cuando termines alguno de los puntos 2 a 5, avísame.** Entonces:
   - lo activo en `data/config.yaml`;
   - aplico los límites nativos y el interruptor del punto 6;
   - paso la prueba de ida y vuelta 10 de 10, con 20 s entre envíos.

Nota: los enlaces `?action=add-api-key` salen del código del panel. Claude no ha podido verlos por
dentro porque el panel pide contraseña. Si alguno no abre el cuadro, entra en **Providers**, busca el
proveedor y pulsa **Add Connection**.

## Riesgos conocidos

- **Tus cuentas.**
  - Los términos de DeepSeek y z.ai prohíben la automatización.
  - OmniRoute marca Qwen web y Meta AI web como **"avoid"** (evitar).
  - Lo aceptaste. El guardián lo limita: 1 envío a la vez, 20 s entre envíos, 150 al día y pausa de 6 h ante cualquier señal de bloqueo. Pero no lo elimina.
- **OmniRoute reintenta él solo:**
  - Tras un 429 lo hace hasta 3 veces. Queda resuelto para las webs con `disableCooling` en cuanto existan las conexiones (punto 6).
  - DeepSeek web, además, renueva el token y reintenta 2 veces tras un 401/403. Eso viene dentro de OmniRoute y no se puede desactivar por conexión.
- **Las webs cambian sin avisar:** cualquier proveedor web de OmniRoute puede romperse con una actualización de su web.
- **aider va lento en novedades:** la última versión es del 12-feb-2026. La alternativa para modelos por API es OpenCode.
- **z.ai también tiene límite de velocidad:**
  - Tras unas 15 peticiones seguidas en minuto y medio devolvió 429, código 1302 "Rate limit reached for requests".
  - La ruta `webllm-default` salta sola a groq.
  - Con `webllm ask --to zai`, OmniRoute espera unos segundos y reintenta (hasta 3 veces, su ajuste general para las IAs por API).
  - Si sigue fallando, `webllm` muestra el FALLO.
  - Límite exacto: [FALTA DATO] (z.ai no lo publica).
- **Los modelos gratis de OpenRouter** tienen tope (50 al día sin comprar créditos) y a veces están saturados (429).
- **OmniRoute trae de fábrica** la caché, la "memoria" y la compresión. `webllm` y aider las desactivan en cada petición; tus otros agentes no.

## Dónde está cada cosa

- `docs/spec.md`: el diseño v2.
- `docs/proveedores-web.md`: qué pide cada web, cómo caduca y su riesgo.
- `docs/plan-b.md`: la extensión de Chrome, solo si hace falta.
- `data/config.yaml`: nombres de IA, modelos, orden, límites.
- `legacy/`: el código viejo de Claude/Playwright, retirado.
- Copias de seguridad de OmniRoute: `C:\Users\angel\.omniroute-backup-20260923-235619` (antes de tocar nada) y `...-20260924-001841` (antes de crear la ruta `webllm-default`).
