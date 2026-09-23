# Plan B: extensión propia en tu Chrome (NO activado)

**Estado (24-sep-2026): no se construye.** Solo se activa si Qwen o DeepSeek
fallan *por diseño* a través de OmniRoute: por ejemplo, si la web cambia y el
proveedor de OmniRoute deja de funcionar aunque la sesión sea buena. Hoy ninguno
ha fallado así; solo falta pegar las sesiones (paso humano).

## Cuándo se activa
- La prueba de ida y vuelta (`tests/golden/golden.py`) falla con un error que
  **no** es 401/403/429 ni sesión caducada, en 3 intentos honestos.
- O OmniRoute retira o rompe `qwen-web` o `deepseek-web` en una versión nueva.

## Diseño (para cuando haga falta)
1. **Base:** fork de una extensión MIT que ya envía un prompt a varias IAs:
   - github.com/dliedke/GenAIPromptExtension (ya trae DeepSeek y Qwen);
   - o github.com/madebysaira/PromptCast (proveedores por URL + selector CSS).
   - Se limita a los dominios chat.qwen.ai y chat.deepseek.com. Nada de claude.ai ni chatgpt.com.
2. **Leer la respuesta** (esas extensiones solo envían):
   - primero, el botón "Copiar" de la web;
   - si no existe, convertir el HTML de la respuesta a markdown.
3. **Puente local:**
   - un pequeño servidor solo en 127.0.0.1, con token;
   - la extensión conecta por WebSocket (Chrome 116+, con un mensaje de mantenimiento cada 20 s);
   - el puente expone la misma interfaz `/v1/chat/completions`;
   - se da de alta en OmniRoute como proveedor compatible con OpenAI (`omniroute nodes add`), así que `webllm` y aider no notan el cambio.
4. **Protección:** el mismo guardián de `webllm` (1 a la vez, pausa, tope, pausa de 6 h). Sin trucos anti-robot: si la web pide verificación humana, se para.

## Por qué es solo plan B
Depende de que Chrome esté abierto y de cómo esté hecha cada web, que cambia sin
avisar. Su ventaja es que usa tu Chrome real, con las verificaciones ya pasadas.
