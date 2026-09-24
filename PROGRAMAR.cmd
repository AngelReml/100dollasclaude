@echo off
rem Double-click (or drop a project folder on this file): an AI from your Chrome
rem changes the code in that folder. Every change is a git commit (/undo reverts).
title PROGRAMAR
chcp 65001 >nul
setlocal
set "HOME_DIR=%~dp0"
set "AIDER_EXE=%USERPROFILE%\.local\bin\aider.exe"
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%HOME_DIR%herramientas\iniciar.cmd" /nopause >nul 2>&1

set "DIR=%~1"
if not "%DIR%"=="" goto have_dir
echo.
echo  ======================= PROGRAMAR =======================
echo   Arrastra aqui la CARPETA de tu proyecto y pulsa Enter.
echo  ==========================================================
set /p "DIR=> "
:have_dir
set "DIR=%DIR:"=%"
if not exist "%DIR%\" (
  echo No encuentro esa carpeta: %DIR%
  pause
  exit /b 1
)

echo.
echo   Que IA uso?   1 = z.ai    2 = Qwen    3 = DeepSeek    4 = Meta AI
set "PICK=1"
set /p "PICK=  Numero (Enter = 1): "
set "SITE=zai"
if "%PICK%"=="2" set "SITE=qwen"
if "%PICK%"=="3" set "SITE=deepseek"
if "%PICK%"=="4" set "SITE=meta"

set "OPENAI_API_BASE=http://127.0.0.1:20130/v1"
set /p OPENAI_API_KEY=<"%HOME_DIR%data\state\bridge_token"
cd /d "%DIR%"
cls
echo.
echo  ==========================================================
echo   Carpeta: %DIR%
echo   IA: %SITE% (en tu Chrome)
echo.
echo   Escribe lo que quieres cambiar y pulsa Enter.
echo   Si pregunta algo, responde  y  (si) o  n  (no).
echo   Deshacer el ultimo cambio: /undo      Salir: /exit
echo  ==========================================================
echo.
"%AIDER_EXE%" --model openai/browser/%SITE% --no-stream --timeout 900 --auto-commits --no-show-model-warnings --analytics-disable
pause
