@echo off
rem webllm command. Examples:
rem   webllm.cmd ask "tu pregunta" --to todas
rem   webllm.cmd ask "tu pregunta" --to qwen
rem   webllm.cmd status
rem   webllm.cmd journal verify --all
python -m webllm_agent.cli.main %*
