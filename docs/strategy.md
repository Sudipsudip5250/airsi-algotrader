# AIRSIStrategy

RSI + EMA + Bollinger Bands trading strategy for Freqtrade.

---

## Logic

### Entry Conditions (all must be true)

1. **Uptrend** — `close > EMA50` (50-period EMA filter)
2. **Oversold** — `RSI < 35` (14-period RSI)
3. **Volume spike** — `volume > volume_mean` (above average)
4. **Below lower band** — `close < bb_lower` (Bollinger Bands)

### Exit Conditions (any one triggers)

1. **Overbought** — `RSI > 70`
2. **Above upper band** — `close > bb_upper`
3. **ROI target reached** — `minimal_roi` table

### Risk Parameters

| Parameter | Value |
|---|---|
| Stoploss | -3.5% (`-0.035`) |
| Trailing stop | On (offset: 2%, trigger: 1%) |
| Max open trades | 2 |
| Minimal ROI | 6% (immediate), 4% (30m), 2% (1h), 1% (2h) |
| Startup candles | 60 (needs 60h of warmup data) |

---

## Customization

Edit `bot/strategies/AIRSIStrategy.py`. Key parameters to tune:

```python
# RSI thresholds (default: entry < 35, exit > 70)
rsi_entry = IntParameter(25, 45, default=35, space="buy")
rsi_exit  = IntParameter(65, 85, default=70, space="sell")

# EMA period (default: 50)
ema_period = IntParameter(20, 100, default=50, space="buy")

# Bollinger Bands (default: 20,2)
bb_period = IntParameter(10, 30, default=20, space="buy")
bb_std    = DecimalParameter(1.5, 3.0, default=2.0, space="buy")
```

---

## Hyperopt (Auto-Tuning)

```bash
source scripts/activate.sh
freqtrade hyperopt \
  --config bot/config.paper.json \
  --strategy AIRSIStrategy \
  --epochs 100 \
  --spaces buy sell roi stoploss trailing
```

---

## Indicators Reference

| Indicator | Source | Purpose |
|---|---|---|
| RSI (14) | Built-in `ta` library | Overbought/oversold |
| EMA (50) | Built-in `ta` library | Trend direction |
| BB (20, 2) | Built-in `ta` library | Volatility & support/resistance |
| Volume SMA (24) | Manual calculation | Volume spike filter |
