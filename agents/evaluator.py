"""Evaluate a proposal using a dry metric comparison or an existing backtest export."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import BACKTEST_DIR, EVALUATIONS_DIR, PROPOSALS_DIR, extract_metrics, safe_artifact_path
from agents.models import EvaluationResult, ExperimentProposal, read_json, update_proposal_status, utc_now, write_json
from agents.runtime import log_action

PAPER_TEMPLATE = ROOT / "bot" / "config.paper.json"
DATA_DIR = ROOT / "bot" / "user_data" / "data"
_PROTECTED = {"bot/config.paper.json", "bot/config.live.json"}
_OHLCV_GLOBS = ("*.feather", "*.json", "*.parquet", "*.json.gz")
extract_backtest_metrics = extract_metrics


def _load_json_payload(path: Path) -> dict[str, Any] | None:
    try:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                names = [name for name in archive.namelist() if name.endswith(".json")]
                preferred = [
                    name
                    for name in names
                    if not Path(name).name.endswith(".meta.json") and "config" not in Path(name).name.lower()
                ]
                for name in preferred or names:
                    payload: Any = json.loads(archive.read(name))
                    if isinstance(payload, dict) and extract_backtest_metrics(payload) is not None:
                        return payload
                return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError, KeyError):
        return None
    return payload if isinstance(payload, dict) else None


def _metrics_from_backtest(path: Path) -> dict[str, float] | None:
    for candidate in (path, path.with_suffix(".zip")):
        if not candidate.exists() or not candidate.is_file():
            continue
        metrics = extract_backtest_metrics(_load_json_payload(candidate))
        if metrics is not None:
            return metrics
    return None


def _load_baseline(proposal: ExperimentProposal, requested: str | None) -> tuple[dict[str, float], str]:
    if requested:
        path = Path(requested)
        if not path.is_absolute():
            path = ROOT / path
        metrics = _metrics_from_backtest(path)
        if metrics is not None:
            return metrics, str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else "external backtest"
        raise ValueError(f"could not extract metrics from {requested}")

    source_metrics = proposal.source_summary.get("baseline_metrics")
    if isinstance(source_metrics, dict):
        try:
            return {key: float(source_metrics[key]) for key in ("expectancy", "max_drawdown", "number_of_trades")}, "proposal source summary"
        except (KeyError, TypeError, ValueError):
            pass

    exports: list[Path] = []
    if BACKTEST_DIR.exists():
        exports = [path for path in BACKTEST_DIR.iterdir() if path.suffix in {".json", ".zip"} and path.is_file()]
        exports.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    for path in exports:
        metrics = _metrics_from_backtest(path)
        if metrics is not None:
            return metrics, str(path.relative_to(ROOT))
    return {"expectancy": 0.0, "max_drawdown": 0.0, "number_of_trades": 0.0}, "no local backtest; dry baseline"


def _verdict(baseline: dict[str, float], candidate: dict[str, float], minimum_trades: int, source: str, ran_backtest: bool) -> tuple[str, str]:
    trades = candidate["number_of_trades"]
    if trades < minimum_trades:
        return (
            "inconclusive",
            f"{'Limited backtest' if ran_backtest else 'Dry evaluation'} from {source}; "
            f"at least {minimum_trades} trades are required for a meaningful comparison.",
        )
    if not ran_backtest:
        return (
            "inconclusive" if candidate == baseline else "promising" if candidate["expectancy"] >= baseline["expectancy"] and candidate["max_drawdown"] <= baseline["max_drawdown"] else "not_promising",
            f"Dry evaluation from {source}; candidate parameters were not executed against live or production files.",
        )
    if candidate["expectancy"] >= baseline["expectancy"] and candidate["max_drawdown"] <= baseline["max_drawdown"]:
        return "promising", f"Limited backtest from {source}; human review is still required before any experimental profile is created."
    return "not_promising", f"Limited backtest from {source}; candidate did not improve expectancy without increasing drawdown."


def evaluate(
    proposal: ExperimentProposal,
    baseline: dict[str, float],
    source: str,
    minimum_trades: int,
    candidate: dict[str, float] | None = None,
    ran_backtest: bool = False,
) -> EvaluationResult:
    candidate_metrics = dict(candidate or baseline)
    delta = {key: candidate_metrics.get(key, 0.0) - baseline[key] for key in baseline}
    verdict, notes = _verdict(baseline, candidate_metrics, minimum_trades, source, ran_backtest)
    if proposal.changes and not ran_backtest:
        notes += " Proposed changes remain unevaluated by Freqtrade until --run-backtest is used."
    return EvaluationResult(
        proposal_id=proposal.proposal_id,
        evaluated_at=utc_now(),
        evaluator_version="phase-b-limited-backtest-1" if ran_backtest else "phase-a-dry-evaluator-1",
        baseline=baseline,
        candidate=candidate_metrics,
        delta=delta,
        verdict=verdict,
        notes=notes,
    )


def assert_experimental_target(target: str) -> None:
    if target in _PROTECTED or "config.live" in target or target == "bot/config.paper.json":
        raise ValueError("refusing to backtest against a protected configuration")


def has_local_ohlcv(data_dir: Path = DATA_DIR) -> bool:
    if not data_dir.exists():
        return False
    return any(any(data_dir.rglob(pattern)) for pattern in _OHLCV_GLOBS)


def preflight_limited_backtest(proposal: ExperimentProposal, data_dir: Path = DATA_DIR) -> str | None:
    """Return a skip reason, or None if a limited backtest may run."""
    try:
        assert_experimental_target(proposal.target_config)
    except ValueError as exc:
        return str(exc)
    if shutil.which("freqtrade") is None:
        return "freqtrade is not installed. Activate the project environment, then retry --run-backtest."
    if not has_local_ohlcv(data_dir):
        return "no local market data under bot/user_data/data. Run: python scripts/download_data.py --days 30"
    if not PAPER_TEMPLATE.exists():
        return f"paper template missing: {PAPER_TEMPLATE}"
    return None


def _temporary_experimental_config(proposal: ExperimentProposal, directory: Path) -> Path:
    assert_experimental_target(proposal.target_config)
    if not PAPER_TEMPLATE.exists():
        raise FileNotFoundError(PAPER_TEMPLATE)
    payload = json.loads(PAPER_TEMPLATE.read_text(encoding="utf-8"))
    payload["dry_run"] = True
    payload["initial_state"] = "stopped"
    payload["force_entry_enable"] = False
    payload["bot_name"] = f"AIRSIAlgoTrader-Eval-{proposal.proposal_id[-12:]}"
    for key, value in proposal.changes.items():
        if key == "max_open_trades":
            payload[key] = max(1, min(int(value), 10))
        elif key == "stake_amount":
            payload[key] = max(1.0, min(float(value), 100.0))
        elif key == "dry_run_wallet":
            payload[key] = max(100.0, min(float(value), 10_000.0))
        elif key == "process_throttle_secs":
            payload.setdefault("internals", {})[key] = max(1, min(int(value), 60))
    output = directory / f"eval-{proposal.proposal_id}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def run_limited_backtest(proposal: ExperimentProposal, days: int) -> tuple[dict[str, float] | None, str]:
    """Run a short Freqtrade backtest against a temporary experimental config.

    Never writes to default paper or live profiles. Missing freqtrade/data is
    fail-closed and returns not_run rather than inventing metrics.
    """
    reason = preflight_limited_backtest(proposal)
    if reason:
        return None, reason
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    export_path = BACKTEST_DIR / f"eval-{proposal.proposal_id}.json"
    tmpdir = Path(tempfile.mkdtemp(prefix="airsi-eval-"))
    try:
        config_path = _temporary_experimental_config(proposal, tmpdir)
        end = date.today()
        start = end - timedelta(days=max(7, min(days, 90)))
        timerange = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
        command = [
            "freqtrade",
            "backtesting",
            "--config",
            str(config_path),
            "--strategy",
            "AIRSIAlgoStrategy",
            "--strategy-path",
            str(ROOT / "bot" / "strategies"),
            "--timeframe",
            "1h",
            "--timerange",
            timerange,
            "--datadir",
            str(DATA_DIR),
            "--userdir",
            str(ROOT / "bot" / "user_data"),
            "--export",
            "trades",
            "--export-filename",
            str(export_path),
        ]
        completed = subprocess.run(command, check=False, cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            snippet = (completed.stderr or completed.stdout or "freqtrade failed")[-500:]
            return None, f"limited backtest failed: {snippet}"
        scoped = [export_path, export_path.with_suffix(".zip")]
        scoped.extend(sorted(BACKTEST_DIR.glob(f"eval-{proposal.proposal_id}*"), key=lambda item: item.stat().st_mtime, reverse=True))
        seen: set[Path] = set()
        for path in scoped:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            metrics = _metrics_from_backtest(path)
            if metrics is not None:
                return metrics, str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        return None, "limited backtest produced no parseable metrics"
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, f"limited backtest failed: {exc}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def evaluate_proposal(
    proposal: ExperimentProposal,
    *,
    backtest_results: str | None = None,
    minimum_trades: int = 10,
    run_backtest: bool = False,
    days: int = 30,
) -> EvaluationResult:
    """Evaluate one proposal. Web/CLI callers must keep run_backtest off unless intended."""
    baseline, source = _load_baseline(proposal, backtest_results)
    if not run_backtest:
        return evaluate(proposal, baseline, source, minimum_trades)
    try:
        candidate, backtest_source = run_limited_backtest(proposal, days)
    except Exception as exc:  # fail-closed: never invent metrics
        candidate, backtest_source = None, f"{type(exc).__name__}: {exc}"
    if candidate is None:
        return EvaluationResult(
            proposal_id=proposal.proposal_id,
            evaluated_at=utc_now(),
            evaluator_version="phase-b-limited-backtest-1",
            baseline=baseline,
            candidate=dict(baseline),
            delta={key: 0.0 for key in baseline},
            verdict="not_run",
            notes=f"Limited backtest skipped or failed ({backtest_source}); production files were not modified.",
        )
    return evaluate(proposal, baseline, backtest_source, minimum_trades, candidate, ran_backtest=True)


def persist_evaluation(proposal_path: Path, result: EvaluationResult) -> Path:
    output = EVALUATIONS_DIR / f"{result.proposal_id}.json"
    write_json(output, result)
    update_proposal_status(proposal_path, "evaluated")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one proposal without touching production files")
    parser.add_argument("proposal", help="Proposal JSON filename under proposals/")
    parser.add_argument("--backtest-results", help="Optional repository-local Freqtrade export JSON or zip")
    parser.add_argument("--minimum-trades", type=int, default=10)
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="Optionally run a limited Freqtrade backtest against a temporary experimental config",
    )
    parser.add_argument("--days", type=int, default=30, help="Timerange days for --run-backtest (7-90)")
    args = parser.parse_args()
    if args.minimum_trades < 1 or args.minimum_trades > 100_000:
        parser.error("--minimum-trades must be between 1 and 100000")
    if args.days < 7 or args.days > 90:
        parser.error("--days must be between 7 and 90")

    proposal_path = safe_artifact_path(PROPOSALS_DIR, Path(args.proposal).name)
    proposal = read_json(proposal_path, ExperimentProposal)
    result = evaluate_proposal(
        proposal,
        backtest_results=args.backtest_results,
        minimum_trades=args.minimum_trades,
        run_backtest=args.run_backtest,
        days=args.days,
    )
    output = persist_evaluation(proposal_path, result)
    log_action(
        "evaluator",
        "proposal_evaluated",
        proposal_id=proposal.proposal_id,
        path=str(output.relative_to(ROOT)),
        verdict=result.verdict,
        source=result.notes,
        run_backtest=args.run_backtest and result.verdict != "not_run",
        evaluator_version=result.evaluator_version,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
