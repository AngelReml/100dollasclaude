@echo off
rem Double-click: brings this PC up to date with GitHub (what Claude Code pushed),
rem reinstalls the package and restarts the webllm server.
title ACTUALIZAR webllm
chcp 65001 >nul
setlocal
set "HOME_DIR=%~dp0"
cd /d "%HOME_DIR%"
for /f %%h in ('git rev-parse HEAD') do set "BEFORE=%%h"
echo.
echo  Bajando lo ultimo de GitHub...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo  NO se pudo actualizar solo: en este PC hay cambios que chocan con los de GitHub.
  echo  No toques nada y avisa a Claude.
  echo.
  pause
  exit /b 1
)
for /f %%h in ('git rev-parse HEAD') do set "AFTER=%%h"
if "%BEFORE%"=="%AFTER%" (
  echo  Ya tenias la ultima version.
) else (
  echo  Actualizado.
  python -m pip install -q -e . >nul 2>&1
  set "EXT="
  for /f %%f in ('git diff --name-only %BEFORE% %AFTER% -- extension') do set "EXT=1"
  for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:20130" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
  start "webllm-puente" /min /d "%HOME_DIR%" python -m webllm_agent.cli.main puente
  echo  Servidor reiniciado con la version nueva.
)
if defined EXT (
  echo.
  echo  IMPORTANTE: ha cambiado la extension de Chrome.
  echo  Abre chrome://extensions y en "webllm puente" pulsa la flecha circular.
)
echo.
pause
