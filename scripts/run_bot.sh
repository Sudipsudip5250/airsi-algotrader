#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-paper}"

# Prefer the project venv even in non-interactive/background shells that never
# sourced scripts/activate.sh (e.g. launched via start_paper.sh / nohup).
if [[ -d "$ROOT_DIR/venv/bin" ]]; then
  export PATH="$ROOT_DIR/venv/bin:$PATH"
fi

# System libs for numpy/pandas/freqtrade (harmless if already set)
if [[ -f "$ROOT_DIR/scripts/env_libs.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/env_libs.sh"
fi

# Preserve CLI env overrides across .env sourcing (e.g. WALLET_MODE=... bash run_bot.sh live).
_OVERRIDDEN_EXCHANGE="${EXCHANGE:-}"
_OVERRIDDEN_WALLET_MODE="${WALLET_MODE:-}"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
if [[ -n "$_OVERRIDDEN_EXCHANGE" ]]; then EXCHANGE="$_OVERRIDDEN_EXCHANGE"; fi
if [[ -n "$_OVERRIDDEN_WALLET_MODE" ]]; then WALLET_MODE="$_OVERRIDDEN_WALLET_MODE"; fi

# EXCHANGE selectable via .env: binance | kraken | okx (default okx = cheapest maker 0.08%).
# Explicit modes still work; bare `paper`/`live` respect $EXCHANGE.
EXCHANGE="${EXCHANGE:-okx}"
WALLET_MODE="${WALLET_MODE:-custodial}"
if [[ "$WALLET_MODE" == self_custody_dex* ]]; then
  echo "WALLET_MODE=$WALLET_MODE requests on-chain DEX execution, which Freqtrade path does not support." >&2
  echo "Refusing live. Use paper mode for research, or see docs for Hummingbot Gateway roadmap." >&2
  if [[ "$MODE" == live ]]; then exit 3; fi
fi

case "$MODE" in
  paper)
    case "$EXCHANGE" in
      kraken) CONFIG="$ROOT_DIR/bot/config.paper.kraken.json" ;;
      okx) CONFIG="$ROOT_DIR/bot/config.paper.okx.json" ;;
      binance) CONFIG="$ROOT_DIR/bot/config.paper.json" ;;
      *) echo "Unknown EXCHANGE=$EXCHANGE (want binance|kraken|okx)" >&2; exit 2 ;;
    esac
    ;;
  live) CONFIG="$ROOT_DIR/bot/config.live.json" ;;
  paper-kraken) CONFIG="$ROOT_DIR/bot/config.paper.kraken.json" ;;
  paper-okx) CONFIG="$ROOT_DIR/bot/config.paper.okx.json" ;;
  paper-micro) CONFIG="$ROOT_DIR/bot/config.paper.micro.json" ;;
  *)
    echo "Usage: $0 {paper|live|paper-kraken|paper-okx|paper-micro}" >&2
    exit 2
    ;;
esac

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 is required. Run bash install.sh first." >&2
  exit 1
fi
if ! command -v freqtrade >/dev/null 2>&1; then
  echo "freqtrade is not installed or not on PATH." >&2
  echo "On this machine run: bash install.sh" >&2
  echo "Then activate: source scripts/activate.sh" >&2
  echo "See docs/quickstart.md Step 2-4. Paper trading needs no exchange keys." >&2
  exit 1
fi

OUTPUT="$ROOT_DIR/bot/user_data/config.${MODE}.rendered.json"
"$PYTHON_BIN" "$ROOT_DIR/scripts/render_config.py" "$CONFIG" "$OUTPUT"

# Telegram alerts: paper templates ship with telegram disabled so no-key runs
# work. If TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set in .env, enable
# alerts on the rendered (local-only, gitignored) config. Never touches the
# tracked template. Live template already wires these via placeholders.
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  "$PYTHON_BIN" - "$OUTPUT" <<'PYEOF'
import json, sys
path = sys.argv[1]
cfg = json.load(open(path))
tg = cfg.get("telegram", {})
tg["enabled"] = True
tg["token"] = __import__("os").environ["TELEGRAM_BOT_TOKEN"]
tg["chat_id"] = __import__("os").environ["TELEGRAM_CHAT_ID"]
cfg["telegram"] = tg
json.dump(cfg, open(path, "w"), indent=2)
print("Telegram alerts enabled on rendered config")
PYEOF
fi

exec freqtrade trade \
  --config "$OUTPUT" \
  --strategy AIRSIAlgoStrategy \
  --strategy-path "$ROOT_DIR/bot/strategies" \
  --userdir "$ROOT_DIR/bot/user_data" \
  --logfile "$ROOT_DIR/bot/user_data/logs/freqtrade.log"
