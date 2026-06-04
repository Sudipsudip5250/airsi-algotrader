# Dashboard Setup

The project includes a React dashboard with live trade monitoring, P&L charts, and bot logs.

---

## Prerequisites

- Node.js 18+ and pnpm installed
- Freqtrade running (paper or live)
- API keys configured in `.env`

---

## Run Locally

### 1. Start the API Server

```bash
pnpm --filter @workspace/api-server run dev
```

Runs on `http://localhost:5000`.

### 2. Start the Dashboard

```bash
pnpm --filter @workspace/dashboard run dev
```

Runs on `http://localhost:23183` (or `http://localhost:3000`).

### 3. Open in Browser

Visit `http://localhost:23183` (or the URL shown in terminal).

---

## Using Docker

```bash
# Paper trading mode (safe)
docker compose up

# With local Ollama AI
docker compose --profile local-ai up

# Stop everything
docker compose down
```

---

## Dashboard Features

- Open positions (real-time)
- P&L chart (per pair and total)
- Trade history
- Per-pair performance breakdown
- Bot logs
- Telegram-style trade alerts

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Dashboard shows `online: false` | Freqtrade REST API not running — start the bot first |
| API returns 401 | Check `FREQTRADE_API_USER` / `FREQTRADE_API_PASS` in `.env` |
| Port conflict | Change `PORT` in `.env` or `docker-compose.yml` |
