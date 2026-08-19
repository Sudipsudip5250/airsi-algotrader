"""Persistent, bounded memory for AIRSI AlgoTrader.

The memory is an evidence store, not an autonomous policy learner. It records
market context and trade outcomes in SQLite, survives process restarts, and
retrieves only sufficiently supported lessons. Positive memories are advisory;
negative memories can veto a matching entry only after a configurable minimum
sample size and persistent poor expectancy.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MEMORY_PATH = "bot/user_data/trading_memory.sqlite"
DEFAULT_MIN_SAMPLES = 12
DEFAULT_MIN_MEAN_REWARD = -0.01
DEFAULT_MIN_WIN_RATE = 0.35


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).astimezone(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class MemoryLesson:
    pair: str
    regime: str
    signal_tag: str
    sample_count: int
    win_rate: float
    mean_reward: float
    confidence: float
    allow_entry: bool
    lesson: str
    updated_at: str


class MemoryStore:
    """SQLite-backed event memory designed for concurrent bot/worker access."""

    def __init__(self, path: str | Path = DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path = Path(
            os.getenv("MEMORY_SUMMARY_PATH", str(self.path.with_suffix(".json")))
        )
        self._initialize()
        self._publish_summary()

    def _publish_summary(self) -> None:
        try:
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.summary_path.with_suffix(self.summary_path.suffix + ".tmp")
            temporary.write_text(json.dumps(self.summary(), sort_keys=True), encoding="utf-8")
            temporary.replace(self.summary_path)
        except Exception:
            # Observability must never affect trading memory or execution.
            return

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    pair TEXT NOT NULL DEFAULT '',
                    regime TEXT NOT NULL DEFAULT '',
                    signal_tag TEXT NOT NULL DEFAULT '',
                    features_json TEXT NOT NULL DEFAULT '{}',
                    outcome_json TEXT NOT NULL DEFAULT '{}',
                    reward REAL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_outcomes
                    ON memory_events(event_type, pair, regime, signal_tag, occurred_at);
                CREATE TABLE IF NOT EXISTS memory_lessons (
                    lesson_key TEXT PRIMARY KEY,
                    pair TEXT NOT NULL DEFAULT '',
                    regime TEXT NOT NULL DEFAULT '',
                    signal_tag TEXT NOT NULL DEFAULT '',
                    sample_count INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    mean_reward REAL NOT NULL,
                    confidence REAL NOT NULL,
                    allow_entry INTEGER NOT NULL,
                    lesson TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def record_event(
        self,
        event_key: str,
        event_type: str,
        *,
        occurred_at: str | None = None,
        pair: str = "",
        regime: str = "",
        signal_tag: str = "",
        features: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
        reward: float | None = None,
    ) -> bool:
        """Insert an event once; repeated worker restarts are idempotent."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO memory_events
                    (event_key, event_type, occurred_at, pair, regime, signal_tag,
                     features_json, outcome_json, reward, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_key,
                    event_type,
                    occurred_at or _iso(),
                    pair,
                    regime,
                    signal_tag,
                    _json(features),
                    _json(outcome),
                    reward,
                    _iso(),
                ),
            )
            inserted = cursor.rowcount == 1
        if inserted:
            self._publish_summary()
        return inserted

    def record_trade_entry(
        self,
        trade_id: str,
        *,
        pair: str,
        regime: str,
        signal_tag: str,
        features: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> bool:
        return self.record_event(
            f"trade:{trade_id}:entry",
            "trade_entry",
            occurred_at=occurred_at,
            pair=pair,
            regime=regime,
            signal_tag=signal_tag,
            features=features,
        )

    def record_trade_outcome(
        self,
        trade_id: str,
        *,
        pair: str,
        regime: str,
        signal_tag: str,
        reward: float,
        features: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> bool:
        inserted = self.record_event(
            f"trade:{trade_id}:outcome",
            "trade_outcome",
            occurred_at=occurred_at,
            pair=pair,
            regime=regime,
            signal_tag=signal_tag,
            features=features,
            outcome=outcome,
            reward=float(reward),
        )
        if inserted:
            self.refresh_lesson(pair=pair, regime=regime, signal_tag=signal_tag)
        return inserted

    def record_intelligence_snapshot(self, snapshot_hash: str, *, risk_level: str, sentiment: float, confidence: float, source_count: int, occurred_at: str | None = None) -> bool:
        return self.record_event(
            f"intelligence:{snapshot_hash}",
            "intelligence_snapshot",
            occurred_at=occurred_at,
            features={"risk_level": risk_level, "sentiment": sentiment, "confidence": confidence, "source_count": source_count},
        )

    def outcome_count(self, *, pair: str = "", regime: str = "", signal_tag: str = "") -> int:
        clauses = ["event_type = 'trade_outcome'"]
        values: list[Any] = []
        for column, value in (("pair", pair), ("regime", regime), ("signal_tag", signal_tag)):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM memory_events WHERE {' AND '.join(clauses)}",
                values,
            ).fetchone()
            return int(row["count"] if row else 0)

    def _outcome_rows(self, *, pair: str, regime: str, signal_tag: str, limit: int = 200) -> list[sqlite3.Row]:
        clauses = ["event_type = 'trade_outcome'"]
        values: list[Any] = []
        for column, value in (("pair", pair), ("regime", regime), ("signal_tag", signal_tag)):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        values.append(limit)
        with self._connect() as connection:
            return list(
                connection.execute(
                    f"SELECT * FROM memory_events WHERE {' AND '.join(clauses)} ORDER BY occurred_at DESC LIMIT ?",
                    values,
                ).fetchall()
            )

    def refresh_lesson(self, *, pair: str, regime: str, signal_tag: str) -> MemoryLesson:
        rows = self._outcome_rows(pair=pair, regime=regime, signal_tag=signal_tag)
        rewards = [float(row["reward"]) for row in rows if row["reward"] is not None]
        sample_count = len(rewards)
        mean_reward = sum(rewards) / sample_count if sample_count else 0.0
        win_rate = sum(1 for reward in rewards if reward > 0) / sample_count if sample_count else 0.0
        confidence = min(1.0, sample_count / 30.0)
        min_samples = max(1, int(os.getenv("MEMORY_MIN_SAMPLES", str(DEFAULT_MIN_SAMPLES))))
        min_mean_reward = float(os.getenv("MEMORY_MIN_MEAN_REWARD", str(DEFAULT_MIN_MEAN_REWARD)))
        min_win_rate = float(os.getenv("MEMORY_MIN_WIN_RATE", str(DEFAULT_MIN_WIN_RATE)))
        allow_entry = not (
            sample_count >= min_samples
            and mean_reward <= min_mean_reward
            and win_rate < min_win_rate
        )
        if sample_count < min_samples:
            lesson = f"Insufficient evidence: {sample_count}/{min_samples} completed outcomes"
        elif allow_entry:
            lesson = f"Historical expectancy is acceptable: mean reward {mean_reward:+.4f}, win rate {win_rate:.1%}"
        else:
            lesson = f"Repeated poor expectancy: mean reward {mean_reward:+.4f}, win rate {win_rate:.1%}; veto this exact context"
        lesson = MemoryLesson(pair, regime, signal_tag, sample_count, win_rate, mean_reward, confidence, allow_entry, lesson, _iso())
        key = f"{pair}|{regime}|{signal_tag}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_lessons
                    (lesson_key, pair, regime, signal_tag, sample_count, win_rate,
                     mean_reward, confidence, allow_entry, lesson, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lesson_key) DO UPDATE SET
                    sample_count=excluded.sample_count,
                    win_rate=excluded.win_rate,
                    mean_reward=excluded.mean_reward,
                    confidence=excluded.confidence,
                    allow_entry=excluded.allow_entry,
                    lesson=excluded.lesson,
                    updated_at=excluded.updated_at
                """,
                (key, *asdict(lesson).values()),
            )
        self._publish_summary()
        return lesson

    def get_lesson(self, *, pair: str, regime: str, signal_tag: str) -> MemoryLesson:
        key = f"{pair}|{regime}|{signal_tag}"
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM memory_lessons WHERE lesson_key = ?", (key,)).fetchone()
        if row is None:
            return self.refresh_lesson(pair=pair, regime=regime, signal_tag=signal_tag)
        return MemoryLesson(
            pair=row["pair"],
            regime=row["regime"],
            signal_tag=row["signal_tag"],
            sample_count=int(row["sample_count"]),
            win_rate=float(row["win_rate"]),
            mean_reward=float(row["mean_reward"]),
            confidence=float(row["confidence"]),
            allow_entry=bool(row["allow_entry"]),
            lesson=row["lesson"],
            updated_at=row["updated_at"],
        )

    def comparable_lessons(
        self,
        *,
        pair: str,
        regime: str,
        signal_tag: str,
        limit: int = 5,
    ) -> list[MemoryLesson]:
        """Retrieve same-regime/signal lessons, including other assets, for advisory context."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memory_lessons
                WHERE regime = ? AND signal_tag = ?
                ORDER BY (pair = ?) DESC, sample_count DESC, confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (regime, signal_tag, pair, max(1, int(limit))),
            ).fetchall()
        return [
            MemoryLesson(
                pair=row["pair"],
                regime=row["regime"],
                signal_tag=row["signal_tag"],
                sample_count=int(row["sample_count"]),
                win_rate=float(row["win_rate"]),
                mean_reward=float(row["mean_reward"]),
                confidence=float(row["confidence"]),
                allow_entry=bool(row["allow_entry"]),
                lesson=row["lesson"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def entry_gate(self, *, pair: str, regime: str, signal_tag: str) -> tuple[bool, MemoryLesson]:
        """Return a conservative gate; positive memory never overrides strategy rules."""
        lesson = self.get_lesson(pair=pair, regime=regime, signal_tag=signal_tag)
        return lesson.allow_entry, lesson

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            event_count = int(connection.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0])
            outcome_count = int(connection.execute("SELECT COUNT(*) FROM memory_events WHERE event_type = 'trade_outcome'").fetchone()[0])
            lesson_count = int(connection.execute("SELECT COUNT(*) FROM memory_lessons").fetchone()[0])
        return {"path": str(self.path), "event_count": event_count, "outcome_count": outcome_count, "lesson_count": lesson_count}
