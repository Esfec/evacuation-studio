@echo off
setlocal
cd /d "%~dp0"

if not defined DEEPSEEK_API_KEY (
  echo ERROR: DEEPSEEK_API_KEY is not set.
  exit /b 2
)
if /I not "%DEEPSEEK_API_KEY:~0,3%"=="sk-" (
  echo ERROR: DEEPSEEK_API_KEY must contain only the key value beginning with sk-.
  exit /b 2
)

echo Running frozen P0 formal LLM design matrix: 3 designs x 2 conditions x 20 paired seeds.
python -B batch_runner.py --policies LLM_Agent --designs D0 D1 D2 --conditions C0 C1 --seeds 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 --max-steps 30 --agents "agent_profiles\Agent_P0_current.json" --provider DeepSeek --model deepseek-v4-flash --llm-concurrency 8 --output "results\formal_design_p0_v1" --resume
set "FORMAL_EXIT=%errorlevel%"
echo Formal LLM output: results\formal_design_p0_v1
exit /b %FORMAL_EXIT%
