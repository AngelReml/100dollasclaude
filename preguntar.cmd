@echo off
rem Double-click: type a question, choose "todas" or one provider, read the answers.
title webllm - preguntar
python -m webllm_agent.cli.main ask
echo.
pause
