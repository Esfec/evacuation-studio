import copy
import random
from test_engine_consistency import make_engine
from test_observation_contract import _path


def test_llm_prompt_receives_observed_directional_flow():
    engine = make_engine()
    prompt = engine._build_prompt(engine.agents[0], [_path('N02', recent_flow=3)], 1)
    assert '上一时步' in prompt and '3' in prompt


def test_tactile_search_does_not_always_choose_lowest_node_id():
    targets = set()
    for seed in range(20):
        engine = make_engine(discovery_probability=0)
        engine.adj['N01'].append(dict(source='N01', target='N03', dist=1))
        engine.rng = random.Random(seed)
        targets.add(engine.get_observation(engine.agents[0])[0]['target_id'])
    assert targets == {'N02', 'N03'}


def test_known_door_remains_available_when_another_door_is_seen(monkeypatch):
    engine = make_engine(discovery_probability=.5)
    agent = engine.agents[0]
    agent['known_connections'] = {'N01': ['N02']}
    engine.adj['N01'].append(dict(source='N01', target='N03', dist=1))
    draws = iter([.9, .1])
    monkeypatch.setattr(engine.rng, 'random', lambda: next(draws))
    paths = engine.get_observation(agent)
    assert {p['target_id'] for p in paths} == {'N02', 'N03'}
    assert next(p for p in paths if p['target_id']=='N02')['_perception_source']=='memory'


def test_death_releases_room_capacity_before_moves(monkeypatch):
    engine = make_engine()
    agent = engine.agents[0]
    agent['params']['physical']['base_speed'] = 5
    dying = copy.deepcopy(agent)
    dying.update(id='C02', current_node='N02', history=['N02'], health=1)
    engine.agents.append(dying)
    engine.nodes['N02']['capacity'] = 1
    def environment(step):
        engine.nodes['N01'].update(current_count=1, risk_level=0, smoke_density=0)
        engine.nodes['N02'].update(current_count=1, risk_level=.6, smoke_density=.6)
    monkeypatch.setattr(engine, 'update_environment_v4', environment)
    engine.run_step()
    assert dying['status']=='Dead'
    assert agent['current_node']=='N02'


def test_rule_policy_uses_declared_panic_parameters(monkeypatch):
    engine = make_engine(policy_id='Local_Rule')
    agent = engine.agents[0]
    agent['panic_level'] = 1
    agent['params']['psychology']['panic_behavior'] = dict(
        mistake_prob=0, follow_crowd_bias=0, ignore_exit_prob=0)
    monkeypatch.setattr(engine, '_baseline_rule_decision', lambda a,p: ('rule', 'N02'))
    result = engine.decide(agent, [_path('N02')], 0)
    assert result[1]=='Local_Rule'
