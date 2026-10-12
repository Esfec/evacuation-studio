from run_config import AgentCounts, RunConfig
from engine import SimulationEngine
import engine as engine_module


def make_engine(discovery_probability=1.0, policy_id="Local_Rule"):
    map_data = {
        "fire_origin": "N01",
        "nodes": [
            {"id": "N01", "name": "起火房间", "type": "fire", "capacity": 10},
            {"id": "N02", "name": "走廊", "type": "corridor", "capacity": 10},
            {"id": "N03", "name": "出口", "type": "exit", "capacity": 10},
        ],
        "edges": [
            {"source": "N01", "target": "N02", "dist": 1, "capacity_per_step": 2},
            {"source": "N02", "target": "N03", "dist": 1, "capacity_per_step": 2},
        ],
    }
    cfg = RunConfig(
        seed=42,
        policy_id=policy_id,
        design_id="D0",
        condition_id="C0",
        fire_origin="N01",
        max_steps=30,
        agent_counts=AgentCounts(1, 0, 0),
    )
    template = [{
        "type": "Cognitive",
        "desc": "test",
        "params": {
            "physical": {"base_speed": 1.2, "stamina": 100, "stamina_decay_rate": 2},
            "psychology": {
                "panic_threshold": 0.8,
                "stress_resistance": 0.8,
                "panic_behavior": {},
            },
            "perception": {
                "discovery_bias": {
                    "high_visibility": discovery_probability,
                    "low_visibility": discovery_probability,
                },
                "noise": 0,
            },
            "memory": {"memory_prompt_length": 2},
            "behavior": {"can_backtrack": True},
        },
    }]
    engine = SimulationEngine(map_data, template, run_config=cfg)
    engine.agents = [{
        "id": "C01",
        "type": "Cognitive",
        "params": template[0]["params"],
        "current_node": "N01",
        "status": "Active",
        "health": 100.0,
        "stamina": 100.0,
        "panic_level": 0.1,
        "history": ["N01"],
        "recent_thoughts": [],
        "last_thought": "",
        "last_reasoning": "",
    }]
    engine.update_environment(0, engine.fire_rate)
    return engine


def test_discovery_probability_zero_keeps_one_tactile_egress_option():
    engine = make_engine(discovery_probability=0.0)
    paths = engine.get_observation(engine.agents[0])

    assert [path["target_id"] for path in paths] == ["N02"]
    assert paths[0]["_perception_source"] == "tactile"


def test_blocked_edge_is_not_restored_by_tactile_fallback():
    engine = make_engine(discovery_probability=0.0)
    engine.nodes["N02"]["status"] = "Blocked"

    assert engine.get_observation(engine.agents[0]) == []


def test_discovery_probability_one_exposes_all_adjacent_edges():
    engine = make_engine(discovery_probability=1.0)
    paths = engine.get_observation(engine.agents[0])
    assert len(paths) == 1
    assert paths[0]["_perception_source"] == "direct"


def test_successful_move_creates_bidirectional_spatial_memory():
    engine = make_engine(discovery_probability=1.0)
    reverse = {"source": "N02", "target": "N01", "dist": 1.0, "capacity_per_step": 2}
    engine.edges.append(reverse)
    engine.adj["N02"].append(reverse)
    engine.G.add_edge("N02", "N01", weight=1.0)

    engine.run_step()

    memory = engine.agents[0]["known_connections"]
    assert memory["N01"] == ["N02"]
    assert memory["N02"] == ["N01"]


def test_cognitive_resistance_has_no_hidden_bonus():
    engine = make_engine()
    assert engine._stress_resistance(engine.agents[0]) == 0.8


def test_statistics_report_exhausted_separately():
    engine = make_engine()
    engine.agents[0]["status"] = "Exhausted"
    stats = engine.get_statistics()
    assert stats["exhausted"] == 1
    assert stats["active"] == 0


def test_global_shortest_policy_is_selected_by_frozen_config():
    engine = make_engine(policy_id="Global_ShortestPath")
    paths = engine.get_observation(engine.agents[0])
    decision, mode, _, _ = engine.decide(engine.agents[0], paths, 0)
    assert decision["target_node"] == "N02"
    assert mode == "Global_ShortestPath"


def test_random_negative_control_bypasses_panic_override():
    engine = make_engine(policy_id="Random")
    engine.agents[0]["panic_level"] = 1.0
    paths = engine.get_observation(engine.agents[0])
    decision, mode, _, _ = engine.decide(engine.agents[0], paths, 0)
    assert decision["target_node"] == "N02"
    assert mode == "Random"


def test_retryable_llm_failure_retries_three_times_then_falls_back(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "secret"
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        return {
            "reasoning": "", "answer": "", "usage": {},
            "error": "timeout", "error_type": "transport", "retryable": True,
        }

    monkeypatch.setattr(engine_module, "call_llm", failing)
    paths = engine.get_observation(engine.agents[0])
    _, mode, _, _ = engine._call_llm(engine.agents[0], paths, 0)
    assert len(calls) == 3
    assert mode == "Rule_Fallback"
    assert engine.fallback_count == 1
    assert engine.valid_run is True


def test_fatal_llm_failure_marks_partial_run_invalid(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "secret"

    def failing(*args, **kwargs):
        return {
            "reasoning": "", "answer": "", "usage": {},
            "error": "billing", "error_type": "billing", "retryable": False,
        }

    monkeypatch.setattr(engine_module, "call_llm", failing)
    paths = engine.get_observation(engine.agents[0])
    engine._call_llm(engine.agents[0], paths, 0)
    assert engine.valid_run is False
    assert engine.invalid_reason == "billing"


def test_invalid_llm_target_id_uses_recorded_fallback(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "secret"

    def invalid_target(*args, **kwargs):
        return {
            "reasoning": "", "answer": '{"target_id":"BAD","brief_justification":"x"}',
            "usage": {}, "model": "test", "error": None,
            "error_type": None, "retryable": False,
        }

    monkeypatch.setattr(engine_module, "call_llm", invalid_target)
    paths = engine.get_observation(engine.agents[0])
    decision, mode, _, _ = engine._call_llm(engine.agents[0], paths, 0)
    assert decision["target_node"] == "N02"
    assert mode == "Rule_Fallback"
    assert engine.fallback_count == 1
