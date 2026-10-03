"""Run an AIRSI AlgoTrader backtest and print a human-readable summary.

Usage:
  python scripts/run_backtest.py
  python scripts/run_backtest.py --days 90
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - requirements install provides this
    load_dotenv = lambda *args, **kwargs: None


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Run an AIRSI AlgoTrader backtest")
    parser.add_argument("--days", type=int, default=180, help="Days of history")
    parser.add_argument("--strategy", default="AIRSIAlgoStrategy", help="Strategy class name")
    parser.add_argument("--config", default="bot/config.paper.json", help="Config template path")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe")
    args = parser.parse_args()

    template = ROOT / args.config
    rendered = ROOT / "bot" / "user_data" / f".{template.stem}.rendered.json"
    rendered.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_config.py"), str(template), str(rendered)],
        check=True,
        cwd=ROOT,
    )

    end = date.today()
    start = end - timedelta(days=args.days)
    timerange = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    results_path = ROOT / "bot" / "user_data" / "backtest_results" / "last_run.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "freqtrade", "backtesting",
        "--config", str(rendered),
        "--strategy", args.strategy,
        "--strategy-path", str(ROOT / "bot" / "strategies"),
        "--timeframe", args.timeframe,
        "--timerange", timerange,
        "--datadir", str(ROOT / "bot" / "user_data" / "data"),
        "--userdir", str(ROOT / "bot" / "user_data"),
        "--export", "trades",
        "--export-filename", str(results_path),
    ]

    print(f"Running AIRSI AlgoTrader backtest: {args.strategy} | {timerange} | {args.timeframe}")
    print("   " + " ".join(cmd) + "\n")
    result = subprocess.run(cmd, check=False, cwd=ROOT)

    # Freqtrade 2026.x writes a timestamped zip + .last_result.json pointer and
    # ignores --export-filename for JSON, so resolve the real results file.
    resolved = resolve_results_file(results_path)
    if resolved is not None:
        print_summary(resolved)
    else:
        print("No backtest results file found; see freqtrade output above.")

    sys.exit(result.returncode)


def resolve_results_file(expected: Path) -> Path | None:
    """Return the actual results JSON (plain or inside the latest zip)."""
    if expected.exists():
        return expected
    pointer = expected.parent / ".last_result.json"
    try:
        latest = json.loads(pointer.read_text()).get("latest_backtest", "")
        if latest:
            candidate = expected.parent / latest
            if candidate.suffix == ".zip" and candidate.exists():
                return candidate
            if candidate.exists():
                return candidate
    except (OSError, json.JSONDecodeError):
        pass
    return None


def load_results(path: Path) -> dict:
    if path.suffix == ".zip":
        import zipfile

        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".json") and "config" not in n and "market_change" not in n and "wallet" not in n]
            if not names:
                raise ValueError(f"No results JSON inside {path.name}")
            with archive.open(sorted(names)[0]) as handle:
                return json.load(handle)
    return json.loads(path.read_text())


def print_summary(path: Path) -> None:
    try:
        data = load_results(path)
        strategy_results = list(data.get("strategy", {}).values())
        if not strategy_results:
            return
        result = strategy_results[0]
        total_trades = result.get("total_trades", 0)
        wins = result.get("wins", 0)
        # Freqtrade 2026.x: profit_total is a ratio, profit_total_abs is stake
        # currency; max_drawdown_account is the wallet drawdown ratio.
        profit_abs = result.get("profit_total_abs", result.get("profit_total", 0))
        drawdown = result.get("max_drawdown_account", result.get("max_drawdown", 0))
        print("\n" + "=" * 60)
        print("AIRSI ALGOTRADER BACKTEST SUMMARY")
        print("=" * 60)
        print(f"  Total trades:     {total_trades}")
        print(f"  Win rate:         {wins / max(total_trades, 1) * 100:.1f}%")
        print(f"  Total profit:     {profit_abs:.4f} USDT")
        print(f"  Profit factor:    {result.get('profit_factor', 0):.2f}")
        print(f"  Max drawdown:     {drawdown * 100:.2f}%")
        print(f"  Sharpe ratio:     {result.get('sharpe', 'N/A')}")
        print("=" * 60)
    except Exception as exc:
        print(f"Could not parse backtest results: {exc}")


if __name__ == "__main__":
    main()
