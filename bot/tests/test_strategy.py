"""Unit tests for the unified AIRSI AlgoTrader strategy."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategies.AIRSIAlgoStrategy import AIRSIAlgoStrategy


def build_strategy() -> AIRSIAlgoStrategy:
    strategy = AIRSIAlgoStrategy.__new__(AIRSIAlgoStrategy)
    strategy.config = {
        "stake_currency": "USDT",
        "stake_amount": 50,
        "dry_run": True,
        "runmode": "backtest",
        "user_data_dir": "bot/user_data",
        "exchange": {"name": "binance"},
    }
    return strategy


def make_ohlcv(n: int = 320, trend: float = 0.0, noise: float = 0.003) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    steps = pd.Series(trend, index=dates)
    close = 30_000 * (1 + steps).cumprod()
    if noise:
        # A deterministic alternating perturbation gives bands without relying
        # on a random seed or an external data source.
        close = close * (1 + pd.Series([noise, -noise] * (n // 2), index=dates)[:n])
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": 1_000.0,
        },
        index=dates,
    )


def test_indicators_and_signal_columns_are_present():
    strategy = build_strategy()
    result = strategy.populate_indicators(make_ohlcv(), {"pair": "BTC/USDT"})
    result = strategy.populate_entry_trend(result, {"pair": "BTC/USDT"})
    result = strategy.populate_exit_trend(result, {"pair": "BTC/USDT"})

    for column in (
        "ema21", "ema50", "ema200", "bb_lower", "bb_mid", "bb_upper",
        "rsi", "volume_ratio", "bull_regime", "range_regime",
        "enter_long", "enter_tag", "exit_long",
    ):
        assert column in result.columns


def test_rsi_stays_in_valid_range():
    strategy = build_strategy()
    result = strategy.populate_indicators(make_ohlcv(), {"pair": "BTC/USDT"})
    rsi = result["rsi"].dropna()
    assert (rsi >= 0).all()
    assert (rsi <= 100).all()


def test_severe_downtrend_has_no_long_entries():
    strategy = build_strategy()
    df = make_ohlcv(trend=-0.002, noise=0.001)
    result = strategy.populate_indicators(df, {"pair": "BTC/USDT"})
    result = strategy.populate_entry_trend(result, {"pair": "BTC/USDT"})

    warm = strategy.startup_candle_count
    assert result.iloc[warm:]["enter_long"].sum() == 0


def test_signal_columns_are_binary():
    strategy = build_strategy()
    result = strategy.populate_indicators(make_ohlcv(), {"pair": "BTC/USDT"})
    result = strategy.populate_entry_trend(result, {"pair": "BTC/USDT"})
    result = strategy.populate_exit_trend(result, {"pair": "BTC/USDT"})

    assert set(result["enter_long"].dropna().unique()).issubset({0, 1})
    assert set(result["exit_long"].dropna().unique()).issubset({0, 1})


def test_production_uses_strict_trend_branch_by_default():
    assert AIRSIAlgoStrategy.range_mean_reversion_enabled is False


def test_live_intelligence_veto_fails_closed(tmp_path):
    strategy = build_strategy()
    strategy.config["runmode"] = "dry_run"
    strategy.config["user_data_dir"] = str(tmp_path)
    assert strategy._intelligence_allows_entry() is False


def test_fresh_normal_intelligence_snapshot_allows_entries(tmp_path):
    strategy = build_strategy()
    strategy.config["runmode"] = "dry_run"
    strategy.config["user_data_dir"] = str(tmp_path)
    (tmp_path / "market_intelligence.json").write_text(
        '{'
        '"generated_at":"2026-01-01T00:00:00+00:00",'
        '"expires_at":"2099-01-01T00:00:00+00:00",'
        '"allow_long_entries":true,'
        '"risk_level":"normal",'
        '"confidence":0.8,'
        '"reason":"normal conditions",'
        '"source_count":1,'
        '"news_count":0,'
        '"model":"deterministic",'
        '"snapshot_hash":"abc123",'
        '"errors":[]'
        '}'
    )
    assert strategy._intelligence_allows_entry() is True


def test_risk_parameters_are_conservative_and_complete():
    assert AIRSIAlgoStrategy.stoploss < 0
    assert AIRSIAlgoStrategy.stoploss >= -0.10
    assert "0" in AIRSIAlgoStrategy.minimal_roi
    assert AIRSIAlgoStrategy.trailing_stop_positive_offset > AIRSIAlgoStrategy.trailing_stop_positive
    assert AIRSIAlgoStrategy.startup_candle_count >= 200
