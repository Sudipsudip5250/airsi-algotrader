#!/usr/bin/env bash
# Replit entry point — runs every time the workspace starts.
set -uo pipefail
echo "=== AIRSI AlgoTrader reboot hook ==="
if [[ -f bot/user_data/logs/mode ]]; then
  MODE="$(cat bot/user_data/logs/mode)"
else
  MODE="paper-micro"
fi
echo "Restoring paper stack (mode=$MODE) ..."
bash scripts/boot_paper.sh "$MODE"
echo "Status after restore:"
bash scripts/status_paper.sh | head -8 || true
echo "Logs: tail -f bot/user_data/logs/freqtrade.log"
