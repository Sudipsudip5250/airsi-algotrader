from datetime import datetime, timedelta, timezone

from market_intelligence import (
    IntelligenceDecision,
    MarketSnapshot,
    _llm_settings,
    deterministic_risk,
    read_decision,
    write_decision,
)


def test_deterministic_gate_vetoes_severe_market_shock():
    snapshot = MarketSnapshot(
        collected_at="2026-08-19T00:00:00+00:00",
        btc_change_1h=-2.0,
        btc_change_24h=-5.0,
        btc_funding_rate=0.001,
    )
    risk, allow, reason = deterministic_risk(snapshot)
    assert risk == "high"
    assert allow is False
    assert "BTC 24h" in reason


def test_missing_core_market_data_fails_closed():
    snapshot = MarketSnapshot(collected_at="2026-08-19T00:00:00+00:00", btc_change_24h=1.0)
    risk, allow, reason = deterministic_risk(snapshot)
    assert risk == "high"
    assert allow is False
    assert "missing" in reason


def test_decision_store_round_trip_and_expiry(tmp_path):
    now = datetime.now(timezone.utc)
    path = tmp_path / "market_intelligence.json"
    decision = IntelligenceDecision(
        generated_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        allow_long_entries=True,
        risk_level="normal",
        confidence=0.8,
        reason="test",
        source_count=2,
        news_count=1,
        model="deterministic",
        snapshot_hash="abc123",
        errors=[],
    )
    write_decision(decision, path)
    assert read_decision(path, now=now) == decision
    assert read_decision(path, now=now + timedelta(minutes=6)) is None


def test_invalid_or_missing_decision_fails_closed(tmp_path):
    assert read_decision(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text('{"allow_long_entries": true}')
    assert read_decision(bad) is None


def test_naive_decision_timestamps_fail_closed(tmp_path):
    path = tmp_path / "naive.json"
    path.write_text(
        '{"generated_at":"2099-01-01T00:00:00","expires_at":"2099-01-01T01:00:00",'
        '"allow_long_entries":true,"risk_level":"normal","confidence":0.8,'
        '"reason":"test","source_count":1,"news_count":0,"model":"deterministic",'
        '"snapshot_hash":"abc123","errors":[]}'
    )
    assert read_decision(path) is None


def test_llm_settings_skip_paid_openai_by_default(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_PAID", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_BASE", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    monkeypatch.setattr("market_intelligence._ollama_available", lambda _url: False)
    base, key, model, cost = _llm_settings()
    assert key == ""
    assert model == ""
    assert cost == "free"


def test_llm_settings_prefer_groq_free(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_PAID", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setattr("market_intelligence._ollama_available", lambda _url: False)
    base, key, model, cost = _llm_settings()
    assert "groq.com" in base
    assert key == "gsk-test"
    assert model == "llama-3.1-8b-instant"
    assert cost == "free"
