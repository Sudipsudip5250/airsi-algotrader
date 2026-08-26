# AIRSI AlgoTrader

A unified educational crypto trading platform built on [Freqtrade](https://freqtrade.io), with a deterministic regime-aware strategy, paper/live configuration profiles, optional AI commentary, Telegram alerts, and a React dashboard.

> **Important:** This project is educational software. Cryptocurrency trading carries significant risk. Start with paper trading, validate with realistic fees and slippage, and never use money you cannot afford to lose.

## Product architecture

```text
Market data → AIRSIAlgoStrategy → Freqtrade risk controls → Paper/live exchange
                                      │
                                      ├─ Dashboard API → React dashboard
                                      ├─ Telegram notifications
                                      └─ Advisory AI commentary
```

AIRSI AlgoTrader is now one trading codebase. The original research variants contributed two useful ideas: RSI/Bollinger mean reversion and EMA trend-pullback logic. They are now combined inside one strategy that chooses the appropriate signal branch from the current market regime.

## Strategy

The only production strategy is `AIRSIAlgoStrategy` in `bot/strategies/AIRSIAlgoStrategy.py`. It uses a 1-hour timeframe and a 240-candle warm-up period. The production default uses strict bullish pullbacks; the range branch remains available only for isolated research.

| Regime | Entry branch | Purpose |
|---|---|---|
| Bullish trend | EMA9 > EMA21 > EMA50, EMA50/EMA200 spread > 0.5%, rising RSI pullback, volume above average | Participate only in selective controlled pullbacks |
| Range | Stable EMA50/EMA200 spread, oversold RSI, lower Bollinger Band, adequate volume | Research-only branch; disabled in production by default after weaker backtest results |
| Bearish trend | No long entry | Avoid averaging into sustained weakness |

The candle strategy itself remains deterministic and contains no network calls or LLM calls. A separate market-intelligence worker may veto new live/dry-run entries when deterministic market risk or structured news classification is elevated. It cannot place orders, choose pairs, set leverage, or increase position size. If its snapshot is missing or expired, the strategy fails closed.

## Quick start

```bash
# Install dependencies and create the Python environment
bash install.sh

# Create local configuration
cp .env.example .env
source scripts/activate.sh

# Run unit tests
cd bot && python3 -m pytest tests/ -v
cd ..

# Download historical data and run a backtest
python3 scripts/download_data.py --days 30
python3 scripts/run_backtest.py --days 30

# Terminal 1: refresh market/news intelligence
bash scripts/run_intelligence.sh

# Terminal 2: start paper trading with the unified strategy
bash scripts/run_bot.sh paper
```

The default paper profiles use `dry_run: true`, a virtual wallet, and environment-injected credentials. The live profile is `dry_run: false` but starts with `initial_state: "stopped"`; starting live trading is an explicit, separately reviewed action. Do not enable live trading until the test, backtest, and paper-trading stages have been reviewed.

## Configuration profiles

| Profile | Purpose | Default safety state |
|---|---|---|
| `bot/config.paper.json` | Binance paper trading | `dry_run: true` |
| `bot/config.paper.kraken.json` | Kraken paper trading | `dry_run: true` |
| `bot/config.paper.okx.json` | OKX paper trading | `dry_run: true` |
| `bot/config.live.json` | Explicit live deployment profile | `dry_run: false`; use only after independent review |

All profiles use `AIRSIAlgoStrategy`. Exchange keys are environment-injected; withdrawal permission must remain disabled.

## AI commentary

The optional fallback chain is **Groq → OpenRouter → Hugging Face → Ollama → plain text**. Provider failures do not stop the bot, and the strategy does not depend on a model response. AI output is commentary for operators, not a trading signal.

## Safety controls

The platform uses Freqtrade protections, a negative stoploss, ROI limits, a cooldown period, a stoploss guard, and a maximum-drawdown guard. The dashboard and Freqtrade API must be kept on a private network or behind an authenticated reverse proxy. The dashboard API only proxies read-only telemetry and validates its numeric limits and intelligence snapshot. Replace all sample credentials and secrets before any non-local deployment.

## Dashboard and services

The React dashboard is served through the Node.js/Express API proxy. The standard local endpoints are:

| Service | URL |
|---|---|
| Freqtrade API/UI | `http://localhost:8080` |
| AIRSI dashboard API | `http://localhost:5000` |
| Optional Ollama | `http://localhost:11434` |

Docker Compose starts the paper-trading stack after the required Freqtrade API credentials are supplied in `.env`. The optional Ollama service is enabled with the `local-ai` profile. The live compose path still requires an explicit `FREQTRADE_CONFIG_TEMPLATE` and the live profile starts stopped.

## Repository layout

```text
airsi-algotrader/
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

## Documentation

| Topic | File |
|---|---|
| Strategy and regime selection | `docs/strategy.md` |
| Setup | `docs/quickstart.md` |
| Testing stages | `docs/testing.md` |
| Dashboard | `docs/dashboard.md` |
| API keys | `docs/api-keys.md` |
| Local AI | `docs/local-ai-setup.md` |
| Unified architecture | `docs/unified-architecture.md` |
| Performance research and loss diagnosis | `docs/performance-research.md` |

## License

MIT. Use, modify, and audit responsibly.
