@echo off
rem Double-click after fixing an account (new account, verification solved):
rem lifts every pause of the Chrome chats. Or: reanudar.cmd qwen
python -m webllm_agent.cli.main puente reanudar %1
if /i not "%~2"=="/nopause" ping -n 5 127.0.0.1 >nul
