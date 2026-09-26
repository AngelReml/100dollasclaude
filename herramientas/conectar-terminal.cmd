@echo off
rem Conecta tu MCP de terminal a Open WebUI (PLAN-v5 F9) a traves de mcpo, en el puerto 8765.
rem Cada comando te pide permiso, y los peligrosos (administrador, apagar, borrar carpetas enteras,
rem discos, registro de Windows) webllm no deja ni pedirlos.
cd /d "%~dp0.."
set "CLAVE="
set /p "CLAVE=Pega aqui tu clave de Open WebUI y pulsa Enter: "
if "%CLAVE%"=="" (
  echo No has pegado ninguna clave. Mira los pasos en docs\F9-acciones.md.
  pause
  exit /b 1
)
set "COMANDO="
if exist "data\state\terminal_mcp.txt" set /p COMANDO=<"data\state\terminal_mcp.txt"
if not "%COMANDO%"=="" echo El comando de tu MCP de terminal que ya tenias: %COMANDO%
set /p "NUEVO=Pega el comando que arranca tu MCP de terminal (o Enter para usar el de arriba): "
if not "%NUEVO%"=="" set "COMANDO=%NUEVO%"
if "%COMANDO%"=="" (
  echo No hay comando. Mira los pasos en docs\F9-acciones.md.
  pause
  exit /b 1
)
> "data\state\terminal_mcp.txt" echo %COMANDO%
start "webllm terminal (mcpo)" /min cmd /c uvx mcpo --host 127.0.0.1 --port 8765 -- %COMANDO%
echo Esperando a que arranque...
timeout /t 8 /nobreak >nul
python scripts\openwebui_setup.py --clave "%CLAVE%" --terminal http://127.0.0.1:8765 --solo-conectores
pause
