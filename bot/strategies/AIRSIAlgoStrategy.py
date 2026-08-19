"""Unified AIRSI AlgoTrader strategy.

The strategy selects between two deterministic entry styles:

* mean reversion in a confirmed range, using RSI and Bollinger Bands;
* trend pullbacks in a confirmed bullish regime, using EMA alignment and RSI.

No network requests, model inference, mutable files, or external side effects
are allowed in the strategy loop. AI commentary and operational risk services
remain outside this class.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy

try:
    from trading_memory import MemoryStore
except ImportError:  # pragma: no cover - only relevant to isolated Freqtrade loaders
    MemoryStore = None  # type: ignore[assignment]

try:
    from freqtrade.persistence import Trade
except ImportError:  # pragma: no cover - lightweight test stubs
    Trade = None  # type: ignore[assignment]


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class AIRSIAlgoStrategy(IStrategy):
    """Single production strategy for the unified AIRSI AlgoTrader project."""

    INTERFACE_VERSION = 3

    minimal_roi = {
        "0": 0.02,
        "45": 0.01,
        "180": 0.005,
    }
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    timeframe = "1h"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 240

    # The range branch remains available for research but is disabled in the
    # production default because it was the weaker branch in the real-data
    # comparison. Enable only after a separate out-of-sample review.
    range_mean_reversion_enabled = False
    live_intelligence_enabled = True
    intelligence_filename = "market_intelligence.json"
    persistent_memory_enabled = True
    memory_filename = "trading_memory.sqlite"

    rsi_oversold = IntParameter(25, 40, default=34, space="buy", optimize=True)
    rsi_overbought = IntParameter(60, 80, default=68, space="sell", optimize=True)
    bb_std = DecimalParameter(1.8, 2.6, default=2.0, decimals=1, space="buy", optimize=True)

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 24,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 192,
                "trade_limit": 20,
                "stop_duration_candles": 48,
                "max_allowed_drawdown": 0.10,
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 4,
            },
        ]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        close = dataframe["close"]
        dataframe["ema9"] = close.ewm(span=9, adjust=False, min_periods=9).mean()
        dataframe["ema21"] = close.ewm(span=21, adjust=False, min_periods=21).mean()
        dataframe["ema50"] = close.ewm(span=50, adjust=False, min_periods=50).mean()
        dataframe["ema200"] = close.ewm(span=200, adjust=False, min_periods=200).mean()

        rolling = close.rolling(window=20, min_periods=20)
        dataframe["bb_mid"] = rolling.mean()
        band_std = rolling.std()
        dataframe["bb_upper"] = dataframe["bb_mid"] + self.bb_std.value * band_std
        dataframe["bb_lower"] = dataframe["bb_mid"] - self.bb_std.value * band_std

        dataframe["rsi"] = self._rsi(close, 14)
        dataframe["volume_mean"] = dataframe["volume"].rolling(20, min_periods=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean"].replace(0, np.nan)

        # Regime labels are diagnostic columns and are also used by entries.
        ema_spread = dataframe["ema50"] / dataframe["ema200"] - 1.0
        dataframe["bull_regime"] = (
            (close > dataframe["ema50"])
            & (dataframe["ema9"] > dataframe["ema21"])
            & (dataframe["ema21"] > dataframe["ema50"])
            & (ema_spread > 0.005)
        )
        dataframe["range_regime"] = ema_spread.abs() <= 0.008
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        # External intelligence can only veto new entries in live/dry-run
        # operation. Backtests and hyperopt remain fully deterministic.
        if not self._intelligence_allows_entry(metadata.get("pair")):
            return dataframe

        mean_reversion = (
            self.range_mean_reversion_enabled
            & dataframe["range_regime"]
            & (dataframe["rsi"] < self.rsi_oversold.value)
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.005)
            & (dataframe["volume_ratio"] > 0.50)
            & (dataframe["volume"] > 0)
        )
        trend_pullback = (
            dataframe["bull_regime"]
            & (dataframe["rsi"] > 42)
            & (dataframe["rsi"] < 52)
            & (dataframe["rsi"] > dataframe["rsi"].shift(1))
            & (dataframe["close"] <= dataframe["ema21"] * 1.005)
            & (dataframe["volume_ratio"] > 1.00)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[mean_reversion, ["enter_long", "enter_tag"]] = [1, "range_mean_reversion"]
        dataframe.loc[trend_pullback, ["enter_long", "enter_tag"]] = [1, "bullish_trend_pullback"]
        return dataframe

    def _intelligence_allows_entry(self, pair: str | None = None) -> bool:
        if not self.live_intelligence_enabled:
            return True
        runmode = self.config.get("runmode")
        runmode_value = getattr(runmode, "value", runmode)
        if runmode_value in {"backtest", "hyperopt", "plot"}:
            return True
        userdir = Path(str(self.config.get("user_data_dir", "bot/user_data")))
        path = userdir / self.intelligence_filename
        try:
            decision = json.loads(path.read_text())
            expires_at = datetime.fromisoformat(str(decision["expires_at"]))
            if expires_at <= datetime.now(timezone.utc):
                return False
            if not bool(decision["allow_long_entries"]) or decision.get("risk_level") in {"high", "elevated"}:
                return False
            base_asset = (pair or "").split("/", 1)[0].upper()
            asset_view = decision.get("asset_sentiment", {}).get(base_asset, {})
            asset_score = float(asset_view.get("score", 0.0))
            asset_confidence = float(asset_view.get("confidence", 0.0))
            if base_asset and asset_score <= -0.60 and asset_confidence >= 0.65:
                return False
            return True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False

    def _memory_store(self) -> MemoryStore | None:
        if not self.persistent_memory_enabled or MemoryStore is None:
            return None
        try:
            userdir = Path(str(self.config.get("user_data_dir", "bot/user_data")))
            path = Path(os.getenv("MEMORY_DB_PATH", str(userdir / self.memory_filename)))
            return MemoryStore(path)
        except Exception:
            return None

    @staticmethod
    def _memory_context(pair: str, entry_tag: str) -> tuple[str, str]:
        regime = "bullish_trend" if entry_tag == "bullish_trend_pullback" else "range_mean_reversion"
        return regime, entry_tag or "unknown"

    def _memory_entry_allowed(self, pair: str, entry_tag: str) -> bool:
        store = self._memory_store()
        if store is None:
            return True
        regime, signal_tag = self._memory_context(pair, entry_tag)
        try:
            allowed, _lesson = store.entry_gate(pair=pair, regime=regime, signal_tag=signal_tag)
            return allowed
        except Exception:
            # Existing deterministic/intelligence gates remain authoritative.
            return True

    def _memory_intelligence_context(self) -> dict:
        try:
            userdir = Path(str(self.config.get("user_data_dir", "bot/user_data")))
            payload = json.loads((userdir / self.intelligence_filename).read_text())
            return {
                "snapshot_hash": payload.get("snapshot_hash", ""),
                "risk_level": payload.get("risk_level", ""),
                "news_sentiment": payload.get("news_sentiment", 0.0),
                "news_confidence": payload.get("news_confidence", 0.0),
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """Reconcile recent closed trades into memory in live/dry-run only."""
        runmode = self.config.get("runmode")
        runmode_value = getattr(runmode, "value", runmode)
        if runmode_value in {"backtest", "hyperopt", "plot"} or Trade is None:
            return
        store = self._memory_store()
        if store is None:
            return
        try:
            recent = Trade.get_trades_proxy(is_open=False, close_date=current_time - timedelta(days=30))
            for trade in recent:
                reward = getattr(trade, "close_profit", None)
                if reward is None:
                    continue
                pair = str(getattr(trade, "pair", ""))
                entry_tag = str(getattr(trade, "enter_tag", "") or "unknown")
                regime, signal_tag = self._memory_context(pair, entry_tag)
                closed_at = getattr(trade, "close_date", None)
                store.record_trade_outcome(
                    str(getattr(trade, "id", "unknown")),
                    pair=pair,
                    regime=regime,
                    signal_tag=signal_tag,
                    reward=float(reward),
                    features=self._memory_intelligence_context(),
                    outcome={
                        "close_profit": float(reward),
                        "close_profit_abs": float(getattr(trade, "close_profit_abs", 0.0) or 0.0),
                        "exit_reason": str(getattr(trade, "exit_reason", "") or "unknown"),
                    },
                    occurred_at=_iso_datetime(closed_at) if isinstance(closed_at, datetime) else _iso_datetime(current_time),
                )
        except Exception:
            return

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """Apply only evidence-backed memory vetoes immediately before entry."""
        tag = entry_tag or "unknown"
        if side != "long":
            return True
        return self._memory_entry_allowed(pair, tag)

    def order_filled(self, pair: str, trade, order, current_time: datetime, **kwargs) -> None:
        """Persist entry context and realized outcome after fills; idempotence is in SQLite."""
        store = self._memory_store()
        if store is None:
            return
        try:
            trade_id = str(getattr(trade, "id", "unknown"))
            entry_tag = str(getattr(trade, "enter_tag", "") or "unknown")
            regime, signal_tag = self._memory_context(pair, entry_tag)
            order_side = str(getattr(order, "ft_order_side", ""))
            entry_side = str(getattr(trade, "entry_side", "buy"))
            if order_side == entry_side and bool(getattr(trade, "is_open", True)):
                store.record_trade_entry(
                    trade_id,
                    pair=pair,
                    regime=regime,
                    signal_tag=signal_tag,
                    features={"entry_rate": float(getattr(trade, "open_rate", 0.0) or 0.0), **self._memory_intelligence_context()},
                    occurred_at=_iso_datetime(current_time),
                )
            elif not bool(getattr(trade, "is_open", True)):
                reward = float(getattr(trade, "close_profit", 0.0) or 0.0)
                store.record_trade_outcome(
                    trade_id,
                    pair=pair,
                    regime=regime,
                    signal_tag=signal_tag,
                    reward=reward,
                    features=self._memory_intelligence_context(),
                    outcome={
                        "close_profit": reward,
                        "close_profit_abs": float(getattr(trade, "close_profit_abs", 0.0) or 0.0),
                        "exit_reason": str(getattr(trade, "exit_reason", "") or "unknown"),
                    },
                    occurred_at=_iso_datetime(current_time),
                )
        except Exception:
            # Memory must never crash or block the trading engine.
            return

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        exit_signal = (
            (
                (dataframe["rsi"] > self.rsi_overbought.value)
                & (dataframe["close"] >= dataframe["bb_mid"])
            )
            | (dataframe["close"] >= dataframe["bb_upper"])
            | (
                (dataframe["close"] < dataframe["ema50"])
                & (dataframe["ema21"] < dataframe["ema50"])
            )
        )
        dataframe.loc[exit_signal, "exit_long"] = 1
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
