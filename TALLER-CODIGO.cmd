@echo off
setlocal
cd /d "%~dp0"
echo.
echo TALLER DE CODIGO F11
echo 1. Nuevo taller desde un repositorio
echo 2. Volver a abrir un worktree existente
choice /c 12 /n /m "Elige 1 o 2: "
if errorlevel 2 goto EXISTENTE

set /p "RUTA=Ruta completa del repositorio: "
if not defined RUTA goto FIN
".venv\Scripts\python.exe" -m webllm_agent.workshop_cli nuevo "%RUTA%"
goto FIN

:EXISTENTE
set /p "RUTA=Ruta completa del worktree webllm: "
if not defined RUTA goto FIN
".venv\Scripts\python.exe" -m webllm_agent.workshop_cli abrir "%RUTA%"

:FIN
echo.
pause
