"""Offline self-improvement helpers for research artifacts only.

The agents package can propose and evaluate experiments, but it has no exchange
client, no order API, and no permission to mutate production strategy code.
"""

from .models import EvaluationResult, ExperimentProposal, HumanDecision, SchemaError

__all__ = ["EvaluationResult", "ExperimentProposal", "HumanDecision", "SchemaError"]
