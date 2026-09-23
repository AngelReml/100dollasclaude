# webllm-agent — Especificación v2 (23-sep-2026)

Sustituye al roadmap de 9 fases del README (v1). Escrita tras leer el código real y verificar fuentes el 23-sep-2026.

## En una frase
Tú escribes un prompt en tu agente y llega solo a tus IAs (una o todas); cuando trabajas en una carpeta, un agente de código aplica los cambios en tu PC. Mezcla dos vías: **web** (tus cuentas gratis de Qwen, DeepSeek y Meta AI) y **API** (z.ai gratis, DeepSeek barato).

## Decisiones fijadas por Iván (no se reabren)
1. Se hace, aceptando el riesgo de cuenta sobre los servicios gratuitos.
2. Claude y ChatGPT **fuera** de la herramienta. Claude sigue siendo el orquestador por su vía normal (Claude Code / Cowork).
3. Prioridad: Qwen → DeepSeek → z.ai → Meta AI. Grok y Gemini al final o fuera.
4. Modo mixto web + API.
5. Envío "a todas" o "a una", a elección en cada prompt.
6. Sus cuentas principales de esos servicios.

## Hallazgos verificados (23-sep-2026)
- **z.ai: GLM-4.7-Flash, GLM-4.5-Flash y GLM-4.6V-Flash son gratis** por API (docs.z.ai, tabla de precios). Límites de uso: [FALTA DATO], la página no los publica.
- **DeepSeek API: no tiene capa gratis.** deepseek-flash cuesta 0,15–0,30 $ por millón de tokens de entrada (sin caché) y 0,60–1,20 $ de salida, según la franja horaria (api-docs.deepseek.com).
- **OpenRouter, modelos :free:** 20 peticiones por minuto; 50 al día, o 1000 al día si has comprado 10 $ de créditos (documentación oficial).
- **Qwen Code con OAuth gratis: cerrado el 15-abr-2026** (issue #3203 de QwenLM/qwen-code). Esa vía ya no existe.
- **OmniRoute (MIT, ya instalado en tu PC: existe `~/.omniroute` con logs y backups) ya trae proveedores web por cookie:** `qwen-web` (Qwen Web, free), `ds-web` (DeepSeek Web), `ms-web` (Muse Spark Web = Meta AI), además de `zai` por API key. Expone `/v1/chat/completions` compatible con OpenAI y tiene un catálogo de riesgo de términos de servicio. No hay proveedor web para chat.z.ai, pero no hace falta: la API de z.ai es gratis.
- **Aider tiene un modo `--copy-paste` pensado exactamente para usar chats web**, y se conecta a cualquier endpoint compatible con OpenAI (`OPENAI_API_BASE` + `--model openai/<modelo>`). Edita con formatos de texto: no necesita que el modelo tenga llamadas a herramientas nativas, que es justo lo que falta en las vías web. Última release verificada: v0.86.0, del 9-ago-2025. Actividad actual: [FALTA DATO] (riesgo, ver R4).
- **Extensiones MIT que ya envían un prompt a varias IAs a la vez:** GenAIPromptExtension (incluye DeepSeek y Qwen) y PromptCast (proveedores configurables por URL + selector). Solo envían, no leen la respuesta. Sirven de base para el plan B.
- **Chrome 136+ no permite controlar el perfil por defecto por depuración remota.** El modo CDP del código actual no sirve para tu Chrome principal.
- **Términos de uso:** DeepSeek 3.5(3) prohíbe "robots, spiders, or other automatic setups"; z.ai III.4.b prohíbe "social bots, spiders, or other automated means". Qwen y Meta AI: [FALTA DATO] (no se pudieron leer). Riesgo aceptado (decisión 1).

## Arquitectura v2 — 4 piezas, 3 ya existen

1. **Puerta única: OmniRoute (existe).** Una sola dirección local a la que se conecta todo. Detrás tiene:
   - vía web: `qwen-web`, `ds-web`, `ms-web`, con la sesión de tus cuentas;
   - vía API: `zai` (GLM-4.7-Flash gratis), DeepSeek API (saldo), OpenRouter :free.
2. **Agente de código: aider (existe)**, apuntado a OmniRoute. Lee y edita tus carpetas, con git como red de seguridad.
3. **Difusor: `webllm ask` (lo único que construimos).** Manda un prompt a todas o a una a través de OmniRoute y te devuelve las respuestas lado a lado. Deja registro en un diario.
4. **Plan B: extensión propia en tu Chrome (solo si la pieza 1 falla** con algún proveedor web). Fork de GenAIPromptExtension o PromptCast, con lectura de la respuesta y un puente local que expone la misma interfaz `/v1`.

Tus otros agentes (Hermes, Shinobi) pueden usar la misma puerta.

### Qué pasa con el código actual
- **Se retira a `legacy/`:** `browser/manager.py` (Playwright), `providers/claude.py`, los selectores de Claude y `scripts/diagnose_claude.py`. Motivo: Claude queda excluido y la vía web la resuelve OmniRoute.
- **Se reutiliza en el difusor:** `config.py`, `observability/logging.py` y `conversations/manager.py` (como registro de envíos).
- **Sale del proyecto a su carpeta propia:** `trend_scout` (con su comando en pyproject), `CENTRAL-INTELIGENCIA-guia-sencilla.md`, `ESTRATEGIA-FINANCIACION-menda.md`, `extract-skill*`, `extract-test`.

## Fases

### Fase 0 — Inventario real y limpieza
- **Qué se hace:**
  - comprobar en tu PC la versión de OmniRoute y si arranca en `:20128`, qué proveedores tiene ya configurados, y la versión de Python;
  - comprobar si aider está instalado; si no, instalarlo;
  - `git init` del proyecto;
  - mover lo legacy y lo ajeno según lo dicho arriba;
  - actualizar el README.
- **Decisión:** usar OmniRoute como puerta frente a LiteLLM proxy o frente a un puente propio. **Elegida:** OmniRoute, porque ya está instalado, ya tiene los tres proveedores web prioritarios y Iván ya lo había elegido el 31-ago. LiteLLM queda como alternativa si OmniRoute falla.
- **Aceptación:** OmniRoute responde en `/v1/models`, el repo tiene un commit base y la raíz del proyecto queda limpia.

### Fase 1 — Vía API (la estable)
- **Qué se hace:** dar de alta en OmniRoute `zai` (GLM-4.7-Flash gratis), DeepSeek API y OpenRouter :free.
- **Única acción de Iván:** crear la API key de z.ai (y de DeepSeek si quiere saldo). Claude no puede crear cuentas ni teclear claves.
- **Decisión:** qué modelo va por defecto. Alternativas: GLM-4.7-Flash (gratis) o deepseek-flash (céntimos). **Elegida:** GLM-4.7-Flash por defecto, con deepseek-flash como respaldo automático.
- **Aceptación:** "prueba de ida y vuelta" con los 2 modelos: la respuesta devuelve intacto un bloque de código de referencia, byte a byte.

### Fase 2 — Vía web (tus cuentas)
- **Qué se hace:** dar de alta `qwen-web`, `ds-web` y `ms-web`.
- **Única acción de Iván:** pegar una vez en el panel de OmniRoute el valor de sesión de cada web, siguiendo la instrucción que da el propio panel. Claude no puede introducir tokens.
- **Decisión:** vía cookie de OmniRoute frente a extensión propia en tu Chrome. **Elegida:** cookie, porque ya existe y no depende de la pantalla. La extensión (Fase 6) solo entra si un proveedor falla.
- **Aviso de Meta AI:** el valor de sesión es el de tu cuenta de Meta. Si esa cuenta la usas para negocio (páginas o anuncios), entra con otra; no se sabe si una sanción se extendería ([FALTA DATO]).
- **Aceptación:** la misma prueba de ida y vuelta, 10 de 10 seguidas, por proveedor. Anotar cuánto dura la sesión antes de caducar.

### Fase 3 — Agente de código en tus carpetas
- **Qué se hace:** aider apuntado a OmniRoute, con un fichero de configuración por proyecto.
- **Decisión 1:** qué agente. Alternativas: aider (edición por texto), OpenCode (necesita herramientas nativas) o un motor propio (las antiguas fases 4-6). **Elegida:** aider, porque es el único que funciona igual con modelos web sin herramientas nativas y con modelos de API. Construir el motor propio sería rehacer lo que ya existe. OpenCode queda como alternativa solo para modelos de API.
- **Decisión 2:** permisos. **Sin clics ni pantallas.** Aider pregunta s/n en la terminal; dentro de la carpeta del proyecto se puede poner en automático porque cada cambio queda como commit de git y se puede deshacer. Los comandos de terminal siempre preguntan.
- **Aceptación:** en un repo de prueba, aider arregla un test que falla usando GLM-4.7-Flash por API, y otra vez usando Qwen web.

### Fase 4 — Difusor "a todas / a una"
- **Qué se hace:** el comando `webllm ask` con destino `todas`, `qwen`, `deepseek`, `zai` o `meta`.
  - Envía en paralelo entre proveedores distintos y de uno en uno dentro de cada proveedor.
  - Muestra las respuestas lado a lado.
  - Guarda un diario JSONL por envío, encadenado por hashes.
- **Decisión:** interfaz. Alternativas: terminal o página local. **Elegida:** terminal primero; la página puede venir después.
- **Aceptación:** un prompt enviado a todas devuelve 4 respuestas completas y el diario queda verificable.

### Fase 5 — Protección de cuentas y ritmo
- **Qué se hace:**
  - límites por proveedor web: 1 petición a la vez, pausa entre peticiones y tope diario;
  - interruptor: si un proveedor devuelve 401/403 o una verificación humana, se desactiva X horas y se te avisa, sin reintentar;
  - aviso cuando caduque una sesión.
- **Decisión:** reintentar frente a parar. **Elegida:** parar. Reintentar contra un bloqueo solo empeora las cosas.
- **Aceptación:** tests que simulan caducidad y bloqueo, y el sistema reacciona como se ha descrito.

### Fase 6 — Plan B: extensión en tu Chrome (solo si hace falta)
- **Cuándo se activa:** si un proveedor web de OmniRoute se rompe o da problemas de cuenta.
- **Qué se hace:**
  - fork MIT de GenAIPromptExtension o PromptCast, limitada a esos dominios;
  - añadirle la lectura de la respuesta (botón Copiar primero, HTML convertido a markdown de respaldo);
  - WebSocket con un puente local solo en 127.0.0.1 y con token (Chrome 116+, con un mensaje de mantenimiento cada 20 s);
  - el puente expone la misma interfaz `/v1`, así que OmniRoute y aider no notan el cambio.
- **Por qué es solo plan B:** depende de que Chrome esté abierto y de la pantalla de cada web. Su ventaja es que usa tu Chrome real, con las verificaciones ya pasadas.

## Riesgos
- **R1. Cuentas:** los términos de DeepSeek y z.ai prohíben la automatización; los de Qwen y Meta: [FALTA DATO]. Mitigación: Fase 5 y ritmo humano.
- **R2. Vía cookie:** el tráfico no sale de tu Chrome sino de OmniRoute con tu sesión. Si eso es más o menos detectable que la extensión: supuesto sin evidencia.
- **R3. Mantenimiento:** los proveedores web de OmniRoute dependen de la comunidad; cada uno puede romperse cuando cambie su web. Estabilidad por proveedor: [FALTA DATO]; se mide en la Fase 2.
- **R4. Aider:** su última release verificada es de ago-2025. Si queda abandonado, la alternativa es OpenCode para los modelos de API.
- **R5. Límites de uso de GLM-4.7-Flash gratis:** [FALTA DATO].

## Pendiente de Iván
1. Crear la API key de z.ai (y de DeepSeek si quiere saldo).
2. Pegar una vez la sesión de Qwen, DeepSeek y Meta AI en el panel de OmniRoute.
3. Meta AI: confirmar si entra con su cuenta de negocio o con otra.

## Fuentes
- docs.z.ai/guides/overview/pricing
- api-docs.deepseek.com/quick_start/pricing
- openrouter.ai/docs/api-reference/limits
- github.com/QwenLM/qwen-code/issues/3203
- github.com/diegosouzapw/OmniRoute (+ wiki Provider-Reference)
- aider.chat/docs/usage/copypaste.html · aider.chat/docs/llms/openai-compat.html · github.com/Aider-AI/aider/releases
- github.com/dliedke/GenAIPromptExtension · github.com/madebysaira/PromptCast
- developer.chrome.com/blog/remote-debugging-port · developer.chrome.com/docs/extensions/how-to/web-platform/websockets
- cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html · chat.z.ai/legal-agreement/terms-of-service
