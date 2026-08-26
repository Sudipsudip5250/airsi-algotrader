# Contributing to AIRSI AlgoTrader

Thank you for helping improve this education and research project. Contributions should improve reproducibility, testing, observability, documentation, or paper-trading safety. They must not present the project as financial advice or promise returns.

## Before opening a pull request

Run the same checks used by GitHub Actions:

```bash
bash -n install.sh scripts/*.sh docker/freqtrade-entrypoint.sh
python -m compileall -q bot scripts
python -m pytest bot/tests/ -q
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
bash scripts/check_repo_policy.sh
```

Keep changes focused and explain the user-visible behavior, test coverage, and operational tradeoffs. Update the relevant documentation whenever configuration, safety defaults, or API contracts change. Regenerate the TypeScript clients from `lib/api-spec/openapi.yaml` rather than hand-editing generated output.

## Trading and intelligence boundaries

Do not add network requests, LLM inference, mutable filesystem gates, exchange writes, or autonomous strategy mutation to Freqtrade strategy callbacks. Market intelligence and AI must remain advisory and fail closed. No contribution may allow AI or external data to place, cancel, size, leverage, or close a trade without a separately reviewed design and explicit human approval.

Paper trading is the default. Live trading changes require an explicit safety review, a test update, and documentation of the manual approval step. Do not commit real credentials or sample values that could be mistaken for working secrets.

## Workflow and dependency safety

Do not use `pull_request_target` or `workflow_run` to execute untrusted pull-request code. Do not add self-hosted runners, broad `GITHUB_TOKEN` permissions, workflow secrets, automatic exchange deployment, or unpinned third-party Actions. Keep GitHub Actions pinned to full commit SHAs and use GitHub-hosted runners for public pull requests.

By submitting a contribution, you agree that it is provided under the repository’s MIT License and that your contribution is intended for this education and research project.
