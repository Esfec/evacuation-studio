"""Operational audit for LLM synthetic-occupant pilot runs."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


AGENT_TYPES = ("Cognitive", "Perceptual", "Follower")
DECISION_MODES = {
    "LLM_API",
    "Rule_Fallback",
    "Panic_Crowd_Override",
    "Panic_Error_Override",
}


def _truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values):
    return round(sum(values) / len(values), 6) if values else None


def evaluate_llm_audit(
    agent_rows,
    llm_rows,
    meta_rows,
    *,
    completeness_ok,
):
    """Evaluate predeclared operational gates without claiming realism."""
    decisions = [
        row for row in agent_rows
        if row.get("decision_mode") in DECISION_MODES
    ]
    fallback_count = sum(
        1 for row in decisions if row.get("decision_mode") == "Rule_Fallback"
    )
    fallback_ratio = fallback_count / len(decisions) if decisions else 1.0
    successful_calls = sum(1 for row in llm_rows if _truthy(row.get("success")))
    api_success_ratio = successful_calls / len(llm_rows) if llm_rows else 0.0
    empty_briefs = sum(
        1 for row in decisions if not str(row.get("brief_justification", "")).strip()
    )
    empty_brief_ratio = empty_briefs / len(decisions) if decisions else 1.0
    invalid_actions = sum(
        1 for row in agent_rows
        if row.get("action_result") == "INVALID_TARGET"
    )

    by_type = {}
    for agent_type in AGENT_TYPES:
        rows = [row for row in decisions if row.get("agent_type") == agent_type]
        chosen_risks = [
            value for value in (_float(row.get("chosen_target_risk")) for row in rows)
            if value is not None
        ]
        safest = []
        dead_end = 0
        for row in rows:
            chosen_risk = _float(row.get("chosen_target_risk"))
            try:
                options = json.loads(row.get("visible_options_json") or "[]")
            except json.JSONDecodeError:
                options = []
            available_risks = [
                _float(option.get("risk")) for option in options
                if option.get("passable", False)
                and _float(option.get("risk")) is not None
            ]
            if chosen_risk is not None and available_risks:
                safest.append(chosen_risk <= min(available_risks) + 1e-9)
            if _truthy(row.get("chosen_is_dead_end")):
                dead_end += 1
        by_type[agent_type] = {
            "decisions": len(rows),
            "fallbacks": sum(
                1 for row in rows
                if row.get("decision_mode") == "Rule_Fallback"
            ),
            "mean_chosen_risk": _mean(chosen_risks),
            "safest_choice_ratio": (
                round(sum(safest) / len(safest), 6) if safest else None
            ),
            "dead_end_choice_ratio": (
                round(dead_end / len(rows), 6) if rows else None
            ),
        }

    gates = {
        "all_runs_valid": bool(meta_rows) and all(
            _truthy(row.get("valid_run")) for row in meta_rows
        ),
        "agent_step_complete": bool(completeness_ok),
        "api_attempt_success_ge_0_90": api_success_ratio >= 0.90,
        "fallback_ratio_le_0_10": fallback_ratio <= 0.10,
        "empty_brief_ratio_le_0_02": empty_brief_ratio <= 0.02,
        "invalid_target_actions_eq_0": invalid_actions == 0,
        "all_agent_types_observed": all(
            by_type[agent_type]["decisions"] > 0 for agent_type in AGENT_TYPES
        ),
    }
    return {
        "overall_pass": all(gates.values()),
        "gates": gates,
        "metrics": {
            "runs": len(meta_rows),
            "hybrid_decisions": len(decisions),
            "llm_or_fallback_decisions": len(decisions),
            "llm_call_attempts": len(llm_rows),
            "api_attempt_success_ratio": round(api_success_ratio, 6),
            "fallback_count": fallback_count,
            "fallback_ratio": round(fallback_ratio, 6),
            "empty_brief_ratio": round(empty_brief_ratio, 6),
            "invalid_target_actions": invalid_actions,
            "stress_override_count": sum(
                1 for row in decisions
                if row.get("decision_mode") in {
                    "Panic_Crowd_Override", "Panic_Error_Override"
                }
            ),
        },
        "by_agent_type": by_type,
        "interpretation_limit": (
            "Passing establishes operational auditability only; it does not "
            "establish empirical behavioural validity or real-world prediction."
        ),
    }


def collect_llm_audit(root):
    root = Path(root)
    meta_rows = []
    agent_rows = []
    llm_rows = []
    completeness_ok = True
    run_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    for run_dir in run_dirs:
        required = [
            run_dir / "simulation_meta.csv",
            run_dir / "agent_step.csv",
            run_dir / "llm_call_log.csv",
        ]
        if not all(path.exists() for path in required):
            continue
        with required[0].open(encoding="utf-8-sig", newline="") as handle:
            meta = next(csv.DictReader(handle))
        if meta.get("policy_id") != "LLM_Agent":
            continue
        meta_rows.append(meta)
        with required[1].open(encoding="utf-8-sig", newline="") as handle:
            current_agent_rows = list(csv.DictReader(handle))
        with required[2].open(encoding="utf-8-sig", newline="") as handle:
            current_llm_rows = list(csv.DictReader(handle))
        if not current_llm_rows:
            state_path = run_dir / "state_log.json"
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
                    current_llm_rows = state.get("llm_call_log", [])
                except (OSError, UnicodeError, json.JSONDecodeError):
                    current_llm_rows = []
        for row in current_agent_rows:
            row["run_id"] = meta.get("run_id", run_dir.name)
        for row in current_llm_rows:
            row["run_id"] = meta.get("run_id", run_dir.name)
        agent_rows.extend(current_agent_rows)
        llm_rows.extend(current_llm_rows)
        expected = int(meta.get("total_agents", 0)) * int(meta.get("total_steps", 0))
        completeness_ok = completeness_ok and len(current_agent_rows) == expected
    return evaluate_llm_audit(
        agent_rows, llm_rows, meta_rows, completeness_ok=completeness_ok
    )


def _markdown(report):
    status = "PASS" if report["overall_pass"] else "FAIL"
    lines = [
        "## Material Passport",
        "",
        "- Artifact: LLM synthetic-user operational audit",
        "- Verification status: ANALYZED",
        "- Evidence class: simulator logs and API metadata",
        "",
        f"# LLM audit: {status}",
        "",
        "## Gates",
        "",
    ]
    for name, passed in report["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — `{name}`")
    lines.extend(["", "## Metrics", ""])
    for name, value in report["metrics"].items():
        lines.append(f"- `{name}`: {value}")
    lines.extend(["", "## Agent types", ""])
    for agent_type, values in report["by_agent_type"].items():
        lines.append(f"- **{agent_type}**: {json.dumps(values, ensure_ascii=False)}")
    lines.extend(["", f"> {report['interpretation_limit']}", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root)
    report = collect_llm_audit(root)
    output = Path(args.output) if args.output else root / "llm_audit_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"overall_pass": report["overall_pass"], "output": str(output)}))
    return 0 if report["overall_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
