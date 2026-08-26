"""Human review CLI for proposal artifacts.

Approval is an audit record, not permission to trade. Applying a proposal can
only create a stopped dry-run profile under experiments/experimental-profiles/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.context import DECISIONS_DIR, EVALUATIONS_DIR, EXPERIMENTAL_PROFILES_DIR, PROPOSALS_DIR, safe_artifact_path
from agents.models import EvaluationResult, ExperimentProposal, HumanDecision, read_json, utc_now, write_json
from agents.runtime import log_action

PAPER_TEMPLATE = ROOT / "bot" / "config.paper.json"
_ALLOWED_NUMERIC_KEYS = {"max_open_trades", "stake_amount", "dry_run_wallet", "process_throttle_secs"}


def _read_optional(path: Path, artifact_type: type[Any]) -> Any | None:
    if not path.exists():
        return None
    try:
        return read_json(path, artifact_type)
    except (OSError, ValueError, TypeError):
        return None


def _evaluation_for(proposal_id: str) -> EvaluationResult | None:
    return _read_optional(EVALUATIONS_DIR / f"{proposal_id}.json", EvaluationResult)


def _decision_for(proposal_id: str) -> HumanDecision | None:
    return _read_optional(DECISIONS_DIR / f"{proposal_id}.json", HumanDecision)


def _experimental_profile(proposal: ExperimentProposal) -> Path:
    if not PAPER_TEMPLATE.exists():
        raise FileNotFoundError(PAPER_TEMPLATE)
    if "config.live" in proposal.target_config:
        raise ValueError("live configuration is never an experimental target")
    unsupported = set(proposal.changes) - _ALLOWED_NUMERIC_KEYS
    if unsupported:
        raise ValueError(f"unsupported config changes: {sorted(unsupported)}")
    payload = json.loads(PAPER_TEMPLATE.read_text(encoding="utf-8"))
    payload["dry_run"] = True
    payload["initial_state"] = "stopped"
    payload["bot_name"] = f"AIRSIAlgoTrader-Experiment-{proposal.proposal_id[-12:]}"
    payload["force_entry_enable"] = False
    for key, value in proposal.changes.items():
        if key == "max_open_trades":
            payload[key] = max(1, min(int(value), 10))
        elif key == "process_throttle_secs":
            payload.setdefault("internals", {})[key] = max(1, min(int(value), 60))
        else:
            payload[key] = value
    output = EXPERIMENTAL_PROFILES_DIR / f"{proposal.proposal_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(output, 0o600)
    return output


def list_queue() -> int:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted(PROPOSALS_DIR.glob("*.json")):
        try:
            proposal = read_json(path, ExperimentProposal)
        except Exception as exc:
            rows.append((path.stem, "invalid", "invalid", type(exc).__name__))
            continue
        evaluation = _evaluation_for(proposal.proposal_id)
        decision = _decision_for(proposal.proposal_id)
        state = decision.decision if decision else proposal.status
        verdict = evaluation.verdict if evaluation else "not_evaluated"
        rows.append((proposal.proposal_id, state, verdict, proposal.title))
    if not rows:
        print("No proposals in the review queue.")
        return 0
    print("PROPOSAL_ID\tSTATE\tEVALUATION\tTITLE")
    for row in rows:
        print("\t".join(row))
    return 0


def decide(proposal_name: str, decision: str, reviewer: str, rationale: str, apply_experimental: bool) -> int:
    proposal_path = safe_artifact_path(PROPOSALS_DIR, Path(proposal_name).name)
    proposal = read_json(proposal_path, ExperimentProposal)
    evaluation = _evaluation_for(proposal.proposal_id)
    if evaluation is None:
        raise ValueError("evaluate the proposal before recording a human decision")
    if not reviewer.strip() or not rationale.strip():
        raise ValueError("reviewer and rationale are required")
    if apply_experimental and decision != "approve":
        raise ValueError("--apply-experimental is valid only with approve")
    applied_path: str | None = None
    if apply_experimental:
        applied_path = str(_experimental_profile(proposal).relative_to(ROOT))
    record = HumanDecision(
        proposal_id=proposal.proposal_id,
        decided_at=utc_now(),
        reviewer=reviewer.strip(),
        decision=decision,
        rationale=rationale.strip(),
        apply_to_experimental=apply_experimental,
        applied_path=applied_path,
    )
    output = DECISIONS_DIR / f"{proposal.proposal_id}.json"
    write_json(output, record)
    log_action(
        "human-review",
        "proposal_decided",
        proposal_id=proposal.proposal_id,
        decision=decision,
        apply_to_experimental=apply_experimental,
        applied_path=applied_path,
        reviewer=record.reviewer,
    )
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review offline self-improvement proposals")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List pending and decided proposals")
    decide_parser = subparsers.add_parser("decide", help="Record a human decision for one evaluated proposal")
    decide_parser.add_argument("proposal", help="Proposal JSON filename under proposals/")
    decide_parser.add_argument("decision", choices=("approve", "reject", "request-more-data"))
    decide_parser.add_argument("--reviewer", required=True)
    decide_parser.add_argument("--rationale", required=True)
    decide_parser.add_argument("--apply-experimental", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        return list_queue()
    try:
        return decide(args.proposal, args.decision, args.reviewer, args.rationale, args.apply_experimental)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
