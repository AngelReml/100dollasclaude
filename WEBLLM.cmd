@echo off
rem Double-click: starts everything and opens the webllm app in its own window
rem (Chrome in app mode, same profile as always, so the extension is there).
title webllm
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%~dp0herramientas\iniciar.cmd" /nopause >nul 2>&1
start "" chrome --app=http://127.0.0.1:20130/app/
exit /b 0
