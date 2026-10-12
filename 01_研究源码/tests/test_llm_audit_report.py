import csv
import json

from llm_audit import collect_llm_audit, evaluate_llm_audit


def _agent_row(agent_type, mode="LLM_API", risk=0.1, brief="安全方向"):
    return {
        "agent_type": agent_type,
        "decision_mode": mode,
        "action_result": "MOVED",
        "brief_justification": brief,
        "chosen_target_risk": str(risk),
        "chosen_is_dead_end": "False",
        "visible_options_json": json.dumps([
            {"target_id": "N02", "risk": risk, "passable": True},
            {"target_id": "N03", "risk": 0.8, "passable": True},
        ]),
    }


def test_clean_llm_audit_passes_and_reports_type_metrics():
    agent_rows = [
        _agent_row("Cognitive"),
        _agent_row("Perceptual"),
        _agent_row("Follower"),
    ]
    llm_rows = [{"success": "True"} for _ in range(3)]
    meta_rows = [{"valid_run": "True"}]

    report = evaluate_llm_audit(
        agent_rows, llm_rows, meta_rows, completeness_ok=True
    )

    assert report["overall_pass"] is True
    assert report["metrics"]["fallback_ratio"] == 0.0
    assert report["by_agent_type"]["Cognitive"]["safest_choice_ratio"] == 1.0


def test_excessive_fallback_fails_audit_gate():
    agent_rows = [
        _agent_row("Cognitive", mode="Rule_Fallback") for _ in range(2)
    ] + [
        _agent_row("Perceptual"),
        _agent_row("Follower"),
    ]
    llm_rows = [{"success": "True"} for _ in range(4)]

    report = evaluate_llm_audit(
        agent_rows, llm_rows, [{"valid_run": "True"}],
        completeness_ok=True,
    )

    assert report["overall_pass"] is False
    assert report["gates"]["fallback_ratio_le_0_10"] is False


def test_collector_recovers_llm_attempts_from_state_when_csv_is_empty(tmp_path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    with (run_dir / "simulation_meta.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "run_id", "policy_id", "valid_run", "total_agents", "total_steps"
        ])
        writer.writeheader()
        writer.writerow({
            "run_id": "run-1", "policy_id": "LLM_Agent", "valid_run": True,
            "total_agents": 3, "total_steps": 1,
        })
    agent_rows = [
        {**_agent_row(agent_type), "agent_id": agent_type}
        for agent_type in ("Cognitive", "Perceptual", "Follower")
    ]
    with (run_dir / "agent_step.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(agent_rows[0]))
        writer.writeheader()
        writer.writerows(agent_rows)
    (run_dir / "llm_call_log.csv").write_text("", encoding="utf-8")
    (run_dir / "state_log.json").write_text(json.dumps({
        "llm_call_log": [{"success": True} for _ in range(3)]
    }), encoding="utf-8")

    report = collect_llm_audit(tmp_path)

    assert report["metrics"]["llm_call_attempts"] == 3
    assert report["gates"]["api_attempt_success_ge_0_90"] is True


def test_declared_stress_overrides_count_as_hybrid_decisions():
    agent_rows = [
        _agent_row("Cognitive", mode="Panic_Error_Override"),
        _agent_row("Perceptual"),
        _agent_row("Follower", mode="Panic_Crowd_Override"),
    ]
    report = evaluate_llm_audit(
        agent_rows,
        [{"success": "True"}],
        [{"valid_run": "True"}],
        completeness_ok=True,
    )

    assert report["metrics"]["hybrid_decisions"] == 3
    assert report["by_agent_type"]["Cognitive"]["decisions"] == 1
    assert report["by_agent_type"]["Follower"]["decisions"] == 1
