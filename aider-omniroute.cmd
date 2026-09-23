@echo off
rem Starts aider in the CURRENT folder, talking to your AIs through OmniRoute.
rem Use it from the folder you want to change, e.g.:
rem   cd /d "C:\ruta\a\tu\proyecto"
rem   "C:\Users\angel\Desktop\proyectos ia\minimax3 coding\aider-omniroute.cmd"
rem Extra aider options are passed through, e.g. --model openai/groq/openai/gpt-oss-120b
rem File edits are applied and committed to git automatically (undo with /undo or git).
rem Shell commands proposed by aider ALWAYS ask first (with --yes-always they are refused).
setlocal
set "WEBLLM_HOME=%~dp0"
set "AIDER_EXE=%USERPROFILE%\.local\bin\aider.exe"
set "DEFAULT_MODEL=openai/combo/webllm-default"
set "OPENAI_API_BASE=http://127.0.0.1:20128/v1"
set "OPENAI_API_KEY="
for /f "usebackq tokens=1,* delims==" %%a in ("%USERPROFILE%\.omniroute\.env") do (
  if "%%a"=="OMNIROUTE_API_KEY" set "OPENAI_API_KEY=%%b"
)
if not defined OPENAI_API_KEY (
  echo ERROR: no encuentro OMNIROUTE_API_KEY en %USERPROFILE%\.omniroute\.env
  exit /b 1
)
if not exist "%AIDER_EXE%" (
  echo ERROR: aider no esta instalado en %AIDER_EXE%
  exit /b 1
)
curl.exe -sf -o nul -m 3 http://127.0.0.1:20128/api/health || (
  echo OmniRoute esta apagado. Enciendelo con doble clic en start-omniroute.cmd
  exit /b 1
)
"%AIDER_EXE%" --model %DEFAULT_MODEL% --model-settings-file "%WEBLLM_HOME%aider\omniroute.model-settings.yml" --auto-commits --no-show-model-warnings --analytics-disable %*
exit /b %ERRORLEVEL%
