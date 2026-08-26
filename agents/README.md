# Self-improvement agents

This package implements a small offline research loop: collect local evidence, create one versioned experiment proposal, evaluate it against a baseline, and wait for a human decision. The agents have no exchange client, no order API, and no permission to modify the production strategy.

The researcher can optionally call the existing advisory AI fallback chain with `--use-ai`. The prompt is bounded and contains only redacted local context. AI text is stored as rationale, never treated as a signal.

Use the repository root commands documented in `docs/self-improvement.md`. Every action is appended to `experiments/agent-actions.jsonl`.
