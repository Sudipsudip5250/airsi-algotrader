#!/usr/bin/env python3
"""
Download free historical OHLCV data from Binance via Freqtrade.

Usage:
  python scripts/download_data.py
  python scripts/download_data.py --days 90 --pairs BTC/USDT ETH/USDT
"""

from __future__ import annotations

import argparse
import subprocess
import sys


PAIRS_DEFAULT = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAMES    = ["1h", "4h", "1d"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Freqtrade historical data")
    parser.add_argument("--days",  type=int,  default=180,    help="Days of history (default 180)")
    parser.add_argument("--pairs", nargs="+", default=PAIRS_DEFAULT, help="Trading pairs")
    parser.add_argument("--exchange", default="binance", help="Exchange (default binance)")
    args = parser.parse_args()

    for tf in TIMEFRAMES:
        cmd = [
            "freqtrade", "download-data",
            "--exchange", args.exchange,
            "--pairs",   *args.pairs,
            "--timeframe", tf,
            "--days",    str(args.days),
            "--datadir", "bot/user_data/data",
        ]
        print(f"\n📥  Downloading {tf} data for {args.days} days...")
        print("   " + " ".join(cmd))
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"⚠️  Warning: download for {tf} returned code {result.returncode}")

    print("\n✅ Data download complete. Files saved to bot/user_data/data/")


if __name__ == "__main__":
    main()
