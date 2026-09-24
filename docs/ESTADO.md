# ESTADO — webllm-agent (24-sep-2026)

> 🚧 **EN CONSTRUCCIÓN.**
> - La pieza principal ya está hecha: **tu Chrome escribe en los chats de IA como si fueran una API**, y aider programa con ellos.
> - Qué está probado:
>   - el funcionamiento completo, con una extensión de prueba;
>   - la parte que escribe y lee la página, en z.ai real;
>   - z.ai, groq y Nemotron por API.
> - Falta probarlo con la extensión de verdad en tu Chrome (paso 1).

## Cómo funciona (en corto)

```
tú / aider / webllm ask ──► puente (127.0.0.1:20130) ──► extensión en TU Chrome ──► chat de Qwen / DeepSeek / z.ai / Meta
                                                                                  (escribe, espera y copia la respuesta)
```

- **Tu Chrome:** usa tu perfil de siempre y tus sesiones abiertas. No hay que copiar cookies ni claves.
- **Ventanas:** cada chat se abre en su propia ventana de Chrome, con una conversación nueva en cada envío.
- **Captura de la respuesta:** se usa el botón "copiar" de la propia web, así llega el texto exacto, con código y todo.

## Los mandamientos

1. **UNA SOLA VEZ, cargar la extensión en Chrome:**
   1. Haz doble clic en `iniciar.cmd`. Así se crea el archivo con la clave del puente.
   2. En Chrome, abre `chrome://extensions`.
   3. Activa **Modo de desarrollador** (arriba a la derecha).
   4. Pulsa **Cargar descomprimida** y elige la carpeta `...\minimax3 coding\extension`.
   5. Deja abiertas en Chrome tus sesiones de Qwen, DeepSeek y Meta AI. z.ai y Qwen funcionan incluso sin cuenta.
2. **Cada día:** doble clic en `iniciar.cmd`. Enciende OmniRoute, el puente (ventana minimizada "webllm-puente") y Chrome.
3. **Preguntar a varias IAs:**
   - doble clic en `preguntar.cmd`, escribe la pregunta y elige `todas` o una (`qwen`, `deepseek`, `zai-chat`, `meta`, `zai`, `groq`, `nemotron`);
   - desde la terminal: `webllm.cmd ask "pregunta" --to todas`.
4. **Programar en una carpeta:** abre una terminal en esa carpeta y ejecuta:
   `"C:\Users\angel\Desktop\proyectos ia\minimax3 coding\programar.cmd" qwen`
   (o `deepseek`, `zai` o `meta`; sin nombre usa z.ai).
   - Cada cambio queda guardado con git y se deshace con `/undo`.
   - Si aider quiere ejecutar un comando de terminal, siempre te pregunta.
   - Cada cambio gasta **2 mensajes** del chat: uno para el código y otro para el mensaje del commit.
5. **Deja a la vista las ventanas de chat que abre webllm.** Pueden estar detrás de otras, pero no minimizadas.
   - Las webs no escriben la respuesta mientras la ventana está oculta. Está comprobado en z.ai.
   - Si webllm detecta que se ha ocultado, trae esa ventana al frente él solo.
6. **Si un chat te echa, te banea o pide verificación,** te sale un **aviso de Windows**:
   - **Sesión cerrada:** entra en ese chat con tu cuenta o con una nueva y vuelve a pedir. No hay que hacer nada más.
   - **Verificación (CAPTCHA):** la ventana se pone al frente, la resuelves tú y el envío sigue solo. Tienes 3 minutos.
   - **Límite o baneo:** ese chat se pausa. Crea otra cuenta, entra con ella en Chrome y haz doble clic en `reanudar.cmd`.
7. **Protección automática:** un mensaje a la vez por chat, 20 s entre mensajes y 150 al día. webllm nunca intenta saltarse una verificación.
8. **Todo queda apuntado** en `data/runs/`. Para comprobarlo: `webllm.cmd journal verify --all`.
9. **Si un chat cambia su web y deja de funcionar:** `webllm.cmd puente diagnosticar qwen` saca la estructura de la página (sin datos tuyos) para arreglar la extensión.

## Qué está comprobado (24-sep-2026)

| Pieza | Estado | Prueba |
|---|---|---|
| Puente local | OK | `iniciar.cmd` lo enciende; `/health` y `/v1/models` responden; 17 tests propios |
| Extensión: escribir, enviar, esperar y copiar | OK en z.ai real, sin cuenta | Prueba de ida y vuelta byte a byte: 185 de 185 caracteres idénticos por el botón "copiar" |
| Extensión: aviso de CAPTCHA | OK | Qwen sin cuenta mostró un CAPTCHA deslizante; se detecta y no se toca |
| Extensión: página oculta | Resuelto | Se detectó que z.ai se para si está oculta; ahora la ventana se trae al frente |
| aider → puente → extensión | OK (extensión de prueba) | `python tests/bridge_aider_check.py`: test de rojo a verde, con commit |
| `webllm ask` a chats del navegador y a APIs a la vez | OK (tests) | 76 tests en verde |
| z.ai por API (GLM-4.7-Flash) | OK | Prueba de ida y vuelta 10/10 |
| groq, Nemotron gratis | OK | Prueba de ida y vuelta 5/5 cada uno |
| **Extensión de verdad en tu Chrome** | **PENDIENTE** | Hace falta el paso 1 |
| Qwen, DeepSeek y Meta con tu sesión | **PENDIENTE** | Los selectores de Qwen, DeepSeek y Meta son una primera versión; se ajustan con `puente diagnosticar` si fallan |

## Riesgos

- **Cuentas.** Las webs pueden banear el uso automático (DeepSeek y z.ai lo prohíben en sus términos). Lo aceptaste; la protección lo frena, pero no lo evita.
- **Las webs cambian.** Si cambia la página de un chat, puede dejar de encontrar la caja de texto o el botón. Se ve en el aviso y se arregla con `diagnosticar`.
- **Ventanas ocultas.** Si minimizas las ventanas de chat, pueden pararse (ver mandamiento 5).
- **z.ai por API** tiene límite de velocidad: devolvió 429 tras unas 15 peticiones seguidas. Si sale gratis de verdad: [FALTA DATO], míralo en tu cuenta de z.ai.

## Dónde está cada cosa

- **Tu Chrome:**
  - `extension/`: la extensión (`driver.js` escribe y lee la página; `sites.js` tiene los ajustes de cada chat).
  - `src/webllm_agent/bridge.py`: el puente.
- **Arrancar y usar:**
  - `iniciar.cmd`: lo enciende todo.
  - `preguntar.cmd`: preguntar a varias IAs.
  - `programar.cmd`: programar en una carpeta.
  - `reanudar.cmd`: quitar las pausas.
- **Configuración y registros:**
  - `data/config.yaml`: nombres, orden, límites.
  - `data/runs/`: el registro de cada envío.
- **Vía antigua por cookies de OmniRoute** (`docs/proveedores-web.md`): ya **no hace falta**. OmniRoute solo se usa para las IAs por API.
