#!/usr/bin/env bash
# Rotate logs so they never eat the free-plan disk.
# Keeps freqtrade.log + 7 daily rotations, intelligence/watchdog tail.
# Run weekly via: bash scripts/rotate_logs.sh  (add to your own cron/weekly check).
set -u
LOG_DIR="bot/user_data/logs"
KEEP="${1:-7}"
for base in freqtrade.log freqtrade.out.log intelligence.log watchdog.log; do
  [[ -f "$LOG_DIR/$base" ]] || continue
  for i in $(seq "$KEEP" -1 1); do
    [[ -f "$LOG_DIR/$base.$i" ]] && mv "$LOG_DIR/$base.$i" "$LOG_DIR/$base.$((i+1))"
  done
  cp "$LOG_DIR/$base" "$LOG_DIR/$base.1"
  : > "$LOG_DIR/$base"
done
echo "Rotated logs (keep $KEEP). Current:"
du -sh "$LOG_DIR" 2>/dev/null
