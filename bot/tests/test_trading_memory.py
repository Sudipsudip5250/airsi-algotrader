from __future__ import annotations

import json

from trading_memory import MemoryStore


def test_memory_survives_restart_and_deduplicates_events(tmp_path):
    path = tmp_path / "trading_memory.sqlite"
    first = MemoryStore(path)
    assert first.record_event("event-1", "incident", pair="BTC/USDT", features={"risk": "high"}) is True
    assert first.record_event("event-1", "incident", pair="BTC/USDT", features={"risk": "high"}) is False

    reopened = MemoryStore(path)
    assert reopened.summary()["event_count"] == 1
    assert reopened.summary()["outcome_count"] == 0
    sidecar = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["event_count"] == 1
    assert sidecar["outcome_count"] == 0


def test_memory_requires_evidence_before_veto(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_MIN_SAMPLES", "3")
    monkeypatch.setenv("MEMORY_MIN_MEAN_REWARD", "-0.01")
    monkeypatch.setenv("MEMORY_MIN_WIN_RATE", "0.35")
    store = MemoryStore(tmp_path / "memory.sqlite")

    for index, reward in enumerate((-0.03, -0.02)):
        store.record_trade_outcome(
            str(index),
            pair="BTC/USDT",
            regime="bullish_trend",
            signal_tag="bullish_trend_pullback",
            reward=reward,
        )
    lesson = store.get_lesson(pair="BTC/USDT", regime="bullish_trend", signal_tag="bullish_trend_pullback")
    assert lesson.sample_count == 2
    assert lesson.allow_entry is True

    store.record_trade_outcome(
        "2",
        pair="BTC/USDT",
        regime="bullish_trend",
        signal_tag="bullish_trend_pullback",
        reward=-0.02,
    )
    lesson = store.get_lesson(pair="BTC/USDT", regime="bullish_trend", signal_tag="bullish_trend_pullback")
    assert lesson.sample_count == 3
    assert lesson.allow_entry is False
    assert "poor expectancy" in lesson.lesson


def test_positive_memory_does_not_override_strategy_rules(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.record_trade_outcome(
        "1",
        pair="ETH/USDT",
        regime="bullish_trend",
        signal_tag="bullish_trend_pullback",
        reward=0.04,
    )
    allowed, lesson = store.entry_gate(pair="ETH/USDT", regime="bullish_trend", signal_tag="bullish_trend_pullback")
    assert allowed is True
    assert lesson.sample_count == 1
    assert lesson.confidence < 1.0


def test_comparable_lessons_include_other_assets_for_advisory_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.record_trade_outcome(
        "btc-1",
        pair="BTC/USDT",
        regime="bullish_trend",
        signal_tag="bullish_trend_pullback",
        reward=0.02,
    )
    store.record_trade_outcome(
        "eth-1",
        pair="ETH/USDT",
        regime="bullish_trend",
        signal_tag="bullish_trend_pullback",
        reward=-0.02,
    )
    lessons = store.comparable_lessons(
        pair="BTC/USDT", regime="bullish_trend", signal_tag="bullish_trend_pullback"
    )
    assert [lesson.pair for lesson in lessons] == ["BTC/USDT", "ETH/USDT"]
