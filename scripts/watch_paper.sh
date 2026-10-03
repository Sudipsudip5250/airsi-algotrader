#!/usr/bin/env bash
# Supervisor loop: keeps the paper stack alive while the system is on.
# Every 60s it restarts a dead intelligence worker / freqtrade bot and logs it.
# Restart storms (>5 restarts of one service in 10 min) trigger one Telegram
# alert per 6h; supervision itself never stops.
#
# Started automatically by scripts/start_paper.sh (NO_WATCH=1 to skip).
# Stopped by scripts/stop_paper.sh. Logs to bot/user_data/logs/watchdog.log.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/bot/user_data/logs"
MODE="paper-micro"
[[ -f "$LOG_DIR/mode" ]] && MODE="$(cat "$LOG_DIR/mode")"
CHECK_SECS="${WATCH_INTERVAL:-60}"
STATE_FILE="$LOG_DIR/watch.state"
ALERT_STAMP="$LOG_DIR/watch.alert"

log() { echo "$(date -u +%FT%TZ) [watch] $*" >> "$LOG_DIR/watchdog.log"; }

alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

record_restart() { # $1 = service -> prints restart count in last 600s
  local service="$1" now cutoff count
  now="$(date +%s)"
  cutoff=$(( now - 600 ))
  echo "$now $service" >> "$STATE_FILE"
  awk -v c="$cutoff" -v s="$service" '$1 > c && $2 == s' "$STATE_FILE" > "$STATE_FILE.tmp" \
    && mv "$STATE_FILE.tmp" "$STATE_FILE"
  count="$(awk -v s="$service" '$2 == s' "$STATE_FILE" | wc -l)"
  echo "$count"
}

maybe_alert() { # $1 = service, $2 = count
  local last=0
  [[ -f "$ALERT_STAMP" ]] && last="$(cat "$ALERT_STAMP")"
  local now
  now="$(date +%s)"
  if (( $2 > 5 )) && (( now - last > 21600 )); then
    echo "$now" > "$ALERT_STAMP"
    bash "$ROOT_DIR/scripts/tg_send.sh" \
      "AIRSI watchdog: $1 died >5x in 10 min (mode $MODE). Still retrying — check logs." \
      >> "$LOG_DIR/watchdog.log" 2>&1 || true
  fi
}

start_intelligence() {
  setsid nohup bash "$ROOT_DIR/scripts/run_intelligence.sh" \
    >>"$LOG_DIR/intelligence.log" 2>&1 < /dev/null &
  echo $! > "$LOG_DIR/intelligence.pid"
  log "restarted intelligence worker pid $!"
}

start_bot() {
  setsid nohup bash "$ROOT_DIR/scripts/run_bot.sh" "$MODE" \
    >>"$LOG_DIR/freqtrade.out.log" 2>&1 < /dev/null &
  echo $! > "$LOG_DIR/freqtrade.pid"
  log "restarted freqtrade bot pid $! mode=$MODE"
}

log "watchdog started (mode=$MODE, check every ${CHECK_SECS}s)"
while true; do
  sleep "$CHECK_SECS"
  if ! alive "$LOG_DIR/intelligence.pid"; then
    log "intelligence worker dead — restarting"
    start_intelligence
    maybe_alert "intelligence" "$(record_restart intelligence)"
  fi
  if ! alive "$LOG_DIR/freqtrade.pid"; then
    log "freqtrade bot dead — restarting"
    start_bot
    maybe_alert "freqtrade" "$(record_restart freqtrade)"
  fi
done
