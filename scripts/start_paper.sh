#!/usr/bin/env bash
# Start continuous paper trading in the background (test money only).
#
# Usage:
#   bash scripts/start_paper.sh [paper-micro|paper|paper-okx|paper-kraken]
#   RUN_HOURS=6 bash scripts/start_paper.sh paper-micro   # auto-stop after 6h
#
# Starts: market-intelligence worker + freqtrade bot, detached via setsid.
# Logs:   bot/user_data/logs/intelligence.log + freqtrade.log (+ .out.log)
# PIDs:   bot/user_data/logs/*.pid
# Stop:   bash scripts/stop_paper.sh   Status: bash scripts/status_paper.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-paper-micro}"
LOG_DIR="$ROOT_DIR/bot/user_data/logs"
mkdir -p "$LOG_DIR"
echo "$MODE" > "$LOG_DIR/mode"
# Rotate if logs exceed ~50MB to protect the free-plan disk.
if [[ $(du -sm "$LOG_DIR" 2>/dev/null | cut -f1) -ge 50 ]]; then
  bash "$ROOT_DIR/scripts/rotate_logs.sh" 5 >>"$LOG_DIR/watchdog.log" 2>&1 || true
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

already_running() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

if already_running "$LOG_DIR/intelligence.pid" || already_running "$LOG_DIR/freqtrade.pid"; then
  echo "Paper stack already running. See bash scripts/status_paper.sh" >&2
  echo "Stop first with bash scripts/stop_paper.sh" >&2
  exit 2
fi

echo "[1/2] Starting market-intelligence worker (mode=$MODE)..."
setsid nohup bash "$ROOT_DIR/scripts/run_intelligence.sh" \
  >>"$LOG_DIR/intelligence.log" 2>&1 < /dev/null &
echo $! > "$LOG_DIR/intelligence.pid"
sleep 3
if ! already_running "$LOG_DIR/intelligence.pid"; then
  echo "Intelligence worker died on boot. Tail:" >&2
  tail -20 "$LOG_DIR/intelligence.log" >&2
  exit 1
fi
echo "  worker pid $(cat "$LOG_DIR/intelligence.pid"), logging to bot/user_data/logs/intelligence.log"

echo "[2/2] Starting freqtrade paper bot (mode=$MODE)..."
setsid nohup bash "$ROOT_DIR/scripts/run_bot.sh" "$MODE" \
  >>"$LOG_DIR/freqtrade.out.log" 2>&1 < /dev/null &
echo $! > "$LOG_DIR/freqtrade.pid"
sleep 12
if ! already_running "$LOG_DIR/freqtrade.pid"; then
  echo "Freqtrade died on boot. Tail:" >&2
  tail -30 "$LOG_DIR/freqtrade.out.log" "$LOG_DIR/freqtrade.log" 2>/dev/null >&2
  kill "$(cat "$LOG_DIR/intelligence.pid")" 2>/dev/null || true
  rm -f "$LOG_DIR/intelligence.pid" "$LOG_DIR/freqtrade.pid"
  exit 1
fi
echo "  bot pid $(cat "$LOG_DIR/freqtrade.pid"), logging to bot/user_data/logs/freqtrade.log"

if [[ -n "${RUN_HOURS:-}" ]]; then
  echo "Auto-stop scheduled in ${RUN_HOURS}h."
  setsid nohup bash -c "sleep $(( RUN_HOURS * 3600 )); bash \"$ROOT_DIR/scripts/stop_paper.sh\"" \
    >>"$LOG_DIR/autostop.log" 2>&1 < /dev/null &
  echo $! > "$LOG_DIR/autostop.pid"
fi

if [[ "${NO_WATCH:-0}" == "1" ]]; then
  echo "Watchdog skipped (NO_WATCH=1). Processes will NOT auto-restart on crash."
else
  setsid nohup bash "$ROOT_DIR/scripts/watch_paper.sh" \
    >>"$LOG_DIR/watchdog.log" 2>&1 < /dev/null &
  echo $! > "$LOG_DIR/watch.pid"
  echo "Watchdog started (pid $(cat "$LOG_DIR/watch.pid")) — restarts dead services, survives terminal closure."
fi

echo ""
echo "Running continuously with TEST money. Stop any time: bash scripts/stop_paper.sh"
echo "Watch: tail -f bot/user_data/logs/freqtrade.log | bash scripts/status_paper.sh"
