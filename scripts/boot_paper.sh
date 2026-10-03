#!/usr/bin/env bash
# Idempotent "make sure paper is running" entry point.
# Use after a full machine reboot (this container has no cron/systemd, so
# nothing can auto-start on boot — run this one command and walk away).
# Safe to run any time: does nothing if the stack is already up.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-paper-micro}"
LOG_DIR="$ROOT_DIR/bot/user_data/logs"

alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

if alive "$LOG_DIR/freqtrade.pid" && alive "$LOG_DIR/intelligence.pid"; then
  echo "Paper stack already running (mode $(cat "$LOG_DIR/mode" 2>/dev/null || echo "$MODE"))."
  bash "$ROOT_DIR/scripts/status_paper.sh" | head -8
  exit 0
fi

bash "$ROOT_DIR/scripts/stop_paper.sh" >/dev/null 2>&1 || true
exec bash "$ROOT_DIR/scripts/start_paper.sh" "$MODE"
