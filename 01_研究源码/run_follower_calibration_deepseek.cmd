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

set "CAL_ROOT=results\follower_calibration_v1"
set "REUSE_ROOT=%CAL_ROOT%\P0"

python -B follower_calibration.py plan --reuse-root "%REUSE_ROOT%" --output "%CAL_ROOT%"
if errorlevel 1 exit /b %errorlevel%

echo [P0] Running six cells: C0/C1 x seeds 41, 42 and 43.
python -B batch_runner.py --policies LLM_Agent --designs D0 --conditions C0 C1 --seeds 41 42 43 --max-steps 30 --agents "agent_profiles\Agent_P0_current.json" --provider DeepSeek --model deepseek-v4-flash --llm-concurrency 8 --output "%CAL_ROOT%\P0" --resume
if errorlevel 1 exit /b %errorlevel%

echo [P1] Running six cells: C0/C1 x seeds 41, 42 and 43.
python -B batch_runner.py --policies LLM_Agent --designs D0 --conditions C0 C1 --seeds 41 42 43 --max-steps 30 --agents "agent_profiles\Agent_P1_moderate.json" --provider DeepSeek --model deepseek-v4-flash --llm-concurrency 8 --output "%CAL_ROOT%\P1" --resume
if errorlevel 1 exit /b %errorlevel%

python -B follower_calibration.py analyze --p0-root "%CAL_ROOT%\P0" --p1-root "%CAL_ROOT%\P1" --reuse-root "%REUSE_ROOT%" --output "%CAL_ROOT%"
set "CAL_EXIT=%errorlevel%"
echo Calibration outputs: %CAL_ROOT%
exit /b %CAL_EXIT%
