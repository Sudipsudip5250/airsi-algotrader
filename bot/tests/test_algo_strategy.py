from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategies.AlgoExplorerStrategy import AlgoExplorerStrategy


def build_strategy() -> AlgoExplorerStrategy:
    strategy = AlgoExplorerStrategy.__new__(AlgoExplorerStrategy)
    strategy.config = {"stake_currency": "USDT", "dry_run": True}
    return strategy


def make_df(n: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = pd.Series(range(n), index=dates, dtype=float) + 100
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000.0,
        },
        index=dates,
    )


def test_indicators_and_signal_columns_are_present():
    strategy = build_strategy()
    result = strategy.populate_indicators(make_df(), {"pair": "BTC/USDT"})
    result = strategy.populate_entry_trend(result, {"pair": "BTC/USDT"})
    result = strategy.populate_exit_trend(result, {"pair": "BTC/USDT"})

    for column in ("ema9", "ema21", "ema50", "ema200", "rsi", "volume_ratio", "enter_long", "exit_long"):
        assert column in result.columns


def test_downtrend_does_not_create_long_entries():
    strategy = build_strategy()
    df = make_df()
    df["close"] = df["close"].iloc[::-1].to_numpy()
    result = strategy.populate_indicators(df, {"pair": "BTC/USDT"})
    result = strategy.populate_entry_trend(result, {"pair": "BTC/USDT"})

    assert result["enter_long"].sum() == 0
