@echo off
rem Double-click: starts everything. OmniRoute (API models), the bridge to your
rem Chrome chats (minimized window "webllm-puente") and Chrome itself.
setlocal
set "HOME_DIR=%~dp0"
call "%HOME_DIR%start-omniroute.cmd" /nopause
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health && goto :bridge_up
echo Encendiendo el puente con tu Chrome (ventana minimizada "webllm-puente")...
start "webllm-puente" /min "%HOME_DIR%lanzar-puente.cmd"
for /l %%i in (1,1,20) do (
  curl.exe -sf -o nul -m 2 http://127.0.0.1:20130/health && goto :bridge_up
  ping -n 2 127.0.0.1 >nul
)
echo ERROR: el puente no arranca. Mira la ventana "webllm-puente".
goto :done
:bridge_up
echo OK: puente encendido en http://127.0.0.1:20130
tasklist /fi "imagename eq chrome.exe" | find /i "chrome.exe" >nul || start "" chrome
:done
if /i not "%~1"=="/nopause" ping -n 6 127.0.0.1 >nul
