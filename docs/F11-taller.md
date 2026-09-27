# F11 — Taller de código (27-sep-2026)

## Qué está preparado

- OpenCode v2 oficial, a través del OmniRoute local. GLM-5.2 queda configurado, pero el 27-sep-2026 su proveedor respondió 429 por saldo o paquete insuficiente; mientras tanto el valor predeterminado es la ruta explícita `auto/coding:free`, probada con respuesta real.
- Empieza siempre en el agente **taller-plan**, sin edición ni terminal. Para ejecutar hay que cambiar visiblemente a **taller-build**, donde cada edición, comando y acceso externo vuelve a pedir permiso.
- Cada edición, comando y acceso fuera del proyecto pregunta; web y compartir están desactivados.
- Las órdenes de elevación, apagado, discos, borrado recursivo, registro, permisos y desactivar protecciones se deniegan.
- Solo arranca sin administrador, con UAC activo, más de 10 GB libres y dentro de un `git worktree`.
- Todo el árbol de procesos corre en un Job Object de Windows: 2 GB de memoria, 50 % de CPU y cierre completo con Ctrl+C.

## Uso

Para Iván: doble clic en `TALLER-CODIGO.cmd`, elige **1** y pega la ruta del repositorio. Para volver otro día a la misma rama, elige **2** y pega la ruta del worktree que mostró el taller.

Equivalente desde PowerShell:

```powershell
webllm-taller comprobar C:\ruta\al\repo
webllm-taller preparar C:\ruta\al\repo
webllm-taller abrir C:\ruta\al\repo-webllm-AAAAMMDD-HHMMSS
```

`preparar` crea una rama `webllm/f11-*` y un worktree vecino; nunca trabaja sobre `main`.

## Prueba D24

`python scripts\f11_d24_check.py` hace seis comprobaciones acotadas: Windows y Archivos de programa rechazan una escritura no elevada; apagar y elevar se rechazan sin ejecutar; poco disco impide arrancar; y el límite de memoria mata un hijo. No ejecuta órdenes destructivas ni intenta llenar el disco.

## Límites honestos

- Windows Sandbox no está habilitado en este PC; por eso no se lanzan órdenes dañinas reales.
- Falta resolver cinco tareas reales, elegidas por Iván, para completar la salida de F11.
- Aceptar conserva la rama aislada; integrar cambios en la rama principal sigue siendo una decisión separada.
