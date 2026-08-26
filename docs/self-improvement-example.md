# Self-improvement artifact example

The following is a shortened example of the JSON emitted by the first loop. Runtime files include the complete source summary and timestamps.

## Proposal

```json
{
  "schema_version": 1,
  "proposal_id": "proposal-20260826T170043Z",
  "proposal_type": "test_idea",
  "target_config": "experiments/experimental-profiles/proposal-20260826T170043Z.json",
  "status": "pending",
  "title": "Measure robustness of the current entry branch on a fresh window",
  "hypothesis": "A fresh out-of-sample paper/backtest window should be evaluated before any parameter change is considered; the current metric snapshot is only a baseline.",
  "changes": {},
  "evaluation_plan": {
    "metrics": ["expectancy", "max_drawdown", "number_of_trades"],
    "minimum_trades": 10,
    "mode": "dry_evaluation"
  }
}
```

## Evaluation result

```json
{
  "schema_version": 1,
  "proposal_id": "proposal-20260826T170043Z",
  "evaluator_version": "phase-a-dry-evaluator-1",
  "baseline": {
    "expectancy": 0.0,
    "max_drawdown": 0.0,
    "number_of_trades": 0.0
  },
  "candidate": {
    "expectancy": 0.0,
    "max_drawdown": 0.0,
    "number_of_trades": 0.0
  },
  "delta": {
    "expectancy": 0.0,
    "max_drawdown": 0.0,
    "number_of_trades": 0.0
  },
  "verdict": "inconclusive",
  "notes": "At least 10 trades are required for a meaningful comparison."
}
```

An `inconclusive` result is deliberate when evidence is insufficient. The human-review command still records an explicit rationale, and any approved profile remains stopped and dry-run only.
