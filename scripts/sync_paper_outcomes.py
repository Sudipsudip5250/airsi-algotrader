"""Sync closed dry-run/live paper trades into the AI tracking ledger.

Reads freqtrade's SQLite (created on first trade) and appends one
trade_outcome event per closed trade that is not already logged.
Links each trade to the most recent ai_decision at/before its close time
(approximate join for aggregate research, not exact causation).

Usage:
  python scripts/sync_paper_outcomes.py            # dry-run default
  python scripts/sync_paper_outcomes.py --runmode live
Run weekly during paper collection + right before any analysis.

Never touches the exchange. Never edits strategy or configs.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

try:
    from ai_tracker import DEFAULT_PATH
except Exception:
    DEFAULT_PATH = "experiments/ai-decisions.jsonl"


def find_db(userdir: Path) -> Path | None:
    cands = sorted(userdir.glob("tradesv3*.sqlite"))
    # Prefer dry-run DB when present.
    for c in cands:
        if "dry" in c.name.lower():
            return c
    return cands[0] if cands else None


def load_ledger(path: Path) -> tuple[set[str], list[tuple[str, str]]]:
    """Return (logged trade ids, [(timestamp, decision_id)] of ai_decisions)."""
    logged: set[str] = set()
    decisions: list[tuple[str, str]] = []
    if not path.exists():
        return logged, decisions
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if rec.get("event") == "trade_outcome" and rec.get("trade_id"):
            logged.add(str(rec["trade_id"]))
        elif rec.get("event") == "ai_decision" and rec.get("timestamp") and rec.get("decision_id"):
            decisions.append((str(rec["timestamp"]), str(rec["decision_id"])))
    decisions.sort()
    return logged, decisions


def covering_decision(decisions: list[tuple[str, str]], close_ts: str) -> str:
    best = "paper-sync:unknown"
    for ts, did in decisions:
        if ts <= close_ts:
            best = did
        else:
            break
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync paper trades into ai-decisions.jsonl")
    parser.add_argument("--runmode", default="dry", help="Label stored on outcomes (dry|live)")
    parser.add_argument("--userdir", default=str(ROOT / "bot" / "user_data"))
    args = parser.parse_args()

    userdir = Path(args.userdir)
    db = find_db(userdir)
    if db is None:
        print("No trades DB yet (freqtrade creates it on the first trade). Nothing to sync.")
        return 0

    ledger = Path(os.getenv("AI_DECISIONS_PATH", DEFAULT_PATH))
    if not ledger.is_absolute():
        ledger = ROOT / ledger
    logged, decisions = load_ledger(ledger)

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cols = {row[1] for row in con.execute("PRAGMA table_info(trades)")}
        rows = con.execute("SELECT * FROM trades WHERE is_open = 0").fetchall()
    finally:
        con.close()

    def get(row: sqlite3.Row, *names: str, default: object = 0.0) -> object:
        for name in names:
            if name in cols and row[name] is not None:
                return row[name]
        return default

    added = 0
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for row in rows:
            tid = str(row["id"])
            if tid in logged:
                continue
            close_date = str(get(row, "close_date", default=""))
            try:
                close_ts = datetime.fromisoformat(close_date).astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError):
                close_ts = datetime.now(timezone.utc).isoformat()
            record = {
                "schema_version": 1,
                "event": "trade_outcome",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision_id": covering_decision(decisions, close_ts),
                "trade_id": tid,
                "snapshot_hash": "",
                "pair": str(get(row, "pair", default="")),
                "profit_abs": float(get(row, "close_profit_abs", "profit_abs", default=0.0) or 0.0),
                "profit_pct": float(get(row, "close_profit", "profit_ratio", default=0.0) or 0.0),
                "fees": float(get(row, "fee_close", "fees", default=0.0) or 0.0),
                "exit_reason": str(get(row, "exit_reason", "close_reason", "sell_reason", default=""))[:120],
                "stake": float(get(row, "stake_amount", default=0.0) or 0.0),
                "runmode": args.runmode,
            }
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            added += 1
    print(f"Synced {added} new trade outcome(s) from {db.name} (skipped {len(rows) - added} already logged).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
