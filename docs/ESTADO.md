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

## Los mandamientos (todo con doble clic en la carpeta del proyecto)

1. **`1 - INSTALAR (solo una vez)`.** Abre Chrome en la página de extensiones y te dice los 3 clics que hay que hacer.
2. **`2 - PROBAR TODO`.** Hace una prueba real de cada cosa y pone **BIEN** o **MAL**.
   - Si algo sale MAL, te dice qué hacer en la misma línea.
   - Tarda unos minutos y verás ventanas de Chrome escribiendo solas.
3. **`PREGUNTAR`.** Escribe tu pregunta, deja una línea vacía y pulsa Enter.
   - Luego pulsa Enter para mandarla a todas, o escribe el nombre de una IA.
4. **`PROGRAMAR`.**
   - Arrastra la carpeta de tu proyecto a la ventana y elige la IA con un número.
   - Pide los cambios en lenguaje normal.
   - Deshacer: `/undo`. Salir: `/exit`.
   - Cada cambio queda guardado con git. Si pregunta algo, responde `y` (sí) o `n` (no).
   - Cada cambio gasta 2 mensajes del chat.
5. **`REANUDAR`.** Quita las pausas cuando ya has entrado con una cuenta nueva o has resuelto una verificación.
6. **Deja a la vista las ventanas de chat que abre webllm.** Pueden estar detrás de otras, pero no minimizadas.
   - Si se ocultan, las webs no escriben la respuesta; webllm las trae al frente él solo.
7. **Si un chat te echa, te banea o pide verificación,** sale un aviso de Windows que te dice qué hacer.
   - **Sin sesión:** entra y repite.
   - **Verificación:** la resuelves tú en esa ventana y el envío sigue solo.
   - **Baneo o límite:** entra con otra cuenta y haz doble clic en `REANUDAR`.
8. **Protección automática:** 1 mensaje a la vez por chat, 20 s entre mensajes, 150 al día. Nunca se salta una verificación.
9. **Todo queda apuntado** en `data/runs/`. Los comandos avanzados están en `herramientas\`.

## Novedades del 24-sep-2026 (tarde)

- **El panel de pruebas está en http://127.0.0.1:20130.** `2 - PROBAR TODO` lo abre.
- **Verificado por Iván en su Chrome:**
  - z.ai y DeepSeek responden;
  - **"Programar con el chat z.ai": BIEN.** Una IA de su Chrome arregló el código de prueba.
- **Una sola ventanita** en una esquina, con una pestaña por IA, que se cierra sola al terminar.
- **"Saturada"** ya no pausa la IA. Ventanas emergentes (como la de la edad en Qwen): te avisa y espera.
- **Pendiente:**
  - Qwen: CAPTCHAs y la ventana de la edad;
  - Meta: repetir la prueba con la versión 0.3.0 de la extensión.
- **Siguiente paso:** `docs/PLAN-v3.md` (Mesa de IAs y aplicación de verdad). Lo programará Claude Code desde GitHub.
- **Para bajar lo que suba Claude Code:** doble clic en **`ACTUALIZAR`**.

## Qué está comprobado (24-sep-2026)

| Pieza | Estado | Prueba |
|---|---|---|
| Puente local | OK | Se enciende solo; `/health` y `/v1/models` responden; 17 tests propios |
| Extensión: escribir, enviar, esperar y copiar | OK en z.ai real, sin cuenta | Prueba de ida y vuelta byte a byte: 185 de 185 caracteres idénticos por el botón "copiar" |
| Extensión: aviso de CAPTCHA | OK | Qwen sin cuenta mostró un CAPTCHA deslizante; se detecta y no se toca |
| Extensión: página oculta | Resuelto | Se detectó que z.ai se para si está oculta; ahora la ventana se trae al frente |
| aider → puente → extensión | OK (extensión de prueba) | `python tests/bridge_aider_check.py`: test de rojo a verde, con commit |
| `webllm ask` a chats del navegador y a APIs a la vez | OK (tests) | 76 tests en verde |
| z.ai por API (GLM-4.7-Flash) | OK | Prueba de ida y vuelta 10/10 |
| groq, Nemotron gratis | OK | Prueba de ida y vuelta 5/5 cada uno |
| **Extensión de verdad en tu Chrome** | **PENDIENTE** | Hace falta `1 - INSTALAR` y después `2 - PROBAR TODO` |
| Qwen, DeepSeek y Meta con tu sesión | **PENDIENTE** | Los selectores de Qwen, DeepSeek y Meta son una primera versión; se ajustan con `puente diagnosticar` si fallan |

## Riesgos

- **Cuentas.** Las webs pueden banear el uso automático (DeepSeek y z.ai lo prohíben en sus términos). Lo aceptaste; la protección lo frena, pero no lo evita.
- **Las webs cambian.** Si cambia la página de un chat, puede dejar de encontrar la caja de texto o el botón. Se ve en el aviso y se arregla con `diagnosticar`.
- **Ventanas ocultas.** Si minimizas las ventanas de chat, pueden pararse (ver mandamiento 6).
- **z.ai por API** tiene límite de velocidad: devolvió 429 tras unas 15 peticiones seguidas. Si sale gratis de verdad: [FALTA DATO], míralo en tu cuenta de z.ai.

## Dónde está cada cosa

- **Lo que usas:**
  - `LEEME - EMPIEZA AQUI.txt`: la guía corta.
  - Los 5 archivos de doble clic, en la carpeta principal.
- **Por dentro:**
  - `extension/`: la extensión de Chrome.
  - `src/webllm_agent/bridge.py`: el puente.
  - `src/webllm_agent/selftest.py`: PROBAR TODO.
  - `herramientas\`: los comandos avanzados.
- **Configuración y registros:**
  - `data/config.yaml`: nombres, orden, límites.
  - `data/runs/`: el registro de cada envío.
- **Vía antigua por cookies de OmniRoute** (`docs/proveedores-web.md`): ya no hace falta. OmniRoute solo se usa para las IAs por API.
