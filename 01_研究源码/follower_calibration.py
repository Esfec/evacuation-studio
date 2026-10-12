"""Preregistered P0/P1 calibration analysis for the Follower archetype."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from llm_audit import DECISION_MODES, evaluate_llm_audit


AGENT_TYPES = ("Cognitive", "Perceptual", "Follower")
DISTINGUISHABILITY_THRESHOLDS = {
    "escape_rate": 0.10,
    "mean_smoke": 0.25,
    "mean_backtracks": 0.50,
    "mean_final_panic": 0.10,
    "stress_override_ratio": 0.05,
}


def build_calibration_cells(seeds=(41, 42, 43)):
    """Return the frozen 2-profile × 2-condition paired matrix."""
    return [
        {"profile": profile, "condition_id": condition, "seed": int(seed)}
        for profile in ("P0", "P1")
        for condition in ("C0", "C1")
        for seed in seeds
    ]


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _range(values):
    return max(values) - min(values) if values else 0.0


def evaluate_profile(records):
    """Evaluate one profile against the preregistered non-degeneracy rules."""
    follower = [row["by_type"]["Follower"] for row in records]
    escape_rates = [row["escape_rate"] for row in follower]
    mixed_runs = sum(0 < value < 1 for value in escape_rates)
    c0 = [
        row["by_type"]["Follower"]["escape_rate"]
        for row in records if row["condition_id"] == "C0"
    ]
    c1 = [
        row["by_type"]["Follower"]["escape_rate"]
        for row in records if row["condition_id"] == "C1"
    ]
    stress_rates = [row["stress_override_ratio"] for row in follower]

    aggregate_ranges = {}
    for metric, threshold in DISTINGUISHABILITY_THRESHOLDS.items():
        type_means = []
        for agent_type in AGENT_TYPES:
            values = [row["by_type"][agent_type][metric] for row in records]
            type_means.append(sum(values) / len(values))
        aggregate_ranges[metric] = {
            "range": round(_range(type_means), 6),
            "threshold": threshold,
            "passes": _range(type_means) >= threshold,
        }
    distinguishable_dimensions = sum(
        item["passes"] for item in aggregate_ranges.values()
    )
    gates = {
        "all_runs_quality_pass": len(records) == 6 and all(
            row.get("quality_pass", False) for row in records
        ),
        "follower_not_uniform_boundary": bool(escape_rates) and not (
            all(value == 0 for value in escape_rates)
            or all(value == 1 for value in escape_rates)
        ),
        "mixed_outcomes_in_at_least_two_runs": mixed_runs >= 2,
        "stress_override_nonzero_below_0_50": bool(stress_rates)
        and max(stress_rates) < 0.50 and sum(stress_rates) > 0,
        "c1_median_not_better_than_c0": bool(c0 and c1)
        and median(c1) <= median(c0),
        "at_least_two_distinguishable_dimensions": (
            distinguishable_dimensions >= 2
        ),
    }
    boundary_concentration = bool(escape_rates) and sum(
        value <= 0.10 or value >= 0.90 for value in escape_rates
    ) >= 5
    return {
        "passes": all(gates.values()),
        "gates": gates,
        "boundary_concentration": boundary_concentration,
        "mixed_run_count": mixed_runs,
        "median_follower_escape_rate_c0": median(c0) if c0 else None,
        "median_follower_escape_rate_c1": median(c1) if c1 else None,
        "distinguishability": aggregate_ranges,
    }


def evaluate_calibration(records):
    """Select a profile only after all twelve frozen cells are present."""
    expected = {
        (cell["profile"], cell["condition_id"], cell["seed"])
        for cell in build_calibration_cells()
    }
    present = {
        (row["profile"], row["condition_id"], int(row["seed"]))
        for row in records
    }
    if present != expected or len(records) != len(expected):
        return {
            "status": "INCOMPLETE",
            "selected_profile": None,
            "expected_cells": len(expected),
            "present_cells": len(present & expected),
            "missing_cells": [
                {"profile": p, "condition_id": c, "seed": s}
                for p, c, s in sorted(expected - present)
            ],
        }

    profiles = {
        profile: evaluate_profile([
            row for row in records if row["profile"] == profile
        ])
        for profile in ("P0", "P1")
    }
    selected = None
    if profiles["P1"]["passes"] and (
        not profiles["P0"]["passes"]
        or profiles["P0"]["boundary_concentration"]
    ):
        selected = "P1"
    elif profiles["P0"]["passes"]:
        selected = "P0"
    return {
        "status": "COMPLETE",
        "selected_profile": selected,
        "profiles": profiles,
        "interpretation_limit": (
            "This calibration establishes operational non-degeneracy and "
            "sensitivity, not empirical behavioural validity."
        ),
    }


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _llm_rows(run_dir):
    rows = _read_csv(run_dir / "llm_call_log.csv")
    if rows:
        return rows
    state_path = run_dir / "state_log.json"
    if not state_path.exists():
        return []
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    return state.get("llm_call_log", [])


def collect_run(run_dir, profile):
    """Collect one saved simulation into a profile-comparison record."""
    run_dir = Path(run_dir)
    required = [
        run_dir / "simulation_meta.csv",
        run_dir / "agent_final.csv",
        run_dir / "agent_step.csv",
        run_dir / "llm_call_log.csv",
    ]
    if not all(path.exists() for path in required):
        return None
    meta_rows = _read_csv(required[0])
    if not meta_rows:
        return None
    meta = meta_rows[0]
    if (
        meta.get("policy_id") != "LLM_Agent"
        or meta.get("design_id") != "D0"
        or meta.get("condition_id") not in {"C0", "C1"}
    ):
        return None
    try:
        seed = int(meta["seed"])
        total_agents = int(meta["total_agents"])
        total_steps = int(meta["total_steps"])
    except (KeyError, TypeError, ValueError):
        return None

    final_rows = _read_csv(required[1])
    agent_rows = _read_csv(required[2])
    llm_rows = _llm_rows(run_dir)
    completeness_ok = len(agent_rows) == total_agents * total_steps
    audit = evaluate_llm_audit(
        agent_rows, llm_rows, [meta], completeness_ok=completeness_ok
    )
    quality_pass = (
        meta.get("schema_version") == "4.1" and audit["overall_pass"]
    )

    steps_by_agent = defaultdict(list)
    for row in agent_rows:
        steps_by_agent[row.get("agent_id", "")].append(row)
    by_type = {}
    for agent_type in AGENT_TYPES:
        finals = [row for row in final_rows if row.get("type") == agent_type]
        type_steps = [
            row for row in agent_rows if row.get("agent_type") == agent_type
        ]
        latest_exposure = []
        for final in finals:
            rows = steps_by_agent.get(final.get("agent_id", ""), [])
            latest_exposure.append(max(
                (_float(row.get("cumulative_smoke_exposure")) for row in rows),
                default=0.0,
            ))
        decisions = [
            row for row in type_steps
            if row.get("decision_mode") in DECISION_MODES
        ]
        stress = sum(
            row.get("decision_mode") in {
                "Panic_Crowd_Override", "Panic_Error_Override"
            }
            for row in decisions
        )
        total = len(finals)
        escaped = sum(row.get("status") == "Escaped" for row in finals)
        by_type[agent_type] = {
            "total": total,
            "escaped": escaped,
            "dead": sum(row.get("status") == "Dead" for row in finals),
            "escape_rate": escaped / total if total else 0.0,
            "mean_smoke": _mean(latest_exposure),
            "mean_backtracks": _mean([
                _float(row.get("backtrack_count")) for row in finals
            ]),
            "mean_final_panic": _mean([
                _float(row.get("final_panic")) for row in finals
            ]),
            "stress_override_ratio": stress / len(decisions) if decisions else 0.0,
            "decision_count": len(decisions),
        }
    return {
        "profile": profile,
        "condition_id": meta["condition_id"],
        "seed": seed,
        "run_id": meta.get("run_id", run_dir.name),
        "run_dir": str(run_dir.resolve()),
        "schema_version": meta.get("schema_version"),
        "quality_pass": quality_pass,
        "audit_gates": audit["gates"],
        "api_success_ratio": audit["metrics"]["api_attempt_success_ratio"],
        "fallback_ratio": audit["metrics"]["fallback_ratio"],
        "by_type": by_type,
    }


def collect_calibration(p0_roots, p1_roots):
    """Collect and deduplicate profile cells; earlier roots take precedence."""
    selected = {}
    for profile, roots in (("P0", p0_roots), ("P1", p1_roots)):
        for root in roots:
            root = Path(root)
            if not root.exists():
                continue
            for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
                record = collect_run(run_dir, profile)
                if record is None or record["seed"] not in {41, 42, 43}:
                    continue
                key = (profile, record["condition_id"], record["seed"])
                selected.setdefault(key, record)
    return [selected[key] for key in sorted(selected)]


def make_plan(reuse_root):
    reusable_records = collect_calibration([reuse_root], [])
    reusable = {
        (row["profile"], row["condition_id"], row["seed"])
        for row in reusable_records if row["quality_pass"]
    }
    cells = []
    for cell in build_calibration_cells():
        key = (cell["profile"], cell["condition_id"], cell["seed"])
        cells.append({**cell, "status": "REUSABLE" if key in reusable else "PENDING"})
    return {
        "cells": cells,
        "reusable_count": sum(cell["status"] == "REUSABLE" for cell in cells),
        "pending_count": sum(cell["status"] == "PENDING" for cell in cells),
    }


def write_calibration_outputs(report, records, output_dir, profile_paths):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "matrix": build_calibration_cells(),
        "profiles": {
            profile: {
                "path": str(Path(path).resolve()),
                "sha256": sha256_file(path),
            }
            for profile, path in profile_paths.items()
        },
        "interpretation_limit": (
            "Operational calibration only; not empirical behavioural validity."
        ),
    }
    manifest_path = output_dir / "calibration_manifest.json"
    decision_path = output_dir / "calibration_decision.json"
    runs_path = output_dir / "calibration_runs.csv"
    types_path = output_dir / "calibration_by_type.csv"
    report_path = output_dir / "calibration_report.md"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    decision_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    run_fields = [
        "profile", "condition_id", "seed", "run_id", "schema_version",
        "quality_pass", "api_success_ratio", "fallback_ratio", "run_dir",
    ]
    with runs_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=run_fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in run_fields} for row in records)
    type_fields = [
        "profile", "condition_id", "seed", "agent_type", "total", "escaped",
        "dead", "escape_rate", "mean_smoke", "mean_backtracks",
        "mean_final_panic", "stress_override_ratio", "decision_count",
    ]
    with types_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=type_fields)
        writer.writeheader()
        for row in records:
            for agent_type, values in row["by_type"].items():
                writer.writerow({
                    "profile": row["profile"],
                    "condition_id": row["condition_id"],
                    "seed": row["seed"],
                    "agent_type": agent_type,
                    **values,
                })
    lines = [
        "# Follower calibration report", "",
        f"- Status: **{report['status']}**",
        f"- Selected profile: **{report.get('selected_profile') or 'NONE'}**",
        f"- Included cells: {len(records)}/12", "",
        "> Operational non-degeneracy and sensitivity only; this does not "
        "establish empirical behavioural validity.", "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "manifest_json": str(manifest_path),
        "decision_json": str(decision_path),
        "runs_csv": str(runs_path),
        "by_type_csv": str(types_path),
        "report_md": str(report_path),
    }


def main(argv=None):
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--reuse-root", required=True)
    plan_parser.add_argument("--output", required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--p0-root", required=True)
    analyze.add_argument("--p1-root", required=True)
    analyze.add_argument("--reuse-root", required=True)
    analyze.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    profile_paths = {
        "P0": base / "agent_profiles" / "Agent_P0_current.json",
        "P1": base / "agent_profiles" / "Agent_P1_moderate.json",
    }
    if args.command == "plan":
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        plan = make_plan(args.reuse_root)
        plan["profiles"] = {
            key: {"path": str(path), "sha256": sha256_file(path)}
            for key, path in profile_paths.items()
        }
        path = output / "calibration_plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        print(json.dumps({
            "cells": len(plan["cells"]),
            "reusable": plan["reusable_count"],
            "pending": plan["pending_count"],
            "output": str(path),
        }, ensure_ascii=False))
        return 0
    records = collect_calibration(
        [args.p0_root, args.reuse_root], [args.p1_root]
    )
    report = evaluate_calibration(records)
    outputs = write_calibration_outputs(
        report, records, args.output, profile_paths
    )
    print(json.dumps({
        "status": report["status"],
        "selected_profile": report.get("selected_profile"),
        "runs": len(records),
        "output": outputs["decision_json"],
    }, ensure_ascii=False))
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
