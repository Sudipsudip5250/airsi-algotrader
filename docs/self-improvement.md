# Self-improvement loop: Phase A and minimal Phase B

This is a deliberately small, file-based research loop. It can collect recent local backtest exports and paper-log tails, create one structured proposal, evaluate a dry candidate against a baseline, and record a human decision. It cannot place orders, modify the production strategy, modify the default paper profile, or modify the live profile. The React dashboard exposes the same artifacts at `/experiments` for inspection and human review.

## Free-first research

Routine researcher runs should **not** pass `--use-ai`. The default path is deterministic and costs nothing. When commentary is wanted:

```bash
python agents/researcher.py --use-ai
```

The existing `bot/ai_client.py` chain is used: **Ollama (if running) → Groq free → Hugging Face free → OpenRouter `:free` → plain text**. Paid models are skipped unless `AI_ALLOW_PAID=1`. Responses are cached under `experiments/cache/ai/` for 24 hours. Duplicate pending ideas are skipped unless `--force` is passed. Logs and stderr print `provider=` and `cost_class=`.

## First full loop

Run all commands from the repository root after installing the project dependencies:

```bash
# 1. Generate one proposal from local backtests and paper logs (no AI quota).
python agents/researcher.py

# 2. List the queue and copy the proposal filename from the first column.
python agents/reviewer.py list

# 3. Evaluate the proposal using the latest local backtest metrics or a dry zero baseline.
python agents/evaluator.py proposals/<proposal-id>.json

# 3b. Optional: limited Freqtrade backtest against a temporary experimental config.
#     Never writes bot/config.paper.json or bot/config.live.json.
python agents/evaluator.py proposals/<proposal-id>.json --run-backtest --days 30

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

The generated files are human-readable JSON: `proposals/<id>.json`, `experiments/evaluations/<id>.json`, `experiments/decisions/<id>.json`, and, only with `--apply-experimental`, `experiments/experimental-profiles/<id>.json`. The action trail is `experiments/agent-actions.jsonl`. A markdown queue is written to `experiments/QUEUE.md` by `reviewer.py list`. A `request-more-data` decision is an explicit review outcome and never creates a profile. Approve and reject are terminal; they cannot be overwritten. A `request-more-data` record may later be replaced by approve or reject after more evidence is reviewed.

## Operator review console

```bash
python scripts/serve_review.py
```

The console binds to port 8080 by default and never talks to an exchange. It can create a free/no-AI proposal, dry-evaluate it, and record a human decision. Optional demo seeding is off unless `AIRSI_REVIEW_SEED=1`. Optional AI from the console stays off unless `AIRSI_REVIEW_ALLOW_AI=1`.

## Dashboard review

Start the API and dashboard as described in [Dashboard Setup](dashboard.md), then open `http://localhost:23183/experiments`. The page lists proposal status, evaluation metrics, provider/cost class, expandable proposal details, and the three review actions. Filters cover pending, evaluated, and historical decisions. Terminal approve/reject records return HTTP 409 if overwritten. The optional approval checkbox creates only a stopped `dry_run: true` experimental profile. The API accepts `POST /api/experiments/<proposal-id>/decision` and writes the same decision JSON plus an append-only `dashboard-review` action entry. Keep the API bound to localhost or a private network because this repository does not add a separate API authentication layer.

## Optional advisory AI

To call the existing advisory fallback chain, add `--use-ai` to the researcher command. Provider failure falls back to a local note. AI output is bounded, redacted context is used, and the response is stored only as proposal rationale. It is not a trade signal and cannot authorize execution.

## What evaluation means

The default evaluator is a dry comparison of expectancy, maximum drawdown, and number of trades. A no-op candidate (no Freqtrade run) is marked `inconclusive` rather than “promising.” `--run-backtest` may run a limited Freqtrade backtest against a **temporary** experimental config copied from the paper template. Missing freqtrade, missing data, or a failed run is `not_run` and fail-closed. The evaluator never writes to production strategy or live configuration.

## Human-review boundary

An approval means “this research artifact may be created for isolated stopped dry-run review.” It does not mean “start the bot,” “go live,” or “merge a strategy change.” The experimental profile is intentionally separate from `bot/config.paper.json` and `bot/config.live.json`. Stake and wallet values on experimental profiles are clamped (`stake_amount` 1–100, `dry_run_wallet` 100–10_000, `max_open_trades` 1–10).
