"""AIRSI-native migration of Algo-Trader-Explorer's trend-pullback strategy.

This is an alternate strategy in the unified AIRSI repository. It intentionally
contains no network calls, sample headlines, or mutable safety-gate state: AI
and risk controls belong outside Freqtrade's indicator loop.
"""

from __future__ import annotations

import pandas as pd
from freqtrade.strategy import IStrategy


class AlgoExplorerStrategy(IStrategy):
    """One-hour EMA trend filter with an RSI pullback entry."""

    INTERFACE_VERSION = 3

    minimal_roi = {
        "0": 0.06,
        "120": 0.04,
        "360": 0.02,
        "720": 0,
    }
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True
    timeframe = "1h"
    startup_candle_count = 200

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        for period in (9, 21, 50, 200):
            dataframe[f"ema{period}"] = dataframe["close"].ewm(
                span=period, adjust=False, min_periods=period
            ).mean()

        delta = dataframe["close"].diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
        rs = gain / loss.replace(0, 1e-10)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        dataframe["volume_ma"] = dataframe["volume"].rolling(20, min_periods=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"].replace(0, 1)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe.loc[
            (
                (dataframe["ema9"] > dataframe["ema21"])
                & (dataframe["close"] > dataframe["ema50"])
                & (dataframe["rsi"] > 38)
                & (dataframe["rsi"] < 50)
                & (dataframe["rsi"] > dataframe["rsi"].shift(1))
                & (dataframe["volume_ratio"] > 0.8)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe.loc[
            (
                (dataframe["ema9"] < dataframe["ema21"])
                | (dataframe["rsi"] > 70)
            ),
            "exit_long",
        ] = 1
        return dataframe
