# Unified Trading Architecture

## Decision

AIRSI-Trader is the canonical execution platform. Algo-Trader-Explorer contributes reusable ideas and optional AI integrations, while gcode-harness remains an external orchestration and analysis client.

The repositories are related at the **domain level**, but they are not one codebase. AIRSI and Algo both use Freqtrade and Python strategy modules, so those two should converge. gcode-harness is a large Rust agent runtime with TUI, sessions, providers, memory, and MCP support; it should not be compiled into the trading bot.

## Runtime boundaries

```text
                    read-only telemetry
 gcode-harness ───────────────────────────────────┐
      │                                           │
      │ optional prompts / analysis               ▼
      └──────────────► AIRSI dashboard API ──► Freqtrade
                         │                         │
                         │                         ├─ paper/live config
                         │                         ├─ AIRSIStrategy
                         │                         └─ exchange adapter
                         │
                         └─ React dashboard / Telegram
```

The gcode bridge is intentionally **read-only**. It can retrieve status, profit, performance, trades, balances, and sanitized configuration. It must not gain force-entry, force-exit, cancel-order, or configuration-write capabilities until a separate authenticated approval workflow exists.

## What was consolidated

The canonical strategy now combines AIRSI's RSI/Bollinger mean-reversion logic with the EMA trend protection expected by the shared test contract and inspired by Algo-Trader-Explorer. It exposes `ema50` and `ema200`, initializes signal columns deterministically, and keeps the strategy hook free of side effects so backtests remain reproducible.

AIRSI's AI client now implements the fallback chain advertised in its environment template: Groq, OpenRouter, Hugging Face, and local Ollama. These providers are advisory-only and are never consulted to decide whether a trade may execute.

## What remains separate

Algo-Trader-Explorer's FinBERT pipeline is not placed directly inside the candle loop. Loading a transformer model during `populate_indicators` is expensive and its current strategy uses sample headlines rather than time-aligned news, which risks stale or non-causal signals. If news sentiment is added later, it should be refreshed by a scheduled worker and stored with a timestamp, source, symbol, and confidence before the strategy consumes it.

gcode-harness remains a general-purpose agent platform. It can orchestrate research, summarize telemetry, run backtests, and explain incidents through its wrapper/MCP surfaces, but it should not own exchange credentials or directly mutate Freqtrade state.

## Operational sequence

1. Run AIRSI in paper mode with `bot/config.paper.json`.
2. Run unit tests, backtests, and at least a multi-day paper-trading soak test.
3. Expose the dashboard API only on a private network or through an authenticated reverse proxy.
4. Give gcode-harness only the read-only adapter URL.
5. Keep exchange keys trade-only, disable withdrawals, and keep live configuration separate from paper configuration.
6. Promote to live trading only after reviewing the backtest assumptions, slippage, fees, and failure behavior.
