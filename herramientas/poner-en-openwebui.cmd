@echo off
rem Pone webllm dentro de Open WebUI (PLAN-v5 F1): tus IAs de webllm como modelos de Open WebUI.
rem Antes: en Open WebUI, Administracion - Ajustes - General - "Enable API Keys" activado,
rem y luego tu usuario - Ajustes - Cuenta - Claves de la API - Crear Nueva Clave.
cd /d "%~dp0.."
set "CLAVE="
set /p "CLAVE=Pega aqui tu clave de Open WebUI y pulsa Enter: "
if "%CLAVE%"=="" (
  echo No has pegado ninguna clave. Mira los pasos en docs\F1-cara.md.
  pause
  exit /b 1
)
python scripts\openwebui_setup.py --clave "%CLAVE%"
pause
