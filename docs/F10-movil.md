# F10 — Móvil (27-sep-2026)

## Estado verificado

- Tailscale `1.102.4` está instalado, arrancado y configurado como servicio automático.
- `Tailscale Serve` publica **solo dentro de la tailnet** `https://<equipo>.<tailnet>.ts.net` y lo envía a `http://127.0.0.1:8080`.
- Open WebUI responde en el PC. No se ha abierto ningún puerto del router.
- El 27-sep-2026 se instaló Tailscale en un móvil Android, se inició sesión en la misma tailnet y Open WebUI cargó por HTTPS desde el navegador móvil.
- La prueba completa móvil → Tailscale → Open WebUI → webllm → LM Studio local → móvil terminó con una respuesta visible de `qwen2.5-1.5b-instruct`.

## Resultado y límites observados

- **F10 queda cerrado:** el acceso privado y una conversación completa con un modelo del PC están verificados desde el móvil.
- Los chats web siguen dependiendo de la sesión abierta en el Chrome del PC: Qwen pidió autenticación.
- DeepSeek contestó a una prueba móvil, pero su web cambió y la extensión no pudo extraer esa respuesta. Es un fallo del lector de DeepSeek, no de Tailscale ni de la interfaz móvil.
- No se comprobó añadir la web a la pantalla de inicio ni guardar esa conversación en un vault de Obsidian; no forman parte de la evidencia de cierre.

La prueba móvil fue manual y quedó documentada sin publicar el nombre real del equipo, la tailnet ni la cuenta usada.
