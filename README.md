# AIRSI Trader

Educational crypto trading bot with AI commentary, Telegram alerts, and a React dashboard. Built on [Freqtrade](https://freqtrade.io).

---

## Quick Start

```bash
git clone https://github.com/sudipsudip5250/airsi-trader.git
cd airsi-trader
bash install.sh                  # one-click: installs everything
cp .env.example .env             # create your config file
source scripts/activate.sh       # activate Python environment
cd bot && pytest tests/ -v       # verify 14/14 tests pass
```

> That's it. You're ready. See [First Time Test](#first-time-test) for what to run next.

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| **Python** | 3.10+ | `python3 --version` |
| **Git** | any | `git --version` |
| **Node.js** (optional) | 18+ | `node --version` — needed only for the dashboard |

The `install.sh` script will check these and prompt you if anything is missing.  
**Windows?** Run `install.ps1` as Administrator instead.

---

## What This Bot Does

This bot connects to Binance (paper or live), analyzes market data using multiple indicators, and executes trades based on a strategy. It can optionally use AI to generate commentary on market conditions.

**How it works:**

```
Market Data (Binance) → Strategy (AIRSIStrategy) → Trade Decision
                                                     ↓
                              AI Commentary ← Telegram Alerts ← Trade Executed
```

**The AI fallback chain** (no key needed for the first one, but each next one needs its own key):
```
Groq (fastest) → OpenRouter (many models) → HuggingFace (free) → Ollama (local)
```
If one provider fails, the next is tried automatically.

---

## Step-by-Step Guide

### 1. Install Dependencies

```bash
bash install.sh
```

This will:
- Create a Python virtual environment (`venv/`)
- Install Python packages (freqtrade, pandas, etc.)
- Install Node.js packages for the dashboard
- Create the `scripts/activate.sh` helper

### 2. Configure API Keys

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in the keys you want to use.  
**Minimum to get started:** you can skip all keys and just run paper trading — it works with public Binance data.

| Key | Required for | How to get |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram alerts | [docs/api-keys.md](docs/api-keys.md) |
| `TELEGRAM_CHAT_ID` | Telegram alerts | [docs/api-keys.md](docs/api-keys.md) |
| `GROQ_API_KEY` | AI commentary (fastest) | [console.groq.com](https://console.groq.com) — free tier |
| `OPENROUTER_API_KEY` | AI fallback | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `HUGGINGFACE_API_KEY` | AI fallback | [hf.co/settings/tokens](https://hf.co/settings/tokens) |
| `EXCHANGE_API_KEY` | Live trading only | Binance API dashboard |

### 3. Activate Environment

```bash
source scripts/activate.sh
```

Do this every time you open a new terminal. You should see `(venv)` appear in your prompt.

### 4. Verify Setup

```bash
cd bot && python3 -m pytest tests/ -v
```

All 14 tests should pass. If they don't, check [troubleshooting](#troubleshooting).

---

## First Time Test

After setup, run through this flow to make sure everything works:

```bash
# 1. Activate (if not already)
source scripts/activate.sh

# 2. Download 30 days of market data
python3 scripts/download_data.py --days 30

# 3. Run a backtest to see how the strategy performs
python3 scripts/run_backtest.py --days 30

# 4. Start paper trading (play money: $1000)
freqtrade trade --config bot/config.paper.json --strategy AIRSIStrategy
```

**Paper trading** simulates real trades with virtual money. The bot:
- Connects to Binance for live price data
- Evaluates the strategy on every new candle
- Logs virtual trades to `tradesv3.dryrun.sqlite`
- Starts a REST API at `http://localhost:8080`

Press `Ctrl+C` to stop.

---

## Common Commands

| Action | Command |
|---|---|
| Activate environment | `source scripts/activate.sh` |
| Run tests | `cd bot && pytest tests/ -v` |
| Download data | `python3 scripts/download_data.py --days 180` |
| Run backtest | `python3 scripts/run_backtest.py --days 180` |
| Start paper trading | `freqtrade trade --config bot/config.paper.json --strategy AIRSIStrategy` |
| Start live trading | `freqtrade trade --config bot/config.live.json --strategy AIRSIStrategy` |
| Check running bot | `tail -f user_data/logs/freqtrade.log` |
| View trade history | `freqtrade trade --db-url sqlite:///tradesv3.dryrun.sqlite` |

---

## Docs

| Topic | Link |
|---|---|
| Full setup walkthrough | [docs/quickstart.md](docs/quickstart.md) |
| API keys explained | [docs/api-keys.md](docs/api-keys.md) |
| Backtest → paper trade → live | [docs/testing.md](docs/testing.md) |
| Strategy logic (entry/exit rules) | [docs/strategy.md](docs/strategy.md) |
| Run AI locally with Ollama | [docs/local-ai-setup.md](docs/local-ai-setup.md) |
| Start the React dashboard | [docs/dashboard.md](docs/dashboard.md) |

---

## Project Structure

```
airsi-trader/
├── bot/                         # Core trading bot
│   ├── strategies/              # Trading strategy (AIRSIStrategy)
│   ├── ai_client.py             # AI commentary engine
│   ├── telegram_notifier.py     # Telegram alert sender
│   ├── config.paper.json        # Paper trading config
│   ├── config.live.json         # Live trading config
│   └── tests/                   # Unit tests (14 tests)
├── scripts/                     # Helper scripts
│   ├── activate.sh              # Activate venv with nix fix
│   ├── download_data.py         # Download historical data
│   ├── run_backtest.py          # Run backtest + summary
│   └── setup_ollama.sh          # Install Ollama locally
├── docs/                        # Detailed documentation
├── artifacts/                   # Web UI
│   ├── api-server/              # Express API proxy
│   └── dashboard/               # React dashboard
├── lib/                         # Shared TypeScript libraries
├── docker/                      # Dockerfiles
├── install.sh                   # Linux/macOS installer
├── install.ps1                  # Windows installer
└── docker-compose.yml           # Docker orchestration
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `command not found: python3` | Install Python 3.10+ from [python.org](https://python.org) |
| `pip install` fails | Make sure `venv/` is activated (see step 3) |
| `No module named freqtrade` | Run `pip install -r bot/requirements.txt` |
| Telegram errors at startup | Leave `TELEGRAM_BOT_TOKEN` empty — bot runs without it |
| Backtest shows 0 trades | The strategy conditions are strict. Tune `rsi_oversold` and `ema_period` in `AIRSIStrategy.py` |
| `user_data` not found | Run `freqtrade create-userdir` |
| Need help | Open an issue on GitHub |

---

## ⚠️ Disclaimer

**This project is for educational purposes only.**

Cryptocurrency trading carries significant financial risk. You may lose all capital invested. This software is provided "as is" without warranty of any kind. Past performance does not guarantee future results. The authors assume no liability for any losses incurred.

- Never trade with money you cannot afford to lose
- Start with paper trading (`bot/config.paper.json`)
- Test thoroughly before considering live trading
- Use at your own risk

---

## License

MIT — see [LICENSE](LICENSE).
