@echo off
rem Starts the local OmniRoute gateway in a minimized window (double-click friendly).
rem API: http://127.0.0.1:20128/v1   Dashboard: http://127.0.0.1:20128
setlocal
set "OMNI_DIR=C:\Users\angel\Desktop\proyectos ia\omnirouter"
set "HEALTH=http://127.0.0.1:20128/api/health"
set "RC=0"

curl.exe -sf -o nul -m 3 "%HEALTH%" && (
  echo OmniRoute ya estaba encendido: http://127.0.0.1:20128
  goto :done
)

if not exist "%OMNI_DIR%\node_modules\omniroute\bin\omniroute.mjs" (
  echo ERROR: no encuentro OmniRoute en "%OMNI_DIR%"
  goto :done
)

echo Encendiendo OmniRoute (ventana minimizada "OmniRoute")...
start "OmniRoute" /min /d "%OMNI_DIR%" node node_modules\omniroute\bin\omniroute.mjs serve --no-open --no-tray

for /l %%i in (1,1,45) do (
  curl.exe -sf -o nul -m 2 "%HEALTH%" && goto :up
  ping -n 3 127.0.0.1 >nul
)
echo ERROR: OmniRoute no ha respondido en 90 segundos. Mira la ventana minimizada "OmniRoute".
set "RC=1"
goto :done

:up
echo OK: OmniRoute encendido. Panel: http://127.0.0.1:20128
echo Para apagarlo: cierra la ventana "OmniRoute" o usa stop-omniroute.cmd

:done
if /i not "%~1"=="/nopause" ping -n 6 127.0.0.1 >nul
exit /b %RC%
