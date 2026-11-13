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
            assert set(json.loads(request.data)) == {
                "model",
                "temperature",
                "max_tokens",
                "response_format",
                "messages",
            }
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


def test_llm_rewrite_preserves_refused_franchise_and_removes_redundant_question():
    from app.llm import Intent, preserve_explicit_context

    result = preserve_explicit_context(
        "Не хочу покупать франшизу. Хочу открыть магазин",
        Intent(goal="Оценить запуск магазина", clarification="Свой бренд или франшиза?"),
    )
    assert result is not None and "Без покупки франшизы" in result.goal and result.clarification is None
    assert preserve_explicit_context("Не хочу покупать франшизу", Intent(goal="Как выбрать франшизу")) is None


def test_llm_rewrite_cannot_drop_ad_budget_constraint():
    from app.llm import Intent, preserve_explicit_context

    result = preserve_explicit_context(
        "Как увеличить прибыль без увеличения рекламного бюджета?",
        Intent(goal="Оценить способы роста прибыли"),
    )
    assert "Без увеличения рекламного бюджета" in result.goal


def test_llm_rewrite_cannot_turn_closing_into_opening():
    from app.llm import Intent, preserve_explicit_context

    assert preserve_explicit_context("Хочу закрыть ИП", Intent(goal="Оценить запуск нового бизнеса")) is None
