import json
import re
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_server import RunSession, load_engine
load_engine()


@pytest.mark.parametrize("answer,finish,error", [
    ("","length","output_truncated"),
    ('{"target_id":"N07","brief_justification":"unfinished',"length","output_truncated"),
    ('{"target_id":"过厅","brief_justification":"test"}',"stop","invalid_target"),
])
def test_bad_output_is_retried_and_audited(monkeypatch,tmp_path,answer,finish,error):
    import engine
    run=RunSession(dict(steps=1,policy="LLM_Agent",provider="DeepSeek",api_key="TEST_ONLY",
        cognitive=1,perceptual=0,follower=0,initial_positions={"C01":"N02"}),output=tmp_path)
    monkeypatch.setattr(engine,"call_llm",lambda *a,**k:dict(answer=answer,finish_reason=finish,
        usage={"prompt_tokens":10,"completion_tokens":1024},error=None))
    run.run()
    assert len(run.engine.llm_call_log)==3
    assert all(x["transport_success"] and not x["success"] and x["error_type"]==error for x in run.engine.llm_call_log)
    assert run.engine.fallback_count==1
    assert run.engine.token_usage["completion"]==3072
    assert run.replay()["quality"]=="degraded"


def test_retry_can_recover_without_fallback(monkeypatch,tmp_path):
    import engine
    run=RunSession(dict(steps=1,policy="LLM_Agent",api_key="TEST_ONLY",
        cognitive=1,perceptual=0,follower=0,initial_positions={"C01":"N02"}),output=tmp_path)
    attempts=[]
    def fake(*args,**kw):
        attempts.append(1)
        target=re.search(r"允许目标：([A-Z0-9]+)=",args[3][-1]["content"]).group(1)
        return dict(answer="" if len(attempts)==1 else json.dumps({"target_id":target,"brief_justification":"test"}),
                    finish_reason="length" if len(attempts)==1 else "stop",usage={},error=None)
    monkeypatch.setattr(engine,"call_llm",fake)
    run.run()
    assert len(attempts)==2
    assert run.engine.fallback_count==0
    assert run.engine.llm_call_log[-1]["success"]
