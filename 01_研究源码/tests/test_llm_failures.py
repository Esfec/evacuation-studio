from llm_api import call_llm


class TimeoutSession:
    def post(self, *args, **kwargs):
        raise TimeoutError("test timeout containing secret")


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FixedSession:
    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response


def test_transport_failure_returns_structured_retryable_error():
    result = call_llm(
        "Poe", "secret", "model", [], session=TimeoutSession()
    )
    assert result["error_type"] == "transport"
    assert result["retryable"] is True
    assert "secret" not in str(result)


def test_401_is_fatal_authentication_error():
    result = call_llm(
        "Poe",
        "secret",
        "model",
        [],
        session=FixedSession(Response(401, {"error": "invalid key"})),
    )
    assert result["error_type"] == "authentication"
    assert result["retryable"] is False


def test_429_is_retryable_rate_limit_error():
    result = call_llm(
        "Poe",
        "secret",
        "model",
        [],
        session=FixedSession(Response(429, {"error": "rate limited"})),
    )
    assert result["error_type"] == "rate_limit"
    assert result["retryable"] is True
