# Results included in this repository

Only compact, processed evidence is versioned here:

- `formal_design_p0_v1/`: 120 LLM-run summaries and the formal report;
- `formal_baselines_p0_v1/`: 480 algorithmic-policy run summaries;
- `follower_calibration_v1/`: P0/P1 calibration manifest, decision and summaries;
- `llm_audit_pair_v41_seed42/`: paired D0/C0–D0/C1 contract-audit reports.
- `matched_ablation/`: C1 diagnostic run metrics, 40 matched LLM-off
  summaries and the archived paired bootstrap contrast output.

All paths above are under `results/processed/`. The analysis script preserves
the archived CSV precision (including rounded LLM escape fractions). It
resamples the 20 seed-paired differences with replacement 20,000 times and
uses percentile 2.5/97.5% intervals. RNG seeds are 20260830+i, 20260840+i and
20260850+i for the three contrasts in metric order in the script.
The receiving branch is N08/N13/N14/N16/N09; load sums occupancy over
nodes and steps, and failures count terminal failures at these nodes.

Timestamped run directories are excluded. Those directories contain complete
state logs, agent trajectories, local observations, movement records and LLM
call logs and together exceed 1 GB in the archived experiment.

