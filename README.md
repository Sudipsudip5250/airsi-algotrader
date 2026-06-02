# 🤖 AI Crypto Trading Bot

> **Educational micro-budget automated crypto trading bot.**  
> Built with Freqtrade, Groq AI (free), Ollama (local AI), Telegram alerts, and a live React dashboard.

---

## ⚡ Quick Start (Clone & Run)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Linux / macOS
bash install.sh

# Windows (PowerShell as Administrator)
.\install.ps1
```

---

## 📁 Repository Structure

```
.
├── bot/                        # Trading bot (Python / Freqtrade)
│   ├── strategies/
│   │   └── AIRSIStrategy.py    # RSI + EMA + Bollinger Bands strategy
│   ├── ai_client.py            # Groq + Ollama AI integration
│   ├── telegram_notifier.py    # Push notifications
│   ├── config.paper.json       # Paper trading config (SAFE — virtual money)
│   ├── config.live.json        # Live trading config (real money — use carefully)
│   ├── requirements.txt        # Python dependencies
│   └── tests/                  # Unit tests (pytest)
│       ├── conftest.py
│       └── test_strategy.py
│
├── artifacts/
│   ├── api-server/             # Express API (proxies Freqtrade REST API)
│   └── dashboard/              # React dashboard (trades, P&L, logs)
│
├── scripts/
│   ├── download_data.py        # Download 6 months of free historical data
│   ├── run_backtest.py         # Run backtest + print Go/No-Go summary
│   └── setup_ollama.sh         # Install Ollama + pull Mistral model
│
├── docker-compose.yml          # Run everything with one command
├── install.sh                  # Linux/macOS installer
├── install.ps1                 # Windows installer
├── .env.example                # Environment variables template
└── README.md                   # This file
```

---

## 🔧 Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| Trading framework | [Freqtrade](https://freqtrade.io) | Free / Open-source |
| AI (cloud) | [Groq API](https://console.groq.com) — LLaMA 3 8B | Free tier (14,400 req/day) |
| AI (local) | [Ollama](https://ollama.com) + Mistral 7B | Free, runs locally |
| Exchange | Binance (testnet for paper, live for real) | Free API |
| Notifications | Telegram Bot API | Free |
| Dashboard | React + Vite + Recharts | Free / Open-source |
| Backend API | Node.js + Express | Free / Open-source |
| Database | SQLite (built into Freqtrade) | Free |

---

## 🗝️ Configuration

```bash
cp .env.example .env
```

Edit `.env` with your keys:

| Variable | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Message `@BotFather` → `/newbot` |
| `TELEGRAM_CHAT_ID` | Open `https://api.telegram.org/bot<TOKEN>/getUpdates` |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free signup |
| `EXCHANGE_API_KEY` | Binance → API Management (leave blank for paper trading) |

---

## 🔬 4-Phase Testing Pipeline

### Phase 1 — Download Historical Data (Free)
```bash
source venv/bin/activate
python scripts/download_data.py --days 180 --pairs BTC/USDT ETH/USDT SOL/USDT
```
Downloads 6 months of 1h, 4h, and 1d candles from Binance's public API.

### Phase 2 — Backtest
```bash
python scripts/run_backtest.py
```
Runs the strategy against historical data and prints a **Go/No-Go** checklist:
- ✅ Max drawdown < 15%
- ✅ Win rate > 50%
- ✅ Total profit > 0
- ✅ Trade count ≥ 30 (statistical significance)

### Phase 3 — Unit Tests
```bash
cd bot && pytest tests/ -v
```
Tests include:
- RSI is always 0–100 ✓
- No buy signals in a downtrend (EMA filter) ✓
- No simultaneous buy + sell ✓
- Stoploss is set and not too aggressive ✓
- Bollinger Bands ordering (upper ≥ mid ≥ lower) ✓

### Phase 4 — Paper Trading (2+ weeks minimum)
```bash
freqtrade trade \
  --config bot/config.paper.json \
  --strategy AIRSIStrategy \
  --logfile bot/user_data/logs/bot.log
```
Virtual $1,000 USDT. Watch Telegram for all alerts. Only proceed to live trading after 2 consistent weeks.

---

## 📱 Telegram Commands

| Command | What it does |
|---|---|
| `/status` | Show open trades |
| `/profit` | Current profit/loss |
| `/balance` | Wallet balance |
| `/stop` | **Emergency stop** the bot |
| `/start` | Resume trading |
| `/trades` | Last 10 closed trades |

---

## 🛡️ Fail-Safes

| Risk | Protection |
|---|---|
| Network drop | Exponential backoff retry (5 attempts, up to 60s) |
| Exchange API down | Freqtrade waits and retries automatically |
| 3 consecutive losses | StoplossGuard pauses trading for 12 candles |
| Portfolio drops 8% | MaxDrawdown protection halts new entries |
| Bot crash | Global exception handler alerts you on Telegram |
| Runaway losses | Hard 3.5% stoploss per trade |

---

## 💰 Going Live (Micro-Investment)

> ⚠️ Only after Phase 4 passes. Start with $5–$10 maximum.

**Checklist before live trading:**
- [ ] 2+ weeks of paper trading with positive results
- [ ] Backtest Go/No-Go: all 4 checks pass
- [ ] Telegram alerts working (tested manually)
- [ ] Emergency `/stop` command tested
- [ ] Exchange API key created with **NO withdrawal permissions**
- [ ] `max_open_trades: 2` and `stake_amount: 5` in config.live.json

```bash
# Start live trading ($5 per trade, max 2 open = $10 total risk)
freqtrade trade \
  --config bot/config.live.json \
  --strategy AIRSIStrategy
```

**Fee minimization:**
- Use limit orders (`"entry": "limit"`) — often free on Binance (maker)
- Hold BNB in wallet for 25% fee discount
- Trade high-liquidity pairs only (BTC/USDT, ETH/USDT)

---

## 🐳 Docker (optional, run everything at once)

```bash
# Paper trading mode (safe)
docker compose up

# With local Ollama AI
docker compose --profile local-ai up

# Stop everything
docker compose down
```

---

## 🗓️ 4-Week Roadmap

| Week | Goal |
|---|---|
| **Week 1** | Run `install.sh`, configure `.env`, download data, run first backtest |
| **Week 2** | Tune strategy parameters, get AI working, verify Telegram alerts |
| **Week 3** | Pass all unit tests, simulate crash scenario, read the logs |
| **Week 4** | Paper trade 7+ days, review daily Telegram summaries, evaluate go-live checklist |

---

## ⚠️ Disclaimer

This software is for **educational purposes only**. Cryptocurrency trading carries significant risk. Past backtest performance does not guarantee future results. Never invest money you cannot afford to lose entirely. The authors are not responsible for any financial losses.
