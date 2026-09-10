"""Read-only context collection for the offline proposal agent."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
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
CACHE_DIR = ROOT / "experiments" / "cache"
QUEUE_MARKDOWN = ROOT / "experiments" / "QUEUE.md"
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


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number == number else None


def _first_number(source: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        number = _finite_number(source.get(key))
        if number is not None:
            return number
    return None


def _strategy_block(payload: dict[str, Any]) -> dict[str, Any] | None:
    strategies = payload.get("strategy")
    if isinstance(strategies, dict):
        for value in strategies.values():
            if isinstance(value, dict) and (
                "total_trades" in value
                or "trades" in value
                or "profit_total" in value
                or "max_drawdown" in value
                or "max_relative_drawdown" in value
            ):
                return value
        for value in strategies.values():
            if isinstance(value, dict):
                return value
    comparison = payload.get("strategy_comparison")
    if isinstance(comparison, dict):
        for value in comparison.values():
            if isinstance(value, dict):
                return value
    if isinstance(comparison, list):
        for value in comparison:
            if isinstance(value, dict):
                return value
    return None


def extract_metrics(payload: dict[str, Any] | None) -> dict[str, float] | None:
    """Extract only the stable metric set used by the evaluator.

    Accepts a Freqtrade strategy block or strategy_comparison entry. Missing or
    non-finite values return None rather than inventing metrics.
    """
    if not isinstance(payload, dict):
        return None
    result = _strategy_block(payload)
    if result is None:
        return None
    trades = _first_number(result, "total_trades", "trade_count", "trades")
    profit = _first_number(result, "profit_total", "profit_total_abs")
    drawdown = _first_number(result, "max_relative_drawdown", "max_drawdown_account", "max_drawdown")
    if trades is None or profit is None or drawdown is None or trades < 0:
        return None
    return {
        "expectancy": profit / trades if trades else 0.0,
        "max_drawdown": max(0.0, drawdown),
        "number_of_trades": trades,
    }


def _read_payload(path: Path) -> dict[str, Any] | None:
    if path.suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                names = [name for name in archive.namelist() if name.endswith(".json")]
                preferred = [
                    name
                    for name in names
                    if not Path(name).name.endswith(".meta.json") and "config" not in Path(name).name.lower()
                ]
                for name in preferred or names:
                    payload: Any = json.loads(archive.read(name))
                    if isinstance(payload, dict) and extract_metrics(payload) is not None:
                        return payload
        except (OSError, json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError):
            return None
        return None
    return _read_json(path)


def _relative_to_root(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def _recent_records(directory: Path, fields: tuple[str, ...], limit: int = 5) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        payload = _read_json(path)
        if not payload:
            continue
        item: dict[str, Any] = {"file": _relative_to_root(path)}
        for field in fields:
            if field not in payload:
                continue
            value = payload[field]
            if isinstance(value, str):
                item[field] = _redact(value)[:400]
            elif isinstance(value, (int, float, bool)) or value is None:
                item[field] = value
        records.append(item)
    return records


def collect_context() -> dict[str, Any]:
    """Collect bounded, redacted research context without modifying production files."""
    backtests: list[dict[str, Any]] = []
    if BACKTEST_DIR.exists():
        exports = [path for path in BACKTEST_DIR.iterdir() if path.is_file() and path.suffix in {".json", ".zip"}]
        exports.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for path in exports[:8]:
            metrics = extract_metrics(_read_payload(path))
            if metrics is not None:
                backtests.append({"file": _relative_to_root(path), "metrics": metrics})

    logs: list[dict[str, Any]] = []
    if LOG_DIR.exists():
        for path in sorted(LOG_DIR.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:3]:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            except OSError:
                continue
            logs.append({"file": _relative_to_root(path), "tail": _redact("\n".join(lines))[:8_000]})

    return {
        "collected_at": now_utc(),
        "backtests": backtests,
        "paper_logs": logs,
        "evaluations": _recent_records(
            EVALUATIONS_DIR,
            ("proposal_id", "verdict", "evaluator_version", "notes"),
        ),
        "decisions": _recent_records(
            DECISIONS_DIR,
            ("proposal_id", "decision", "reviewer", "rationale"),
        ),
        "notes": [
            "Context is read-only and may be incomplete.",
            "No credentials or exchange commands are included in the research prompt.",
            "Results are hypotheses for human review, not trading instructions.",
            "Recent evaluations and decisions are local artifacts only; they are not live signals.",
        ],
    }


def latest_metrics(context: dict[str, Any]) -> dict[str, float]:
    backtests = context.get("backtests", [])
    if isinstance(backtests, list):
        for item in backtests:
            if isinstance(item, dict) and isinstance(item.get("metrics"), dict):
                return {key: float(value) for key, value in item["metrics"].items()}
    return {"expectancy": 0.0, "max_drawdown": 0.0, "number_of_trades": 0.0}


def fingerprint_idea(proposal_type: str, title: str, changes: dict[str, Any]) -> str:
    """Stable id for skipping redundant research on the same idea."""
    payload = {"proposal_type": proposal_type, "title": title, "changes": changes}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
