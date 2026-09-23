# ESTADO — webllm-agent v2 (24-sep-2026)

> 🚧 **EN CONSTRUCCIÓN.** Hoy funciona con IAs por API (groq y OpenRouter gratis).
> Qwen, DeepSeek, Meta AI y z.ai todavía **no están conectadas**: faltan los pasos
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
| Ruta por defecto `webllm-default` (GLM-4.7-Flash → DeepSeek API → groq) | OK. Hoy contesta groq porque z.ai y DeepSeek API aún no tienen clave | Prueba de ida y vuelta 5/5 |
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
| Qwen web | BLOQUEADO POR IVÁN | Pegar la cookie en el panel (punto 3 de la lista) |
| DeepSeek web | BLOQUEADO POR IVÁN | Pegar el userToken (punto 4) |
| Meta AI web | BLOQUEADO POR IVÁN | Pegar `ecto_1_sess` y el token `ecto1:` (punto 5) |
| z.ai GLM-4.7-Flash (gratis) | BLOQUEADO POR IVÁN | Crear la API key (punto 2). No se sabe si el endpoint que usa OmniRoute da la versión gratis: [FALTA DATO] |
| DeepSeek API (de pago) | Opcional | Solo si quieres poner saldo (punto 7) |
| Límites nativos de OmniRoute para las webs | Preparado | Se aplican con `python scripts/apply_web_limits.py --apply` cuando existan las conexiones |
| Plan B (extensión de Chrome) | No hace falta | Ninguna IA ha fallado por diseño. El diseño está en `docs/plan-b.md` |

## Lo que tienes que hacer tú (una sola vez)

1. **Entrar al panel de OmniRoute:** http://127.0.0.1:20128 con tu contraseña. Claude no puede escribir contraseñas. Si la has olvidado, usa "¿Olvidaste tu contraseña?" en esa misma pantalla.
2. **z.ai (gratis):**
   - crea una API key en tu cuenta de z.ai;
   - en el panel: Providers → **Z.AI** → **Add Connection** → pega la clave → comprobar → guardar.
   - El panel dice que la clave sale de open.bigmodel.cn, pero OmniRoute llama a api.z.ai: usa la clave de z.ai.
3. **Qwen:**
   - en tu Chrome normal, entra en chat.qwen.ai con tu cuenta;
   - F12 → pestaña **Network** → recarga → pulsa cualquier petición a chat.qwen.ai;
   - en "Request Headers", copia el valor entero de **cookie** (tiene que llevar `cna`, `ssxmod_itna` y `token`);
   - en el panel: Providers → **Qwen Web** → **Add Connection** → pégalo (sin la palabra "Cookie:") → **Check cookie** → guardar.
4. **DeepSeek:**
   - en chat.deepseek.com con tu cuenta: F12 → **Application** → Local Storage → `https://chat.deepseek.com` → copia el valor de **userToken**;
   - en el panel: Providers → **DeepSeek Web** → **Add Connection** → pégalo → **Check token** → guardar.
5. **Meta AI.** Si tu cuenta de Meta es la del negocio, usa otra para Meta AI.
   - En www.meta.ai: F12 → Application → Cookies → copia **ecto_1_sess**.
   - Después: F12 → Network → filtro **WS** → petición `clippy` → copia el valor `ecto1:...` del parámetro `Authorization`.
   - En el panel: Providers → **Muse Spark Web (Meta AI)** → **Add Connection** → pega las dos cosas como pide el cuadro → comprobar → guardar.
6. **Decisión (sí/no):** ¿apago el reintento automático de OmniRoute tras un 429 (`waitForCooldown`)?
   - Hoy OmniRoute reintenta hasta 3 veces por su cuenta, también con las webs. Apagarlo protege más tus cuentas.
   - El cambio afecta a todo OmniRoute, así que también a Hermes y Shinobi.
7. **Opcional:** DeepSeek API de pago. Solo si quieres poner saldo: crea la clave en la web de DeepSeek → panel → Providers → **DeepSeek** → Add Connection.
8. **Cuando termines 2–5, avísame.** Entonces:
   - activo esas IAs en `data/config.yaml`;
   - les pongo los límites nativos;
   - paso la prueba de ida y vuelta 10 de 10 a cada web, con 20 s entre envíos;
   - repito la prueba de aider con Qwen.

## Riesgos conocidos

- **Tus cuentas.**
  - Los términos de DeepSeek y z.ai prohíben la automatización.
  - OmniRoute marca Qwen web y Meta AI web como **"avoid"** (evitar).
  - Lo aceptaste. El guardián lo limita: 1 envío a la vez, 20 s entre envíos, 150 al día y pausa de 6 h ante cualquier señal de bloqueo. Pero no lo elimina.
- **OmniRoute reintenta él solo:** hasta 3 veces tras un 429, y DeepSeek web renueva el token y reintenta 2 veces tras un 401/403. El guardián de `webllm` no puede impedirlo (ver el punto 6).
- **Las webs cambian sin avisar:** cualquier proveedor web de OmniRoute puede romperse con una actualización de su web.
- **aider va lento en novedades:** la última versión es del 12-feb-2026. La alternativa para modelos por API es OpenCode.
- **Los modelos gratis de OpenRouter** tienen tope (50 al día sin comprar créditos) y a veces están saturados (429).
- **OmniRoute trae de fábrica** la caché, la "memoria" y la compresión. `webllm` y aider las desactivan en cada petición; tus otros agentes no.

## Dónde está cada cosa

- `docs/spec.md`: el diseño v2.
- `docs/proveedores-web.md`: qué pide cada web, cómo caduca y su riesgo.
- `docs/plan-b.md`: la extensión de Chrome, solo si hace falta.
- `data/config.yaml`: nombres de IA, modelos, orden, límites.
- `legacy/`: el código viejo de Claude/Playwright, retirado.
- Copias de seguridad de OmniRoute: `C:\Users\angel\.omniroute-backup-20260923-235619` (antes de tocar nada) y `...-20260924-001841` (antes de crear la ruta `webllm-default`).
