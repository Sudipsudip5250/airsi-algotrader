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

from agents.context import (
    DECISIONS_DIR,
    EVALUATIONS_DIR,
    EXPERIMENTAL_PROFILES_DIR,
    PROPOSALS_DIR,
    QUEUE_MARKDOWN,
    safe_artifact_path,
)
from agents.models import EvaluationResult, ExperimentProposal, HumanDecision, read_json, update_proposal_status, utc_now, write_json
from agents.runtime import log_action

PAPER_TEMPLATE = ROOT / "bot" / "config.paper.json"
_ALLOWED_NUMERIC_KEYS = {"max_open_trades", "stake_amount", "dry_run_wallet", "process_throttle_secs"}
_STATUS_FOR_DECISION = {
    "approve": "approved",
    "reject": "rejected",
    "request-more-data": "evaluated",
}
_TERMINAL_DECISIONS = {"approve", "reject"}
_QUEUE_PRIORITY = {
    "evaluated": 0,
    "pending": 1,
    "request-more-data": 2,
    "approved": 3,
    "applied": 3,
    "reject": 4,
    "rejected": 4,
    "invalid": 5,
}


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
    if "config.live" in proposal.target_config or proposal.target_config == "bot/config.paper.json":
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
        elif key == "stake_amount":
            payload[key] = max(1.0, min(float(value), 100.0))
        elif key == "dry_run_wallet":
            payload[key] = max(100.0, min(float(value), 10_000.0))
        elif key == "process_throttle_secs":
            payload.setdefault("internals", {})[key] = max(1, min(int(value), 60))
        else:
            payload[key] = value
    output = EXPERIMENTAL_PROFILES_DIR / f"{proposal.proposal_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(output, 0o600)
    return output


def load_summaries() -> list[dict[str, Any]]:
    """Return newest-first proposal/evaluation/decision records for CLI and review UI."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(PROPOSALS_DIR.glob("*.json"), reverse=True):
        try:
            proposal = read_json(path, ExperimentProposal)
        except Exception as exc:
            items.append(
                {
                    "id": path.stem,
                    "status": "invalid",
                    "proposal": {"proposal_id": path.stem, "title": path.name, "hypothesis": type(exc).__name__},
                    "evaluation": None,
                    "decision": None,
                    "experimental_profile": None,
                }
            )
            continue
        evaluation = _evaluation_for(proposal.proposal_id)
        decision = _decision_for(proposal.proposal_id)
        if decision and decision.decision in _TERMINAL_DECISIONS:
            status = "applied" if decision.apply_to_experimental else _STATUS_FOR_DECISION[decision.decision]
        elif decision and decision.decision == "request-more-data":
            status = "request-more-data"
        elif evaluation:
            status = "evaluated"
        else:
            status = proposal.status
        items.append(
            {
                "id": proposal.proposal_id,
                "status": status,
                "proposal": proposal.to_dict(),
                "evaluation": evaluation.to_dict() if evaluation else None,
                "decision": decision.to_dict() if decision else None,
                "experimental_profile": decision.applied_path if decision else None,
            }
        )
    items.sort(key=lambda item: str((item.get("proposal") or {}).get("created_at") or ""), reverse=True)
    items.sort(key=lambda item: _QUEUE_PRIORITY.get(str(item.get("status")), 9))
    return items


def _queue_rows() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for item in load_summaries():
        proposal = item.get("proposal") or {}
        evaluation = item.get("evaluation") or {}
        title = str(proposal.get("title") or item["id"])
        verdict = str(evaluation.get("verdict") or "not_evaluated")
        rows.append((str(item["id"]), str(item["status"]), verdict, title))
    return rows


def write_queue_markdown(rows: list[tuple[str, str, str, str]] | None = None) -> Path:
    """Write a git-ignored markdown review queue for operators without the dashboard."""
    rows = rows if rows is not None else _queue_rows()
    lines = [
        "# Self-improvement review queue",
        "",
        "This file is generated by `python agents/reviewer.py list`. It is not a trading signal.",
        "",
        "| Proposal | State | Evaluation | Title |",
        "| --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| _empty_ | — | — | No proposals in the review queue. |")
    else:
        for proposal_id, state, verdict, title in rows:
            safe_title = title.replace("|", "/")
            lines.append(f"| `{proposal_id}` | {state} | {verdict} | {safe_title} |")
    lines.extend(
        [
            "",
            "Approve only after reading the evaluation JSON. Approval may create a stopped `dry_run: true` profile under `experiments/experimental-profiles/`; it never edits `AIRSIAlgoStrategy.py` or default paper/live configs.",
            "",
        ]
    )
    QUEUE_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")
    return QUEUE_MARKDOWN


def list_queue() -> int:
    rows = _queue_rows()
    write_queue_markdown(rows)
    if not rows:
        print("No proposals in the review queue.")
        return 0
    print("PROPOSAL_ID\tSTATE\tEVALUATION\tTITLE")
    for row in rows:
        print("\t".join(row))
    try:
        queue_display = QUEUE_MARKDOWN.relative_to(ROOT)
    except ValueError:
        queue_display = QUEUE_MARKDOWN
    print(f"\nMarkdown queue: {queue_display}", file=sys.stderr)
    return 0


def print_status() -> int:
    """Print local queue counts and recent decisions. Makes no network calls."""
    items = load_summaries()
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    print("QUEUE")
    print(
        f"proposals={len(items)} "
        f"pending={counts.get('pending', 0)} "
        f"evaluated={counts.get('evaluated', 0)} "
        f"request-more-data={counts.get('request-more-data', 0)} "
        f"approved={counts.get('approved', 0)} "
        f"applied={counts.get('applied', 0)} "
        f"rejected={counts.get('rejected', 0)}"
    )
    print("\nRECENT DECISIONS")
    decisions = [item for item in items if isinstance(item.get("decision"), dict)]
    decisions.sort(key=lambda item: str((item.get("decision") or {}).get("decided_at") or ""), reverse=True)
    if not decisions:
        print("none")
        return 0
    print("PROPOSAL_ID\tDECISION\tREVIEWER\tRATIONALE")
    for item in decisions[:8]:
        decision = item["decision"]
        rationale = str(decision.get("rationale") or "").replace("\t", " ").replace("\n", " ")[:80]
        print(
            f"{decision.get('proposal_id') or item['id']}\t"
            f"{decision.get('decision')}\t"
            f"{decision.get('reviewer')}\t"
            f"{rationale}"
        )
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
    existing = _decision_for(proposal.proposal_id)
    if existing and existing.decision in _TERMINAL_DECISIONS:
        raise ValueError("proposal already has a terminal human decision")
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
    status = "applied" if apply_experimental else _STATUS_FOR_DECISION[decision]
    update_proposal_status(proposal_path, status)
    write_queue_markdown()
    log_action(
        "human-review",
        "proposal_decided",
        proposal_id=proposal.proposal_id,
        decision=decision,
        apply_to_experimental=apply_experimental,
        applied_path=applied_path,
        reviewer=record.reviewer,
        proposal_status=status,
        replaced_request_more_data=bool(existing and existing.decision == "request-more-data"),
    )
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review offline self-improvement proposals")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List pending and decided proposals")
    subparsers.add_parser("status", help="Print queue counts and recent decisions (local artifacts only)")
    decide_parser = subparsers.add_parser("decide", help="Record a human decision for one evaluated proposal")
    decide_parser.add_argument("proposal", help="Proposal JSON filename under proposals/")
    decide_parser.add_argument("decision", choices=("approve", "reject", "request-more-data"))
    decide_parser.add_argument("--reviewer", required=True)
    decide_parser.add_argument("--rationale", required=True)
    decide_parser.add_argument("--apply-experimental", action="store_true")
    args = parser.parse_args()
    if args.command == "list":
        return list_queue()
    if args.command == "status":
        return print_status()
    try:
        return decide(args.proposal, args.decision, args.reviewer, args.rationale, args.apply_experimental)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
