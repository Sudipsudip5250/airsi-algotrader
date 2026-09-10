from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_client import AIClient, CompletionResult, OllamaClient, allow_paid_providers


class Provider:
    def __init__(self, response: str | None = None, error: Exception | None = None, name: str = "Test", cost_class: str = "free"):
        self.response = response
        self.error = error
        self.calls = 0
        self.name = name
        self.cost_class = cost_class

    def complete(self, prompt: str, max_tokens: int = 200):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


def test_fallback_stops_at_first_success():
    client = AIClient()
    failed = Provider(None)
    successful = Provider("usable commentary")
    unreachable = Provider("must not be called")
    client._providers = [failed, successful, unreachable]

    assert client.complete("test prompt") == "usable commentary"
    assert failed.calls == 1
    assert successful.calls == 1
    assert unreachable.calls == 0


def test_provider_exception_falls_through_to_next_provider():
    client = AIClient()
    failed = Provider(error=RuntimeError("provider unavailable"))
    successful = Provider("usable commentary")
    client._providers = [failed, successful]

    assert client.complete("test prompt") == "usable commentary"
    assert failed.calls == 1
    assert successful.calls == 1


def test_all_provider_failures_are_non_fatal():
    client = AIClient()
    first = Provider(None)
    second = Provider(None)
    client._providers = [first, second]

    result = client.complete("test prompt")

    assert "unavailable" in result.lower()
    assert first.calls == 1
    assert second.calls == 1


def test_empty_prompt_is_non_fatal():
    client = AIClient()
    client._providers = [Provider("must not be called")]
    assert "unavailable" in client.complete("   ").lower()
    assert client._providers[0].calls == 0


def test_complete_with_meta_records_provider_and_cost_class():
    client = AIClient()
    client._providers = [Provider("hello", name="Groq", cost_class="free")]
    result = client.complete_with_meta("test prompt")
    assert isinstance(result, CompletionResult)
    assert result.text == "hello"
    assert result.provider == "Groq"
    assert result.cost_class == "free"
    assert "cost_class=free" in result.log_line()


def test_paid_provider_skipped_without_flag(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_PAID", raising=False)
    client = AIClient()
    paid = Provider("secret paid text", name="OpenRouter", cost_class="paid")
    free = Provider("free text", name="Groq", cost_class="free")
    client._providers = [paid, free]
    result = client.complete_with_meta("test prompt")
    assert result.text == "free text"
    assert paid.calls == 0
    assert free.calls == 1


def test_paid_provider_used_when_flag_enabled(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_PAID", "1")
    assert allow_paid_providers() is True
    client = AIClient()
    paid = Provider("paid text", name="OpenRouter", cost_class="paid")
    client._providers = [paid]
    result = client.complete_with_meta("test prompt")
    assert result.text == "paid text"
    assert result.cost_class == "paid"


def test_ollama_available_is_false_when_unreachable(monkeypatch):
    client = OllamaClient(base_url="http://127.0.0.1:9")
    monkeypatch.setattr("ai_client.requests.get", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("down")))
    assert client.available() is False
