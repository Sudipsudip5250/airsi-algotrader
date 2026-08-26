#!/usr/bin/env python3
"""
Download free historical OHLCV data from Binance via Freqtrade.

Usage:
  python scripts/download_data.py
  python scripts/download_data.py --days 90 --pairs BTC/USDT ETH/USDT
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAIRS_DEFAULT = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAMES = ["1h", "4h", "1d"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Freqtrade historical data")
    parser.add_argument("--days",  type=int,  default=180,    help="Days of history (default 180)")
    parser.add_argument("--pairs", nargs="+", default=PAIRS_DEFAULT, help="Trading pairs")
    parser.add_argument("--exchange", default="binance", help="Exchange (default binance)")
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be greater than zero")

    data_dir = ROOT / "bot" / "user_data" / "data"
    user_dir = ROOT / "bot" / "user_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    for tf in TIMEFRAMES:
        cmd = [
            "freqtrade", "download-data",
            "--exchange", args.exchange,
            "--pairs",   *args.pairs,
            "--timeframe", tf,
            "--days",    str(args.days),
            "--datadir", str(data_dir),
            "--userdir", str(user_dir),
        ]
        print(f"\nDownloading {tf} data for {args.days} days...")
        print("  " + " ".join(cmd))
        result = subprocess.run(cmd, check=False, cwd=ROOT, env=os.environ.copy())
        if result.returncode != 0:
            failures.append(tf)
            print(f"Download for {tf} failed with exit code {result.returncode}", file=sys.stderr)

    if failures:
        print(f"Data download failed for timeframe(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"\nData download complete. Files saved to {data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
