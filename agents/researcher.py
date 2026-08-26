"""Generate one inspectable experiment proposal from local trading evidence.

The researcher can ask the existing advisory AI client for commentary, but AI
output is never treated as a trade signal and never edits source code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import PROPOSALS_DIR, collect_context, latest_metrics
from agents.models import ExperimentProposal, write_json
from agents.runtime import log_action


def _proposal_id() -> str:
    return "proposal-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _advisory(context: dict[str, object], use_ai: bool) -> str:
    if not use_ai:
        return "AI commentary was intentionally disabled for this run."
    try:
        from bot.ai_client import AIClient

        prompt = (
            "You are an advisory research assistant. Do not give an order, price target, "
            "position size, leverage, or live-trading instruction. Review this bounded JSON "
            "summary and suggest one falsifiable paper-trading experiment or documentation "
            "improvement in at most 100 words:\n" + json.dumps(context, sort_keys=True)[:12_000]
        )
        return AIClient().complete(prompt, max_tokens=180)[:1_500]
    except Exception as exc:  # provider failure must never block proposal creation
        return f"AI commentary unavailable: {type(exc).__name__}"


def build_proposal(context: dict[str, object], use_ai: bool) -> ExperimentProposal:
    metrics = latest_metrics(context)
    proposal_id = _proposal_id()
    advisory = _advisory(context, use_ai)
    return ExperimentProposal(
        proposal_id=proposal_id,
        created_at=str(context["collected_at"]),
        title="Measure robustness of the current entry branch on a fresh window",
        hypothesis=(
            "A fresh out-of-sample paper/backtest window should be evaluated before any "
            "parameter change is considered; the current metric snapshot is only a baseline."
        ),
        proposal_type="test_idea",
        target_config=f"experiments/experimental-profiles/{proposal_id}.json",
        changes={},
        evaluation_plan={
            "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
            "minimum_trades": 10,
            "compare_against": "latest local backtest metrics",
            "mode": "dry_evaluation",
        },
        source_summary={
            "backtests": context.get("backtests", []),
            "paper_logs": context.get("paper_logs", []),
            "baseline_metrics": metrics,
        },
        rationale=(
            "Research proposal only; no production strategy file or live configuration is "
            f"modified. Advisory note: {advisory}"
        ),
        status="pending",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one offline experiment proposal")
    parser.add_argument("--use-ai", action="store_true", help="Ask the advisory AI fallback chain for commentary")
    args = parser.parse_args()
    context = collect_context()
    proposal = build_proposal(context, args.use_ai)
    output = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    write_json(output, proposal)
    log_action(
        "researcher",
        "proposal_created",
        proposal_id=proposal.proposal_id,
        path=str(output.relative_to(ROOT)),
        use_ai=args.use_ai,
        context_files=len(context.get("backtests", [])) + len(context.get("paper_logs", [])),
    )
    print(json.dumps(proposal.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
