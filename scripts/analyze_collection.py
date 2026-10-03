"""Grade the paper-collection ledger for the option-1 research plan.

Reads experiments/ai-decisions.jsonl (+ joined trade outcomes) and optional
1h klines, then reports:
  - veto behavior (allow rate, risk mix, provider mix)
  - paper P/L (win rate, avg win/loss, profit factor, fees)
  - avoided-loss estimate: buy-and-hold BTC return in the TTL window after
    each BLOCKED decision (what the veto kept us out of)
  - readiness verdict: keep collecting vs ready for asymmetry-fix analysis

Usage:
  python scripts/analyze_collection.py
  python scripts/analyze_collection.py --ledger experiments/ai-decisions.jsonl
Run any time; run first sync_paper_outcomes.py so closed trades are included.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_DECISIONS = 200
MIN_TRADES = 5


def load_ledger(path: Path) -> tuple[list[dict], list[dict]]:
    decisions, outcomes = [], []
    if not path.exists():
        return decisions, outcomes
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if rec.get("event") == "ai_decision":
            decisions.append(rec)
        elif rec.get("event") == "trade_outcome":
            outcomes.append(rec)
    return decisions, outcomes


def avoided_loss_estimate(decisions: list[dict]) -> dict:
    """BTC buy-and-hold return after each blocked decision (TTL window).

    Needs pandas + downloaded 1h klines; skips gracefully without them.
    """
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError:
        return {"status": "skipped (pandas unavailable)"}
    feather = ROOT / "bot" / "user_data" / "data" / "BTC_USDT-1h.feather"
    if not feather.exists():
        return {"status": "skipped (no klines; run download_data.py)"}
    try:
        klines = pd.read_feather(feather).sort_values("date")
    except Exception as exc:
        return {"status": f"skipped ({exc})"}
    klines["date"] = pd.to_datetime(klines["date"], utc=True)
    closes = klines.set_index("date")["close"].astype(float)

    rets: list[float] = []
    for dec in decisions:
        action = dec.get("action", {})
        if not isinstance(action, dict) or action.get("allow_long_entries") is not False:
            continue
        try:
            start = datetime.fromisoformat(str(dec["timestamp"])).astimezone(timezone.utc)
        except (ValueError, TypeError, KeyError):
            continue
        window = closes.loc[start : start + pd.Timedelta(minutes=30)]
        if len(window) >= 2:
            rets.append(float(window.iloc[-1] / window.iloc[0] - 1))
    if not rets:
        return {"status": "no blocked windows with kline coverage yet (re-run download_data.py weekly)"}
    avg = sum(rets) / len(rets)
    return {
        "status": "ok",
        "blocked_windows": len(rets),
        "avg_bh_return_after_block_pct": round(avg * 100, 3),
        "median_bh_return_after_block_pct": round(float(sorted(rets)[len(rets) // 2]) * 100, 3),
        "negative_windows_pct": round(sum(1 for r in rets if r < 0) / len(rets) * 100, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade the paper-collection ledger")
    parser.add_argument("--ledger", default=os.getenv("AI_DECISIONS_PATH", "experiments/ai-decisions.jsonl"))
    args = parser.parse_args()

    ledger = Path(args.ledger)
    if not ledger.is_absolute():
        ledger = ROOT / ledger
    decisions, outcomes = load_ledger(ledger)

    print("=" * 60)
    print("PAPER COLLECTION REPORT")
    print("=" * 60)
    print(f"Ledger: {ledger} ({len(decisions)} decisions, {len(outcomes)} outcomes)")

    print("\n--- Veto behavior ---")
    risk = Counter(
        d.get("action", {}).get("risk_level", "?") for d in decisions if isinstance(d.get("action"), dict)
    )
    prov = Counter(str(d.get("provider", "?")) for d in decisions)
    allows = sum(1 for d in decisions if isinstance(d.get("action"), dict) and d["action"].get("allow_long_entries") is True)
    print(f"Allow rate: {allows}/{len(decisions)}", f"({allows / max(len(decisions), 1) * 100:.1f}%)" if decisions else "")
    print("Risk mix:", dict(risk) or "(none yet)")
    print("Providers:", dict(prov) or "(none yet)")

    print("\n--- Paper P/L ---")
    if not outcomes:
        print("No closed trades yet. (Freqtrade creates its DB on the first fill;")
        print(" run scripts/sync_paper_outcomes.py after trades close.)")
        pnl_total = 0.0
        wins = losses = 0
    else:
        pnls = [float(o.get("profit_abs", 0.0) or 0.0) for o in outcomes]
        fees = sum(float(o.get("fees", 0.0) or 0.0) for o in outcomes)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        pnl_total = sum(pnls)
        avg_win = sum(p for p in pnls if p > 0) / max(wins, 1)
        avg_loss = sum(p for p in pnls if p <= 0) / max(losses, 1)
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p <= 0))
        print(f"Trades: {len(pnls)}  Win rate: {wins / max(len(pnls), 1) * 100:.1f}%")
        print(f"Total P/L: {pnl_total:+.4f} USDT  (fees paid: {fees:.4f})")
        print(f"Avg win: {avg_win:+.4f}  Avg loss: {avg_loss:+.4f}")
        print(f"Profit factor: {(gross_profit / gross_loss) if gross_loss else float('inf'):.2f}")
        if avg_loss < 0 and avg_win < abs(avg_loss):
            print("NOTE: winners still smaller than losers — the asymmetry to fix.")

    print("\n--- Avoided-loss estimate (blocked windows) ---")
    for key, value in avoided_loss_estimate(decisions).items():
        print(f"{key}: {value}")

    print("\n--- Verdict ---")
    ready = len(decisions) >= MIN_DECISIONS and len(outcomes) >= MIN_TRADES
    if ready:
        print("READY: enough evidence for the asymmetry-fix analysis.")
    else:
        missing = []
        if len(decisions) < MIN_DECISIONS:
            missing.append(f"{MIN_DECISIONS - len(decisions)} more decisions (~{(MIN_DECISIONS - len(decisions)) * 15 // 60}h)")
        if len(outcomes) < MIN_TRADES:
            missing.append(f"{MIN_TRADES - len(outcomes)} more closed paper trades")
        print("KEEP COLLECTING: " + "; ".join(missing) + ".")
        print("Bot stays on paper. Nothing changes in production until READY.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
