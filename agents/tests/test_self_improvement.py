from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.context import _redact, extract_metrics, fingerprint_idea
from agents.evaluator import evaluate, evaluate_proposal, run_limited_backtest
from agents.models import ExperimentProposal, HumanDecision, SchemaError, read_json, update_proposal_status, write_json
from agents.researcher import build_proposal, find_duplicate, select_experiment
from agents.reviewer import write_queue_markdown


def test_models_round_trip_as_versioned_json(tmp_path: Path) -> None:
    proposal = ExperimentProposal(
        proposal_id="proposal-test-001",
        created_at="2026-01-01T00:00:00Z",
        title="Test a paper-only hypothesis",
        hypothesis="A bounded test should be reproducible.",
        proposal_type="test_idea",
        target_config="experiments/experimental-profiles/proposal-test-001.json",
    )
    path = tmp_path / "proposal.json"
    write_json(path, proposal)
    assert json.loads(path.read_text())["schema_version"] == 1
    assert read_json(path, ExperimentProposal) == proposal


def test_schema_rejects_live_targets_and_future_versions() -> None:
    with pytest.raises(SchemaError):
        ExperimentProposal(
            proposal_id="proposal-test-002",
            created_at="2026-01-01T00:00:00Z",
            title="Unsafe target",
            hypothesis="This must not pass.",
            proposal_type="test_idea",
            target_config="bot/config.live.json",
        )
    with pytest.raises(SchemaError):
        ExperimentProposal.from_dict({"schema_version": 99})


def test_context_redacts_secrets_and_extracts_stable_metrics() -> None:
    assert "super-secret" not in _redact("api_key=super-secret")
    assert "<redacted>" in _redact("api_key=super-secret")
    assert extract_metrics({"strategy": {"AIRSIAlgoStrategy": {"total_trades": 4, "profit_total": 2, "max_drawdown": 0.5}}}) == {
        "expectancy": 0.5,
        "max_drawdown": 0.5,
        "number_of_trades": 4.0,
    }
    assert extract_metrics({"bad": "shape"}) is None


def test_researcher_builds_pending_proposal_without_ai() -> None:
    proposal = build_proposal(
        {"collected_at": "2026-01-01T00:00:00Z", "backtests": [], "paper_logs": []},
        use_ai=False,
    )
    assert proposal.status == "pending"
    assert proposal.proposal_type == "documentation"
    assert proposal.changes == {}
    assert proposal.target_config.startswith("experiments/experimental-profiles/")
    assert proposal.source_summary["ai_provider"] == "none"
    assert proposal.source_summary["ai_cost_class"] == "free"


def test_researcher_proposes_conservative_stake_on_high_drawdown() -> None:
    idea = select_experiment({"expectancy": 0.1, "max_drawdown": 0.15, "number_of_trades": 20})
    assert idea["proposal_type"] == "parameter_change"
    assert idea["changes"] == {"stake_amount": 25.0}


def test_researcher_skips_duplicate_fingerprint(tmp_path: Path) -> None:
    first = ExperimentProposal(
        proposal_id="proposal-test-dup-1",
        created_at="2026-01-01T00:00:00Z",
        title="Collect a local backtest or paper-log sample before changing parameters",
        hypothesis="Without a metric snapshot, any parameter change would be unfalsifiable.",
        proposal_type="documentation",
        target_config="experiments/experimental-profiles/proposal-test-dup-1.json",
        source_summary={"fingerprint": fingerprint_idea(
            "documentation",
            "Collect a local backtest or paper-log sample before changing parameters",
            {},
        )},
    )
    write_json(tmp_path / f"{first.proposal_id}.json", first)
    found = find_duplicate(str(first.source_summary["fingerprint"]), tmp_path)
    assert found is not None
    assert found.proposal_id == first.proposal_id


def test_evaluator_fails_closed_on_insufficient_trades() -> None:
    proposal = ExperimentProposal(
        proposal_id="proposal-test-003",
        created_at="2026-01-01T00:00:00Z",
        title="Dry evaluation",
        hypothesis="Insufficient evidence remains inconclusive.",
        proposal_type="test_idea",
        target_config="experiments/experimental-profiles/proposal-test-003.json",
        source_summary={"baseline_metrics": {"expectancy": 1.0, "max_drawdown": 0.2, "number_of_trades": 3}},
    )
    result = evaluate(proposal, {"expectancy": 1.0, "max_drawdown": 0.2, "number_of_trades": 3.0}, "test", 10)
    assert result.verdict == "inconclusive"
    assert result.candidate == result.baseline


def test_dry_parameter_change_does_not_claim_improvement() -> None:
    proposal = ExperimentProposal(
        proposal_id="proposal-test-006",
        created_at="2026-01-01T00:00:00Z",
        title="Halve stake",
        hypothesis="Smaller stake should be tested in isolation.",
        proposal_type="parameter_change",
        target_config="experiments/experimental-profiles/proposal-test-006.json",
        changes={"stake_amount": 25.0},
    )
    result = evaluate(
        proposal,
        {"expectancy": 0.1, "max_drawdown": 0.05, "number_of_trades": 20.0},
        "test",
        10,
    )
    assert result.verdict == "inconclusive"
    assert "unevaluated" in result.notes


def test_request_more_data_is_explicit_and_never_applies_profile() -> None:
    decision = HumanDecision(
        proposal_id="proposal-test-005",
        decided_at="2026-01-01T00:00:00Z",
        reviewer="Reviewer",
        decision="request-more-data",
        rationale="Collect more paper evidence.",
        apply_to_experimental=False,
        applied_path=None,
    )
    assert decision.decision == "request-more-data"
    assert decision.applied_path is None


def test_human_decision_requires_experimental_directory_for_apply() -> None:
    with pytest.raises(SchemaError):
        HumanDecision(
            proposal_id="proposal-test-004",
            decided_at="2026-01-01T00:00:00Z",
            reviewer="Reviewer",
            decision="approve",
            rationale="Not a live path.",
            apply_to_experimental=True,
            applied_path="bot/config.live.json",
        )


def test_apply_experimental_rejected_unless_approve() -> None:
    with pytest.raises(SchemaError):
        HumanDecision(
            proposal_id="proposal-test-007",
            decided_at="2026-01-01T00:00:00Z",
            reviewer="Reviewer",
            decision="reject",
            rationale="Must not apply.",
            apply_to_experimental=True,
        )


def test_update_proposal_status_rewrites_only_status(tmp_path: Path) -> None:
    proposal = ExperimentProposal(
        proposal_id="proposal-test-008",
        created_at="2026-01-01T00:00:00Z",
        title="Status update",
        hypothesis="Status should move to evaluated.",
        proposal_type="test_idea",
        target_config="experiments/experimental-profiles/proposal-test-008.json",
    )
    path = tmp_path / "proposal.json"
    write_json(path, proposal)
    updated = update_proposal_status(path, "evaluated")
    assert updated.status == "evaluated"
    assert updated.title == proposal.title


def test_queue_markdown_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agents import reviewer

    monkeypatch.setattr(reviewer, "QUEUE_MARKDOWN", tmp_path / "QUEUE.md")
    monkeypatch.setattr(reviewer, "PROPOSALS_DIR", tmp_path / "proposals")
    (tmp_path / "proposals").mkdir()
    path = reviewer.write_queue_markdown([])
    text = path.read_text(encoding="utf-8")
    assert "review queue" in text.lower()
    assert "not a trading signal" in text


def test_experimental_profile_is_stopped_dry_run_and_clamped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agents import reviewer

    paper = {
        "dry_run": True,
        "initial_state": "running",
        "force_entry_enable": True,
        "max_open_trades": 2,
        "stake_amount": 50,
        "dry_run_wallet": 1000,
        "bot_name": "AIRSIAlgoTrader",
        "internals": {"process_throttle_secs": 5},
    }
    template = tmp_path / "config.paper.json"
    template.write_text(json.dumps(paper), encoding="utf-8")
    monkeypatch.setattr(reviewer, "PAPER_TEMPLATE", template)
    monkeypatch.setattr(reviewer, "EXPERIMENTAL_PROFILES_DIR", tmp_path / "profiles")
    proposal = ExperimentProposal(
        proposal_id="proposal-test-profile",
        created_at="2026-01-01T00:00:00Z",
        title="Halve stake",
        hypothesis="Smaller stake.",
        proposal_type="parameter_change",
        target_config="experiments/experimental-profiles/proposal-test-profile.json",
        changes={"stake_amount": 999.0, "max_open_trades": 99.0},
    )
    path = reviewer._experimental_profile(proposal)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["initial_state"] == "stopped"
    assert payload["force_entry_enable"] is False
    assert payload["stake_amount"] == 100.0
    assert payload["max_open_trades"] == 10


def test_limited_backtest_without_freqtrade_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents import evaluator

    monkeypatch.setattr(evaluator.shutil, "which", lambda _: None)
    proposal = ExperimentProposal(
        proposal_id="proposal-test-backtest",
        created_at="2026-01-01T00:00:00Z",
        title="Halve stake",
        hypothesis="Smaller stake.",
        proposal_type="parameter_change",
        target_config="experiments/experimental-profiles/proposal-test-backtest.json",
        changes={"stake_amount": 25.0},
    )
    metrics, reason = run_limited_backtest(proposal, 30)
    assert metrics is None
    assert "not installed" in reason
    result = evaluate_proposal(proposal, run_backtest=True, days=30)
    assert result.verdict == "not_run"
    assert "production files were not modified" in result.notes


def test_decide_rejects_missing_evaluation_and_terminal_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents import reviewer, runtime

    proposals = tmp_path / "proposals"
    evaluations = tmp_path / "evaluations"
    decisions = tmp_path / "decisions"
    profiles = tmp_path / "profiles"
    for path in (proposals, evaluations, decisions, profiles):
        path.mkdir()
    monkeypatch.setattr(reviewer, "PROPOSALS_DIR", proposals)
    monkeypatch.setattr(reviewer, "EVALUATIONS_DIR", evaluations)
    monkeypatch.setattr(reviewer, "DECISIONS_DIR", decisions)
    monkeypatch.setattr(reviewer, "EXPERIMENTAL_PROFILES_DIR", profiles)
    monkeypatch.setattr(reviewer, "QUEUE_MARKDOWN", tmp_path / "QUEUE.md")
    monkeypatch.setattr(runtime, "ACTION_LOG", tmp_path / "actions.jsonl")
    monkeypatch.setattr(reviewer, "PAPER_TEMPLATE", tmp_path / "config.paper.json")
    (tmp_path / "config.paper.json").write_text(
        json.dumps({"dry_run": True, "initial_state": "running", "force_entry_enable": True, "stake_amount": 50}),
        encoding="utf-8",
    )

    proposal = ExperimentProposal(
        proposal_id="proposal-test-decide",
        created_at="2026-01-01T00:00:00Z",
        title="Collect more evidence",
        hypothesis="Need an evaluation first.",
        proposal_type="test_idea",
        target_config="experiments/experimental-profiles/proposal-test-decide.json",
    )
    write_json(proposals / f"{proposal.proposal_id}.json", proposal)
    with pytest.raises(ValueError, match="evaluate the proposal"):
        reviewer.decide(f"{proposal.proposal_id}.json", "reject", "Reviewer", "No eval yet", False)

    evaluation = evaluate(
        proposal,
        {"expectancy": 0.0, "max_drawdown": 0.0, "number_of_trades": 0.0},
        "test",
        10,
    )
    write_json(evaluations / f"{proposal.proposal_id}.json", evaluation)
    assert reviewer.decide(f"{proposal.proposal_id}.json", "request-more-data", "Reviewer", "Need a longer window.", False) == 0
    assert reviewer.decide(f"{proposal.proposal_id}.json", "reject", "Reviewer", "Still insufficient evidence.", False) == 0
    with pytest.raises(ValueError, match="terminal human decision"):
        reviewer.decide(f"{proposal.proposal_id}.json", "approve", "Reviewer", "Should not overwrite.", False)

