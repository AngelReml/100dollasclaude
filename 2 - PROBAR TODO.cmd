@echo off
rem Step 2: opens the test panel in your Chrome (http://127.0.0.1:20130/).
rem Everything shown there happens for real: answers, code before/after, tests.
title 2 - PROBAR TODO
set "HOME_DIR=%~dp0"
echo Encendiendo... (unos segundos)
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%HOME_DIR%herramientas\iniciar.cmd" /nopause >nul 2>&1
start "" chrome "http://127.0.0.1:20130/"
echo.
echo  Se ha abierto el PANEL DE PRUEBAS en Chrome.
echo  Pulsa el boton azul "Probar todo" y mira como se pone cada linea.
echo.
echo  (Si no se abrio, escribe en Chrome:  127.0.0.1:20130 )
ping -n 8 127.0.0.1 >nul
