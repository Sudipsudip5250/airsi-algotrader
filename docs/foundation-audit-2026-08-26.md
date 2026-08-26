# AIRSI AlgoTrader Foundation Audit

**Date:** 26 August 2026
**Repository:** `Sudipsudip5250/airsi-algotrader`
**Scope:** Foundation hardening only; the future self-improving agent system was deliberately not implemented.

## Executive summary

The repository had a coherent safety-first architecture, but several implementation details were inconsistent with that architecture. The most important issues were an incomplete generated API client, permissive and unvalidated Express proxy inputs, raw Freqtrade configuration exposure, a dashboard that depended on `any` casts and lacked request-error states, an intelligence gate that accepted only a partial snapshot in tests and did not strictly validate its schema, a downloader that wrote relative to the caller’s working directory and always reported success, Docker Compose that did not pass the credentials required by its own template renderer, paper profiles that required optional Telegram credentials, and a live profile that started immediately when invoked.

The foundation is now internally consistent. The strategy remains deterministic and side-effect free. AI remains advisory-only. The market-intelligence worker and strategy gate fail closed for missing, malformed, stale, or timezone-naive snapshots. The Express API is read-only, validates limits, sanitizes configuration responses, and restricts CORS to an explicit allowlist. The dashboard consumes generated types, includes the intelligence state, and surfaces API failures instead of silently rendering empty values. Paper trading remains the default; live trading is explicit and the live profile starts stopped.

> **Important:** This pass improves correctness and operational safety; it does not establish profitability, guarantee exchange availability, or replace independent paper-trading and out-of-sample review.

## Prioritized findings and fixes

| Priority | Finding before the pass | Resolution |
|---|---|---|
| Critical | The live profile used `initial_state: "running"`, so the explicit live launcher could start trading immediately. | Changed the live profile to `initial_state: "stopped"` and documented the separate checklist/start action. |
| Critical | The strategy accepted a minimal JSON object as a valid intelligence snapshot, and the API returned any parseable JSON without checking expiry or schema. | Added strict required-field, type, risk-level, numeric-range, timezone, and expiry validation in both the strategy and API proxy. |
| Critical | Docker Compose did not pass `FREQTRADE_API_USER`, `FREQTRADE_API_PASS`, or `FREQTRADE_JWT_SECRET` to the Freqtrade container, even though the renderer requires them. | Added required environment interpolation and kept exchange keys optional for paper mode. |
| High | `/bot/trades` and `/bot/logs` forwarded arbitrary query strings; `/bot/config` exposed raw `show_config` output. | Added bounded integer parsing (`1`–`200`), upstream timeouts, retry-on-expired-token, and a fixed sanitized configuration response. |
| High | The generated React and Zod clients did not contain `/bot/intelligence`, despite the OpenAPI specification and route already defining it. | Tightened the OpenAPI schema and regenerated both clients. |
| High | Paper profiles enabled Telegram while `.env.example` left Telegram credentials empty, making optional notifications capable of blocking paper startup. | Disabled Telegram in paper profiles by default; live configuration still requires its credentials. |
| High | The downloader used `~/user_data` while writing data to `bot/user_data/data`, and returned success after failed timeframe downloads. | Resolved paths from the repository root, validated `--days`, and returned a nonzero status if any timeframe failed. |
| Medium | The dashboard used `any` casts and omitted error states on the Trades, Performance, Logs, and Dashboard views. | Replaced casts with generated `OpenTrade`, `ClosedTrade`, `PairPerformance`, and `LogLine` types; added shared query error/empty states. |
| Medium | AI fallback was safe for provider implementations that caught their own errors but not for a provider object that raised unexpectedly. | Wrapped each provider invocation, bounded token counts, and added exception/empty-prompt tests. |
| Medium | The RSS worker treated one feed failure as a failure of all optional RSS collection. | Isolated per-feed request/XML errors and logged them while continuing with other feeds. |
| Low | Documentation and setup scripts still referred to Python 3.10+/Node 18+, and `SESSION_SECRET` was documented although unused. | Updated runtime requirements, removed the unused variable, pinned the package manager, and reconciled README, agent guidance, quick-start, dashboard, API-key, and live-testing docs. |

## Concrete code changes

The following table is the complete before/after map for every changed file. Generated files were regenerated from `lib/api-spec/openapi.yaml`; they were not hand-edited.

| File | Before | After |
|---|---|---|
| `.agents/airsi-algotrader.md` | Agent commands used `python3`; runtime guidance said Node 18+. | Commands use the activated environment and guidance now says Node 20+. |
| `.env.example` | Missing `GROQ_MODEL`, OpenRouter metadata, and `CORS_ORIGINS`; included unused `SESSION_SECRET`. | Documents all consumed AI/API variables and removes the unused secret. |
| `README.md` | Described general safety but not stopped live state, sanitized read-only proxy behavior, or Docker credential requirements. | Documents explicit live opt-in, proxy hardening, and required Compose credentials. |
| `docs/api-keys.md` | Listed unused `SESSION_SECRET`. | Lists only variables consumed by the project. |
| `docs/dashboard.md` | Said Node 18+ and did not explain proxy validation/sanitization. | Requires Node 20+ and explains read-only proxy behavior and unavailable intelligence. |
| `docs/quickstart.md` | Said Python 3.10+/Node 18+; implied Telegram was an optional setting without explaining that paper profiles enabled it. | Uses Python 3.11+/Node 20+, explains disabled-by-default paper Telegram, renderer requirements, and fail-closed intelligence. |
| `docs/testing.md` | Live checklist did not mention the live profile’s startup state. | Requires confirmation that live starts stopped and is explicitly started only after review. |
| `install.sh` | Accepted any installed Python 3 and used non-reproducible `pnpm install`. | Checks Python 3.11+, uses `python -m pip`, and uses `pnpm install --frozen-lockfile`. |
| `install.ps1` | Accepted any Python version, used bare `pip`, and used an unlocked pnpm install. | Checks Python 3.11+, uses `python -m pip`, and uses a frozen pnpm install. |
| `package.json` | Did not pin the package-manager version. | Pins `pnpm@11.24.0`. |
| `pnpm-workspace.yaml` | Did not explicitly allow the required esbuild build. | Adds `allowBuilds.esbuild: true` while retaining the existing supply-chain policy. |
| `.github/workflows/ci.yml` | Only installed Python dependencies and ran Python tests. | Adds Python compilation, a separate Node/pnpm job, full workspace typechecks, and production builds. |
| `bot/strategies/AIRSIAlgoStrategy.py` | Coerced no input types, used a less explicit RSI edge-case implementation, and accepted partial intelligence JSON. | Validates OHLCV columns, handles numeric inputs, bounds RSI including flat markets, and strictly validates snapshots before allowing entries. No network, LLM, or exchange side effects were added. |
| `bot/market_intelligence.py` | Missing core values could silently produce a permissive normal-risk result; TTL parsing could abort; source count was imprecise; RSS failures were not isolated. | Missing core inputs produce a high-risk veto, TTL is bounded, risk classification cannot downgrade deterministic risk, source counts use distinct sources, RSS failures are isolated, and snapshots are validated. |
| `bot/ai_client.py` | A provider object that raised outside its own client could break the chain. | Each provider call is isolated and token counts/prompts are bounded and validated. |
| `bot/telegram_notifier.py` | Credentials were captured at import time; messages could exceed Telegram limits or fail on Markdown formatting. | Credentials are read at send time, messages are bounded, and a 400 Markdown failure retries as plain text. |
| `bot/config.paper.json` | Telegram was enabled with empty-required placeholders. | Telegram is disabled and credentials are empty by default; paper remains `dry_run: true`. |
| `bot/config.paper.kraken.json` | Same optional Telegram startup issue. | Same safe paper default as the Binance profile. |
| `bot/config.paper.okx.json` | Same optional Telegram startup issue. | Same safe paper default as the Binance profile. |
| `bot/config.live.json` | Live profile started with `initial_state: "running"`. | Live profile starts `stopped`; `dry_run` remains `false` and keys remain environment-injected. |
| `bot/requirements.txt` | All dependencies used broad lower bounds. | Dependencies are pinned to the validated environment versions, including Freqtrade 2026.7, pandas 3.0.5, NumPy 2.5.2, and the test/tooling versions used for this pass. |
| `bot/tests/test_ai_client.py` | Covered `None` provider responses only. | Adds provider-exception and empty-prompt coverage. |
| `bot/tests/test_market_intelligence.py` | Did not cover missing core market data or timezone-naive timestamps. | Adds fail-closed coverage for both cases. |
| `bot/tests/test_strategy.py` | Used a partial intelligence snapshot as an allow-case. | Uses the complete snapshot contract, matching production validation. |
| `scripts/download_data.py` | Used a caller-dependent `~/user_data` path and always returned success. | Uses repository-local absolute paths, validates days, continues all timeframes, and returns failure if any download fails. |
| `scripts/render_config.py` | Substituted placeholders and checked only missing variables. | Rejects sample/placeholder credentials, validates template and rendered JSON, and writes a mode-600 file. |
| `scripts/run_bot.sh` | Relied on whichever `python3` and `freqtrade` were first on `PATH`. | Prefers the repository venv, verifies Python/Freqtrade availability, and renders before launch. |
| `scripts/run_intelligence.sh` | Used bare `python3` and passed unvalidated polling values. | Prefers the repository venv and requires a polling interval of at least 60 seconds. |
| `docker-compose.yml` | Published services on all interfaces and omitted required Freqtrade renderer credentials. | Binds published ports to localhost and passes required API/JWT variables plus optional paper credentials. |
| `artifacts/api-server/src/app.ts` | Allowed all CORS origins and had no JSON request limit or final error responses. | Uses an explicit `CORS_ORIGINS` allowlist, credentials support, 32 KB request limits, 404 JSON responses, and redacted logged 500 responses. |
| `artifacts/api-server/src/routes/bot.ts` | Had raw limits, no upstream timeouts, no token refresh, raw config forwarding, and unvalidated intelligence JSON. | Adds bounded limits, timeouts, token refresh, fixed read-only routes, sanitized config, and strict intelligence validation. No order-control route is exposed. |
| `lib/api-spec/openapi.yaml` | Intelligence was missing from generated clients and its decision fields were partly optional/unconstrained. | Uses the strict required decision contract and risk enum; clients were regenerated. |
| `lib/api-client-react/src/generated/api.ts` | Had no intelligence function/hook. | Adds `botIntelligence` and `useBotIntelligence`. |
| `lib/api-client-react/src/generated/api.schemas.ts` | Had no intelligence types. | Adds `MarketIntelligence` and strict decision types. |
| `lib/api-zod/src/generated/api.ts` | Had no generated intelligence schemas. | Adds the intelligence response schema and query schemas. |
| `lib/api-zod/src/generated/types/index.ts` | Did not export intelligence types. | Exports the generated intelligence types. |
| `lib/api-zod/src/generated/types/marketIntelligence.ts` | Did not exist. | Adds the generated response type. |
| `lib/api-zod/src/generated/types/marketIntelligenceDecision.ts` | Did not exist. | Adds the generated decision type. |
| `artifacts/dashboard/src/components/QueryState.tsx` | No shared error/empty-state component existed. | Adds typed shared query error and empty states. |
| `artifacts/dashboard/src/pages/Dashboard.tsx` | Used `any`, could render an object-valued exchange, and omitted most query errors. | Uses generated types, displays intelligence risk/expiry, and surfaces telemetry failures. |
| `artifacts/dashboard/src/pages/Trades.tsx` | Used `any` for the response and rows and did not display errors. | Uses `ClosedTrade`, validates duration output, and shows API errors. |
| `artifacts/dashboard/src/pages/Performance.tsx` | Used `any` and had loading/empty states only. | Uses `PairPerformance`, typed chart payloads, and shows API errors. |
| `artifacts/dashboard/src/pages/Logs.tsx` | Duplicated `LogEntry`, had dead `levelColors`, and had no error state. | Uses generated `LogLine`, removes dead code, validates timestamps, and shows errors. |

## Tests and validation

The final local verification passed with the following results:

| Check | Result |
|---|---|
| Python module compilation | Passed with `python -m compileall -q bot scripts`. |
| Python dependency consistency | Passed with `python -m pip check`. |
| Python unit tests | **17 passed** with `python -m pytest bot/tests/ -q`. |
| Shell syntax | Passed with `bash -n install.sh scripts/*.sh docker/freqtrade-entrypoint.sh`. |
| Freqtrade template JSON parsing | All `bot/config*.json` templates parsed successfully. |
| Paper config rendering | Passed with test credentials; `dry_run` remained true and Telegram remained disabled. |
| Live config rendering without exchange/Telegram credentials | Correctly rejected missing credentials. |
| Frozen pnpm install | Passed with `pnpm install --frozen-lockfile`. |
| Workspace typecheck | Passed for libraries, API server, dashboard, and scripts. |
| Production build | Passed for the API server and dashboard via `pnpm run build`. |
| API smoke test | Health returned 200; invalid limit returned 400; offline bot returned 503 with a safe empty status; missing intelligence returned `available: false`. |
| Diff hygiene | Passed `git diff --check`; no tracked secret pattern was found. |
| Docker Compose runtime validation | Not executed because Docker is unavailable in the sandbox; the Compose file was reviewed and its interpolation changes were tested conceptually with non-secret values. |

The Vite build still prints a non-failing warning about a JavaScript chunk larger than 500 KB. It is a performance optimization opportunity, not a correctness failure, and was left outside this minimal foundation pass.

## Before versus after

| Area | Before | After |
|---|---|---|
| Trading strategy | Deterministic by design but permissive around malformed intelligence snapshots and less explicit around indicator inputs. | Deterministic, input-checked, bounded, and fail-closed for all external snapshot paths. |
| AI | Advisory fallback chain with broad provider catches. | Advisory fallback chain with per-provider isolation and regression coverage; it still cannot authorize or size trades. |
| Intelligence worker | Optional provider failures could interfere with RSS collection; missing market values could look normal. | Core-data absence is high-risk veto; optional feed failures are isolated; deterministic risk cannot be downgraded by the model. |
| API | Broad CORS, raw configuration forwarding, unbounded query values, and stale generated clients. | Explicit CORS, read-only routes, sanitized config, bounded limits, timeouts, token refresh, and regenerated clients. |
| Dashboard | `any` casts and silent empty states. | Generated types, shared error states, typed chart/log/trade rows, and visible intelligence status. |
| Operations | Docker credentials did not match renderer requirements; downloader path depended on current directory; live started running. | Compose wiring matches renderer, tools resolve from repository root, paper is safe by default, and live starts stopped. |
| Documentation | Several runtime and setup statements drifted from code. | README, `.agents`, setup guides, dashboard docs, API-key docs, and live checklist reflect the implementation. |

## Future self-improving phase: deliberately deferred

The following items should remain outside this foundation pass: autonomous strategy mutation, automatic parameter optimization, model-driven trade decisions, model-driven sizing or leverage, automatic exchange actions, online learning inside Freqtrade callbacks, remote agent execution, and any self-modifying deployment path. If later work introduces continuous improvement, it should remain offline or shadow-mode first, use versioned artifacts and reproducible datasets, require explicit human approval before promotion, and preserve the current hard boundary that AI and market intelligence cannot place, cancel, size, or close trades.

## Final checklist

| Item | Status |
|---|---|
| Single production strategy preserved | Solid. |
| No network/LLM/exchange writes inside strategy callbacks | Solid by code review and unchanged architecture. |
| Missing/stale/malformed intelligence fails closed | Solid and covered by tests. |
| AI remains advisory-only | Solid and covered by fallback tests. |
| Paper mode remains the default | Solid across all paper profiles. |
| Live mode is opt-in and starts stopped | Solid in the live profile and documentation. |
| API exposes only read-only telemetry routes | Solid in the dashboard proxy. |
| Generated OpenAPI/Zod/React clients agree with the spec | Solid after regeneration and typecheck. |
| Python tests | 17 passed. |
| TypeScript typecheck/build | Passed. |
| Docker Compose actual runtime | Pending a Docker-capable environment. |
| Full paper-trading session, backtest, and exchange behavior | Must be performed by the operator before any live use. |

## References

[1]: https://www.freqtrade.io/en/stable/rest-api/ "Freqtrade REST API documentation"
