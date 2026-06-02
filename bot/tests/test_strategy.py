"""
Unit tests for AIRSIStrategy.

Run with:  cd bot && pytest tests/ -v
"""

from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "strategies"))

from AIRSIStrategy import AIRSIStrategy


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_strategy() -> AIRSIStrategy:
    """Construct strategy with minimal config (no exchange required)."""
    config = {
        "stake_currency": "USDT",
        "stake_amount": 50,
        "dry_run": True,
        "exchange": {"name": "binance"},
    }
    s = AIRSIStrategy.__new__(AIRSIStrategy)
    s.config = config
    s.dp = None
    return s


# ── Indicator tests ───────────────────────────────────────────────────────────

class TestIndicators:
    def test_rsi_range(self, neutral_df):
        """RSI must always be between 0 and 100."""
        rsi = AIRSIStrategy._rsi(neutral_df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all(), "RSI went below 0"
        assert (valid <= 100).all(), "RSI went above 100"

    def test_rsi_high_on_uptrend(self, uptrend_df):
        """RSI should be elevated during a sustained uptrend."""
        rsi = AIRSIStrategy._rsi(uptrend_df["close"], 14)
        mean_rsi = rsi.dropna().mean()
        assert mean_rsi > 50, f"Expected RSI > 50 in uptrend, got {mean_rsi:.1f}"

    def test_rsi_low_on_downtrend(self, downtrend_df):
        """RSI should be depressed during a sustained downtrend."""
        rsi = AIRSIStrategy._rsi(downtrend_df["close"], 14)
        mean_rsi = rsi.dropna().mean()
        assert mean_rsi < 50, f"Expected RSI < 50 in downtrend, got {mean_rsi:.1f}"

    def test_indicators_no_nan_after_warmup(self, neutral_df):
        """After warmup candles, no NaN values in key indicators."""
        s = build_strategy()
        result = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        warmup = AIRSIStrategy.startup_candle_count
        after_warmup = result.iloc[warmup:]
        assert after_warmup["rsi"].isna().sum() == 0
        assert after_warmup["ema50"].isna().sum() == 0
        assert after_warmup["bb_lower"].isna().sum() == 0
        assert after_warmup["bb_upper"].isna().sum() == 0

    def test_bollinger_bands_ordering(self, neutral_df):
        """Upper BB must always be >= Mid >= Lower."""
        s = build_strategy()
        df = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        warmup = AIRSIStrategy.startup_candle_count
        after = df.iloc[warmup:]
        assert (after["bb_upper"] >= after["bb_mid"]).all()
        assert (after["bb_mid"] >= after["bb_lower"]).all()


# ── Signal tests ──────────────────────────────────────────────────────────────

class TestSignals:
    def test_entry_column_exists(self, neutral_df):
        """populate_entry_trend must return 'enter_long' column."""
        s = build_strategy()
        df = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        df = s.populate_entry_trend(df, {"pair": "BTC/USDT"})
        assert "enter_long" in df.columns

    def test_exit_column_exists(self, neutral_df):
        """populate_exit_trend must return 'exit_long' column."""
        s = build_strategy()
        df = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        df = s.populate_exit_trend(df, {"pair": "BTC/USDT"})
        assert "exit_long" in df.columns

    def test_no_simultaneous_entry_and_exit(self, neutral_df):
        """A candle should not signal both entry and exit."""
        s = build_strategy()
        df = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        df = s.populate_entry_trend(df, {"pair": "BTC/USDT"})
        df = s.populate_exit_trend(df, {"pair": "BTC/USDT"})
        conflict = (df.get("enter_long", 0) == 1) & (df.get("exit_long", 0) == 1)
        assert not conflict.any(), "Found candle with both buy AND sell signal"

    def test_signals_are_binary(self, neutral_df):
        """Signal columns must only contain 0 or 1 (or NaN)."""
        s = build_strategy()
        df = s.populate_indicators(neutral_df.copy(), {"pair": "BTC/USDT"})
        df = s.populate_entry_trend(df, {"pair": "BTC/USDT"})
        df = s.populate_exit_trend(df, {"pair": "BTC/USDT"})
        for col in ("enter_long", "exit_long"):
            if col in df.columns:
                vals = df[col].dropna().unique()
                assert set(vals).issubset({0, 1}), f"{col} has non-binary values: {vals}"

    def test_no_buy_signals_in_severe_downtrend(self, downtrend_df):
        """
        In a severe downtrend price stays below EMA50, so the strategy's
        uptrend filter should suppress most (ideally all) entry signals.
        """
        s = build_strategy()
        df = s.populate_indicators(downtrend_df.copy(), {"pair": "BTC/USDT"})
        df = s.populate_entry_trend(df, {"pair": "BTC/USDT"})
        warmup = AIRSIStrategy.startup_candle_count
        signals_after_warmup = df.iloc[warmup:].get("enter_long", pd.Series(dtype=float))
        buy_count = (signals_after_warmup == 1).sum()
        total = len(signals_after_warmup)
        assert buy_count / total < 0.05, (
            f"Too many buys ({buy_count}/{total}) in a downtrend — "
            "EMA uptrend filter may be broken"
        )


# ── Risk management sanity checks ─────────────────────────────────────────────

class TestRiskParameters:
    def test_stoploss_is_set_and_negative(self):
        assert AIRSIStrategy.stoploss < 0, "Stoploss must be negative (e.g. -0.035)"

    def test_stoploss_not_too_aggressive(self):
        assert AIRSIStrategy.stoploss >= -0.10, (
            "Stoploss > 10% is too aggressive for micro capital"
        )

    def test_minimal_roi_has_entry(self):
        assert "0" in AIRSIStrategy.minimal_roi, "minimal_roi must include a '0' entry"

    def test_trailing_stop_offset_greater_than_trigger(self):
        if AIRSIStrategy.trailing_stop and AIRSIStrategy.trailing_only_offset_is_reached:
            assert (
                AIRSIStrategy.trailing_stop_positive_offset
                > AIRSIStrategy.trailing_stop_positive
            ), "Trailing stop offset must be > positive stop to avoid immediate triggers"
