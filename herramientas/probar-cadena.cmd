@echo off
rem Double-click: runs the example chain "Reparto + integracion" for real.
rem Two chats in your Chrome do one part each, an API AI joins them, and the
rem record is checked (green lock). Costs 1 message per chat.
title PROBAR CADENA
chcp 65001 >nul
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%~dp0iniciar.cmd" /nopause >/dev/null 2>&1
cd /d "%~dp0.."
echo.
echo  ===================== PROBAR CADENA =====================
echo   Dos chats de tu Chrome hacen cada uno una parte y una
echo   IA por API lo une todo. Deja a la vista la ventanita.
echo  =========================================================
echo.
python -m webllm_agent.cli.main cadena prueba
echo.
echo  Pulsa una tecla para cerrar.
pause >nul
