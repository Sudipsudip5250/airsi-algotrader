# Unified strategy reference

AIRSI-Trader now contains two selectable, paper-testable Freqtrade strategies. They share the same execution, dashboard, exchange, notification, and safety infrastructure, but they represent different trading hypotheses.

## Strategy profiles

| Strategy | Timeframe | Trading idea | Configuration |
|---|---:|---|---|
| `AIRSIStrategy` | 15m | RSI/Bollinger mean reversion protected by an EMA50 uptrend filter | `bot/config.paper.json` |
| `AlgoExplorerStrategy` | 1h | EMA9/EMA21 trend alignment with an RSI pullback and volume filter | `bot/config.paper.algo-explorer.json` |

Run only one profile per Freqtrade process unless you intentionally isolate API ports and databases. Both profiles are paper-trading configurations by default.

## AIRSIStrategy: RSI/Bollinger mean reversion

Entry requires all of the following conditions: price is above EMA50, RSI is below the configured oversold threshold, price is close to or below the lower Bollinger Band, and volume is at least half of its 20-candle average. Exit is triggered when RSI is above the configured overbought threshold and price has recovered to the Bollinger midline. The ROI table, stoploss, cooldown, and StoplossGuard remain active as additional controls.

The strategy exposes EMA200 for analysis and future higher-timeframe filters. AI commentary is not called from the strategy loop and cannot block or authorize an order.

## AlgoExplorerStrategy: trend pullback

Entry requires EMA9 above EMA21, price above EMA50, RSI between 38 and 50 and rising, and volume ratio above 0.8. Exit is triggered by EMA9 falling below EMA21 or RSI moving above 70. It uses a one-hour timeframe, a 200-candle startup period, a 3% stoploss, and a trailing stop that activates after a 1.5% favorable move.

The original Algo-Trader-Explorer implementation also contained a FinBERT/sample-headline sentiment field and an external mutable safety gate. Those pieces were not copied into the signal loop because sample headlines are not causal market data and mutable filesystem state makes backtests non-reproducible. If sentiment is reintroduced, it should arrive as a timestamped feature from a separate worker.

## Commands

```bash
# AIRSI mean reversion, paper mode
freqtrade trade \
  --config bot/config.paper.json \
  --strategy AIRSIStrategy

# Algo Explorer trend pullback, paper mode
freqtrade trade \
  --config bot/config.paper.algo-explorer.json \
  --strategy AlgoExplorerStrategy

# Backtest each profile separately
freqtrade backtesting --config bot/config.paper.json --strategy AIRSIStrategy
freqtrade backtesting --config bot/config.paper.algo-explorer.json --strategy AlgoExplorerStrategy
```

Before live deployment, compare both strategies using identical pairs, fee assumptions, date ranges, slippage assumptions, and out-of-sample periods. A profitable backtest alone is not evidence that either strategy is safe for live capital.
