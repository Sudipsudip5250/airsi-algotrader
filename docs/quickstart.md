# Quick Start Guide

This guide walks you through every step — from cloning the repo to running your first paper trade.

---

## What You'll Need

- **Git** — to clone the repo
- **Python 3.10+** — the bot runs on Python
- **Node.js 18+** (optional) — only if you want the dashboard
- **Terminal** — all commands are run from the command line

---

## Step 1: Clone

```bash
git clone https://github.com/sudipsudip5250/airsi-trader.git
cd airsi-trader
```

---

## Step 2: Install

**Linux / macOS:**
```bash
bash install.sh
```

**Windows (PowerShell as Administrator):**
```powershell
.\install.ps1
```

The installer will:
- Check that Python and Git are installed
- Create a virtual environment (`venv/`)
- Install all Python dependencies (freqtrade, pandas, etc.)
- Install Node.js dependencies (for the dashboard)
- Create a helper activation script

After it finishes, you should see a "Setup Complete!" message.

---

## Step 3: Configure

```bash
cp .env.example .env
```

Open `.env` in any text editor. Each setting has a comment explaining what it does.

**For paper trading only**, most keys are optional. The only ones you might want:
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — to get Telegram alerts
- `GROQ_API_KEY` — to get AI commentary on trades

See [docs/api-keys.md](api-keys.md) for detailed instructions on obtaining each key.

---

## Step 4: Activate

```bash
source scripts/activate.sh
```

You should see `(venv)` appear in your terminal prompt.  
Do this every time you open a new terminal.

> **On standard Linux/macOS** (no nix): you can also use `source venv/bin/activate`

---

## Step 5: Verify

```bash
cd bot && python3 -m pytest tests/ -v
```

All strategy and AI unit tests should pass with a green `PASSED` message. If any fail, inspect the first traceback and check the troubleshooting section in the README.

---

## Step 6: Download Data

```bash
python3 scripts/download_data.py --days 30
```

This downloads 30 days of 1h/4h/1d candle data from Binance for BTC/USDT and ETH/USDT. Data is stored in `bot/user_data/data/`.

---

## Step 7: Run a Backtest

```bash
python3 scripts/run_backtest.py --days 30
```

This tests the strategy against historical data. You'll see a summary table showing trades, profit, and win rate. If it shows 0 trades, the strategy conditions didn't trigger — this is normal for the default settings.

---

## Step 8: Start Market Intelligence and Paper Trading

In one terminal, refresh market/news intelligence:

```bash
bash scripts/run_intelligence.sh
```

In a second terminal, start paper trading:

```bash
bash scripts/run_bot.sh paper
```

The bot starts with:
- **$1,000 virtual wallet** — play money
- **$50 per trade** — virtual stake amount
- **Max 2 open trades** — at any time
- **REST API** — at `http://localhost:8080`
- **Live price feed** — from Binance

Let it run. Watch the terminal output. Press `Ctrl+C` to stop.

---

## What Next?

| You want to... | Go here |
|---|---|
| Get API keys | [docs/api-keys.md](api-keys.md) |
| Go live with real money | [docs/testing.md](testing.md) |
| Understand the strategy | [docs/strategy.md](strategy.md) |
| Run AI locally | [docs/local-ai-setup.md](local-ai-setup.md) |
| Start the dashboard | [docs/dashboard.md](dashboard.md) |
