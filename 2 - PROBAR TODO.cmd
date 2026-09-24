@echo off
rem Step 2: real test of everything (your Chrome chats, the API models and a
rem programming test). Prints BIEN / MAL for each item.
title 2 - PROBAR TODO
chcp 65001 >nul
python -m webllm_agent.cli.main probar
echo.
pause
