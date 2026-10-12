import json
import sys
from dataclasses import replace
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_server import RunSession, validate, DEFAULT_REPO


def test_exact_positions_and_settings_roundtrip(tmp_path):
    params=dict(cognitive=2,perceptual=1,follower=1,steps=2,fire_origin='N06',fire_rate=.08,
                smoke_rate=.12,step_seconds=7,base_edge_capacity=6,
                initial_positions={'C01':'N01','C02':'N03','P03':'N04','F04':'N17'})
    r=RunSession(params,output=tmp_path);r.run()
    assert r.status=='completed'
    assert {a['id']:a['node'] for a in r.snapshots[0]['agents']}==params['initial_positions']
    assert r.engine.map_data['fire_origin']=='N06'
    assert r.snapshots[1]['sim_time_s']==7
    assert all(e['capacity_per_step']==6 for e in r.engine.edges)
    saved=json.loads((r.output/'settings.json').read_text('utf8'))
    b=RunSession(saved,output=tmp_path);b.run()
    for x,y in zip(r.snapshots,b.snapshots):
        assert {k:v for k,v in x.items() if k!='wall_seconds'}=={k:v for k,v in y.items() if k!='wall_seconds'}


def test_room_distribution_is_honored(tmp_path):
    r=RunSession(dict(cognitive=2,perceptual=1,follower=1,steps=1,
        initial_distribution={'N01':1,'N04':3}),output=tmp_path)
    r.run()
    assert r.engine.actual_initial_distribution=={'N01':1,'N04':3}


@pytest.mark.parametrize('extra',[
 {'initial_distribution':{'N11':48}},
 {'condition':'C1','initial_distribution':{'N10':48}},
 {'initial_distribution':{'N04':48}},
 {'initial_distribution':{'N03':3}},
 {'initial_positions':{'C01':'N03'}},
 {'fire_origin':'N11'}, {'fire_origin':'invalid'},
 {'fire_rate':float('nan')}, {'smoke_rate':0}, {'step_seconds':1.5},
 {'unrecognized_parameter':5},
])
def test_invalid_settings_rejected_before_running(extra):
    with pytest.raises(ValueError):
        validate(extra,DEFAULT_REPO)


def test_independent_smoke_timing_and_legacy_default(tmp_path):
    r=RunSession(dict(steps=1),output=tmp_path);r.run();e=r.engine
    risk,smoke,status=e._hazard_state('N03',2)
    assert smoke==pytest.approx(risk*.9)
    e.run_config=replace(e.run_config,smoke_rate=.2)
    risk2,smoke2,status2=e._hazard_state('N03',2)
    assert (risk2,status2)==(risk,status)
    assert smoke2>smoke


def test_profiles_are_validated_and_saved(tmp_path):
    profiles=json.loads((DEFAULT_REPO/'Agent.json').read_text('utf8'))
    profiles['agents'][0]['params']['memory']['memory_prompt_length']=6
    profiles['agents'][0]['params']['physical']['stamina']=75
    r=RunSession(dict(steps=1,agent_profiles=profiles),output=tmp_path);r.run()
    assert r.snapshots[0]['agents'][0]['stamina']==75
    assert r.settings['agent_profiles']['agents'][0]['params']['memory']['memory_prompt_length']==6
    profiles['agents'][0]['params']['perception']['noise']=1.5
    with pytest.raises(ValueError):
        RunSession(dict(agent_profiles=profiles),output=tmp_path)
