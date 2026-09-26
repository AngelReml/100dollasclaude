@echo off
rem Conecta GitHub a Open WebUI (PLAN-v5 F9): solo leer y proponer (issues, ramas webllm/, PR).
rem Antes: en github.com - Settings - Developer settings - Fine-grained tokens - Generate new token:
rem   solo tus repositorios; Issues, Pull requests y Contents: Read and write; nada de Administration.
rem El token solo se guarda en Open WebUI (nunca en webllm ni en git). Cada uso te pide permiso.
cd /d "%~dp0.."
set "CLAVE="
set /p "CLAVE=Pega aqui tu clave de Open WebUI y pulsa Enter: "
if "%CLAVE%"=="" (
  echo No has pegado ninguna clave. Mira los pasos en docs\F9-acciones.md.
  pause
  exit /b 1
)
python scripts\openwebui_setup.py --clave "%CLAVE%" --github --solo-conectores
pause
