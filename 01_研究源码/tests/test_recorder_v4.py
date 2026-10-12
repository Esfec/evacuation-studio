import csv
import io
from types import SimpleNamespace

from recorder import export_llm_call_log, export_simulation_meta, save_run_v4
from run_config import AgentCounts, RunConfig


def test_meta_contains_policy_scenario_status_and_no_secret():
    cfg = RunConfig(
        seed=42,
        policy_id="Global_ShortestPath",
        design_id="D2",
        condition_id="C1",
        fire_origin="N06",
        max_steps=30,
        agent_counts=AgentCounts(1, 1, 1),
    )
    engine = SimpleNamespace(
        agents=[
            {"type": "Cognitive", "status": "Escaped"},
            {"type": "Perceptual", "status": "Exhausted"},
            {"type": "Follower", "status": "Active"},
        ],
        nodes={"N18": {"type": "exit"}},
        llm_call_log=[],
        sim_start_time=None,
        sim_end_time=None,
        step_stats=[],
        run_id="test",
        run_config=cfg,
        information_scope="global_current_state",
        intervention_manifest={"added_edges": ["N06->N08"]},
        actual_initial_distribution={"N06": 3},
        fallback_count=0,
        valid_run=True,
        invalid_reason="",
        api_key="must-not-appear",
        logs=[],
        cot_logs=[],
        node_occupancy_log=[],
        panic_event_log=[],
    )

    row = next(csv.DictReader(io.StringIO(export_simulation_meta(engine))))
    assert row["schema_version"] == "4.1"
    assert row["policy_id"] == "Global_ShortestPath"
    assert row["design_id"] == "D2"
    assert row["condition_id"] == "C1"
    assert row["exhausted"] == "1"
    assert "api_key" not in row
    assert "must-not-appear" not in str(row)


def test_save_run_v4_creates_run_directory_and_summary(tmp_path):
    cfg = RunConfig(
        seed=42,
        policy_id="Global_ShortestPath",
        design_id="D0",
        condition_id="C0",
        fire_origin="N06",
        max_steps=3,
        agent_counts=AgentCounts(1, 0, 0),
    )
    engine = SimpleNamespace(
        agents=[{"id": "C01", "type": "Cognitive", "status": "Active"}],
        nodes={"N06": {"type": "room"}},
        llm_call_log=[], sim_start_time=None, sim_end_time=None,
        step_stats=[], run_id="run-test", run_config=cfg,
        information_scope="global_current_state",
        intervention_manifest={}, actual_initial_distribution={"N06": 1},
        fallback_count=0, valid_run=True, invalid_reason="",
        logs=[], cot_logs=[], node_occupancy_log=[], panic_event_log=[],
    )
    run_dir = save_run_v4(engine, tmp_path)
    assert (run_dir / "simulation_meta.csv").exists()
    assert (run_dir / "state_log.json").exists()
    assert (tmp_path / "summary_v4.csv").exists()
    assert (tmp_path / "paper_summary_v1.csv").exists()


def test_export_llm_call_log_preserves_api_attempts():
    engine = SimpleNamespace(llm_call_log=[{
        "step": 2,
        "agent_id": "C01",
        "agent_type": "Cognitive",
        "model": "deepseek-v4-flash",
        "attempt": 1,
        "prompt_tokens": 101,
        "completion_tokens": 9,
        "total_tokens": 110,
        "latency_ms": 830,
        "success": True,
        "error_type": None,
        "error_msg": "",
    }])

    rows = list(csv.DictReader(io.StringIO(export_llm_call_log(engine))))

    assert len(rows) == 1
    assert rows[0]["agent_id"] == "C01"
    assert rows[0]["success"] == "True"
    assert rows[0]["total_tokens"] == "110"
