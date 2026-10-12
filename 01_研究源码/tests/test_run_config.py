from dataclasses import FrozenInstanceError

import pytest

from run_config import AgentCounts, RunConfig


def test_run_config_is_frozen_and_serializable():
    cfg = RunConfig(
        seed=42,
        policy_id="Global_ShortestPath",
        design_id="D2",
        condition_id="C1",
        fire_origin="N06",
        max_steps=30,
        agent_counts=AgentCounts(10, 15, 23),
    )

    assert cfg.to_dict()["agent_counts"]["Follower"] == 23
    with pytest.raises(FrozenInstanceError):
        cfg.seed = 7


def test_run_config_rejects_invalid_identifiers_and_counts():
    with pytest.raises(ValueError, match="policy_id"):
        RunConfig(
            seed=42,
            policy_id="unknown",
            design_id="D0",
            condition_id="C0",
            fire_origin="N06",
            max_steps=30,
            agent_counts=AgentCounts(10, 10, 10),
        )
    with pytest.raises(ValueError, match="non-negative"):
        AgentCounts(-1, 1, 1)
