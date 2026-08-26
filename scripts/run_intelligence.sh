#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

INTERVAL="${INTELLIGENCE_POLL_SECONDS:-900}"
if [[ ! "$INTERVAL" =~ ^[0-9]+$ ]] || (( INTERVAL < 60 )); then
  echo "INTELLIGENCE_POLL_SECONDS must be an integer of at least 60 seconds" >&2
  exit 2
fi

cd "$ROOT_DIR"
exec "$PYTHON_BIN" bot/market_intelligence.py \
  --interval "$INTERVAL" \
  --output "${INTELLIGENCE_DECISION_PATH:-bot/user_data/market_intelligence.json}"
