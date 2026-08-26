"""Read-only context collection for the offline proposal agent."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "bot"
USER_DATA_DIR = BOT_DIR / "user_data"
BACKTEST_DIR = USER_DATA_DIR / "backtest_results"
LOG_DIR = USER_DATA_DIR / "logs"
PROPOSALS_DIR = ROOT / "proposals"
EVALUATIONS_DIR = ROOT / "experiments" / "evaluations"
DECISIONS_DIR = ROOT / "experiments" / "decisions"
EXPERIMENTAL_PROFILES_DIR = ROOT / "experiments" / "experimental-profiles"
_SECRET_PATTERN = re.compile(r"(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*[^\s,}]+")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_artifact_path(directory: Path, name: str) -> Path:
    """Return a path under a known artifact directory; reject traversal."""
    candidate = (directory / name).resolve()
    base = directory.resolve()
    if candidate.parent != base or candidate.suffix != ".json":
        raise ValueError("artifact path must be a direct JSON child of its queue directory")
    return candidate


def _redact(text: str) -> str:
    return _SECRET_PATTERN.sub(r"\1=<redacted>", text)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def extract_metrics(payload: dict[str, Any] | None) -> dict[str, float] | None:
    """Extract only the stable metric set used by the evaluator."""
    if not payload:
        return None
    strategies = payload.get("strategy")
    if not isinstance(strategies, dict) or not strategies:
        return None
    result = next(iter(strategies.values()))
    if not isinstance(result, dict):
        return None
    try:
        trades = float(result.get("total_trades", 0))
        profit = float(result.get("profit_total", 0.0))
        drawdown = float(result.get("max_drawdown", 0.0))
    except (TypeError, ValueError):
        return None
    if trades < 0 or profit != profit or drawdown != drawdown:
        return None
    return {
        "expectancy": profit / trades if trades else 0.0,
        "max_drawdown": max(0.0, drawdown),
        "number_of_trades": trades,
    }


def collect_context() -> dict[str, Any]:
    """Collect bounded, redacted research context without modifying production files."""
    backtests: list[dict[str, Any]] = []
    if BACKTEST_DIR.exists():
        for path in sorted(BACKTEST_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
            payload = _read_json(path)
            metrics = extract_metrics(payload)
            if metrics is not None:
                backtests.append({"file": str(path.relative_to(ROOT)), "metrics": metrics})

    logs: list[dict[str, Any]] = []
    if LOG_DIR.exists():
        for path in sorted(LOG_DIR.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:3]:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            except OSError:
                continue
            logs.append({"file": str(path.relative_to(ROOT)), "tail": _redact("\n".join(lines))[:8_000]})

    return {
        "collected_at": now_utc(),
        "backtests": backtests,
        "paper_logs": logs,
        "notes": [
            "Context is read-only and may be incomplete.",
            "No credentials or exchange commands are included in the research prompt.",
            "Results are hypotheses for human review, not trading instructions.",
        ],
    }


def latest_metrics(context: dict[str, Any]) -> dict[str, float]:
    backtests = context.get("backtests", [])
    if isinstance(backtests, list):
        for item in backtests:
            if isinstance(item, dict) and isinstance(item.get("metrics"), dict):
                return {key: float(value) for key, value in item["metrics"].items()}
    return {"expectancy": 0.0, "max_drawdown": 0.0, "number_of_trades": 0.0}
