@echo off
rem Programs in the CURRENT folder using one of your Chrome AI chats.
rem Use it from the folder you want to change:
rem   programar.cmd            (z.ai chat)
rem   programar.cmd qwen       (or deepseek, zai, meta)
rem Every change is a git commit (undo with /undo). Shell commands always ask first.
setlocal
set "WEBLLM_HOME=%~dp0"
set "SITE=%~1"
if "%SITE%"=="" set "SITE=zai"
set "AIDER_EXE=%USERPROFILE%\.local\bin\aider.exe"
curl.exe -sf -o nul -m 3 http://127.0.0.1:20130/health || call "%WEBLLM_HOME%iniciar.cmd" /nopause
set "OPENAI_API_BASE=http://127.0.0.1:20130/v1"
set /p OPENAI_API_KEY=<"%WEBLLM_HOME%data\state\bridge_token"
"%AIDER_EXE%" --model openai/browser/%SITE% --no-stream --timeout 900 --auto-commits --no-show-model-warnings --analytics-disable
exit /b %ERRORLEVEL%
