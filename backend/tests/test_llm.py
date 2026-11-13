import json

from app.llm import interpret


def test_disabled_never_calls_network(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "off")
    assert interpret("Продажи")[1] == "disabled"


def test_remote_blocked_in_local_mode(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "local")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    assert interpret("Продажи")[1] == "configuration_blocked"


def test_external_requires_explicit_enable(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "api")
    monkeypatch.delenv("LLM_ALLOW_EXTERNAL", raising=False)
    assert interpret("Продажи")[1] == "configuration_blocked"


def test_validated_response_and_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "local")
    monkeypatch.setenv("LLM_MODEL", "fixture")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            return json.dumps({"choices": [{"message": {"content": self.answer}}]}).encode()
    response = Response()
    class Opener:
        def open(self, request, timeout):
            assert timeout == 8
            assert set(json.loads(request.data)) == {"model", "temperature", "max_tokens", "response_format", "messages"}
            return response
    monkeypatch.setattr("app.llm.build_opener", lambda *args: Opener())
    response.answer = '{"goal":"Увеличить продажи","clarification":null}'
    assert interpret("Продажи")[0].goal == "Увеличить продажи"
    response.answer = '{"goal":"Продажи!","clarification":null}'
    assert interpret("Продажи") == (None, "unchanged")
    response.answer = '{"goal":"Продажи","invented_course":"123"}'
    assert interpret("Продажи") == (None, "unavailable")


def test_cloud_alias_blocked_in_local_mode(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "local")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen:cloud")
    assert interpret("Продажи")[1] == "configuration_blocked"
