"""
Shared pytest fixtures for strategy tests.
Generates synthetic OHLCV DataFrames so tests run without a live exchange.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(n: int = 200, base_price: float = 30000.0,
               trend: float = 0.0, noise: float = 0.01) -> pd.DataFrame:
    """Generate a synthetic OHLCV dataframe."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = base_price * np.cumprod(1 + np.random.normal(trend, noise, n))
    high  = close * (1 + np.abs(np.random.normal(0, noise / 2, n)))
    low   = close * (1 - np.abs(np.random.normal(0, noise / 2, n)))
    open_ = np.roll(close, 1)
    open_[0] = base_price
    volume = np.random.uniform(100, 1000, n)

    return pd.DataFrame({
        "date":   dates,
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": volume,
    }).set_index("date")


@pytest.fixture
def neutral_df():
    """Sideways market — minimal directional bias."""
    return make_ohlcv(200, trend=0.0, noise=0.005)


@pytest.fixture
def uptrend_df():
    """Strong uptrend — price rises over time."""
    return make_ohlcv(200, trend=0.002, noise=0.005)


@pytest.fixture
def downtrend_df():
    """Consistent downtrend — price falls over time."""
    return make_ohlcv(200, trend=-0.002, noise=0.005)


@pytest.fixture
def volatile_df():
    """High-volatility market."""
    return make_ohlcv(200, trend=0.0, noise=0.04)
