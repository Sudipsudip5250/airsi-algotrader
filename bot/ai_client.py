"""
AI Client — supports Groq (free cloud) and Ollama (free local).
Falls back gracefully: Groq → Ollama → plain text summary.
"""

from __future__ import annotations

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class GroqClient:
    """Groq free-tier client (14 400 req/day on LLaMA 3 8B)."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama3-8b-8192"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def complete(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        try:
            resp = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Groq request failed: %s", exc)
            return None


class OllamaClient:
    """Local Ollama client — no API key required."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as exc:
            logger.warning("Ollama request failed: %s", exc)
            return None


class AIClient:
    """
    Auto-selects the best available AI backend.
    Priority: Groq (fast, cloud) → Ollama (local) → fallback plain text.
    """

    def __init__(self):
        groq_key = os.getenv("GROQ_API_KEY", "")
        self._groq = GroqClient(groq_key) if groq_key else None
        self._ollama = OllamaClient(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "mistral"),
        )

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        if self._groq:
            result = self._groq.complete(prompt, max_tokens)
            if result:
                return result
        result = self._ollama.complete(prompt, max_tokens)
        if result:
            return result
        return "AI analysis unavailable — check GROQ_API_KEY or Ollama."

    def explain_trade(self, pair: str, action: str, price: float,
                       profit_pct: float, exit_reason: str) -> str:
        prompt = (
            f"Explain this crypto trade in 2 short sentences for a beginner:\n"
            f"Pair: {pair}\n"
            f"Action: {action}\n"
            f"Price: ${price:.4f}\n"
            f"Profit/Loss: {profit_pct:+.2f}%\n"
            f"Exit reason: {exit_reason}\n"
            f"Be concise. Do not use jargon."
        )
        return self.complete(prompt, max_tokens=120)

    def market_sentiment(self, pair: str, rsi: float, trend: str) -> str:
        prompt = (
            f"Give a one-sentence market sentiment for {pair}.\n"
            f"RSI: {rsi:.1f}, Trend: {trend}.\n"
            f"Is this a good time to enter a long trade? Answer in plain English."
        )
        return self.complete(prompt, max_tokens=80)
