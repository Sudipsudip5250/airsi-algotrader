#!/usr/bin/env bash
set -euo pipefail

TEMPLATE="${FREQTRADE_CONFIG_TEMPLATE:-/freqtrade/config.template.json}"
OUTPUT="/freqtrade/user_data/config.rendered.json"

python3 /freqtrade/project_scripts/render_config.py "$TEMPLATE" "$OUTPUT"

exec freqtrade trade \
  --config "$OUTPUT" \
  --strategy AIRSIAlgoStrategy \
  --strategy-path /freqtrade/user_data/strategies \
  --userdir /freqtrade/user_data \
  --logfile /freqtrade/user_data/logs/freqtrade.log
