from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.context import _redact, extract_metrics
from agents.evaluator import evaluate
from agents.models import EvaluationResult, ExperimentProposal, HumanDecision, SchemaError, read_json, write_json
from agents.researcher import build_proposal


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
    assert proposal.proposal_type == "test_idea"
    assert proposal.target_config.startswith("experiments/experimental-profiles/")


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
