from __future__ import annotations

from datetime import datetime, timedelta, timezone

from market_intelligence import (
    IntelligenceDecision,
    MarketSnapshot,
    NewsAnalysis,
    aggregate_news,
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


def test_news_aggregation_requires_corroboration_for_negative_signal():
    analyses = [
        NewsAnalysis("a", "Security incident", "https://a.example/1", "coindesk.com", "2026-08-19T00:00:00+00:00", ["BTC"], -0.9, "high", "security", 0.9, "confirmed exploit", "test"),
        NewsAnalysis("b", "Exchange outage", "https://b.example/2", "cointelegraph.com", "2026-08-19T00:05:00+00:00", ["BTC", "MARKET"], -0.7, "high", "exchange", 0.8, "reported outage", "test"),
    ]
    result = aggregate_news(analyses, now=datetime(2026, 8, 19, 0, 10, tzinfo=timezone.utc))
    assert result["score"] < -0.45
    assert result["negative_source_count"] == 2
    assert result["source_diversity"] == 2
    assert result["asset_sentiment"]["BTC"]["score"] < 0


def test_single_negative_source_does_not_create_corroborated_veto():
    analysis = NewsAnalysis("a", "Rumor", "https://a.example/1", "unknown.example", "2026-08-19T00:00:00+00:00", ["MARKET"], -1.0, "critical", "rumor", 1.0, "unconfirmed", "test")
    result = aggregate_news([analysis], now=datetime(2026, 8, 19, 0, 10, tzinfo=timezone.utc))
    assert result["negative_source_count"] == 1
    assert result["source_diversity"] == 1


def test_invalid_or_missing_decision_fails_closed(tmp_path):
    assert read_decision(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text('{"allow_long_entries": true}')
    assert read_decision(bad) is None
