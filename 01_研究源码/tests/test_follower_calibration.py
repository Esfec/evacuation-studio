import json
from pathlib import Path

import pytest

from follower_calibration import (
    build_calibration_cells,
    collect_calibration,
    evaluate_calibration,
    make_plan,
    sha256_file,
    write_calibration_outputs,
)


BASE = Path(__file__).resolve().parents[1]
PROFILE_DIR = BASE / "agent_profiles"


def _require_archived_audit_runs(root):
    if not any(root.glob("*/simulation_meta.csv")):
        pytest.skip("full paid-model audit runs are not distributed in the Git repository")


def _load_profile(name):
    return json.loads((PROFILE_DIR / name).read_text(encoding="utf-8"))


def _agents_by_type(data):
    return {agent["type"]: agent for agent in data["agents"]}


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            result.update(_flatten(child, path))
        return result
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def test_profiles_change_only_predeclared_follower_fields():
    p0 = _agents_by_type(_load_profile("Agent_P0_current.json"))
    p1 = _agents_by_type(_load_profile("Agent_P1_moderate.json"))
    assert p0["Cognitive"] == p1["Cognitive"]
    assert p0["Perceptual"] == p1["Perceptual"]

    flat0 = _flatten(p0["Follower"])
    flat1 = _flatten(p1["Follower"])
    changed = {key for key in flat0 if flat0[key] != flat1[key]}
    assert changed == {
        "params.physical.stamina_decay_rate",
        "params.psychology.panic_threshold",
        "params.psychology.stress_resistance",
        "params.psychology.panic_behavior.mistake_prob",
        "params.psychology.panic_behavior.ignore_exit_prob",
        "params.psychology.panic_behavior.follow_crowd_bias",
    }
    assert p1["Follower"]["params"]["physical"]["stamina_decay_rate"] == 4.0
    psychology = p1["Follower"]["params"]["psychology"]
    assert psychology["panic_threshold"] == 0.70
    assert psychology["stress_resistance"] == 0.25
    assert psychology["panic_behavior"] == {
        "mistake_prob": 0.45,
        "ignore_exit_prob": 0.35,
        "follow_crowd_bias": 0.60,
    }


def _record(profile, condition, seed, follower_escape_rate):
    follower_total = 10
    follower_escaped = round(follower_total * follower_escape_rate)
    return {
        "profile": profile,
        "condition_id": condition,
        "seed": seed,
        "quality_pass": True,
        "by_type": {
            "Cognitive": {
                "total": 10, "escaped": 9, "escape_rate": 0.9,
                "mean_smoke": 0.8, "mean_backtracks": 0.5,
                "mean_final_panic": 0.2, "stress_override_ratio": 0.02,
            },
            "Perceptual": {
                "total": 10, "escaped": 7, "escape_rate": 0.7,
                "mean_smoke": 1.6, "mean_backtracks": 1.2,
                "mean_final_panic": 0.5, "stress_override_ratio": 0.12,
            },
            "Follower": {
                "total": follower_total, "escaped": follower_escaped,
                "escape_rate": follower_escaped / follower_total,
                "mean_smoke": 2.8, "mean_backtracks": 2.0,
                "mean_final_panic": 0.8, "stress_override_ratio": 0.25,
            },
        },
    }


def test_build_calibration_cells_is_complete_and_paired():
    cells = build_calibration_cells((41, 42, 43))
    assert len(cells) == 12
    assert {
        (cell["profile"], cell["condition_id"], cell["seed"])
        for cell in cells
    } == {
        (profile, condition, seed)
        for profile in ("P0", "P1")
        for condition in ("C0", "C1")
        for seed in (41, 42, 43)
    }


def test_incomplete_matrix_never_selects_profile():
    rows = [
        _record(profile, condition, seed, 0.4)
        for profile in ("P0", "P1")
        for condition in ("C0", "C1")
        for seed in (41, 42, 43)
    ][:-1]
    report = evaluate_calibration(rows)
    assert report["status"] == "INCOMPLETE"
    assert report["selected_profile"] is None


def test_p1_selected_only_when_p0_is_saturated_and_p1_passes():
    rows = []
    for profile in ("P0", "P1"):
        for condition in ("C0", "C1"):
            for seed in (41, 42, 43):
                escape_rate = 0.0 if profile == "P0" else (
                    0.5 if condition == "C0" else 0.3
                )
                rows.append(_record(profile, condition, seed, escape_rate))
    report = evaluate_calibration(rows)
    assert report["status"] == "COMPLETE"
    assert report["selected_profile"] == "P1"


def test_profile_hash_is_stable_and_distinct():
    p0 = PROFILE_DIR / "Agent_P0_current.json"
    p1 = PROFILE_DIR / "Agent_P1_moderate.json"
    assert sha256_file(p0) == sha256_file(p0)
    assert sha256_file(p0) != sha256_file(p1)


def test_existing_v41_seed42_pair_is_reusable():
    root = BASE / "results" / "llm_audit_pair_v41_seed42"
    _require_archived_audit_runs(root)
    records = collect_calibration([root], [])
    assert {
        (row["profile"], row["condition_id"], row["seed"])
        for row in records
    } == {("P0", "C0", 42), ("P0", "C1", 42)}
    assert all(row["quality_pass"] for row in records)


def test_dry_plan_reuses_two_cells_and_leaves_ten_pending():
    root = BASE / "results" / "llm_audit_pair_v41_seed42"
    _require_archived_audit_runs(root)
    plan = make_plan(root)
    assert len(plan["cells"]) == 12
    assert plan["reusable_count"] == 2
    assert plan["pending_count"] == 10


def test_incomplete_outputs_never_claim_selection(tmp_path):
    report = evaluate_calibration([])
    outputs = write_calibration_outputs(
        report,
        [],
        tmp_path,
        {
            "P0": PROFILE_DIR / "Agent_P0_current.json",
            "P1": PROFILE_DIR / "Agent_P1_moderate.json",
        },
    )
    decision = json.loads(Path(outputs["decision_json"]).read_text("utf-8"))
    assert decision["status"] == "INCOMPLETE"
    assert decision["selected_profile"] is None
    manifest = json.loads(Path(outputs["manifest_json"]).read_text("utf-8"))
    assert manifest["profiles"]["P0"]["sha256"] == sha256_file(
        PROFILE_DIR / "Agent_P0_current.json"
    )


def test_windows_wrapper_freezes_low_cost_matrix_without_key_material():
    text = (BASE / "run_follower_calibration_deepseek.cmd").read_text(
        encoding="utf-8"
    )
    assert "deepseek-v4-flash" in text
    assert "--llm-concurrency 8" in text
    assert "--designs D0" in text
    assert "--conditions C0 C1" in text
    assert "--max-steps 30" in text
    # A public checkout has no paid seed-42 raw logs to reuse.
    assert text.count("--seeds 41 42 43") == 2
    assert text.count("--resume") == 2
    assert "DEEPSEEK_API_KEY" in text
    assert "sk-485" not in text
