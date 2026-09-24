@echo off
rem Double-click after fixing an account (new account logged in, verification
rem solved): lifts every pause of the Chrome chats.
title REANUDAR
chcp 65001 >nul
python -m webllm_agent.cli.main puente reanudar
echo.
echo  Listo. Ya puedes seguir usando PREGUNTAR o PROGRAMAR.
echo.
pause
