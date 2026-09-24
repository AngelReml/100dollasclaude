@echo off
rem Double-click: ask one question to all your AIs (or to one).
title PREGUNTAR
chcp 65001 >nul
set "HOME_DIR=%~dp0"
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%HOME_DIR%herramientas\iniciar.cmd" /nopause >nul 2>&1
:again
cls
echo.
echo  ======================= PREGUNTAR =======================
echo   Escribe tu pregunta. Cuando acabes, deja una linea vacia
echo   y pulsa Enter. Luego elige a quien (Enter = a todas).
echo  =========================================================
echo.
python -m webllm_agent.cli.main ask
echo.
echo  Pulsa una tecla para hacer otra pregunta (o cierra esta ventana).
pause >nul
goto again
