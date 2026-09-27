# F11 — Taller de código (27-sep-2026)

## Qué está implementado

- OpenCode v2 oficial, a través del OmniRoute local. GLM-5.2 queda configurado, pero el 27-sep-2026 su proveedor respondió 429 por saldo o paquete insuficiente; mientras tanto el valor predeterminado es la ruta explícita `auto/coding:free`, probada con respuesta real.
- La configuración declara **taller-plan** como agente inicial, sin edición ni terminal. Para ejecutar hay que cambiar visiblemente a **taller-build**.
- La configuración de OpenCode marca edición, terminal y acceso fuera del proyecto como `ask`; web y compartir están desactivados.
- `opencode.json` contiene reglas `deny` para elevación, apagado, discos, borrado recursivo, registro, permisos y desactivar protecciones. Las pruebas comprueban que las reglas existen, pero todavía no demuestran su aplicación dentro de una sesión real de OpenCode.
- Solo arranca sin administrador, con UAC activo, más de 10 GB libres y dentro de un `git worktree`.
- El lanzador asigna el árbol de procesos a un Job Object de Windows con 2 GB de memoria, un límite configurado del 50 % de CPU y cierre del Job Object con Ctrl+C. El límite de memoria y la terminación del árbol están probados; el límite de CPU aún no se ha medido bajo carga.

## Uso

Para Iván: doble clic en `TALLER-CODIGO.cmd`, elige **1** y pega la ruta del repositorio. Para volver otro día a la misma rama, elige **2** y pega la ruta del worktree que mostró el taller.

Equivalente desde PowerShell:

```powershell
webllm-taller comprobar C:\ruta\al\repo
webllm-taller preparar C:\ruta\al\repo
webllm-taller abrir C:\ruta\al\repo-webllm-AAAAMMDD-HHMMSS
```

`preparar` crea una rama `webllm/f11-*` y un worktree vecino; nunca trabaja sobre `main`.

## Prueba D24: alcance exacto

`python scripts\f11_d24_check.py` hace seis comprobaciones acotadas:

1. Windows rechaza de verdad una escritura no elevada en `C:\Windows`.
2. Windows rechaza de verdad una escritura no elevada en `C:\Program Files`.
3. El filtro Python reconoce `shutdown` como prohibido, sin ejecutarlo.
4. El filtro Python reconoce `runas` como prohibido, sin ejecutarlo.
5. Se simula un umbral imposible de espacio libre y el preflight impide arrancar.
6. El límite de memoria del Job Object termina de verdad un proceso hijo.

No ejecuta órdenes destructivas ni intenta llenar el disco. El filtro Python de los puntos 3 y 4 no está interpuesto entre OpenCode y su terminal: la denegación en una sesión real depende actualmente de las reglas de `opencode.json`.

## Límites honestos

- Windows Sandbox no está habilitado en este PC; por eso no se lanzan órdenes dañinas reales.
- Faltan cinco tareas reales, elegidas por Iván, y una prueba segura de permisos dentro de una sesión real para considerar F11 aceptado de extremo a extremo.
- Aceptar conserva la rama aislada; integrar cambios en la rama principal sigue siendo una decisión separada.
