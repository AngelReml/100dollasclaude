@echo off
rem Stops the local OmniRoute gateway.
setlocal
set "OMNI_DIR=C:\Users\angel\Desktop\proyectos ia\omnirouter"
pushd "%OMNI_DIR%"
node node_modules\omniroute\bin\omniroute.mjs stop
popd
if /i not "%~1"=="/nopause" ping -n 4 127.0.0.1 >nul
