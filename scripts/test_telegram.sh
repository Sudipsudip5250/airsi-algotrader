#!/usr/bin/env bash
# Verify Telegram bot token + chat id by sending one test message.
# Prints only ok/fail — never prints the token.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if bash "$ROOT_DIR/scripts/tg_send.sh" "AIRSI AlgoTrader test: Telegram alerts are wired. Paper trading will report entries/exits here."; then
  echo "Telegram OK — check your chat for the test message."
fi
