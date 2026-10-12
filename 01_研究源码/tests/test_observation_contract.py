import json
from dataclasses import replace
from pathlib import Path

from observation import archetype_guidance, body_state, smoke_state
from test_engine_consistency import make_engine


PROJECT_ROOT = Path(__file__).parents[1]


def _path(
    target_id,
    *,
    crowd=0,
    risk=0.1,
    is_exit=False,
    passable=True,
    static_hint="可见的局部空间线索",
    recent_flow=0,
):
    return {
        "target_id": target_id,
        "target_name": target_id,
        "air_condition": smoke_state(risk * 0.9, "Open"),
        "crowd_feeling": "几乎没人" if crowd == 0 else "有些拥挤",
        "static_hint": static_hint,
        "event_hint": "",
        "passable": passable,
        "_risk": risk,
        "_is_exit": is_exit,
        "_is_dead_end": False,
        "_status": "Open" if passable else "Blocked",
        "_crowd_count": crowd,
        "_recent_flow": recent_flow,
    }


def test_smoke_language_uses_one_monotonic_scale():
    assert smoke_state(0.10, "Open") == "空气清晰"
    assert smoke_state(0.50, "Risky") == "可见烟雾，能见度下降"
    assert smoke_state(0.90, "Blocked") == "严重浓烟和热风险，无法通行"


def test_body_state_uses_health_and_stamina():
    assert "体力接近耗尽" in body_state(100, 20)
    assert "烟雾伤害严重" in body_state(30, 90)


def test_archetypes_receive_distinct_guidance():
    guidance = {
        archetype_guidance(agent_type)
        for agent_type in ("Cognitive", "Perceptual", "Follower")
    }
    assert len(guidance) == 3


def test_prompt_contains_current_state_static_cues_and_no_distance():
    engine = make_engine(policy_id="LLM_Agent")
    engine.run_config = replace(engine.run_config, step_seconds=7)
    agent = engine.agents[0]
    agent.update(health=80.0, stamina=20.0, panic_level=0.5)
    engine.nodes["N01"].update(
        smoke_density=0.5,
        risk_level=0.55,
        status="Risky",
        current_count=2,
        area=10.0,
        static_cues=["挑高空间", "多向门廊"],
    )
    paths = [_path("N02", static_hint="宽走廊；可见方向标识")]

    prompt = engine._build_prompt(agent, paths, step=2)

    assert "火灾已持续约 14 秒" in prompt
    assert "当前位置环境" in prompt
    assert "可见烟雾，能见度下降" in prompt
    assert "体力接近耗尽" in prompt
    assert "挑高空间；多向门廊" in prompt
    assert "宽走廊；可见方向标识" in prompt
    assert "距离较近" not in prompt


def test_blocked_observation_is_reported_separately():
    engine = make_engine(policy_id="LLM_Agent")
    agent = engine.agents[0]
    blocked = _path("N03", passable=False)
    blocked["target_name"] = "封堵走廊"

    prompt = engine._build_prompt(
        agent,
        [_path("N02")],
        step=0,
        blocked_paths=[blocked],
    )

    assert "封堵走廊" in prompt
    assert "无法选择" in prompt


def test_declared_crowd_bias_follows_recent_flow_not_room_occupancy():
    engine = make_engine(policy_id="LLM_Agent")
    agent = engine.agents[0]
    agent["panic_level"] = 1.0
    agent["params"]["psychology"].update(
        panic_threshold=0.5,
        panic_behavior={
            "follow_crowd_bias": 1.0,
            "ignore_exit_prob": 0.0,
            "mistake_prob": 0.0,
        },
    )

    filtered, override, meta = engine._apply_stress_modulation(
        agent,
        [
            _path("N02", crowd=8, recent_flow=3),
            _path("N03", crowd=20, recent_flow=0),
        ],
    )

    assert [item["target_id"] for item in filtered] == ["N02", "N03"]
    assert override[0]["target_node"] == "N02"
    assert override[1] == "Panic_Crowd_Override"
    assert meta["stress_level"] == 1.0
    assert meta["behavior_override"] == "crowd_follow"


def test_mock_policy_does_not_call_every_zero_risk_room_an_exit():
    engine = make_engine(policy_id="Mock_Heterogeneous")
    agent = engine.agents[0]

    thought, target = engine._mock_decision(
        agent,
        [_path("N02", risk=0.0, is_exit=False)],
    )

    assert target == "N02"
    assert "发现出路" not in thought


def test_exit_masking_changes_llm_options_and_is_audited():
    engine = make_engine(policy_id="LLM_Agent")
    agent = engine.agents[0]
    agent["panic_level"] = 1.0
    agent["params"]["psychology"].update(
        panic_threshold=0.5,
        panic_behavior={
            "follow_crowd_bias": 0.0,
            "ignore_exit_prob": 1.0,
            "mistake_prob": 0.0,
        },
    )

    filtered, override, meta = engine._apply_stress_modulation(
        agent,
        [_path("N02"), _path("N03", is_exit=True)],
    )

    assert [item["target_id"] for item in filtered] == ["N02"]
    assert override is None
    assert meta["exit_cue_masked"] is True


def test_agent_profiles_are_conditional_and_allow_backtracking():
    data = json.loads((PROJECT_ROOT / "Agent.json").read_text(encoding="utf-8"))
    assert all(
        agent["params"]["behavior"]["can_backtrack"]
        for agent in data["agents"]
    )
    assert all(agent.get("paper_label") for agent in data["agents"])
    follower = next(
        agent for agent in data["agents"] if agent["type"] == "Follower"
    )
    assert "丧失" not in follower["desc"]
    assert "完全无法" not in follower["role_description"]
    assert "唯一的本能" not in follower["role_description"]


def test_map_nodes_have_hazard_neutral_static_cues():
    data = json.loads((PROJECT_ROOT / "Map.json").read_text(encoding="utf-8"))
    assert all(node.get("static_cues") for node in data["nodes"])
    fixed_hazard_words = ("烈火熊熊", "烟味", "热浪扑面", "火焰")
    assert all(
        not any(word in node.get("desc", "") for word in fixed_hazard_words)
        for node in data["nodes"]
    )


def test_adjacent_static_cues_do_not_reveal_hidden_topology():
    data = json.loads((PROJECT_ROOT / "Map.json").read_text(encoding="utf-8"))
    hidden_truth_phrases = ("没有可开启的外部出口", "没有其他房门")
    cue_text = " ".join(
        cue
        for node in data["nodes"]
        for cue in node.get("static_cues", [])
    )
    assert not any(phrase in cue_text for phrase in hidden_truth_phrases)


def test_formal_llm_run_applies_and_audits_stress_override(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "test-only"
    engine.llm_concurrency = 1
    engine.agents[0]["panic_level"] = 1.0
    engine.agents[0]["params"]["psychology"].update(
        panic_threshold=0.5,
        panic_behavior={
            "follow_crowd_bias": 0.0,
            "ignore_exit_prob": 0.0,
            "mistake_prob": 1.0,
        },
    )

    def llm_must_not_run(*args, **kwargs):
        raise AssertionError("stress override should precede the LLM request")

    monkeypatch.setattr(engine, "_call_llm", llm_must_not_run)
    engine.run_step()

    row = engine.agent_step_log[0]
    assert row["decision_mode"] == "Panic_Error_Override"
    assert row["stress_level"] == 1.0
    assert row["exit_cue_masked"] is False
    assert row["behavior_override"] == "action_error"


def test_formal_llm_run_passes_blocked_observations_separately(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "test-only"
    engine.llm_concurrency = 1
    engine.agents[0]["panic_level"] = 0.0
    visible = [_path("N02"), _path("N03", passable=False)]
    captured = {}

    monkeypatch.setattr(engine, "get_observation", lambda agent: visible)

    def capture_call(agent, paths, step, blocked_paths=None):
        captured["allowed"] = [path["target_id"] for path in paths]
        captured["blocked"] = [
            path["target_id"] for path in (blocked_paths or [])
        ]
        return {"target_node": "N02"}, "LLM_API", "局部选择", ""

    monkeypatch.setattr(engine, "_call_llm", capture_call)
    engine.run_step()

    assert captured == {"allowed": ["N02"], "blocked": ["N03"]}
