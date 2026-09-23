# Proveedores web en OmniRoute (Qwen, DeepSeek, Meta AI)

> 🚧 **EN CONSTRUCCIÓN.** Ninguno de estos tres está dado de alta todavía. Esto es lo
> que dice el código de OmniRoute; aún no se ha probado con una sesión real.

Leído el 24-sep-2026 en el código de OmniRoute v3.8.50 instalado en tu PC
(`omnirouter\node_modules\omniroute`). Cada dato lleva su fichero y línea en el
informe de investigación; aquí va lo que necesitas saber.

## Resumen

| Nombre en `webllm` | Proveedor OmniRoute | Qué hay que pegar | Dónde se saca | Riesgo de términos (catálogo de OmniRoute) |
|---|---|---|---|---|
| `qwen` | `qwen-web` (alias `qwen-web`) | La **cabecera Cookie completa** (tiene que llevar `cna`, `ssxmod_itna` y `token`) | chat.qwen.ai, con la sesión abierta | **"avoid"** (evitar) |
| `deepseek` | `deepseek-web` (alias `ds-web`) | El **userToken** | chat.deepseek.com → DevTools → Application → Local Storage → `userToken` | [FALTA DATO] (no está en el catálogo); aviso genérico de "úsalo bajo tu riesgo" |
| `meta` | `muse-spark-web` (alias `ms-web`) | **Dos cosas**: la cookie `ecto_1_sess` **y** el token `ecto1:...` del WebSocket | www.meta.ai → DevTools → Network → WS → petición `clippy` → parámetro `Authorization` | **"avoid"** (evitar) |

Modelos que usa `webllm` por defecto (se cambian en `data/config.yaml`):
- `qwen-web/qwen3.8-max` (también hay `qwen3.7-max`, `qwen3.7-plus`, `qwen3.6-plus`)
- `ds-web/deepseek-v4-pro` (también `deepseek-v4-flash`, variantes `-think` y `-search`, `deepseek-chat`, `deepseek-reasoner`)
- `ms-web/muse-spark` (también `muse-spark-thinking`, `muse-spark-contemplating`)

## Cómo caduca cada sesión

- **Qwen:** no se renueva sola. Si la web devuelve HTML, un 504 o el cortafuegos de Alibaba (WAF), OmniRoute lo convierte en un 401 "session expired or blocked by Alibaba's WAF". Solución: pegar la cookie otra vez.
- **DeepSeek:** OmniRoute cambia tu `userToken` por un pase corto y lo renueva solo cada 50 minutos. Si DeepSeek responde 401/403, **OmniRoute renueva y reintenta hasta 2 veces por su cuenta** (lo trae así de fábrica). Si el `userToken` ya no vale, error "Token invalid or expired".
- **Meta AI:** no se renueva sola. Si falta el token `ecto1:` da error 400; si la cookie caduca, 401. Meta cambió el nombre de la cookie (`abra_sess` → `ecto_1_sess`); OmniRoute todavía acepta el nombre viejo.

Cuánto dura cada sesión antes de caducar: [FALTA DATO]. Se medirá cuando estén dadas de alta.

## Lo que NO se usa y por qué

- **`zai-web` (chat.z.ai):** existe en OmniRoute, pero resuelve el CAPTCHA de cada petición con un navegador automático escondido. Eso es saltarse la protección anti-robots, y está prohibido en este proyecto. Para GLM se usa la API de z.ai (`zai`), que es gratis para GLM-4.7-Flash.
- **`zcode` (`zc/...`):** aparece en la lista de modelos sin pedir clave, pero en realidad arranca en tu PC el programa ZCode de Z.ai con su propia cuenta del "GLM Coding Plan". No lo tienes instalado ni configurado.
- **`codex`, `cx`, `cxa` y los modelos `gpt-5.x` sin prefijo:** son tu sesión de ChatGPT/Codex. `webllm` los rechaza siempre.

## Dónde se pegan (panel de OmniRoute)

El panel pide contraseña. Claude no puede escribirla, así que ese paso lo haces tú.
Rutas, sacadas del código del panel porque no se pudo ver por dentro sin contraseña:

1. Abre http://127.0.0.1:20128 y entra con tu contraseña.
2. Ve a **Providers** (`/dashboard/providers`), sección **"Web Cookie Providers"**.
3. Entra en el proveedor: `/dashboard/providers/qwen-web`, `/dashboard/providers/deepseek-web` o `/dashboard/providers/muse-spark-web`.
4. Pulsa **"Add Connection"**. Se abre "Add {proveedor} session cookie" (o "web token").
5. Pega el valor, pulsa **"Check cookie"** / **"Check token"** y guarda.

## Lo que hace OmniRoute por su cuenta (y el guardián de `webllm` no puede impedir)

Leído en `GET /api/resilience` el 24-sep-2026:
- `waitForCooldown` está **activado**: tras un 429, OmniRoute espera (hasta 30 s) y **reintenta hasta 3 veces** antes de devolver el error.
- Para los proveedores web, un 401 **no** congela la conexión en OmniRoute. Solo prueba la siguiente opción.
- Tras un 429, OmniRoute solo congela unos segundos, como mucho 2 minutos.

Por eso `webllm` tiene su propio guardián, con pausa de 6 h, tope diario y 1 envío a la vez.
Además, en cuanto existan las conexiones web, se les aplica el límite nativo de OmniRoute
(`scripts/apply_web_limits.py --apply`: 1 a la vez, 20 s entre peticiones, 3 por minuto).
Así nada que pase por OmniRoute, ni aider ni otros agentes, las satura.
