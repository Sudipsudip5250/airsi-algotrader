"""Versioned, human-readable schemas for the offline self-improvement loop.

These models deliberately describe research artifacts only. They contain no
exchange commands and cannot represent a live deployment or an order.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

SCHEMA_VERSION = 1
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,127}$")
_ALLOWED_PROPOSAL_TYPES = {"parameter_change", "test_idea", "documentation"}
_ALLOWED_PROPOSAL_STATUSES = {"pending", "evaluated", "approved", "rejected", "applied"}
_ALLOWED_VERDICTS = {"promising", "not_promising", "inconclusive", "not_run"}


class SchemaError(ValueError):
    """Raised when a research artifact is malformed or unsafe."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, field_name: str, *, max_length: int = 2_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field_name} must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise SchemaError(f"{field_name} exceeds {max_length} characters")
    return value


def _id(value: Any, field_name: str = "id") -> str:
    value = _text(value, field_name, max_length=128)
    if not _ID_PATTERN.fullmatch(value):
        raise SchemaError(f"{field_name} contains unsafe characters")
    return value


def _timestamp(value: Any, field_name: str) -> str:
    value = _text(value, field_name, max_length=64)
    if not value.endswith("Z") and not re.search(r"[+-]\d{2}:?\d{2}$", value):
        raise SchemaError(f"{field_name} must include an explicit timezone")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaError(f"{field_name} must be ISO-8601") from exc
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{field_name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise SchemaError(f"{field_name} must be finite")
    return value


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{field_name} must be an object")
    return dict(value)


@dataclass(frozen=True)
class ExperimentProposal:
    """A bounded research idea awaiting evaluation and human review."""

    proposal_id: str
    created_at: str
    title: str
    hypothesis: str
    proposal_type: str
    target_config: str
    changes: dict[str, float] = field(default_factory=dict)
    evaluation_plan: dict[str, Any] = field(default_factory=dict)
    source_summary: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    status: str = "pending"
    schema_version: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _id(self.proposal_id, "proposal_id")
        _timestamp(self.created_at, "created_at")
        _text(self.title, "title")
        _text(self.hypothesis, "hypothesis")
        if self.proposal_type not in _ALLOWED_PROPOSAL_TYPES:
            raise SchemaError(f"unsupported proposal_type: {self.proposal_type}")
        target = _text(self.target_config, "target_config", max_length=256)
        if target == "bot/config.paper.json" or not target.startswith("experiments/experimental-profiles/") or "config.live" in target:
            raise SchemaError("target_config must be an experimental paper profile")
        if self.status not in _ALLOWED_PROPOSAL_STATUSES:
            raise SchemaError(f"unsupported proposal status: {self.status}")
        changes = _mapping(self.changes, "changes")
        for key, value in changes.items():
            _text(key, "change key", max_length=128)
            _number(value, f"changes.{key}")
        _mapping(self.evaluation_plan, "evaluation_plan")
        _mapping(self.source_summary, "source_summary")
        if self.rationale:
            _text(self.rationale, "rationale")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = self.schema_version
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentProposal":
        _check_version(payload)
        fields = {key: payload[key] for key in (
            "proposal_id", "created_at", "title", "hypothesis", "proposal_type",
            "target_config", "changes", "evaluation_plan", "source_summary",
            "rationale", "status",
        ) if key in payload}
        return cls(**fields)


@dataclass(frozen=True)
class EvaluationResult:
    """A reproducible baseline-versus-candidate research comparison."""

    proposal_id: str
    evaluated_at: str
    evaluator_version: str
    baseline: dict[str, float]
    candidate: dict[str, float]
    delta: dict[str, float]
    verdict: str
    notes: str = ""
    schema_version: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _id(self.proposal_id, "proposal_id")
        _timestamp(self.evaluated_at, "evaluated_at")
        _text(self.evaluator_version, "evaluator_version", max_length=128)
        for name, metrics in (("baseline", self.baseline), ("candidate", self.candidate), ("delta", self.delta)):
            metrics = _mapping(metrics, name)
            for key, value in metrics.items():
                _text(key, f"{name} key", max_length=128)
                _number(value, f"{name}.{key}")
        if self.verdict not in _ALLOWED_VERDICTS:
            raise SchemaError(f"unsupported verdict: {self.verdict}")
        if self.notes:
            _text(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = self.schema_version
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationResult":
        _check_version(payload)
        fields = {key: payload[key] for key in (
            "proposal_id", "evaluated_at", "evaluator_version", "baseline",
            "candidate", "delta", "verdict", "notes",
        ) if key in payload}
        return cls(**fields)


@dataclass(frozen=True)
class HumanDecision:
    """A human decision; approval never implies live deployment."""

    proposal_id: str
    decided_at: str
    reviewer: str
    decision: str
    rationale: str
    apply_to_experimental: bool = False
    applied_path: str | None = None
    schema_version: ClassVar[int] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _id(self.proposal_id, "proposal_id")
        _timestamp(self.decided_at, "decided_at")
        _text(self.reviewer, "reviewer", max_length=256)
        if self.decision not in {"approve", "reject", "request-more-data"}:
            raise SchemaError("decision must be approve, reject, or request-more-data")
        _text(self.rationale, "rationale")
        if not isinstance(self.apply_to_experimental, bool):
            raise SchemaError("apply_to_experimental must be boolean")
        if self.applied_path is not None:
            path = _text(self.applied_path, "applied_path", max_length=256)
            if not path.startswith("experiments/experimental-profiles/") or "config.live" in path:
                raise SchemaError("applied_path must stay inside the experimental profile directory")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = self.schema_version
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HumanDecision":
        _check_version(payload)
        fields = {key: payload[key] for key in (
            "proposal_id", "decided_at", "reviewer", "decision", "rationale",
            "apply_to_experimental", "applied_path",
        ) if key in payload}
        return cls(**fields)


def _check_version(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError(f"expected schema_version={SCHEMA_VERSION}")


def write_json(path: Path, artifact: ExperimentProposal | EvaluationResult | HumanDecision) -> None:
    """Atomically write one versioned artifact with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path, artifact_type: type[ExperimentProposal] | type[EvaluationResult] | type[HumanDecision]) -> Any:
    """Load and validate an artifact from JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaError(f"could not read {path}: {exc}") from exc
    return artifact_type.from_dict(payload)
