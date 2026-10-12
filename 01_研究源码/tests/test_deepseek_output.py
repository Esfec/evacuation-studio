from llm_api import call_llm
import csv
import io
from types import SimpleNamespace
from recorder import export_decision_log


class Session:
    def post(self, *args, **kwargs):
        self.body = kwargs["json"]
        return self
    status_code = 200
    text = ""
    def json(self):
        return {"model":"deepseek-flash","choices":[{"finish_reason":"length",
            "message":{"content":"","reasoning_content":"internal"}}],
            "usage":{"completion_tokens":1024}}


def test_deepseek_structured_decisions_disable_thinking_and_request_json():
    session = Session()
    result = call_llm("DeepSeek","test-key","deepseek-v4-flash",[],session)
    assert session.body["thinking"] == {"type":"disabled"}
    assert session.body["response_format"] == {"type":"json_object"}
    assert result["finish_reason"] == "length"
    assert result["request_mode"] == "non_thinking_json"


def test_decision_csv_accounts_for_all_attempts():
    engine=SimpleNamespace(cot_logs=[dict(step=0,agent_id="C01",decision_mode="LLM_API")],
        llm_call_log=[dict(step=0,agent_id="C01",model="deepseek-flash",prompt_tokens=10,
                          completion_tokens=20,total_tokens=30,latency_ms=100) for _ in range(2)])
    row=next(csv.DictReader(io.StringIO(export_decision_log(engine))))
    assert (row["prompt_tokens"],row["completion_tokens"],row["total_tokens"],row["latency_ms"])==("20","40","60","200")
