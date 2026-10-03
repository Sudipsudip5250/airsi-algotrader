"""Append-only AI self-tracking for AIRSI AlgoTrader.

Every AI decision logs: timestamp, provider/model/cost, market snapshot,
action, and later trade outcome. Used offline by researcher/evaluator to
improve future prompts/thresholds. Never auto-mutates live strategy.

File: experiments/ai-decisions.jsonl (gitignored, JSONL, immutable).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = "experiments/ai-decisions.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(path: str | Path | None = None) -> Path:
    override = os.getenv("AI_DECISIONS_PATH", "").strip()
    return Path(str(path or override or DEFAULT_PATH))


def log_ai_decision(
    *,
    agent: str,
    provider: str,
    model: str,
    cost_class: str,
    snapshot_hash: str,
    market: dict[str, Any],
    action: dict[str, Any],
    decision_id: str | None = None,
    latency_ms: int | None = None,
    cached: bool = False,
    errors: list[str] | None = None,
    path: str | Path | None = None,
) -> str:
    """Append one ai_decision event. Returns decision_id. Never raises."""
    try:
        if decision_id is None:
            decision_id = f"aid-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}-{int(time.time()*1000)%100000}"
        # Redact + bound reason to 500 chars, market to known numeric keys.
        safe_market = {
            k: market.get(k)
            for k in ("btc_change_1h", "btc_change_24h", "btc_change_7d",
                      "total_market_cap_change_24h", "btc_funding_rate",
                      "btc_open_interest", "news_count", "source_count")
            if k in market
        }
        safe_action = {
            "allow_long_entries": bool(action.get("allow_long_entries", False)),
            "risk_level": str(action.get("risk_level", "high")),
            "confidence": float(action.get("confidence", 0.0)),
            "reason": str(action.get("reason", ""))[:500],
        }
        record = {
            "schema_version": 1,
            "event": "ai_decision",
            "decision_id": decision_id,
            "timestamp": _now_iso(),
            "agent": agent,
            "provider": provider,
            "model": model,
            "cost_class": cost_class,
            "cached": bool(cached),
            "latency_ms": latency_ms,
            "snapshot_hash": snapshot_hash,
            "market": safe_market,
            "action": safe_action,
            "errors": list(errors or []),
        }
        dest = _path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return decision_id
    except Exception:
        return decision_id or "aid-unlogged"


def log_trade_outcome(
    *,
    decision_id: str,
    snapshot_hash: str = "",
    pair: str = "",
    profit_abs: float = 0.0,
    profit_pct: float = 0.0,
    fees: float = 0.0,
    exit_reason: str = "",
    stake: float = 0.0,
    runmode: str = "",
    path: str | Path | None = None,
) -> None:
    """Append one trade_outcome event linked by decision_id. Never raises."""
    try:
        record = {
            "schema_version": 1,
            "event": "trade_outcome",
            "timestamp": _now_iso(),
            "decision_id": decision_id,
            "snapshot_hash": snapshot_hash,
            "pair": pair,
            "profit_abs": float(profit_abs),
            "profit_pct": float(profit_pct),
            "fees": float(fees),
            "exit_reason": str(exit_reason)[:120],
            "stake": float(stake),
            "runmode": runmode,
        }
        dest = _path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        return


def stats(path: str | Path | None = None, limit: int = 2000) -> dict[str, Any]:
    """Summarise recent decisions for researcher/dashboard. Bounded, no secrets."""
    dest = _path(path)
    decisions = 0
    allows = 0
    by_risk: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    outcomes = 0
    profit_sum = 0.0
    try:
        if not dest.exists():
            return {"decisions": 0, "allows": 0, "by_risk": {}, "by_provider": {}, "outcomes": 0, "profit_sum": 0.0}
        lines = dest.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("event") == "ai_decision":
                decisions += 1
                action = rec.get("action", {})
                if isinstance(action, dict) and action.get("allow_long_entries") is True:
                    allows += 1
                risk = action.get("risk_level") if isinstance(action, dict) else None
                if isinstance(risk, str):
                    by_risk[risk] = by_risk.get(risk, 0) + 1
                prov = rec.get("provider")
                if isinstance(prov, str):
                    by_provider[prov] = by_provider.get(prov, 0) + 1
            elif rec.get("event") == "trade_outcome":
                outcomes += 1
                try:
                    profit_sum += float(rec.get("profit_abs", 0.0))
                except Exception:
                    pass
    except Exception:
        pass
    return {
        "decisions": decisions,
        "allows": allows,
        "by_risk": by_risk,
        "by_provider": by_provider,
        "outcomes": outcomes,
        "profit_sum": round(profit_sum, 4),
    }
