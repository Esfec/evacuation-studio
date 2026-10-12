from test_live import RunSession


def test_replay_topology_reports_configured_fire_origin(tmp_path):
    run = RunSession(dict(steps=1, fire_origin='N06'), output=tmp_path)
    run.run()
    assert run.replay()['topology']['fire_origin'] == 'N06'
    started = next(e for e in run.events if e['type']=='run.started')
    assert started['data']['topology']['fire_origin'] == 'N06'


def test_runtime_failure_is_invalid_in_saved_replay_and_research(monkeypatch, tmp_path):
    run = RunSession(dict(steps=2), output=tmp_path)
    from engine import SimulationEngine
    def fail(self, *args, **kwargs):
        raise RuntimeError('controlled execution failure')
    monkeypatch.setattr(SimulationEngine, 'run_step', fail)
    run.run()
    assert run.status == 'failed'
    assert run.replay()['valid'] is False
    assert run.replay()['quality'] == 'invalid'
    assert run.engine.valid_run is False
