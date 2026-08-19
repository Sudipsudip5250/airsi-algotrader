# AIRSI AlgoTrader architecture

## Product decision

AIRSI AlgoTrader is the single unified trading project. The original research variants contributed compatible trading concepts, but they should not remain as independent bots. A single Freqtrade process, one strategy class, one set of configurations, one dashboard API, and one operational risk boundary are easier to test and safer to operate.

The unified strategy is `AIRSIAlgoStrategy`. Its production default uses a strict bullish trend-pullback branch; the range mean-reversion branch remains implemented behind `range_mean_reversion_enabled = False` for isolated research only. The strategy does not call AI providers, read mutable safety files, or make exchange/API calls while calculating candles.

## Runtime boundary

```text
Market data → AIRSIAlgoStrategy → Freqtrade protections → Exchange
                         │
                         ├─ Dashboard API → React dashboard
                         ├─ Telegram notifications
                         ├─ Advisory AI commentary
                         └─ Trading memory SQLite store (advisory veto only)

Optional gcode-harness integration → read-only dashboard telemetry
```

AIRSI AlgoTrader owns execution, strategy signals, Freqtrade protections, exchange configuration, dashboard data, and operator notifications. AI is a commentary service. The gcode-harness project, if connected, remains a separate agent and research client that can read telemetry and summarize results but cannot place, cancel, or modify trades.

## Strategy branches

| Branch | When it activates | Why it exists |
|---|---|---|
| `bullish_trend_pullback` | EMA9 > EMA21 > EMA50, EMA50/EMA200 spread above 0.5%, rising RSI pullback, sufficient volume | Production branch selected by the robustness review |
| `range_mean_reversion` | EMA50/EMA200 spread is near flat, RSI is oversold, price is near the lower Bollinger Band, sufficient volume | Research-only branch; disabled by default because it reduced expectancy in the tested sample |
| No entry | Bearish trend or incomplete warm-up data | Prevents long entries against sustained weakness |

## Services

| Service | Responsibility | Trade authority |
|---|---|---|
| Freqtrade | Market data, orders, trade lifecycle, protections, persistence | Yes, within configured safeguards |
| `AIRSIAlgoStrategy` | Deterministic indicators and entry/exit signals | Signals only |
| Market intelligence worker | Public market/news collection, structured risk classification, and intelligence incidents | No; writes a short-lived veto snapshot and durable context event |
| `trading_memory.py` | Restart-safe event history, trade-outcome reconciliation, similar-context lessons | No; only an evidence-gated entry veto |
| `ai_client.py` | Optional commentary through provider fallback; never a trade gate | No |
| Telegram notifier | Operator alerts and summaries | No |
| Express API | Authenticated proxy to Freqtrade telemetry | No direct exchange access |
| React dashboard | Status, positions, trades, performance, logs | No direct exchange access |
| Docker Compose | Local paper stack, intelligence worker, and optional Ollama service | No |

The intelligence worker is deliberately isolated from exchange credentials and the Freqtrade control API. Its output can only veto new live/dry-run entries; it cannot select pairs, change stake size, set leverage, or close positions. The memory store is local SQLite with WAL mode and idempotent event keys. It records environmental snapshots and realized outcomes but cannot rewrite strategy parameters. A memory veto requires a minimum sample count plus both poor expectancy and poor win rate for the exact pair/regime/signal context.

## Safety requirements

Paper mode remains the default. Production deployments must reject sample secrets, restrict CORS, keep the dashboard and Freqtrade API private or authenticated, and use exchange keys with trading permission only and withdrawals disabled. Live trading must be preceded by unit tests, realistic backtests, out-of-sample validation, and a sustained paper-trading period.

The former FinBERT/sample-headline implementation is not part of the unified strategy because repeated sample headlines are not timestamped market data and model loading inside `populate_indicators` is operationally expensive. The new `market_intelligence.py` worker provides the timestamped data contract. Missing market data or a stale/malformed snapshot fails closed; optional news-feed or LLM failures fall back to the deterministic market-risk rules and are recorded in the snapshot errors.
