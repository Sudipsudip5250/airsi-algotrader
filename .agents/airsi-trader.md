# AIRSI Trader — AI Agent Context

## Project Overview
Educational micro-budget automated crypto trading bot.
Built with Freqtrade (Python), AI providers (Groq → OpenRouter → HuggingFace → Ollama), Telegram alerts, and a React dashboard.

## Tech Stack
- **Trading**: Freqtrade (Python), strategy RSI + EMA + Bollinger Bands
- **AI**: Groq (free cloud) → OpenRouter → HuggingFace → Ollama (local fallback)
- **Notifications**: Telegram Bot API
- **Backend**: Node.js + Express (proxies Freqtrade REST API)
- **Frontend**: React 19 + Vite + Recharts + Tailwind
- **Build**: pnpm workspaces, TypeScript 5.9, esbuild

## Project Structure
```
airsi-trader/
├── bot/                          # Python trading bot
│   ├── strategies/               # Freqtrade strategies
│   │   └── AIRSIStrategy.py      # RSI + EMA + BB strategy
│   ├── ai_client.py              # AI integration (multi-provider fallback)
│   ├── telegram_notifier.py      # Telegram push notifications
│   ├── config.paper.json         # Paper trading config
│   ├── config.live.json          # Live trading config
│   └── tests/                    # Pytest unit tests
├── artifacts/
│   ├── api-server/               # Express API (proxies Freqtrade)
│   └── dashboard/                # React dashboard
├── scripts/
│   ├── download_data.py          # Download historical data
│   ├── run_backtest.py           # Run backtest + Go/No-Go
│   └── setup_ollama.sh           # Install Ollama
├── docs/                         # Documentation
│   ├── api-keys.md               # How to get API keys
│   ├── quickstart.md             # Commands reference
│   ├── testing.md                # 4-phase testing pipeline
│   ├── local-ai-setup.md         # Ollama on VPS
│   ├── dashboard.md              # Dashboard & Docker
│   └── strategy.md               # Strategy details
├── scripts/activate.sh            # Venv activation (nix fix)
├── install.sh                    # Linux/macOS installer
├── install.ps1                   # Windows installer
├── docker-compose.yml            # Docker setup
└── .env.example                  # Environment template
```

## Key Commands (for AI to reference)

### Setup
```bash
bash install.sh                          # First-time setup
cp .env.example .env                     # Create env file
source venv/bin/activate                 # Activate Python
```

### Testing Pipeline
```bash
cd bot && python3 -m pytest tests/ -v   # Unit tests
python3 scripts/download_data.py         # Download data
python3 scripts/run_backtest.py          # Backtest
freqtrade trade --config bot/config.paper.json --strategy AIRSIStrategy  # Paper trade
```

### AI Provider Fallback Chain
The bot tries providers in order: Groq → OpenRouter → HuggingFace → Ollama → plain text.
Define keys in `.env` (see `docs/api-keys.md`).

## Strategy Entry/Exit Conditions
- **Entry**: RSI < 35 AND close > EMA50 AND close ≤ BB lower AND volume > average
- **Exit**: RSI > 68 AND close ≥ BB upper (or ROI/stoploss)
- **Risk**: 3.5% stoploss, trailing stop, max 2 open trades, $50 per trade

## Environment Notes
- Python 3.11+ required, Node.js 18+
- On Replit: use `scripts/activate.sh` instead of `venv/bin/activate` (sets LD_LIBRARY_PATH)
- `.env` is git-ignored — never commit real keys
- Freqtrade user_data goes in `~/user_data/`
