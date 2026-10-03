#!/usr/bin/env bash
# Stop the background paper stack started by scripts/start_paper.sh.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/bot/user_data/logs"

stop_pid() {
  local name="$1" pidfile="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      # Kill the whole process group (setsid) so children die too.
      kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
      sleep 3
      kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
      echo "Stopped $name (was $pid)"
    else
      echo "$name already stopped (stale pid $pid)"
    fi
    rm -f "$pidfile"
  else
    echo "$name not running (no pidfile)"
  fi
}

stop_pid "watchdog supervisor" "$LOG_DIR/watch.pid"
stop_pid "freqtrade paper bot" "$LOG_DIR/freqtrade.pid"
stop_pid "intelligence worker" "$LOG_DIR/intelligence.pid"
if [[ -f "$LOG_DIR/autostop.pid" ]]; then
  pid="$(cat "$LOG_DIR/autostop.pid")"
  kill "$pid" 2>/dev/null || true
  rm -f "$LOG_DIR/autostop.pid"
  echo "Cancelled scheduled auto-stop"
fi
echo "Paper stack stopped. Logs kept in bot/user_data/logs/"
