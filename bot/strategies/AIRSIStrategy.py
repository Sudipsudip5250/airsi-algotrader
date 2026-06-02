"""
AIRSIStrategy — RSI + EMA + Bollinger Bands with optional AI commentary.

Works with Freqtrade 2024+.
Safe defaults: 2% stoploss, 6% ROI, max 2 open trades.
"""

from __future__ import annotations

import logging
from functools import reduce

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

logger = logging.getLogger(__name__)


class AIRSIStrategy(IStrategy):
    """
    Entry logic:
      - RSI crosses above oversold threshold (default 35)
      - Price above 50-period EMA (uptrend filter)
      - Price touches or crosses below lower Bollinger Band (mean-reversion)

    Exit logic:
      - RSI crosses above overbought threshold (default 68)
      - Freqtrade minimal_roi table
      - Hard stoploss

    AI commentary is attached to each trade via the Telegram notifier
    (see telegram_notifier.py) — does not affect trade logic.
    """

    INTERFACE_VERSION = 3

    # ── Risk management ──────────────────────────────────────────────
    minimal_roi = {
        "0":   0.06,   # 6% immediately (safety exit)
        "30":  0.04,   # 4% after 30 min
        "60":  0.02,   # 2% after 60 min
        "120": 0.01,   # 1% after 2 hours
    }

    stoploss = -0.035   # 3.5% hard stoploss — protects micro capital

    trailing_stop = True
    trailing_stop_positive = 0.015        # lock in 1.5% profit
    trailing_stop_positive_offset = 0.025 # activate once +2.5% reached
    trailing_only_offset_is_reached = True

    timeframe = "1h"

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 60

    # ── Hyperopt parameters (safe starting values) ────────────────────
    rsi_oversold  = IntParameter(25, 45, default=35, space="buy",  optimize=True)
    rsi_overbought = IntParameter(60, 80, default=68, space="sell", optimize=True)
    ema_period    = IntParameter(20, 100, default=50, space="buy", optimize=True)
    bb_std        = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # ── Protections ───────────────────────────────────────────────────
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
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 5,
                "max_allowed_drawdown": 0.08,
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
        ]

    # ── Indicators ────────────────────────────────────────────────────
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI
        dataframe["rsi"] = self._rsi(dataframe["close"], 14)

        # EMA
        dataframe["ema50"] = dataframe["close"].ewm(span=self.ema_period.value).mean()

        # Bollinger Bands
        rolling = dataframe["close"].rolling(window=20)
        bb_mean = rolling.mean()
        bb_std = rolling.std()
        mult = self.bb_std.value
        dataframe["bb_upper"] = bb_mean + mult * bb_std
        dataframe["bb_lower"] = bb_mean - mult * bb_std
        dataframe["bb_mid"]   = bb_mean

        # Volume filter: 20-period average
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] < self.rsi_oversold.value) &
                (dataframe["close"] > dataframe["ema50"]) &
                (dataframe["close"] <= dataframe["bb_lower"] * 1.005) &
                (dataframe["volume"] > dataframe["volume_mean"] * 0.8) &
                (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe["rsi"] > self.rsi_overbought.value) &
                (dataframe["close"] >= dataframe["bb_upper"] * 0.995)
            ),
            "exit_long",
        ] = 1

        return dataframe

    # ── Utility: manual RSI (works without ta-lib) ────────────────────
    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    # ── Optional: log AI commentary on each confirmed trade ───────────
    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time, entry_tag, side: str, **kwargs
    ) -> bool:
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from ai_client import AIClient
            from telegram_notifier import notify_trade_entry

            df = self.dp.get_pair_dataframe(pair, self.timeframe)
            rsi_val = df["rsi"].iloc[-1] if "rsi" in df.columns else 0
            trend = "uptrend" if df["close"].iloc[-1] > df["ema50"].iloc[-1] else "downtrend"

            ai = AIClient()
            comment = ai.market_sentiment(pair, rsi_val, trend)
            notify_trade_entry(pair, rate, amount * rate, "RSI+BB", comment)
        except Exception as exc:
            logger.warning("AI commentary failed on entry: %s", exc)

        return True
