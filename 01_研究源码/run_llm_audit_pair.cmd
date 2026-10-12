@echo off
setlocal
cd /d "%~dp0"

if not defined DEEPSEEK_API_KEY (
  echo ERROR: DEEPSEEK_API_KEY is not set in this terminal.
  echo Use: set "DEEPSEEK_API_KEY=sk-..."
  exit /b 2
)

if /i not "%DEEPSEEK_API_KEY:~0,3%"=="sk-" (
  echo ERROR: DEEPSEEK_API_KEY must start with sk-.
  echo Do not include the text DEEPSEEK_API_KEY= inside the value.
  exit /b 2
)

set "AUDIT_OUTPUT=%~1"
if not defined AUDIT_OUTPUT set "AUDIT_OUTPUT=results\llm_audit_pair_v41_seed42"

echo Running paired LLM audit: D0/C0 and D0/C1, seed 42, concurrency 8.
python -B batch_runner.py --policies LLM_Agent --designs D0 --conditions C0 C1 --seeds 42 --max-steps 30 --provider DeepSeek --model deepseek-v4-flash --llm-concurrency 8 --output "%AUDIT_OUTPUT%"
if errorlevel 1 exit /b %errorlevel%

python -B llm_audit.py "%AUDIT_OUTPUT%"
exit /b %errorlevel%
