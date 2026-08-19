## Project Overview

AIRSI AlgoTrader is an educational crypto trading platform built on Freqtrade, optional AI commentary providers, Telegram alerts, a Node.js/Express API proxy, and a React dashboard.

## Core design rule

There is one production strategy: `AIRSIAlgoStrategy`. It combines a bullish trend-pullback branch with a range mean-reversion branch. Do not reintroduce separate competing bot runtimes or call external services from Freqtrade strategy methods.

## Tech stack

- **Trading:** Freqtrade and Python
- **Strategy:** `bot/strategies/AIRSIAlgoStrategy.py`
- **AI commentary:** Groq → OpenRouter → Hugging Face → Ollama → plain text
- **Notifications:** Telegram Bot API
- **Backend:** Node.js + Express proxy for the Freqtrade REST API
- **Frontend:** React + Vite + Recharts + Tailwind
- **Build:** pnpm workspaces, TypeScript, esbuild

## Project structure

```text
airsi-trader/
├── bot/
│   ├── strategies/AIRSIAlgoStrategy.py
│   ├── ai_client.py
│   ├── telegram_notifier.py
│   ├── config.paper*.json
│   ├── config.live.json
│   └── tests/
├── artifacts/
│   ├── api-server/
│   └── dashboard/
├── scripts/
├── docs/
├── docker/
├── install.sh
├── install.ps1
├── docker-compose.yml
└── .env.example
```

## Required workflow

```bash
bash install.sh
cp .env.example .env
source scripts/activate.sh
cd bot && python3 -m pytest tests/ -v
python3 scripts/download_data.py --days 30
python3 scripts/run_backtest.py --days 30 --strategy AIRSIAlgoStrategy
freqtrade trade --config bot/config.paper.json --strategy AIRSIAlgoStrategy
```

Run paper mode before any live mode. Use realistic fees, slippage, liquidity, and out-of-sample periods when assessing performance.

## Strategy behavior

The strategy uses EMA21, EMA50, EMA200, RSI14, Bollinger Bands, and volume ratio. In a bullish regime it looks for a rising RSI pullback near EMA21. In a range it looks for oversold RSI near the lower Bollinger Band. In a bearish regime it does not open long positions.

## Safety rules

Do not add network requests, LLM inference, mutable filesystem gates, or exchange writes to `populate_indicators`, `populate_entry_trend`, or `populate_exit_trend`. AI is advisory-only. Keep live exchange keys trade-only and withdrawal-disabled. Never expose Freqtrade or the dashboard API publicly without strong authentication and restricted CORS.

## Environment notes

Python 3.11+ and Node.js 18+ are expected. `.env` is git-ignored; never place real credentials in tracked files. Freqtrade data, logs, and databases belong under the configured `bot/` user-data volume.
