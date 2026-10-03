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
python3 -m pytest bot/tests/test_ai_client.py bot/tests/test_market_intelligence.py -v --noconftest
```

In this container that is 19/19 green. Strategy tests (`test_strategy.py`) need
pandas/numpy + system `libstdc++` + freqtrade, so on a full PC/VPS run the whole suite:

```bash
source scripts/activate.sh
cd bot && python3 -m pytest tests/ -v && cd ..
```

Tests include:
- RSI always 0–100 ✓
- No buy signals in downtrend (EMA filter) ✓
- No simultaneous buy + sell ✓
- Stoploss is set and not too aggressive ✓
- Bollinger Bands ordering (upper ≥ mid ≥ lower) ✓

---

## Phase 4 — Paper Trading (2+ weeks minimum)

Start the intelligence worker in one terminal:

```bash
source scripts/activate.sh
bash scripts/run_intelligence.sh
```

Start the bot in a second terminal (paper-micro mirrors the $5-10 real plan):

```bash
source scripts/activate.sh
bash scripts/run_bot.sh paper-micro
```

`paper` respects `EXCHANGE` in `.env` (`okx` = cheapest 0.08% maker). Smoke-test the
intelligence worker any time without keys:

```bash
source scripts/activate.sh
python3 bot/market_intelligence.py --once
```

The intelligence worker can only veto new entries. It cannot place trades, select pairs, change stake size, set leverage, or close positions. Missing or expired snapshots fail closed.

- Paper-micro: $10 virtual wallet, $5 x1 BTC/USDT (closest to $5-10 real)
- Paper default: $1,000 virtual wallet (legacy template)
- Watch Telegram for alerts
- Only proceed to live after **2 consistent weeks** of positive results

---

## Going Live Checklist

- [ ] 2+ weeks of paper trading with positive results
- [ ] Backtest Go/No-Go: all 4 checks pass
- [ ] Telegram alerts working (tested manually)
- [ ] Emergency `/stop` command tested
- [ ] Exchange API key created with **NO withdrawal permissions**
- [ ] `max_open_trades: 2` and a reviewed stake amount in `config.live.json`
- [ ] Confirm the live profile’s `initial_state: "stopped"` and explicitly start only after this checklist passes

```bash
# Start live trading only after every checklist item is complete.
source scripts/activate.sh
bash scripts/run_bot.sh live
```
