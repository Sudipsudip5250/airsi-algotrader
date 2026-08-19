# AIRSI AlgoTrader strategy reference

AIRSI AlgoTrader uses one production Freqtrade strategy: `AIRSIAlgoStrategy`. It combines the strongest compatible ideas from both source projects without running two competing bots.

## Why one hybrid strategy

The former AIRSI approach was a Bollinger/RSI mean-reversion system. The former Algo-Trader approach was an EMA trend-pullback system. Neither is universally best. Mean reversion is more appropriate when the market is oscillating inside a range; trend pullbacks are more appropriate when price and moving averages show a sustained bullish regime.

The unified strategy first classifies the regime and then activates only the matching entry branch:

| Market condition | Signal branch | Main indicators | Expected behavior |
|---|---|---|---|
| Confirmed bullish regime | `bullish_trend_pullback` | EMA9 > EMA21 > EMA50, EMA50/EMA200 spread > 0.5%, RSI 42–52 and rising, volume ratio > 1.0 | Buy selective pullbacks rather than chasing extended candles |
| Confirmed range | `range_mean_reversion` (disabled by default) | EMA50/EMA200 spread within ±0.8%, RSI oversold, lower Bollinger Band, volume ratio > 0.5 | Research-only candidate; not used in production until it passes separate out-of-sample tests |
| Sustained bearish regime | No long entry | Price/EMA alignment fails | Stay out rather than averaging into a downtrend |

This design is a better fit for a single project because it preserves both ideas in one researchable class while allowing production to use only the branch that survived the initial robustness review. Execution, risk protection, logging, configuration, and dashboard behavior remain centralized.

## Entry and exit rules

The strategy uses a 1-hour timeframe and a 240-candle warm-up period. It calculates EMA21, EMA50, EMA200, RSI14, Bollinger Bands, and 20-candle volume ratio. All calculations are local and deterministic; there are no network requests, model calls, mutable files, or external side effects inside the Freqtrade strategy loop.

The production trend-pullback entry requires EMA9 > EMA21 > EMA50, an EMA50/EMA200 spread above 0.5%, RSI between 42 and 52 and rising, price within 0.5% of EMA21, and volume above its 20-candle average. The range mean-reversion entry remains implemented for research but is disabled by default because it was the weaker branch in the real-data comparison. Every production entry is long-only and is blocked in a sustained bearish regime.

Exits occur through the configured ROI table, stoploss, trailing stop, or an explicit signal. The explicit signal exits when RSI is overbought with recovery toward the Bollinger midpoint, price reaches the upper Bollinger Band, or bearish EMA structure develops. Freqtrade protections add a cooldown, a stoploss guard, and a maximum-drawdown guard.

## Risk defaults

| Parameter | Default |
|---|---:|
| Timeframe | 1h |
| Stoploss | -2.0% |
| Trailing activation offset | 1.5% |
| Trailing positive stop | 0.8% |
| Stoploss guard | 3 losses in 96 candles, 24-candle pause |
| Maximum drawdown guard | 10% over 192 candles |
| Default mode | Paper trading |

These values are safety-oriented starting points, not promises of profitability. They must be evaluated with fees, slippage, liquidity, and out-of-sample data before any live use.

## Commands

```bash
# Paper trading
bash scripts/run_bot.sh paper

# Backtest
python3 scripts/run_backtest.py --days 180

# Hyperopt only after establishing a clean out-of-sample evaluation.
# Render a config first, then run hyperopt against the rendered file.
python3 scripts/render_config.py bot/config.paper.json bot/user_data/config.hyperopt.rendered.json
freqtrade hyperopt \
  --config bot/user_data/config.hyperopt.rendered.json \
  --strategy AIRSIAlgoStrategy \
  --strategy-path bot/strategies \
  --epochs 100 \
  --spaces buy sell roi stoploss trailing
```

The former FinBERT/sample-headline path is not part of the strategy loop. If news sentiment is added later, it should be produced by a separate timestamped worker and treated as an advisory feature with clear causal availability.
