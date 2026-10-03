"""Join Freqtrade trade exports to AI decisions for self-improvement.

Reads backtest_results/last_run.json or --trades JSON, appends trade_outcome
events to experiments/ai-decisions.jsonl linked by snapshot_hash when possible.

Usage:
  python scripts/log_trade_outcomes.py --trades bot/user_data/backtest_results/last_run.json
  python scripts/log_trade_outcomes.py --trades trades.json --decision-id aid-... --snapshot-hash abc123
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

try:
    from ai_tracker import log_trade_outcome
except Exception as exc:  # never fail the pipeline
    print(f"ai_tracker unavailable: {exc}")
    raise SystemExit(0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", required=True, help="Path to Freqtrade trades export JSON")
    parser.add_argument("--decision-id", default="manual-import")
    parser.add_argument("--snapshot-hash", default="")
    parser.add_argument("--runmode", default="backtest")
    args = parser.parse_args()

    path = Path(args.trades)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return 1

    # Support both Freqtrade backtest export shape and flat list.
    trades: list[dict] = []
    if isinstance(data, dict):
        for strat in (data.get("strategy") or {}).values():
            if isinstance(strat, dict) and isinstance(strat.get("trades"), list):
                trades.extend(strat["trades"])
        if not trades and isinstance(data.get("trades"), list):
            trades = data["trades"]
    elif isinstance(data, list):
        trades = data

    count = 0
    for t in trades:
        if not isinstance(t, dict):
            continue
        try:
            log_trade_outcome(
                decision_id=args.decision_id,
                snapshot_hash=args.snapshot_hash or str(t.get("snapshot_hash", "")),
                pair=str(t.get("pair", "")),
                profit_abs=float(t.get("profit_abs", t.get("profit_total", 0.0)) or 0.0),
                profit_pct=float(t.get("profit_ratio", t.get("profit_pct", 0.0)) or 0.0),
                fees=float(t.get("fee", 0.0) or 0.0),
                exit_reason=str(t.get("exit_reason", t.get("sell_reason", ""))),
                stake=float(t.get("stake_amount", t.get("stake", 0.0)) or 0.0),
                runmode=args.runmode,
            )
            count += 1
        except Exception:
            continue
    print(f"Logged {count} trade outcomes to experiments/ai-decisions.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
