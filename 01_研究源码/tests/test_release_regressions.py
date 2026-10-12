import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import batch_runner
from llm_api import call_llm
from test_engine_consistency import make_engine
from test_llm_failures import FixedSession, Response, TimeoutSession

BASE = Path(__file__).resolve().parents[1]


def test_unknown_provider_never_sends_a_request():
    class NoNetwork:
        def post(self, *args, **kwargs):
            pytest.fail("Unknown provider must fail before sending credentials")
    result = call_llm("typo", "secret", "model", [], session=NoNetwork())
    assert result["error_type"] == "configuration"


@pytest.mark.parametrize("provider", ["Anthropic Claude", "Google Gemini", "MiniMax"])
def test_all_adapters_redact_errors_and_classify_transport(provider):
    result = call_llm(provider, "secret", "model", [], session=TimeoutSession())
    assert "secret" not in result["error"]
    assert result["retryable"] is True
    assert result["error_type"] == "transport"


@pytest.mark.parametrize("provider", ["Anthropic Claude", "Google Gemini", "MiniMax"])
def test_adapter_http_errors_are_fatal_and_redacted(provider):
    result = call_llm(provider, "secret", "model", [],
                      session=FixedSession(Response(401, {"error": "invalid secret"})))
    assert "secret" not in result["error"]
    assert result["error_type"] == "authentication"
    assert result["retryable"] is False


@pytest.mark.parametrize("answer", ["[]", "null", '"hello"', "42"])
def test_non_object_json_response_falls_back(monkeypatch, answer):
    engine = make_engine(policy_id="LLM_Agent")
    paths = engine.get_observation(engine.agents[0])
    monkeypatch.setattr("engine.call_llm", lambda *a, **kw: {
        "answer": answer, "error": None, "usage": {}
    })
    _, mode, _, _ = engine._call_llm(engine.agents[0], paths, 0)
    assert mode == "Rule_Fallback"
    assert engine.fallback_count == 1


def test_ui_runs_from_another_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(BASE / "app.py")).run(timeout=30)
    assert not at.exception


def test_provider_switch_does_not_reuse_another_providers_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-only")
    monkeypatch.setenv("POE_API_KEY", "test-poe-only")
    at = AppTest.from_file(str(BASE / "app.py")).run(timeout=30)
    next(w for w in at.text_input if w.label == "API Key").set_value("typed-deepseek-only")
    at.run()
    next(w for w in at.selectbox if w.label == "服务商").set_value("Poe")
    at.run()
    assert next(w for w in at.text_input if w.label == "API Key").value == "test-poe-only"


def test_ui_requires_a_key_for_llm_mode():
    at = AppTest.from_file(str(BASE / "app.py")).run(timeout=30)
    next(w for w in at.selectbox if w.label == "决策策略").set_value("LLM_Agent")
    next(w for w in at.text_input if w.label == "API Key").set_value("")
    next(w for w in at.button if w.label == "🚀 初始化").click()
    at.run()
    assert at.session_state.engine is None
    assert at.error


def test_cli_provider_selects_its_own_env_by_default():
    args = batch_runner.build_parser().parse_args([
        "--policies", "LLM_Agent", "--seeds", "42", "--provider", "OpenAI"
    ])
    assert args.api_key_env is None


def test_resume_rejects_changed_configuration_before_running(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(batch_runner, "run_case", lambda *args: ran.append(args))
    common = ["--policies", "Local_Rule", "--designs", "D0", "--conditions", "C0",
              "--seeds", "42", "--output", str(tmp_path)]
    batch_runner.main(common + ["--max-steps", "30"])
    assert len(ran) == 1
    with pytest.raises(ValueError, match="configuration"):
        batch_runner.main(common + ["--max-steps", "5", "--resume"])
    assert len(ran) == 1


def test_invalid_run_stops_batch_and_returns_error(tmp_path, monkeypatch):
    ran = []
    def invalid_case(*args):
        ran.append(args)
        return SimpleNamespace(valid_run=False, invalid_reason="billing")
    monkeypatch.setattr(batch_runner, "run_case", invalid_case)
    status = batch_runner.main(["--policies", "Local_Rule", "--designs", "D0",
                               "--conditions", "C0", "--seeds", "41", "42",
                               "--output", str(tmp_path)])
    assert status != 0
    assert len(ran) == 1
