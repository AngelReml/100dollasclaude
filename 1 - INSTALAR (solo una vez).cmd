@echo off
rem Step 1 (only once): starts everything, opens Chrome's extensions page and
rem puts the extension folder path on the clipboard.
title 1 - INSTALAR (solo una vez)
set "HOME_DIR=%~dp0"
echo Preparando... (unos segundos)
call "%HOME_DIR%herramientas\iniciar.cmd" /nopause >nul 2>&1
powershell -NoProfile -Command "Set-Clipboard -Value '%HOME_DIR%extension'"
start "" chrome "http://127.0.0.1:20130/"
start "" chrome "chrome://extensions"
cls
echo.
echo  ==============================================================
echo    INSTALAR  -  3 clics en Chrome (solo esta vez)
echo  ==============================================================
echo.
echo   Se acaba de abrir Chrome en la pagina de EXTENSIONES.
echo   (Si no se abrio: escribe  chrome://extensions  arriba en Chrome)
echo.
echo   CLIC 1.  Arriba a la DERECHA: enciende el interruptor
echo            "Modo de desarrollador".
echo.
echo   CLIC 2.  Arriba a la IZQUIERDA: pulsa "Cargar descomprimida".
echo.
echo   CLIC 3.  Se abre una ventana para elegir carpeta.
echo            Abajo, en el recuadro "Carpeta", pulsa Ctrl+V
echo            (la carpeta ya esta copiada) y pulsa "Seleccionar carpeta".
echo.
echo   Veras aparecer "webllm puente". En la otra pestana (el PANEL)
echo   el circulo "Extension en tu Chrome" se pondra VERDE.
echo.
echo   Ahora: en el PANEL pulsa el boton azul "Probar todo".
echo  ==============================================================
echo.
pause
