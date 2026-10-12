from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1] / "results" / "processed" / "matched_ablation"
POLICY_RUNS = ROOT / "policy_diagnostic_run_metrics.csv"
ABLATION_RUNS = ROOT / "llm_off_ablation_c1" / "run_summary.csv"
OUT = ROOT.parents[1] / "reanalysis" / "llm_increment_analysis.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def bootstrap(values: np.ndarray, seed: int) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(20_000, len(values)), replace=True).mean(axis=1)
    return {
        "mean": float(values.mean()),
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
    }


policy = pd.read_csv(POLICY_RUNS)
llm = policy[policy.policy_id == "LLM_Agent"].copy()
# The diagnostic input contains C1-only rows; reject duplicate pair identities.
if llm.duplicated(["design_id", "seed"]).any():
    raise ValueError("Expected unique C1 design-seed rows")
ablation = pd.read_csv(ABLATION_RUNS)

metrics = [
    "escape_rate", "rmet30", "n04_failures", "receiving_person_steps",
    "receiving_failures", "total_failures",
]
output = {
    "estimand": "(D2-D0)_LLM minus (D2-D0)_LLM-off under C1, paired by seed",
    "metrics": {},
}
for index, metric in enumerate(metrics):
    llm_d0 = llm[llm.design_id == "D0"].set_index("seed")[metric]
    llm_d2 = llm[llm.design_id == "D2"].set_index("seed")[metric]
    off_d0 = ablation[ablation.design_id == "D0"].set_index("seed")[metric]
    off_d2 = ablation[ablation.design_id == "D2"].set_index("seed")[metric]
    seeds = list(range(101, 121))
    llm_effect = llm_d2.loc[seeds] - llm_d0.loc[seeds]
    off_effect = off_d2.loc[seeds] - off_d0.loc[seeds]
    output["metrics"][metric] = {
        "llm_d2_minus_d0": bootstrap(llm_effect.to_numpy(), 20260830 + index),
        "llm_off_d2_minus_d0": bootstrap(off_effect.to_numpy(), 20260840 + index),
        "difference_of_effects": bootstrap((llm_effect - off_effect).to_numpy(), 20260850 + index),
    }

OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(output, ensure_ascii=False, indent=2))
print(f"WROTE {OUT}")
