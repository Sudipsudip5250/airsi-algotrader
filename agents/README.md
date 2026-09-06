# Self-improvement agents

This package implements a small offline research loop: collect local evidence, create one versioned experiment proposal, evaluate it against a baseline, and wait for a human decision. The agents have no exchange client, no order API, and no permission to modify the production strategy.

The researcher is deterministic by default. `--use-ai` may call the existing advisory AI fallback chain (Ollama → Groq → Hugging Face → OpenRouter `:free` → plain text). Paid models require `AI_ALLOW_PAID=1`. Prompts are bounded and contain only redacted local context. Duplicate pending ideas are skipped. AI text is stored as rationale, never treated as a signal.

Use the repository root commands documented in `docs/self-improvement.md`. Every action is appended to `experiments/agent-actions.jsonl`. `python agents/reviewer.py list` also writes `experiments/QUEUE.md`. `python scripts/serve_review.py` exposes the same queue in a local browser console. Approve/reject decisions are terminal.
