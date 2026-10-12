import csv
import io
import json

from recorder import (
    export_agent_step_log,
    export_decision_log,
    export_edge_step_log,
    export_movement_log,
    export_node_step_log,
    export_run_metrics,
    save_checkpoint_v4,
)
from test_engine_consistency import make_engine


def test_every_agent_has_one_auditable_row_per_step():
    engine = make_engine()
    engine.agents[0]["params"]["physical"]["base_speed"] = 0.0

    engine.run_step()

    assert len(engine.agent_step_log) == len(engine.agents)
    row = engine.agent_step_log[0]
    assert row["step"] == 0
    assert row["action_result"] == "STAMINA_WAIT"
    assert row["from_node"] == "N01"
    assert row["actual_node"] == "N01"


def test_agent_step_time_is_end_of_completed_step():
    engine = make_engine()

    engine.run_step()

    assert engine.agent_step_log[0]["sim_time_s"] == engine.run_config.step_seconds


def test_terminal_health_and_stamina_are_clamped_to_zero():
    engine = make_engine()
    agent = engine.agents[0]
    engine.nodes["N01"].update(risk_level=1.0, smoke_density=1.0)
    agent["health"] = 20.0

    assert engine.apply_consequences(agent) is False
    assert agent["status"] == "Dead"
    assert agent["health"] == 0.0
    assert agent["stamina"] >= 0.0


def test_movement_export_contains_post_consequence_health():
    engine = make_engine()
    engine.run_step()

    row = next(csv.DictReader(io.StringIO(export_movement_log(engine))))

    assert float(row["health"]) == engine.agents[0]["health"]


def test_decision_audit_preserves_visible_options_and_selected_attributes():
    engine = make_engine()

    engine.run_step()

    row = engine.agent_step_log[0]
    options = json.loads(row["visible_options_json"])
    assert options[0]["target_id"] == "N02"
    assert row["chosen_target_risk"] != ""
    assert row["chosen_target_crowd"] != ""
    assert row["chosen_is_exit"] is False


def test_rejected_move_keeps_proposed_target(monkeypatch):
    engine = make_engine()

    def reject(*args, **kwargs):
        return {"accepted": [], "rejected": {"C01": "EDGE_QUEUE"}}

    monkeypatch.setattr("engine.resolve_moves", reject)
    engine.run_step()

    row = engine.agent_step_log[0]
    assert row["proposed_target"] == "N02"
    assert row["actual_node"] == "N01"
    assert row["action_result"] == "EDGE_QUEUE"
    assert engine.logs[0]["Proposed_To"] == "N02"


def test_all_nodes_and_edges_are_recorded_even_when_empty():
    engine = make_engine()
    engine.run_step()

    assert len(engine.node_step_log) == len(engine.nodes)
    assert len(engine.edge_step_log) == len(engine.edges)
    assert {row["node_id"] for row in engine.node_step_log} == set(engine.nodes)
    assert all("smoke_density" in row for row in engine.node_step_log)
    assert all("proposals" in row for row in engine.edge_step_log)


def test_checkpoint_writes_analysis_ready_csv_without_summary(tmp_path):
    engine = make_engine()
    engine.run_step()

    run_dir = save_checkpoint_v4(engine, tmp_path)

    for name in (
        "agent_step.csv", "node_step.csv", "edge_step.csv", "run_metrics.csv"
    ):
        assert (run_dir / name).exists()
    assert not (tmp_path / "summary_v4.csv").exists()
    state = json.loads((run_dir / "state_log.json").read_text(encoding="utf-8"))
    assert len(state["agent_step_log"]) == len(engine.agents)


def test_audit_log_exporters_have_stable_headers():
    engine = make_engine()
    engine.run_step()

    agent_row = next(csv.DictReader(io.StringIO(export_agent_step_log(engine))))
    node_row = next(csv.DictReader(io.StringIO(export_node_step_log(engine))))
    edge_row = next(csv.DictReader(io.StringIO(export_edge_step_log(engine))))

    assert agent_row["action_result"]
    assert "stress_level" in agent_row
    assert "exit_cue_masked" in agent_row
    assert "behavior_override" in agent_row
    assert "smoke_density" in node_row
    assert "utilization" in edge_row


def test_decision_export_preserves_origin_target_and_brief_justification():
    engine = make_engine()
    engine.run_step()

    row = next(csv.DictReader(io.StringIO(export_decision_log(engine))))

    assert row["from_node"] == "N01"
    assert row["to_node"] == "N02"
    assert row["brief_justification"]


def test_run_metrics_report_horizon_exposure_and_waiting():
    engine = make_engine()
    engine.run_step()
    engine.run_step()

    row = next(csv.DictReader(io.StringIO(export_run_metrics(engine))))

    assert row["termination_reason"] == "all_agents_resolved"
    assert row["escaped"] == "1"
    assert row["t80_step"] == "2"
    assert row["t80_seconds"] == str(2 * engine.run_config.step_seconds)
    assert row["median_escape_step"] == "2.0"
    assert float(row["mean_cumulative_smoke_exposure"]) >= 0.0
    assert "total_wait_events" in row
