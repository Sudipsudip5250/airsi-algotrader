#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

cd "$ROOT_DIR"
exec python3 bot/market_intelligence.py \
  --interval "${INTELLIGENCE_POLL_SECONDS:-900}" \
  --output "${INTELLIGENCE_DECISION_PATH:-bot/user_data/market_intelligence.json}"
