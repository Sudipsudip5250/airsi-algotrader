#!/usr/bin/env python3
"""One free-first research day: propose, evaluate, then stop for a human decision.

Never talks to an exchange, never edits AIRSIAlgoStrategy, and never writes
bot/config.paper.json or bot/config.live.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import PROPOSALS_DIR, collect_context
from agents.evaluator import (
    DATA_DIR,
    PAPER_TEMPLATE,
    evaluate_proposal,
    has_local_ohlcv,
    persist_evaluation,
    preflight_limited_backtest,
)
from agents.models import write_json
from agents.researcher import build_proposal, find_duplicate
from agents.reviewer import list_queue, print_status
from agents.runtime import log_action


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def evaluation_kind(version: str, verdict: str) -> str:
    if verdict == "not_run":
        return "Limited backtest (not run)"
    if "limited-backtest" in version:
        return "Limited backtest"
    return "Dry evaluation"


def collect_preflight() -> dict[str, str]:
    """Describe local readiness. Does not download data or start Freqtrade."""
    freqtrade = shutil.which("freqtrade")
    ohlcv = has_local_ohlcv(DATA_DIR)
    return {
        "freqtrade": (
            f"found ({freqtrade})"
            if freqtrade
            else "missing — activate the project environment; limited backtest will be not_run"
        ),
        "ohlcv": (
            f"found under {DATA_DIR.relative_to(ROOT)}"
            if ohlcv
            else "missing — run: python scripts/download_data.py --days 30"
        ),
        "paper_template": (
            f"found {PAPER_TEMPLATE.relative_to(ROOT)} (read-only; will not be modified)"
            if PAPER_TEMPLATE.exists()
            else f"missing {PAPER_TEMPLATE}"
        ),
    }


def print_preflight(checks: dict[str, str]) -> None:
    print("PREFLIGHT")
    for key, value in checks.items():
        print(f"  {key}: {value}")
    print()


def maybe_download_data(days: int) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "download_data.py"),
        "--days",
        str(days),
    ]
    print("Downloading OHLCV via scripts/download_data.py (public market data only)...")
    completed = subprocess.run(command, check=False, cwd=ROOT)
    return completed.returncode


def run_research_day(
    *,
    use_ai: bool = False,
    force: bool = False,
    run_backtest: bool = False,
    days: int = 30,
    download: bool = False,
) -> int:
    print("AIRSI research day — educational use only; not financial advice.")
    print("Agents cannot place, cancel, size, or leverage trades.\n")
    checks = collect_preflight()
    print_preflight(checks)

    if download and not has_local_ohlcv(DATA_DIR):
        code = maybe_download_data(days)
        if code != 0:
            print("Data download failed; continuing with dry evaluation (fail-closed).\n")
        checks = collect_preflight()
        print_preflight(checks)

    context = collect_context()
    proposal = build_proposal(context, use_ai)
    fingerprint = str(proposal.source_summary.get("fingerprint", ""))
    duplicate = None if force else find_duplicate(fingerprint, directory=PROPOSALS_DIR)
    reused = False
    if duplicate is not None:
        proposal = duplicate
        reused = True
        print(f"Reusing active proposal {proposal.proposal_id} (same idea fingerprint).")
        log_action(
            "research-day",
            "proposal_reused",
            proposal_id=proposal.proposal_id,
            fingerprint=fingerprint,
            use_ai=use_ai,
        )
    else:
        output = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
        write_json(output, proposal)
        log_action(
            "research-day",
            "proposal_created",
            proposal_id=proposal.proposal_id,
            path=_relative(output),
            use_ai=use_ai,
            ai_provider=proposal.source_summary.get("ai_provider"),
            ai_cost_class=proposal.source_summary.get("ai_cost_class"),
        )
        print(f"Created proposal {proposal.proposal_id}")
        print(
            f"  provider={proposal.source_summary.get('ai_provider')} "
            f"cost_class={proposal.source_summary.get('ai_cost_class')}",
            file=sys.stderr,
        )

    proposal_path = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    if run_backtest:
        skip = preflight_limited_backtest(proposal)
        if skip:
            print(f"Limited backtest preflight: {skip}")
            print("Evaluator will record verdict=not_run rather than inventing metrics.\n")
    result = evaluate_proposal(
        proposal,
        minimum_trades=10,
        run_backtest=run_backtest,
        days=days,
    )
    persist_evaluation(proposal_path, result)
    kind = evaluation_kind(result.evaluator_version, result.verdict)
    print("EVALUATION")
    print(f"  kind: {kind}")
    print(f"  verdict: {result.verdict}")
    print(f"  evaluator_version: {result.evaluator_version}")
    print(f"  notes: {result.notes}")
    print()
    print_status()
    print()
    list_queue()
    print()
    print("NEXT HUMAN STEP")
    print("  Review the evaluation JSON, then record an explicit decision:")
    print(
        f"  python agents/reviewer.py decide proposals/{proposal.proposal_id}.json reject \\\n"
        f'    --reviewer "Your Name" \\\n'
        f'    --rationale "Insufficient evidence for an experimental profile."'
    )
    print()
    print("  Approval may create only a stopped dry_run experimental profile.")
    print("  It never edits AIRSIAlgoStrategy.py, bot/config.paper.json, or bot/config.live.json.")
    print(json.dumps({"proposal_id": proposal.proposal_id, "reused": reused, "verdict": result.verdict, "kind": kind}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one free-first research day and stop for a human decision",
    )
    parser.add_argument("--use-ai", action="store_true", help="Optional advisory commentary (free-first chain)")
    parser.add_argument("--force", action="store_true", help="Create a proposal even if the same idea is already pending")
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="Optional limited Freqtrade backtest against a throwaway experimental config",
    )
    parser.add_argument("--days", type=int, default=30, help="Timerange days for download/--run-backtest (7-90)")
    parser.add_argument(
        "--download",
        action="store_true",
        help="If local OHLCV is missing, download public Binance history before evaluating",
    )
    args = parser.parse_args()
    if args.days < 7 or args.days > 90:
        parser.error("--days must be between 7 and 90")
    try:
        return run_research_day(
            use_ai=args.use_ai,
            force=args.force,
            run_backtest=args.run_backtest,
            days=args.days,
            download=args.download,
        )
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
