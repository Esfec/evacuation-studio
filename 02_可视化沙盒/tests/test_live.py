import json
import sys
import threading
import time
import os
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_server import DEFAULT_REPO, PROTOCOL, RunSession, validate


def wait_until(predicate, seconds=5):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if predicate():
            return
        time.sleep(.01)
    assert predicate(), 'timed out'


def test_no_secret_means_no_llm_run(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(ValueError,match='API Key'):
        validate(dict(policy='LLM_Agent',provider='OpenAI'),DEFAULT_REPO)


def test_live_steps_pause_stop_and_persist(tmp_path):
    run=RunSession(dict(autoplay=False,steps=3),output=tmp_path)
    thread=threading.Thread(target=run.run)
    thread.start()
    wait_until(lambda:run.status=='paused')
    assert len(run.snapshots)==1
    initial=run.snapshots[0]
    assert initial['sim_time_s']==0
    assert sum(n['occupancy'] for n in initial['nodes'])==48
    run.control('step')
    wait_until(lambda:len(run.snapshots)==2 and run.status=='paused')
    time.sleep(.05)
    assert run.engine.current_step==1
    assert run.snapshots[-1]['sim_time_s']==5
    run.control('stop')
    thread.join(5)
    assert not thread.is_alive()
    assert run.status=='cancelled'
    assert (run.output/'replay.json').is_file()
    events=[json.loads(s) for s in (run.output/'events.jsonl').read_text('utf8').splitlines()]
    assert [e['seq'] for e in events]==list(range(1,len(events)+1))
    assert all(e['protocol']==PROTOCOL for e in events)
    assert events[-1]['type']=='run.ended'
    assert any(run.output.glob('research/*/agent_step.csv'))


def test_recording_is_deterministic_and_frames_do_not_alias(tmp_path):
    a=RunSession(dict(steps=8,design='D2',condition='C1'),output=tmp_path)
    b=RunSession(dict(steps=8,design='D2',condition='C1'),output=tmp_path)
    a.run();b.run()
    for aa,bb in zip(a.snapshots,b.snapshots):
        assert {k:v for k,v in aa.items() if k!='wall_seconds'}=={k:v for k,v in bb.items() if k!='wall_seconds'}
    assert a.snapshots[0]['completed_steps']==0
    assert a.snapshots[-1]['completed_steps']==8
    for f in a.snapshots:
        assert sum(f['counts'].values())==48
        for agent in f['agents']:
            assert agent['node']!='N10'


def test_llm_events_are_explicit_and_secret_free(monkeypatch,tmp_path):
    run=RunSession(dict(steps=1,policy='LLM_Agent',provider='OpenAI',api_key='TEST_SECRET',cognitive=4,perceptual=0,follower=0),output=tmp_path)
    import engine
    def fake_call(provider,key,model,messages,*args,**kwargs):
        # Deliberately invalid output exercises explicit, auditable fallback.
        time.sleep(.01)
        return dict(answer='{}',usage={},error=None)
    monkeypatch.setattr(engine,'call_llm',fake_call)
    run.run()
    kinds=[e['type'] for e in run.events]
    assert 'api.started' in kinds and 'api.finished' in kinds
    assert 'agent.observed' in kinds and 'agent.decided' in kinds
    assert run.engine.fallback_count>0
    replay=json.dumps(run.replay())
    assert 'TEST_SECRET' not in replay and 'api_key' not in replay
    assert all(not a['summary'] or isinstance(a['summary'],str) for a in run.snapshots[-1]['agents'])
    assert kinds.index('api.started')<kinds.index('api.finished')<max(i for i,k in enumerate(kinds) if k=='snapshot')


def test_fatal_llm_failure_is_not_completed(monkeypatch,tmp_path):
    run=RunSession(dict(steps=3,policy='LLM_Agent',provider='OpenAI',api_key='TEST_SECRET',cognitive=1,perceptual=0,follower=0),output=tmp_path)
    import engine
    monkeypatch.setattr(engine,'call_llm',lambda *a,**kw:dict(error='denied',error_type='authentication',retryable=False,usage={}))
    run.run()
    assert run.status=='failed'
    assert run.replay()['valid'] is False
    assert run.events[-1]['data']['status']=='failed'


def test_fallback_rng_does_not_depend_on_request_completion_order(monkeypatch,tmp_path):
    import engine
    def execute(reverse):
        run=RunSession(dict(steps=2,policy='LLM_Agent',provider='OpenAI',api_key='TEST_SECRET',cognitive=6,perceptual=0,follower=0),output=tmp_path)
        def fake_call(provider,key,model,messages,*args,**kwargs):
            # Different completion delays, identical invalid model responses.
            delay=(len(messages[-1]['content'])%5)
            time.sleep((5-delay if reverse else delay)*.002)
            return dict(error=None,answer='{}',usage={})
        monkeypatch.setattr(engine,'call_llm',fake_call)
        run.run()
        return [{k:v for k,v in f.items() if k!='wall_seconds'} for f in run.snapshots]
    assert execute(False)==execute(True)


def test_same_seed_reproduces_across_fresh_interpreters(tmp_path):
    script = """
import json, hashlib, sys
from studio_server import RunSession
r=RunSession(dict(steps=8), output=sys.argv[1]);r.run()
frames=[{k:v for k,v in f.items() if k!='wall_seconds'} for f in r.snapshots]
print(hashlib.sha256(json.dumps(frames,sort_keys=True).encode()).hexdigest())
"""
    hashes=[]
    for hashseed in ('1','77','1234'):
        env={**os.environ,'PYTHONHASHSEED':hashseed}
        hashes.append(subprocess.check_output([sys.executable,'-c',script,str(tmp_path)],
                        cwd=str(Path(__file__).resolve().parents[1]),env=env,text=True).strip())
    assert len(set(hashes))==1


def test_observation_context_is_recorded_before_movement(tmp_path):
    r=RunSession(dict(steps=3),output=tmp_path);r.run()
    for f in r.snapshots[1:]:
        for a in f['agents']:
            assert a['context']['memory'][-1]==a['from_node']
            assert a['context']['environment']['air']
            assert a['context']['state']['body']
