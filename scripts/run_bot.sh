#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-paper}"

case "$MODE" in
  paper) CONFIG="$ROOT_DIR/bot/config.paper.json" ;;
  live) CONFIG="$ROOT_DIR/bot/config.live.json" ;;
  paper-kraken) CONFIG="$ROOT_DIR/bot/config.paper.kraken.json" ;;
  paper-okx) CONFIG="$ROOT_DIR/bot/config.paper.okx.json" ;;
  *)
    echo "Usage: $0 {paper|live|paper-kraken|paper-okx}" >&2
    exit 2
    ;;
esac

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 is required. Run bash install.sh first." >&2
  exit 1
fi
if ! command -v freqtrade >/dev/null 2>&1; then
  echo "freqtrade is not installed or not on PATH. Activate venv or run bash install.sh first." >&2
  exit 1
fi

OUTPUT="$ROOT_DIR/bot/user_data/config.${MODE}.rendered.json"
"$PYTHON_BIN" "$ROOT_DIR/scripts/render_config.py" "$CONFIG" "$OUTPUT"

exec freqtrade trade \
  --config "$OUTPUT" \
  --strategy AIRSIAlgoStrategy \
  --strategy-path "$ROOT_DIR/bot/strategies" \
  --userdir "$ROOT_DIR/bot/user_data" \
  --logfile "$ROOT_DIR/bot/user_data/logs/freqtrade.log"
