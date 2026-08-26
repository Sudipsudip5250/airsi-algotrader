# Dashboard Setup

The project includes a React dashboard with live trade monitoring, P&L charts, bot logs, and a human-gated experiments review page.

---

## Prerequisites

- Node.js 22.13+ and pnpm installed
- Freqtrade running (paper or live)
- `FREQTRADE_API_USER`, `FREQTRADE_API_PASS`, and `FREQTRADE_JWT_SECRET` configured in `.env`

---

## Run Locally

### 1. Start the API Server

```bash
pnpm --filter @workspace/api-server run dev
```

Runs on `http://localhost:5000`. The proxy exposes read-only telemetry routes plus file-backed experiment history and decision routes. It validates limits and artifact IDs, sanitizes Freqtrade configuration responses, and reports missing or expired intelligence as unavailable. The experiment decision route writes only under `experiments/` and cannot control Freqtrade or modify strategy files.

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
- Human-gated experiment proposals, evaluation metrics, and review decisions at `/experiments`
- Telegram-style trade alerts

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Dashboard shows `online: false` | Freqtrade REST API not running — start the bot first |
| API returns 401 or 503 | Check `FREQTRADE_API_USER` / `FREQTRADE_API_PASS` in `.env` and confirm Freqtrade is running |
| Experiments page is empty in Docker | Confirm `./proposals` and `./experiments` exist on the host; Compose mounts proposals read-only and experiments writable at `/app/research` |
| Experiment decision returns 503 | Confirm the API can read `bot/config.paper.json` and write `experiments/`; live and strategy paths are intentionally not mounted |
| Port conflict | Change `PORT` in `.env` or `docker-compose.yml` |
