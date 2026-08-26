"""
Telegram Notifier — sends trade alerts, daily summaries, and crash reports.
Uses the free Telegram Bot API (no cost).
"""

from __future__ import annotations

import os
import sys
import logging
import traceback
from datetime import date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

def _send(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a bounded Telegram message without ever raising to the caller."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        logger.warning("Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    payload = {"chat_id": chat_id, "text": str(text)[:4096]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=10,
        )
        if response.ok:
            return True
        # Markdown is user/content dependent; retry as plain text on parse errors.
        if parse_mode and response.status_code == 400:
            payload.pop("parse_mode", None)
            fallback = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
                timeout=10,
            )
            if fallback.ok:
                return True
        response.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
    return False


def notify_startup(dry_run: bool, pairs: list[str], stake: float) -> None:
    mode = "📄 PAPER TRADING" if dry_run else "💰 LIVE TRADING"
    _send(
        f"🤖 *Bot Started* — {mode}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Pairs: `{', '.join(pairs)}`\n"
        f"Stake per trade: `${stake:.2f} USDT`\n"
        f"Type /status to check at any time."
    )


def notify_trade_entry(pair: str, price: float, stake: float,
                        signal_reason: str, ai_comment: str = "") -> None:
    msg = (
        f"📈 *BUY — {pair}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Price: `${price:.4f}`\n"
        f"Amount: `${stake:.2f} USDT`\n"
        f"Signal: `{signal_reason}`\n"
    )
    if ai_comment:
        msg += f"🤖 AI: _{ai_comment}_"
    _send(msg)


def notify_trade_exit(pair: str, price: float, profit_pct: float,
                       profit_usdt: float, exit_reason: str,
                       ai_comment: str = "") -> None:
    emoji = "✅" if profit_pct >= 0 else "🔴"
    msg = (
        f"{emoji} *{'PROFIT' if profit_pct >= 0 else 'LOSS'} — {pair}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Close Price: `${price:.4f}`\n"
        f"P&L: `{profit_pct:+.2f}%` (`{profit_usdt:+.4f} USDT`)\n"
        f"Reason: `{exit_reason}`\n"
    )
    if ai_comment:
        msg += f"🤖 AI: _{ai_comment}_"
    _send(msg)


def notify_daily_summary(trade_count: int, win_count: int, total_profit_usdt: float,
                          best_trade: Optional[str] = None,
                          worst_trade: Optional[str] = None) -> None:
    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
    profit_emoji = "📈" if total_profit_usdt >= 0 else "📉"
    msg = (
        f"{profit_emoji} *Daily Summary — {date.today().strftime('%b %d, %Y')}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Trades: `{trade_count}`\n"
        f"Win Rate: `{win_rate:.1f}%`\n"
        f"P&L: `{total_profit_usdt:+.4f} USDT`\n"
    )
    if best_trade:
        msg += f"🏆 Best: `{best_trade}`\n"
    if worst_trade:
        msg += f"💀 Worst: `{worst_trade}`\n"
    _send(msg)


def notify_error(context: str, error: Exception) -> None:
    tb = traceback.format_exc()[-800:]
    _send(
        f"🚨 *ERROR — {context}*\n"
        f"```\n{str(error)[:300]}\n```\n"
        f"Last traceback:\n```\n{tb}\n```",
        parse_mode="Markdown",
    )


def notify_crash(exc_type, exc_value, exc_traceback) -> None:
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))[-800:]
    _send(
        f"💥 *BOT CRASHED*\n"
        f"The bot has stopped unexpectedly.\n"
        f"```\n{tb}\n```\n"
        f"Restart manually or check logs.",
        parse_mode="Markdown",
    )


def install_crash_handler() -> None:
    """Hook into Python's global exception handler to alert Telegram on crash."""
    original_hook = sys.excepthook

    def handler(exc_type, exc_value, exc_tb):
        notify_crash(exc_type, exc_value, exc_tb)
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = handler
    logger.info("Telegram crash handler installed.")
