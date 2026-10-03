#!/usr/bin/env bash
# Send one Telegram message. Usage: bash scripts/tg_send.sh "text"
# Prints only ok/fail — never prints the token.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "tg_send: TELEGRAM keys not set, skipping." >&2
  exit 2
fi

RESP="$(curl -sS --max-time 15 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${1:-AIRSI AlgoTrader}")"
if echo "$RESP" | grep -q '"ok":true'; then
  echo "tg_send: delivered."
else
  echo "tg_send: FAILED (token/chat-id rejected)." >&2
  exit 1
fi
