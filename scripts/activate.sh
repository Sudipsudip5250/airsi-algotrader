#!/usr/bin/env bash
# Activate Python venv with library path fix for this environment
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${SCRIPT_DIR}/../venv/bin/activate"
export LD_LIBRARY_PATH="${SCRIPT_DIR}/../venv/lib"
