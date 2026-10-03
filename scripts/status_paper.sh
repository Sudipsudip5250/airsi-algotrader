#!/usr/bin/env bash
# Status of the background paper stack + recent activity. Never prints secrets.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/bot/user_data/logs"

alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

echo "=== Paper stack status ==="
if alive "$LOG_DIR/freqtrade.pid"; then
  echo "freqtrade bot:  RUNNING (pid $(cat "$LOG_DIR/freqtrade.pid"))"
else
  echo "freqtrade bot:  stopped"
fi
if alive "$LOG_DIR/intelligence.pid"; then
  echo "intelligence:   RUNNING (pid $(cat "$LOG_DIR/intelligence.pid"))"
else
  echo "intelligence:   stopped"
fi
if alive "$LOG_DIR/watch.pid"; then
  echo "watchdog:       RUNNING (pid $(cat "$LOG_DIR/watch.pid")) — auto-restarts dead services"
else
  echo "watchdog:       stopped (no auto-restart; start with NO_WATCH= unset)"
fi
if [[ -f "$LOG_DIR/autostop.pid" ]] && kill -0 "$(cat "$LOG_DIR/autostop.pid")" 2>/dev/null; then
  echo "auto-stop:      scheduled (pid $(cat "$LOG_DIR/autostop.pid"))"
fi

echo ""
echo "=== Latest intelligence decision ==="
DECISION="${INTELLIGENCE_DECISION_PATH:-$ROOT_DIR/bot/user_data/market_intelligence.json}"
if [[ -f "$DECISION" ]]; then
  PYBIN="$ROOT_DIR/venv/bin/python"
  [[ -x "$PYBIN" ]] || PYBIN="$(command -v python3)"
  DECISION_PATH="$DECISION" "$PYBIN" -c "
import json, os
d = json.load(open(os.environ['DECISION_PATH']))
print('risk=%s allow_long=%s conf=%s model=%s news=%s' % (
  d.get('risk_level'), d.get('allow_long_entries'), d.get('confidence'),
  d.get('model'), d.get('news_count')))
print('reason:', str(d.get('reason', ''))[:200])
" 2>/dev/null || echo "(decision file unreadable)"
else
  echo "(no decision file yet — worker still warming up)"
fi

echo ""
echo "=== freqtrade.log (last 8 lines) ==="
tail -8 "$LOG_DIR/freqtrade.log" 2>/dev/null || echo "(no freqtrade.log yet)"
echo ""
echo "=== Trades so far (dry-run wallet) ==="
grep -aiE "order|trade|entry|exit|profit" "$LOG_DIR/freqtrade.log" 2>/dev/null | tail -8 || echo "(no trades logged yet)"
