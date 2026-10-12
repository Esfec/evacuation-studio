@echo off
setlocal
cd /d "%~dp0"

echo Running matched no-API baselines: 4 policies x 3 designs x 2 conditions x 20 paired seeds.
python -B batch_runner.py --policies Local_Rule Global_ShortestPath RiskAware_Dijkstra Random --designs D0 D1 D2 --conditions C0 C1 --seeds 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 --max-steps 30 --agents "agent_profiles\Agent_P0_current.json" --output "results\formal_baselines_p0_v1" --resume
set "BASELINE_EXIT=%errorlevel%"
echo Formal baseline output: results\formal_baselines_p0_v1
exit /b %BASELINE_EXIT%
