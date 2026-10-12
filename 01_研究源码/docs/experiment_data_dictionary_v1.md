# Experiment data dictionary v1

Every completed run and every UI manual step writes to
`results/<run_id>/`. Manual steps refresh a checkpoint without adding an
unfinished row to the final summary.

## Files

| File | Unit of observation | Scientific use |
|---|---|---|
| `simulation_meta.csv` | one run | frozen configuration, model, D/C, validity |
| `run_metrics.csv` | one run | primary and secondary endpoints |
| `agent_step.csv` | one agent × one step | behaviour, exposure, waiting, audit trail |
| `node_step.csv` | one node × one step | hazard evolution, occupancy, spatial failure |
| `edge_step.csv` | one directed edge × one step | demand, throughput, queue, bottleneck |
| `decision_log.csv` | one decision | origin, target, policy, brief justification |
| `movement_log.csv` | one movement proposal | intended target, actual node, rejection cause |
| `llm_call_log.csv` | one API call | model, latency, tokens, error and fallback audit |
| `agent_final.csv` | one agent | final outcome and complete path |
| `state_log.json` | one run | lossless combined record and initial snapshot |

`paper_summary_v1.csv` contains one final row per completed run. It is not
updated by UI checkpoints.

## Required action results

- `MOVED`
- `STAMINA_WAIT`
- `NO_VISIBLE_PATHS`
- `EDGE_QUEUE`
- `NODE_FULL`
- `TARGET_BLOCKED`
- `INVALID_TARGET`
- `NO_DECISION`
- `DIED`
- `EXHAUSTED`
- `INACTIVE_ESCAPED`, `INACTIVE_DEAD`, or `INACTIVE_EXHAUSTED`

## Recorded run metrics

These are available recorder fields, not equally weighted paper endpoints.
The paper's primary endpoint is horizon escape fraction. Nominal time
fields are scheduling labels; report evacuation outcomes in steps.

- escape, death, exhaustion, and active-at-horizon counts;
- T80, T90, T95, and clearance step/time, with blank values when unreached;
- median and p95 escape step;
- mean and p95 cumulative smoke exposure;
- total waiting, stamina waiting, edge queue, and node-full events;
- maximum edge queue, node occupancy, and density;
- mean backtracking, wall time, LLM calls, and fallback count;
- explicit termination reason and run-validity flag.

## Audit policy

Store only a concise, task-relevant justification. Do not request, publish, or
analyse hidden chain-of-thought. Prompt/model/version, structured observation,
selected target, latency, usage, error, retry, and fallback are sufficient for
reproducibility and auditability.

