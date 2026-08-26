"""Evaluate a proposal using a dry metric comparison or an existing backtest export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import BACKTEST_DIR, EVALUATIONS_DIR, PROPOSALS_DIR, safe_artifact_path
from agents.models import EvaluationResult, ExperimentProposal, read_json, utc_now, write_json
from agents.runtime import log_action


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


def evaluate(proposal: ExperimentProposal, baseline: dict[str, float], source: str, minimum_trades: int) -> EvaluationResult:
    # Phase A intentionally evaluates a no-op candidate. Future evaluators may run
    # a sandboxed backtest, but the candidate must never be a live or production file.
    candidate = dict(baseline)
    delta = {key: candidate[key] - baseline[key] for key in baseline}
    trades = candidate["number_of_trades"]
    if trades < minimum_trades:
        verdict = "inconclusive"
        notes = f"Dry evaluation from {source}; at least {minimum_trades} trades are required for a meaningful comparison."
    else:
        verdict = "promising" if candidate["expectancy"] >= baseline["expectancy"] and candidate["max_drawdown"] <= baseline["max_drawdown"] else "not_promising"
        notes = f"Dry evaluation from {source}; no candidate parameter was applied."
    return EvaluationResult(
        proposal_id=proposal.proposal_id,
        evaluated_at=utc_now(),
        evaluator_version="phase-a-dry-evaluator-1",
        baseline=baseline,
        candidate=candidate,
        delta=delta,
        verdict=verdict,
        notes=notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one proposal without touching production files")
    parser.add_argument("proposal", help="Proposal JSON filename under proposals/")
    parser.add_argument("--backtest-results", help="Optional repository-local Freqtrade export JSON")
    parser.add_argument("--minimum-trades", type=int, default=10)
    args = parser.parse_args()
    if args.minimum_trades < 1 or args.minimum_trades > 100_000:
        parser.error("--minimum-trades must be between 1 and 100000")

    proposal_path = safe_artifact_path(PROPOSALS_DIR, Path(args.proposal).name)
    proposal = read_json(proposal_path, ExperimentProposal)
    baseline, source = _load_baseline(proposal, args.backtest_results)
    result = evaluate(proposal, baseline, source, args.minimum_trades)
    output = EVALUATIONS_DIR / f"{proposal.proposal_id}.json"
    write_json(output, result)
    log_action(
        "evaluator",
        "proposal_evaluated",
        proposal_id=proposal.proposal_id,
        path=str(output.relative_to(ROOT)),
        verdict=result.verdict,
        source=source,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
