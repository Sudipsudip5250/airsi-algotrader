# AIRSI AlgoTrader performance research

> Trading disclaimer: backtests are historical simulations, not guarantees. Keep the bot in paper mode until the full validation process is complete.

## Loss diagnosis

The first unified 1-hour version lost approximately 7.61 USDT on a 1,000 USDT paper wallet over the tested sample. The main causes were identifiable in the exported trades rather than hidden model behavior:

| Cause | Evidence | Decision |
|---|---|---|
| Stoploss asymmetry | 18 stoploss exits lost about 19.71 USDT; average losing trade was about -1.59% while the average winning trade was about +0.57% | Do not increase trade frequency; require more selective entries |
| Weak range branch | 12 range trades in the strict comparison lost about 1.44 USDT, while the trend branch made about 2.43 USDT | Disable range mean reversion in production; retain behind a research flag |
| Broad trend filter | The initial trend branch used a 0.2% EMA50/EMA200 spread, RSI 38–55, price within 1% of EMA21, and volume ratio 0.8 | Tighten to 0.5% spread, RSI 42–52, price within 0.5%, and volume ratio above 1.0 |
| Market/pair dependence | SOL was profitable in the sample while BTC and ETH were negative | Keep pair-level reporting and do not assume one pair generalizes to another |
| Historical-window sensitivity | The baseline was negative in both the train and test windows; the strict trend variant was slightly negative in train and positive in test | Treat the improvement as preliminary and require more periods before live deployment |

## Current production decision

`AIRSIAlgoStrategy` now uses the strict trend-pullback branch by default. The range branch remains in the class as a research candidate but is disabled with `range_mean_reversion_enabled = False`. This prevents a known weaker branch from consuming live paper capital while preserving the code needed for a controlled future experiment.

## Observed comparison

The same public Binance spot data was used for BTC/USDT, ETH/USDT, SOL/USDT, and BNB/USDT. The full sample covered approximately 180 days ending 18 August 2026. These results include the configured Freqtrade fee assumptions and are not a promise of future performance.

| Version | Trades | Total result | Max drawdown |
|---|---:|---:|---:|
| Former AIRSI 15m strategy | 767 | -129.12 USDT | 13.25% |
| Former Algo-Trader 1h strategy | 95 | -11.44 USDT | 1.14% |
| Initial unified 1h strategy | 113 | -7.61 USDT | 0.76% |
| Current strict trend-only production default | 24 | **+2.43 USDT** | **0.17%** |

The current positive result is encouraging but statistically weak because it contains only 24 trades. A small number of trades can be dominated by a few market events. It must not be described as a guaranteed profit engine.

## Required validation before live consideration

Use the following sequence without changing thresholds after looking at the final test window:

1. Keep the current thresholds frozen and run at least three non-overlapping historical periods.
2. Include bull, range, and bearish market conditions, not only the recent period.
3. Run pair-level analysis and remove pairs whose behavior is persistently negative after fees.
4. Add conservative slippage and spread assumptions.
5. Run forward paper trading for at least several weeks with the same configuration that would be used live.
6. Compare expected fills, realized fills, rejected entries, stoploss behavior, and drawdown.
7. Only consider live deployment if performance is positive out-of-sample, drawdown remains within a predeclared limit, and operational failures are understood.

## What not to do

Do not add an LLM call to the strategy loop, increase leverage, widen the stoploss to hide losing trades, or repeatedly tune parameters against the same backtest period. Those actions can make the historical curve look better while reducing the chance that the result survives live conditions.

## References

[1]: https://github.com/Sudipsudip5250/AIRSI-Trader "AIRSI AlgoTrader source repository"

[2]: https://github.com/Sudipsudip5250/Algo-Trader-Explorer "Former Algo-Trader source repository"

[3]: https://www.freqtrade.io/en/stable/backtesting/ "Freqtrade backtesting documentation"

[4]: https://www.freqtrade.io/en/stable/protections/ "Freqtrade protections documentation"
