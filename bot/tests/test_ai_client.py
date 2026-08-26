from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_client import AIClient


class Provider:
    def __init__(self, response: str | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = 0

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
