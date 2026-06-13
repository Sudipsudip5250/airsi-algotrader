from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

logger = logging.getLogger(__name__)


class AIRSIStrategy(IStrategy):
    INTERFACE_VERSION = 3

    minimal_roi = {
        "0": 0.02,
        "30": 0.01,
        "120": 0.005,
    }

    stoploss = -0.015

    trailing_stop = False

    timeframe = "15m"

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 60

    rsi_oversold = IntParameter(25, 45, default=38, space="buy", optimize=True)
    rsi_overbought = IntParameter(60, 80, default=70, space="sell", optimize=True)
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
        ]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["rsi"] = self._rsi(dataframe["close"], 14)
        rolling = dataframe["close"].rolling(window=20)
        bb_mean = rolling.mean()
        bb_std = rolling.std()
        mult = self.bb_std.value
        dataframe["bb_upper"] = bb_mean + mult * bb_std
        dataframe["bb_lower"] = bb_mean - mult * bb_std
        dataframe["bb_mid"] = bb_mean
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] < self.rsi_oversold.value) &
                (dataframe["close"] <= dataframe["bb_lower"] * 1.01) &
                (dataframe["volume"] > dataframe["volume_mean"] * 0.5) &
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] > self.rsi_overbought.value) &
                (dataframe["close"] >= dataframe["bb_mid"])
            ),
            "exit_long",
        ] = 1
        return dataframe

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time, entry_tag, side: str, **kwargs
    ) -> bool:
        return True
