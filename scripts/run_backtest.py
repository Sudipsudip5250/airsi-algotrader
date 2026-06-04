#!/usr/bin/env python3
"""
Run a Freqtrade backtest and print a human-readable summary.

Usage:
  python scripts/run_backtest.py
  python scripts/run_backtest.py --days 90 --strategy AIRSIStrategy
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Freqtrade backtest")
    parser.add_argument("--days",     type=int, default=180,          help="Days of history")
    parser.add_argument("--strategy", default="AIRSIStrategy",        help="Strategy class name")
    parser.add_argument("--config",   default="bot/config.paper.json", help="Config file path")
    parser.add_argument("--timeframe", default="1h",                  help="Candle timeframe")
    args = parser.parse_args()

    end   = date.today()
    start = end - timedelta(days=args.days)
    timerange = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"

    cmd = [
        "freqtrade", "backtesting",
        "--config",    args.config,
        "--strategy",  args.strategy,
        "--timeframe", args.timeframe,
        "--timerange", timerange,
        "--datadir",   "bot/user_data/data",
        "--userdir",   os.path.expanduser("~/user_data"),
        "--export",    "trades",
        "--export-filename", "bot/user_data/backtest_results/last_run.json",
    ]

    print(f"🔬 Running backtest: {args.strategy} | {timerange} | {args.timeframe}")
    print("   " + " ".join(cmd) + "\n")
    result = subprocess.run(cmd, check=False)

    results_path = Path("bot/user_data/backtest_results/last_run.json")
    if results_path.exists():
        print_summary(results_path)

    sys.exit(result.returncode)


def print_summary(path: Path) -> None:
    try:
        data = json.loads(path.read_text())
        strategy_results = list(data.get("strategy", {}).values())
        if not strategy_results:
            return
        r = strategy_results[0]
        print("\n" + "=" * 60)
        print("📊  BACKTEST SUMMARY")
        print("=" * 60)
        print(f"  Total trades:     {r.get('total_trades', 'N/A')}")
        print(f"  Win rate:         {r.get('wins', 0) / max(r.get('total_trades', 1), 1) * 100:.1f}%")
        print(f"  Total profit:     {r.get('profit_total', 0):.4f} USDT")
        print(f"  Profit factor:    {r.get('profit_factor', 0):.2f}")
        print(f"  Max drawdown:     {r.get('max_drawdown', 0) * 100:.2f}%")
        print(f"  Sharpe ratio:     {r.get('sharpe', 'N/A')}")
        print(f"  Best trade:       {r.get('best_trade', 'N/A')}")
        print(f"  Worst trade:      {r.get('worst_trade', 'N/A')}")
        print("=" * 60)

        drawdown_ok  = r.get("max_drawdown", 1) < 0.15
        trades_ok    = r.get("total_trades", 0) >= 30
        winrate      = r.get("wins", 0) / max(r.get("total_trades", 1), 1)
        win_ok       = winrate > 0.5
        profit_ok    = r.get("profit_total", 0) > 0

        print("\n🚦 Go/No-Go Checks:")
        print(f"  Max drawdown < 15%:   {'✅' if drawdown_ok else '❌'}")
        print(f"  Win rate > 50%:       {'✅' if win_ok else '❌'}")
        print(f"  Total profit > 0:     {'✅' if profit_ok else '❌'}")
        print(f"  Trade count >= 30:    {'✅' if trades_ok else '❌'}")
        all_pass = all([drawdown_ok, win_ok, profit_ok, trades_ok])
        print(f"\n  Verdict: {'✅ Strategy looks ready for paper trading!' if all_pass else '❌ Needs improvement — do NOT go live.'}")
    except Exception as exc:
        print(f"⚠️  Could not parse results: {exc}")


if __name__ == "__main__":
    main()
