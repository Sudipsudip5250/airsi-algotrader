# Experiments

This directory contains offline self-improvement artifacts. `evaluations/` stores baseline-versus-candidate results, `decisions/` stores human approval or rejection records, and `experimental-profiles/` stores stopped dry-run Freqtrade configs created only after explicit human approval.

The default paper profile and live profile are never modified by this loop. Experimental profiles are not production-ready and require independent review before any use. `agent-actions.jsonl` is an append-only audit trail for researcher, evaluator, and reviewer actions.
