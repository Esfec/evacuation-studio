import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_formal_profile_lock_matches_selected_p0_hash():
    lock = json.loads(
        (BASE / "agent_profiles" / "formal_profile_lock.json").read_text("utf-8")
    )
    profile = BASE / "agent_profiles" / "Agent_P0_current.json"
    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    assert lock["selected_profile"] == "P0"
    assert lock["sha256"] == digest
    assert lock["calibration_status"] == "COMPLETE"


def test_llm_formal_script_freezes_full_paired_matrix():
    text = (BASE / "run_formal_design_p0_deepseek.cmd").read_text("utf-8")
    assert "--policies LLM_Agent" in text
    assert "--designs D0 D1 D2" in text
    assert "--conditions C0 C1" in text
    assert "--max-steps 30" in text
    assert "Agent_P0_current.json" in text
    assert "deepseek-v4-flash" in text
    assert "--llm-concurrency 8" in text
    assert "--resume" in text
    for seed in range(101, 121):
        assert str(seed) in text
    assert "sk-485" not in text


def test_baseline_script_uses_same_matrix_without_api():
    text = (BASE / "run_formal_baselines_p0.cmd").read_text("utf-8")
    assert "Local_Rule Global_ShortestPath RiskAware_Dijkstra Random" in text
    assert "--designs D0 D1 D2" in text
    assert "--conditions C0 C1" in text
    assert "Agent_P0_current.json" in text
    assert "--resume" in text
    assert "DEEPSEEK_API_KEY" not in text
    for seed in range(101, 121):
        assert str(seed) in text
