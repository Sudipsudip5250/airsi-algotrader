"""Generate one inspectable experiment proposal from local trading evidence.

The researcher can ask the existing advisory AI client for commentary, but AI
output is never treated as a trade signal and never edits source code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import CACHE_DIR, PROPOSALS_DIR, collect_context, fingerprint_idea, latest_metrics
from agents.models import ExperimentProposal, read_json, write_json
from agents.runtime import log_action

_AI_CACHE_TTL_SECONDS = 24 * 60 * 60
_ACTIVE_STATUSES = {"pending", "evaluated"}


def _proposal_id() -> str:
    return "proposal-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def select_experiment(metrics: dict[str, float]) -> dict[str, Any]:
    """Choose one conservative, falsifiable idea from local metrics.

    Parameter proposals are bounded to experimental paper profiles and never
    increase risk relative to the default paper stake.
    """
    trades = float(metrics.get("number_of_trades", 0.0) or 0.0)
    expectancy = float(metrics.get("expectancy", 0.0) or 0.0)
    drawdown = float(metrics.get("max_drawdown", 0.0) or 0.0)

    if trades < 1:
        return {
            "proposal_type": "documentation",
            "title": "Collect a local backtest or paper-log sample before changing parameters",
            "hypothesis": (
                "Without a metric snapshot, any parameter change would be unfalsifiable. "
                "A fresh local backtest export should be captured first."
            ),
            "changes": {},
            "evaluation_plan": {
                "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
                "minimum_trades": 10,
                "compare_against": "latest local backtest metrics",
                "mode": "dry_evaluation",
            },
        }
    if trades < 10:
        return {
            "proposal_type": "test_idea",
            "title": "Extend the evaluation window until at least 10 trades exist",
            "hypothesis": (
                "The current snapshot has too few trades for a meaningful expectancy or "
                "drawdown comparison; a longer paper/backtest window is the next test."
            ),
            "changes": {},
            "evaluation_plan": {
                "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
                "minimum_trades": 10,
                "compare_against": "latest local backtest metrics",
                "mode": "dry_evaluation",
            },
        }
    if drawdown >= 0.10:
        return {
            "proposal_type": "parameter_change",
            "title": "Halve paper stake_amount on an isolated experimental profile",
            "hypothesis": (
                "A high drawdown snapshot should be re-tested with a smaller paper stake "
                "before any other parameter or strategy change is considered."
            ),
            "changes": {"stake_amount": 25.0},
            "evaluation_plan": {
                "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
                "minimum_trades": 10,
                "compare_against": "latest local backtest metrics",
                "mode": "dry_evaluation",
                "optional_backtest": True,
            },
        }
    if expectancy <= 0:
        return {
            "proposal_type": "test_idea",
            "title": "Re-evaluate the production branch on a fresh out-of-sample window",
            "hypothesis": (
                "Non-positive expectancy in the current snapshot should be confirmed on a "
                "fresh window before any production parameter change is proposed."
            ),
            "changes": {},
            "evaluation_plan": {
                "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
                "minimum_trades": 10,
                "compare_against": "latest local backtest metrics",
                "mode": "dry_evaluation",
            },
        }
    return {
        "proposal_type": "test_idea",
        "title": "Measure robustness of the current entry branch on a fresh window",
        "hypothesis": (
            "A fresh out-of-sample paper/backtest window should be evaluated before any "
            "parameter change is considered; the current metric snapshot is only a baseline."
        ),
        "changes": {},
        "evaluation_plan": {
            "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
            "minimum_trades": 10,
            "compare_against": "latest local backtest metrics",
            "mode": "dry_evaluation",
        },
    }


def find_duplicate(fingerprint: str, directory: Path = PROPOSALS_DIR) -> ExperimentProposal | None:
    """Return an active proposal with the same idea fingerprint, if any."""
    if not directory.exists():
        return None
    for path in sorted(directory.glob("*.json")):
        try:
            proposal = read_json(path, ExperimentProposal)
        except Exception:
            continue
        if proposal.status not in _ACTIVE_STATUSES:
            continue
        if str(proposal.source_summary.get("fingerprint", "")) == fingerprint:
            return proposal
    return None


def _read_ai_cache(prompt: str) -> dict[str, Any] | None:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    path = CACHE_DIR / "ai" / f"{digest}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - created).total_seconds()
        if age > _AI_CACHE_TTL_SECONDS:
            return None
        return payload
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_ai_cache(prompt: str, payload: dict[str, Any]) -> None:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    path = CACHE_DIR / "ai" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _advisory(context: dict[str, object], use_ai: bool) -> dict[str, str]:
    if not use_ai:
        return {
            "text": "AI commentary was intentionally disabled for this run.",
            "provider": "none",
            "cost_class": "free",
            "cached": "false",
        }
    prompt = (
        "You are an advisory research assistant. Do not give an order, price target, "
        "position size, leverage, or live-trading instruction. Review this bounded JSON "
        "summary and suggest one falsifiable paper-trading experiment or documentation "
        "improvement in at most 100 words:\n" + json.dumps(context, sort_keys=True)[:12_000]
    )
    cached = _read_ai_cache(prompt)
    if cached:
        return {
            "text": str(cached.get("text", ""))[:1_500],
            "provider": str(cached.get("provider", "none")),
            "cost_class": str(cached.get("cost_class", "free")),
            "cached": "true",
        }
    try:
        from bot.ai_client import AIClient

        result = AIClient().complete_with_meta(prompt, max_tokens=180)
        payload = {
            "text": result.text[:1_500],
            "provider": result.provider,
            "cost_class": result.cost_class,
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        _write_ai_cache(prompt, payload)
        return {
            "text": payload["text"],
            "provider": result.provider,
            "cost_class": result.cost_class,
            "cached": "false",
        }
    except Exception as exc:  # provider failure must never block proposal creation
        return {
            "text": f"AI commentary unavailable: {type(exc).__name__}",
            "provider": "none",
            "cost_class": "free",
            "cached": "false",
        }


def build_proposal(context: dict[str, object], use_ai: bool) -> ExperimentProposal:
    metrics = latest_metrics(context)
    idea = select_experiment(metrics)
    proposal_id = _proposal_id()
    advisory = _advisory(context, use_ai)
    fingerprint = fingerprint_idea(idea["proposal_type"], idea["title"], idea["changes"])
    return ExperimentProposal(
        proposal_id=proposal_id,
        created_at=str(context["collected_at"]),
        title=idea["title"],
        hypothesis=idea["hypothesis"],
        proposal_type=idea["proposal_type"],
        target_config=f"experiments/experimental-profiles/{proposal_id}.json",
        changes=idea["changes"],
        evaluation_plan=idea["evaluation_plan"],
        source_summary={
            "backtests": context.get("backtests", []),
            "paper_logs": context.get("paper_logs", []),
            "recent_evaluations": context.get("evaluations", []),
            "recent_decisions": context.get("decisions", []),
            "baseline_metrics": metrics,
            "fingerprint": fingerprint,
            "ai_provider": advisory["provider"],
            "ai_cost_class": advisory["cost_class"],
            "ai_cached": advisory["cached"] == "true",
        },
        rationale=(
            "Research proposal only; no production strategy file or live configuration is "
            f"modified. Advisory note ({advisory['provider']}/{advisory['cost_class']}"
            f"{', cached' if advisory['cached'] == 'true' else ''}): {advisory['text']}"
        ),
        status="pending",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one offline experiment proposal")
    parser.add_argument("--use-ai", action="store_true", help="Ask the advisory AI fallback chain for commentary")
    parser.add_argument("--force", action="store_true", help="Create a proposal even if the same idea is already pending")
    args = parser.parse_args()
    context = collect_context()
    proposal = build_proposal(context, args.use_ai)
    fingerprint = str(proposal.source_summary.get("fingerprint", ""))
    duplicate = None if args.force else find_duplicate(fingerprint)
    if duplicate is not None:
        log_action(
            "researcher",
            "proposal_skipped_duplicate",
            proposal_id=duplicate.proposal_id,
            fingerprint=fingerprint,
            use_ai=args.use_ai,
        )
        print(
            json.dumps(
                {
                    "skipped": True,
                    "reason": "duplicate_active_proposal",
                    "existing_proposal_id": duplicate.proposal_id,
                    "fingerprint": fingerprint,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    output = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    write_json(output, proposal)
    log_action(
        "researcher",
        "proposal_created",
        proposal_id=proposal.proposal_id,
        path=str(output.relative_to(ROOT)),
        use_ai=args.use_ai,
        ai_provider=proposal.source_summary.get("ai_provider"),
        ai_cost_class=proposal.source_summary.get("ai_cost_class"),
        ai_cached=proposal.source_summary.get("ai_cached"),
        fingerprint=fingerprint,
        context_files=(
            len(context.get("backtests", []))
            + len(context.get("paper_logs", []))
            + len(context.get("evaluations", []))
            + len(context.get("decisions", []))
        ),
    )
    print(json.dumps(proposal.to_dict(), indent=2, sort_keys=True))
    print(
        f"provider={proposal.source_summary.get('ai_provider')} "
        f"cost_class={proposal.source_summary.get('ai_cost_class')} "
        f"cached={proposal.source_summary.get('ai_cached')}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
