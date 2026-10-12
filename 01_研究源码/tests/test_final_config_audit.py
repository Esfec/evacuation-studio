from dataclasses import replace
import pytest
from engine import SimulationEngine
from run_config import AgentCounts
from test_engine_consistency import make_engine


def test_frozen_config_drives_engine_without_duplicate_arguments():
    base = make_engine()
    cfg = replace(base.run_config, seed=91, fire_origin='N02', fire_rate=.2,
                  risky_coeff=5, blocked_coeff=9, temperature=.4)
    engine = SimulationEngine(base.map_data, list(base.template_map.values()), run_config=cfg)
    assert (engine.seed, engine.fire_rate, engine.risky_coeff, engine.blocked_coeff) == (91, .2, 5, 9)
    assert engine.map_data['fire_origin'] == 'N02'
    assert engine.temperature == .4


@pytest.mark.parametrize('count', [1.5, True])
def test_fractional_and_boolean_agent_counts_are_rejected(count):
    with pytest.raises(ValueError):
        AgentCounts(count, 0, 0)


def test_fractional_distribution_is_not_silently_truncated():
    with pytest.raises(ValueError):
        replace(make_engine().run_config, initial_distribution={'N01': 1.9})


def test_smoke_scale_follows_documented_pre_saturation_scope():
    engine = make_engine()
    engine.run_config = replace(engine.run_config, smoke_scale=0)
    assert engine._hazard_state('N01', 0)[1] == 0
    assert engine._hazard_state('N01', 100)[1] == 1


def test_original_map_is_not_mutated_by_fire_origin_override():
    base = make_engine()
    SimulationEngine(base.map_data, list(base.template_map.values()), fire_origin='N02')
    assert base.map_data['fire_origin'] == 'N01'
