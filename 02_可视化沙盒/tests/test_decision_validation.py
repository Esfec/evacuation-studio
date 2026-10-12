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


def test_room_name_target_is_normalized_and_audited(monkeypatch,tmp_path):
    import engine
    run=RunSession(dict(steps=1,policy="LLM_Agent",api_key="TEST_ONLY",
        cognitive=1,perceptual=0,follower=0,initial_positions={"C01":"N02"}),output=tmp_path)
    def fake(*args,**kw):
        name=re.search(r"允许目标：[A-Z0-9]+=([^,\n]+)",args[3][-1]["content"]).group(1).strip()
        return dict(answer=json.dumps({"target_id":name,"brief_justification":"test"},ensure_ascii=False),
                    finish_reason="stop",usage={},error=None)
    monkeypatch.setattr(engine,"call_llm",fake)
    run.run()
    log=run.engine.llm_call_log
    assert len(log)==1 and log[0]["success"] and log[0]["target_normalization"]=="name"
    assert run.engine.fallback_count==0
    assert run.engine.cot_logs[-1]["decision_mode"]=="LLM_API"


def test_invalid_target_retry_carries_correction(monkeypatch,tmp_path):
    import engine
    run=RunSession(dict(steps=1,policy="LLM_Agent",api_key="TEST_ONLY",
        cognitive=1,perceptual=0,follower=0,initial_positions={"C01":"N02"}),output=tmp_path)
    seen=[]
    def fake(*args,**kw):
        msgs=args[3];seen.append(msgs)
        if len(seen)==1:
            return dict(answer='{"target_id":"过厅","brief_justification":"test"}',finish_reason="stop",usage={},error=None)
        target=re.search(r"允许目标：([A-Z0-9]+)=",msgs[-1]["content"]).group(1)
        return dict(answer=json.dumps({"target_id":target,"brief_justification":"test"}),finish_reason="stop",usage={},error=None)
    monkeypatch.setattr(engine,"call_llm",fake)
    run.run()
    assert len(seen)==2 and len(seen[0])==2
    assert seen[1][2]=={"role":"assistant","content":'{"target_id":"过厅","brief_justification":"test"}'}
    assert "「过厅」" in seen[1][3]["content"]
    log=run.engine.llm_call_log
    assert [x["feedback_retry"] for x in log]==[False,True] and log[-1]["success"]
    assert run.engine.fallback_count==0
