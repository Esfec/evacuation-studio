# Auditable LLM-Agent Fire-Evacuation Design Screening

This repository contains the code and frozen design specifications for an
early-stage fire-evacuation design-screening workflow. A semantic building
topology is coupled with dynamic hazard states, heterogeneous synthetic
occupants, local partial observations, LLM or algorithmic route-choice
policies, synchronous capacity-constrained movement, and step-level audit
logs.

The repository supports comparative design diagnosis at the architectural
bubble-diagram stage. It is a research proof of concept, not a CFD model,
code-compliance tool, or validated predictor of real human evacuation.

## Repository contents

| Path | Purpose |
|---|---|
| `Agent.json` | Three frozen operational profiles and their prompts/parameters |
| `Map.json` | Eighteen-node semantic museum topology and static spatial cues |
| `agent_profiles/` | P0/P1 calibration profiles and the formal profile lock |
| `engine.py` | Hazard, agent-state and synchronous simulation loop |
| `observation.py` | Local partial-observation construction |
| `llm_api.py` | Provider adapters and structured LLM calls |
| `policies.py` | Local Rule, Global Shortest Path, Risk-Aware Dijkstra and Random baselines |
| `movement.py` | Capacity arbitration and simultaneous movement resolution |
| `scenarios.py` | D0/D1/D2 designs and C0/C1 conditions |
| `recorder.py` | Step-, agent-, node-, edge- and decision-level audit logs |
| `batch_runner.py` | Experiment matrix runner with configuration-checked resume |
| `app.py` | Streamlit visual interface |
| `tests/` | Mechanism, logging, UI and experiment-contract tests |
| `docs/` | Scientific framework, data dictionary and release-review limitations |
| `research_analysis/` | Matched LLM-off contrast reanalysis from compact run-level data |
| `figures/` | Final framework, topology and result figures in PNG/SVG |
| `results/processed/` | Compact summaries and audit reports; raw logs are excluded |

## Model conventions

- The map is a semantic topology. One directed edge represents one movement
  opportunity rather than a calibrated physical distance.
- One step is one synchronized decision epoch. An active occupant can move at
  most one topological hop per step.
- Fire and smoke cues are generated from the current simulation state. They
  are not embedded as fixed hazard claims in room prompts.
- Every LLM receives the same frozen start-of-step state as other occupants in
  that step. Accepted movements become visible at the next step.
- Operational profiles are controlled behavioural probes, not demographic
  classes or empirically validated population models.
- LLM outputs are constrained to locally perceived feasible targets and a
  short model-generated decision trace. Parsing, retries, fallbacks, stress
  overrides and final state transitions are recorded.

## Designs and conditions

| ID | Definition |
|---|---|
| D0 | Original topology |
| D1 | N06↔N10 per-step service capacity increased from 4 to 8 |
| D2 | Bidirectional unit-hop connection N06↔N08 added |
| C0 | Dynamic fire with all routes initially available |
| C1 | Same dynamic fire with N10 unavailable from step 0 |

The formal design matrix uses 48 synthetic occupants, 30 decision epochs and
20 paired seeds (101–120) for each design–condition cell.

## Installation

Python 3.12 was used for the archived experiments.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Web interface

```bash
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

The interface can configure the decision policy, provider/model, D/C
scenario, fire origin, seed, horizon, population composition and initial room
distribution. Widget changes take effect after reinitialization.
This UI is intended for local use; authentication and public hosting
hardening are outside this release.

## API configuration

API keys are read from environment variables and must never be committed.
For DeepSeek in PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your-key-here"
```

For Windows Command Prompt:

```cmd
set "DEEPSEEK_API_KEY=your-key-here"
```

Other provider variable names are defined in `config.py`.

## Rerun the experiment workflows

These commands rerun the study protocol; they do not promise byte-identical
historical LLM responses or initial assignments. Read
[`docs/RELEASE_REVIEW.md`](docs/RELEASE_REVIEW.md) before interpreting new runs.
For a quick no-API smoke test:

```bash
python batch_runner.py --policies Local_Rule --designs D0 --conditions C0 --seeds 42 --max-steps 3 --output results/smoke
```

Run the one-seed LLM contract audit before paid formal experiments:

```cmd
run_llm_audit_pair.cmd
```

Run the four no-API baselines:

```cmd
run_formal_baselines_p0.cmd
```

Run the formal DeepSeek matrix after setting the API key:

```cmd
run_formal_design_p0_deepseek.cmd
```

The runners resume completed valid runs, not partially executed steps.
A saved configuration/content-hash contract prevents reuse after parameter,
map, profile or computational-code changes. Use a fresh output directory
for legacy outputs without a contract. Use only one process per output
directory. Authentication/billing failures invalidate and stop a batch.
New raw outputs are written under `results/` and ignored by Git by default.

The optional `run_follower_calibration_deepseek.cmd` runs all 12 calibration
runs in a fresh checkout (two profiles × two conditions × three seeds);
it no longer assumes the two paid seed-42 logs already exist.
It does not automatically change the frozen formal P0 profile.

To recompute the matched LLM-off bootstrap contrasts without an API:

```bash
python research_analysis/analyze_llm_increment.py
```

The API model names in `config.py` are archived choices, not a verified
catalogue of currently available models. Supply a provider-compatible model
with `--provider` and `--model`; changes define a new experiment.
Non-DeepSeek adapters have offline tests, not live-provider validation.

## Tests

```bash
python -m pytest -q
```

## Public data scope

Two archive-dependent tests are skipped when excluded raw seed-42 logs are
absent. A skipped archive check is not evidence that new LLM runs pass
the scientific audit.

`results/processed/` contains the compact run summaries, calibration decision
and LLM audit reports used to document the study. Full state, agent-step,
node-step and LLM-call logs are intentionally not stored in Git because of
their size. They should be deposited in a research-data repository if public
release of the complete dataset is required.

## Citation and licence

The code accompanies the manuscript *LLM-Agent Stress Testing for Early-Stage
Fire-Evacuation Design Screening*. Add the final bibliographic record and an
author-approved open-source licence before making the repository public.

