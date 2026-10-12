import ast
import threading
import time
from dataclasses import replace
from pathlib import Path

from run_config import AgentCounts, RunConfig
from config import LLM_PROVIDERS
from test_engine_consistency import make_engine


def test_engine_defines_only_one_llm_call_method():
    source = (Path(__file__).parents[1] / "engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    engine_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SimulationEngine"
    )
    definitions = [
        node for node in engine_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_call_llm"
    ]
    assert len(definitions) == 1


def test_prompt_contract_requests_target_id_and_brief_only():
    engine = make_engine(policy_id="LLM_Agent")
    paths = engine.get_observation(engine.agents[0])

    prompt = engine._build_prompt(engine.agents[0], paths, step=0)

    assert '"target_id"' in prompt
    assert '"brief_justification"' in prompt
    assert '"thought"' not in prompt
    assert '"target_name"' not in prompt
    assert "思维链" not in prompt


def test_run_config_freezes_llm_concurrency():
    config = RunConfig(
        seed=42,
        policy_id="LLM_Agent",
        design_id="D0",
        condition_id="C0",
        fire_origin="N01",
        max_steps=30,
        agent_counts=AgentCounts(1, 0, 0),
        llm_concurrency=8,
    )

    assert config.llm_concurrency == 8
    assert config.to_dict()["llm_concurrency"] == 8


def test_deepseek_flash_is_the_default_deepseek_model():
    assert LLM_PROVIDERS["DeepSeek"]["models"][0] == "deepseek-v4-flash"


def test_revised_audit_uses_a_fresh_v41_output_directory():
    script = (
        Path(__file__).parents[1] / "run_llm_audit_pair.cmd"
    ).read_text(encoding="utf-8")
    assert "llm_audit_pair_v41_seed42" in script
    assert "results\\llm_audit_pair_seed42\"" not in script


def test_llm_decisions_share_frozen_step_state_and_run_concurrently(monkeypatch):
    engine = make_engine(policy_id="LLM_Agent")
    engine.api_key = "test-only"
    engine.run_config = replace(
        engine.run_config,
        agent_counts=AgentCounts(4, 0, 0),
        llm_concurrency=4,
    )
    template = engine.agents[0]
    engine.agents = []
    for index in range(4):
        agent = {
            **template,
            "id": f"C{index + 1:02d}",
            "params": {
                **template["params"],
                "physical": {**template["params"]["physical"]},
            },
            "history": ["N01"],
            "recent_thoughts": [],
        }
        engine.agents.append(agent)

    lock = threading.Lock()
    active_calls = 0
    max_active_calls = 0
    observed_counts = []

    def fake_call(agent, paths, step, blocked_paths=None):
        nonlocal active_calls, max_active_calls
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
            observed_counts.append(engine.nodes["N01"]["current_count"])
        time.sleep(0.05)
        with lock:
            active_calls -= 1
        return {"target_node": "N02"}, "LLM_API", "brief", ""

    monkeypatch.setattr(engine, "_call_llm", fake_call)

    engine.run_step()

    assert max_active_calls > 1
    assert observed_counts == [4, 4, 4, 4]
    assert len(engine.agent_step_log) == 4
