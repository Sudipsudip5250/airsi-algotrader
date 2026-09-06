"""Evaluate a proposal using a dry metric comparison or an existing backtest export."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import BACKTEST_DIR, EVALUATIONS_DIR, PROPOSALS_DIR, safe_artifact_path
from agents.models import EvaluationResult, ExperimentProposal, read_json, update_proposal_status, utc_now, write_json
from agents.runtime import log_action

PAPER_TEMPLATE = ROOT / "bot" / "config.paper.json"
_PROTECTED = {"bot/config.paper.json", "bot/config.live.json"}


def _metrics_from_backtest(path: Path) -> dict[str, float] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("strategy", {})
        result = next(iter(values.values())) if isinstance(values, dict) and values else {}
        trades = float(result.get("total_trades", 0))
        profit = float(result.get("profit_total", 0.0))
        drawdown = float(result.get("max_drawdown", 0.0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError, StopIteration):
        return None
    if trades < 0 or not all(value == value for value in (profit, drawdown)):
        return None
    return {
        "expectancy": profit / trades if trades else 0.0,
        "max_drawdown": max(0.0, drawdown),
        "number_of_trades": trades,
    }


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

    for path in sorted(BACKTEST_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
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


def _temporary_experimental_config(proposal: ExperimentProposal) -> Path:
    if proposal.target_config in _PROTECTED or "config.live" in proposal.target_config:
        raise ValueError("refusing to backtest against a protected configuration")
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
    handle = tempfile.NamedTemporaryFile(
        prefix=f"eval-{proposal.proposal_id}-",
        suffix=".json",
        dir=ROOT / "bot" / "user_data",
        delete=False,
    )
    Path(handle.name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handle.close()
    return Path(handle.name)


def run_limited_backtest(proposal: ExperimentProposal, days: int) -> tuple[dict[str, float] | None, str]:
    """Run a short Freqtrade backtest against a temporary experimental config.

    Never writes to default paper or live profiles. Missing freqtrade/data is
    fail-closed and returns not_run rather than inventing metrics.
    """
    if shutil.which("freqtrade") is None:
        return None, "freqtrade is not installed"
    data_dir = ROOT / "bot" / "user_data" / "data"
    if not any(data_dir.rglob("*.feather")) and not any(data_dir.rglob("*.json")) and not any(data_dir.rglob("*.parquet")):
        return None, "no local market data under bot/user_data/data"
    config_path = _temporary_experimental_config(proposal)
    export_path = ROOT / "bot" / "user_data" / "backtest_results" / f"eval-{proposal.proposal_id}.json"
    try:
        from datetime import date, timedelta

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
            str(data_dir),
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
        metrics = _metrics_from_backtest(export_path) if export_path.exists() else None
        if metrics is None:
            return None, "limited backtest produced no parseable metrics"
        return metrics, str(export_path.relative_to(ROOT))
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass


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
    candidate, backtest_source = run_limited_backtest(proposal, days)
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
    parser.add_argument("--backtest-results", help="Optional repository-local Freqtrade export JSON")
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
