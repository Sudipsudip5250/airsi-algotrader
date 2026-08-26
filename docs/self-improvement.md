# Self-improvement loop: Phase A and minimal Phase B

This is a deliberately small, file-based research loop. It can collect recent local backtest exports and paper-log tails, create one structured proposal, evaluate a dry candidate against a baseline, and record a human decision. It cannot place orders, modify the production strategy, modify the default paper profile, or modify the live profile. The React dashboard exposes the same artifacts at `/experiments` for inspection and human review.

## First full loop

Run all commands from the repository root after installing the project dependencies:

```bash
# 1. Generate one proposal from local backtests and paper logs.
python agents/researcher.py

# 2. List the queue and copy the proposal filename from the first column.
python agents/reviewer.py list

# 3. Evaluate the proposal using the latest local backtest metrics or a dry zero baseline.
python agents/evaluator.py proposals/<proposal-id>.json

# 4. Inspect the generated evaluation and list the queue again.
cat experiments/evaluations/<proposal-id>.json
python agents/reviewer.py list

# 5. Record an explicit human rejection, request for more data, or approval.
python agents/reviewer.py decide proposals/<proposal-id>.json request-more-data \
  --reviewer "Your Name" \
  --rationale "Collect a longer paper-log sample before reconsidering."

# 6. For an approved experiment only, create a stopped dry-run profile.
python agents/reviewer.py decide proposals/<proposal-id>.json approve \
  --reviewer "Your Name" \
  --rationale "Approved for isolated paper evaluation after reviewing the metrics." \
  --apply-experimental
```

The generated files are human-readable JSON: `proposals/<id>.json`, `experiments/evaluations/<id>.json`, `experiments/decisions/<id>.json`, and, only with `--apply-experimental`, `experiments/experimental-profiles/<id>.json`. The action trail is `experiments/agent-actions.jsonl`. A `request-more-data` decision is an explicit review outcome and never creates a profile.

## Dashboard review

Start the API and dashboard as described in [Dashboard Setup](dashboard.md), then open `http://localhost:23183/experiments`. The page lists proposal status, evaluation metrics, expandable proposal details, and the three review actions. The optional approval checkbox creates only a stopped `dry_run: true` experimental profile. The API accepts `POST /api/experiments/<proposal-id>/decision` and writes the same decision JSON plus an append-only `dashboard-review` action entry. Keep the API bound to localhost or a private network because this repository does not add a separate API authentication layer.

## Optional advisory AI

To call the existing advisory fallback chain, add `--use-ai` to the researcher command:

```bash
python agents/researcher.py --use-ai
```

Provider failure falls back to a local note. AI output is bounded, redacted context is used, and the response is stored only as proposal rationale. It is not a trade signal and cannot authorize execution.

## What evaluation means in the first version

Phase A uses a no-op dry candidate so the queue, schemas, baseline metric set, and review controls can be tested without silently changing strategy behavior. It compares expectancy, maximum drawdown, and number of trades. A future sandbox evaluator may run a limited backtest against a copied experimental profile, but it must retain the same human gate and must never write to production or live configuration.

## Human-review boundary

An approval means “this research artifact may be created for isolated stopped dry-run review.” It does not mean “start the bot,” “go live,” or “merge a strategy change.” The experimental profile is intentionally separate from `bot/config.paper.json` and `bot/config.live.json`.
