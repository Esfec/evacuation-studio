# Upload review — 2026-10-09

## Scope and provenance

This public copy derives from the operational_v3 implementation used for the
paper, with packaging and defensive error-handling fixes. The original
experiment directory and archived numerical results were not modified.
This is not a new experimentally validated engine version.

## Release fixes

- Added missing pinned Python requirements.
- Resolve UI map/profile files relative to the application.
- Isolate UI credentials by provider; infer the CLI credential variable from
  the provider; reject unknown providers without sending a request.
  Empty-key interactive LLM runs are blocked rather than silently producing
  rule-only runs with an LLM label.
- Redact keys and classify transport/HTTP failures in special adapters.
- Non-object LLM JSON follows the logged invalid-response fallback instead
  of crashing. Successful valid responses are unchanged.
- Check parameters, map/profile and source hashes before resuming; stop after
  an invalid run. Resume is run-level, not an incomplete-state continuation.
- Fresh calibration includes seed 42 without needing historical raw logs.
  Selection thresholds themselves are unchanged.
- Correct profile-lock preregistration wording, label D1 as capacity
  enhancement, and distinguish the final study from earlier plans.

## Scientific/reproducibility boundaries retained

1. **Time and geometry.** One hop is a unit topological movement. The legacy
   code retains STEP_SECONDS=5 and a prompt's elapsed-seconds label.
   These are nominal scheduling labels, not calibrated travel/fire times.
   Interpret paper endpoints in steps. Changing this prompt would define
   a different LLM experiment and was not done here.
2. **Initial states.** The legacy start-node candidate set is unsorted.
   Python hash randomization can change node assignments between processes
   even for the same simulation seed. For new campaigns set PYTHONHASHSEED
   before starting Python and retain initial snapshots. A fixed hash seed
   does not reconstruct unknown historical assignments. Strict matching
   requires replaying recorded initial states.
3. **Concurrency/API.** Shared random draws during threaded fallbacks and
   variable remote responses can prevent exact repeatability. A seed is not
   a deterministic replay guarantee. Dynamic model aliases may also change.
4. **LLM-off.** Local_Rule is a legacy baseline, not the exact matched
   LLM-off ablation. The latter preserves the LLM-path state/stress pipeline
   and uses archived initial states. Compact summaries support bootstrap
   reanalysis, not full state replay without the omitted raw logs.
5. **Behaviour and hazard.** Personas, stress, health/stamina, smoke and
   graph-distance hazard evolution are synthetic assumptions, not
   empirically validated population or CFD models.
6. **Historical reports.** Processed reports preserve earlier wording such
   as calibration/preregistered. A stored label is not independent evidence
   of preregistration; the final manuscript and current framework describe
   implementation selection. Audit passes do not establish human validity.
7. **Schemas.** The recorder exports more fields than the paper analyses;
   T80/T90/T95 are diagnostics, not the primary endpoint.

## Publication checklist

## Verification evidence

- Regression tests: 17 failures reproduced before fixes, all 17 pass after.
- Full suite in both the existing and newly installed isolated Python 3.12
  environment: **93 passed, 2 skipped**. Skips require omitted original paid
  seed-42 logs. Isolated environment has three upstream deprecation/cache
  warnings and no failing tests; dependency consistency check passes.
- A fresh install exposed an Arrow/NumPy incompatibility; Arrow is now pinned
  to the working 14.0.2 version. No compiler-dependent plotting package is
  required by this public runtime.
- Original vs public copy: four no-API policies × three designs × two
  conditions, seed 42, 48 occupants, 30-step horizon, PYTHONHASHSEED=0.
  All 24 runs agree across 36 paper-summary columns, excluding run ID and
  wall time. This is a regression check, not behavioural validation.
- The included matched-ablation reanalysis reproduces the archived JSON
  byte-for-byte (SHA-256:
  c83fefc1d2561c50b2d7b412560a571033f3add803f3bf5576f3debcaf504f01).

## Author actions before publication

- Author must approve an explicit licence and final citation. No licence was
  selected on the author's behalf.
- Never publish API keys, .env files, private correspondence, or the full
  working-directory/Git history. Previously shared keys should be revoked.
- Full reproduction of figures and spatial diagnostics needs a separate
  raw-data deposit; compact summaries alone do not provide that evidence.
- No new paid API calls or remote GitHub writes were performed in this review.
- API adapters were checked offline. Model availability and live
  authentication are not certified by these tests.
