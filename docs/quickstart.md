# Quick Start Guide

This guide walks you through every step — from cloning the repo to running your first paper trade.

---

## What You'll Need

- **Git** — to clone the repo
- **Python 3.11+** — required by the supported dependency set
- **Node.js 22.13+** (optional) — only if you want the dashboard
- **Terminal** — all commands are run from the command line

---

## Step 1: Clone

```bash
git clone https://github.com/Sudipsudip5250/airsi-algotrader.git
cd airsi-algotrader
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

**For paper trading only**, most keys are optional. Telegram is disabled in the paper profiles by default; enable it locally only after setting both credentials. The optional settings are:
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
cd bot && python -m pytest tests/ -v
```

All strategy and AI unit tests should pass with a green `PASSED` message. If any fail, inspect the first traceback and check the troubleshooting section in the README.

---

## Step 6: Download Data

```bash
python scripts/download_data.py --days 30
```

This downloads 30 days of 1h/4h/1d candle data from Binance for BTC/USDT and ETH/USDT. Data is stored in `bot/user_data/data/`.

---

## Step 7: Run a Backtest

```bash
python scripts/run_backtest.py --days 30
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

Before starting, set `FREQTRADE_API_USER`, `FREQTRADE_API_PASS`, and `FREQTRADE_JWT_SECRET` in `.env`; the renderer rejects missing or sample credentials. The bot starts with:
- **$1,000 virtual wallet** — play money
- **$50 per trade** — virtual stake amount
- **Max 2 open trades** — at any time
- **REST API** — at `http://localhost:8080`
- **Live price feed** — from Binance

The intelligence worker is fail-closed for missing or stale snapshots. It can only veto new entries; it cannot place, cancel, or size trades.

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
