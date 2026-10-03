# Quick Start Guide

This environment is pre-setup: `venv/` exists, `.env` exists with no-key test defaults,
`source scripts/activate.sh` works, and 18/18 API/intelligence tests pass here.
**Only you must do manually:** add model API keys + exchange keys (see Manual-only table).

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

## Step 3: Configure — ONLY manual step is keys

`.env` already exists with working no-key test defaults (`EXCHANGE=okx`,
`WALLET_MODE=custodial`, deterministic AI + Pollinations keyless).
Open `.env` only to add keys when ready:

| You add manually | Where to get it | Required for |
|---|---|---|
| `GROQ_API_KEY` (`GROQ_MODEL=openai/gpt-oss-20b`) | https://console.groq.com | AI commentary (primary) |
| `GEMINI_API_KEY` (`GEMINI_MODEL=gemini-2.5-flash`) | https://aistudio.google.com/app/apikey | AI fallback |
| `OPENROUTER_API_KEY` (`OPENROUTER_MODEL=openrouter/free`) | https://openrouter.ai/keys | AI failover |
| `EXCHANGE_API_KEY` + `EXCHANGE_API_SECRET` (trade-only, withdrawals OFF) | Binance / OKX / Kraken API management | LIVE only — leave empty for paper |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | @BotFather + getUpdates | Telegram alerts (optional) |

Everything else (`FREQTRADE_API_USER/PASS/JWT`, `EXCHANGE`, `WALLET_*`, intelligence
intervals) is already set for local paper-micro testing.

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

## Step 5: Verify (already green here)

```bash
source scripts/activate.sh
python -m pytest bot/tests/test_ai_client.py bot/tests/test_market_intelligence.py -v --noconftest
```

In this container that is green for the API/intelligence suites, and strategy tests
run too once `source scripts/activate.sh` exports the system library paths
(see `scripts/env_libs.sh`). On a full PC/VPS after `bash install.sh` run the whole suite:

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
source scripts/activate.sh
bash scripts/run_intelligence.sh
```

In a second terminal, start paper-micro testing ($10 fake, closest to $5-10 real):

```bash
source scripts/activate.sh
bash scripts/run_bot.sh paper-micro
```

`paper` respects `EXCHANGE` in `.env` (`okx` = cheapest 0.08% maker). Before starting,
`.env` already has local `FREQTRADE_API_USER/PASS/JWT`; the renderer rejects missing
or sample credentials. Paper-micro starts with:
- **$10 virtual wallet** — play money mirroring $5-10 real plan
- **$5 per trade, max 1 open trade, BTC/USDT only**
- **REST API** — at `http://localhost:8080`
- **Live price feed** — from selected `EXCHANGE`

The intelligence worker is fail-closed for missing or stale snapshots. It can only veto new entries; it cannot place, cancel, or size trades.

Let it run. Watch the terminal output. Press `Ctrl+C` to stop.

---

## Step 9: Continuous paper run (background, test money)

For a multi-hour test session that survives terminal closure:

```bash
source scripts/activate.sh
bash scripts/test_telegram.sh        # one test message; proves alerts work
bash scripts/start_paper.sh paper-micro
# optional timed run: RUN_HOURS=6 bash scripts/start_paper.sh paper-micro
```

Useful commands while it runs:

| Command | What it shows |
|---|---|
| `bash scripts/status_paper.sh` | bot/worker alive? latest AI decision, last log lines, recent trades |
| `tail -f bot/user_data/logs/freqtrade.log` | full debug log: orders, fills, protections, heartbeats |
| `tail -f bot/user_data/logs/intelligence.log` | each 15-min AI risk cycle (provider, model, failures) |
| `cat bot/user_data/market_intelligence.json` | current veto snapshot (risk/allow/confidence/reason) |
| `bash scripts/stop_paper.sh` | stop everything (also cancels a scheduled auto-stop) |

How continuity works: `freqtrade trade` is an infinite loop (heartbeat every ~60s in
the log) until you stop it; the intelligence worker refreshes its veto snapshot every
`INTELLIGENCE_POLL_SECONDS` (default 900s). `start_paper.sh` also launches a
**watchdog supervisor** (`scripts/watch_paper.sh`, `NO_WATCH=1` to skip) that checks
both processes every 60s and restarts dead ones, logging to `watchdog.log` — a
restart storm (>5 deaths/10 min) sends one Telegram alert per 6h but supervision
never stops. If the worker dies, entries stay blocked (fail-closed) — the bot keeps
running but opens nothing new. `start_paper.sh` refuses to double-start;
`RUN_HOURS` schedules an auto-stop. `stop_paper.sh` stops the watchdog first so
nothing resurrects mid-shutdown. Telegram entry/exit/startup alerts fire
automatically when `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are set —
`run_bot.sh` enables them on the rendered (gitignored) config only.

One honest limit: this machine has no cron/systemd, so after a **full reboot**
nothing auto-starts — run one command and walk away:

```bash
bash scripts/boot_paper.sh paper-micro   # no-op if already running
```

After a few hours, review `freqtrade.log` (search `order`/`profit`) and
`experiments/ai-decisions.jsonl` (every AI veto + joined outcomes) to improve the
strategy — that ledger is the input for the next research iteration.

Every few days (and always before asking for analysis), sync closed paper trades
into the ledger — freqtrade keeps them in SQLite, this joins them to the covering
AI decision:

```bash
source scripts/activate.sh
python scripts/sync_paper_outcomes.py
```

Refresh klines weekly so the avoided-loss estimate stays covered, then grade
the collection any time:

```bash
source scripts/activate.sh
python scripts/download_data.py --days 180 --pairs BTC/USDT
python scripts/analyze_collection.py
```

The report ends with KEEP COLLECTING (with what's missing) or READY — only
act on the strategy after READY.

---

## What Next?

| You want to... | Go here |
|---|---|
| Get API keys | [docs/api-keys.md](api-keys.md) |
| Go live with real money | [docs/testing.md](testing.md) |
| Understand the strategy | [docs/strategy.md](strategy.md) |
| Select exchange | `EXCHANGE=okx` in `.env`, then `bash scripts/run_bot.sh paper` |
| Start the dashboard | [docs/dashboard.md](dashboard.md) |
