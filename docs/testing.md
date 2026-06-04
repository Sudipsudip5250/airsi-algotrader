# 4-Phase Testing Pipeline

Always test in this order before going live.

---

## Phase 1 — Download Historical Data

```bash
source scripts/activate.sh
python3 scripts/download_data.py --days 180 --pairs BTC/USDT ETH/USDT
```

Downloads 6 months of 1h, 4h, and 1d candles from Binance public API.
Files saved to `bot/user_data/data/`.

---

## Phase 2 — Backtest

```bash
source scripts/activate.sh
python3 scripts/run_backtest.py --days 180
```

Runs the strategy against historical data. The script prints a Go/No-Go checklist:

| Check | Pass Criteria |
|---|---|
| Max drawdown | < 15% |
| Win rate | > 50% |
| Total profit | > 0 USDT |
| Trade count | ≥ 30 (statistically significant) |

**All 4 must pass** before moving to paper trading.

### Custom Backtest

```bash
# Different timeframe
python3 scripts/run_backtest.py --days 90 --timeframe 4h

# Different strategy
python3 scripts/run_backtest.py --strategy MyCustomStrategy

# Different config
python3 scripts/run_backtest.py --config bot/config.custom.json
```

---

## Phase 3 — Unit Tests

```bash
source scripts/activate.sh
cd bot && python3 -m pytest tests/ -v
```

Tests include:
- RSI always 0–100 ✓
- No buy signals in downtrend (EMA filter) ✓
- No simultaneous buy + sell ✓
- Stoploss is set and not too aggressive ✓
- Bollinger Bands ordering (upper ≥ mid ≥ lower) ✓

---

## Phase 4 — Paper Trading (2+ weeks minimum)

```bash
source scripts/activate.sh
freqtrade trade \
  --config bot/config.paper.json \
  --strategy AIRSIStrategy \
  --logfile bot/user_data/logs/bot.log
```

- Virtual $1,000 USDT wallet
- Watch Telegram for alerts
- Only proceed to live after **2 consistent weeks** of positive results

---

## Going Live Checklist

- [ ] 2+ weeks of paper trading with positive results
- [ ] Backtest Go/No-Go: all 4 checks pass
- [ ] Telegram alerts working (tested manually)
- [ ] Emergency `/stop` command tested
- [ ] Exchange API key created with **NO withdrawal permissions**
- [ ] `max_open_trades: 2` and `stake_amount: 5` in `config.live.json`

```bash
# Start live trading ($5 per trade, max 2 open = $10 total risk)
source scripts/activate.sh
freqtrade trade \
  --config bot/config.live.json \
  --strategy AIRSIStrategy
```
