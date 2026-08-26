"""Shared runtime helpers for the file-based research queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACTION_LOG = ROOT / "experiments" / "agent-actions.jsonl"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log_action(actor: str, action: str, **details: Any) -> None:
    """Record one bounded, JSON-serializable audit event."""
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": now_utc(), "actor": actor, "action": action, "details": details}
    with ACTION_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
