"""Small, failure-tolerant AI client for optional trade commentary.

The strategy must never depend on an LLM response to place or close a trade.
This module is therefore advisory-only: every provider failure falls through to
another provider and finally to a plain-text fallback.
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Client for Groq/OpenRouter-style chat completion endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str, name: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name

    def complete(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "AIRSI AlgoTrader"),
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=20,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return str(content).strip() or None
        except Exception as exc:  # provider failures are expected and isolated
            logger.warning("%s request failed: %s", self.name, exc)
            return None


class HuggingFaceClient:
    """Client for the Hugging Face text-generation inference endpoint."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{quote(self.model, safe='/')}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "inputs": prompt,
                    "parameters": {"max_new_tokens": max_tokens, "temperature": 0.3, "return_full_text": False},
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return str(payload[0].get("generated_text", "")).strip() or None
            return None
        except Exception as exc:
            logger.warning("HuggingFace request failed: %s", exc)
            return None


class OllamaClient:
    """Local Ollama client with no external API key."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.3},
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip() or None
        except Exception as exc:
            logger.warning("Ollama request failed: %s", exc)
            return None


class AIClient:
    """Advisory-only fallback chain: Groq → OpenRouter → HuggingFace → Ollama."""

    def __init__(self):
        groq_key = os.getenv("GROQ_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        hf_key = os.getenv("HUGGINGFACE_API_KEY", "")

        self._providers = []
        if groq_key:
            self._providers.append(
                OpenAICompatibleClient(
                    "https://api.groq.com/openai/v1",
                    groq_key,
                    os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                    "Groq",
                )
            )
        if openrouter_key:
            self._providers.append(
                OpenAICompatibleClient(
                    "https://openrouter.ai/api/v1",
                    openrouter_key,
                    os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
                    "OpenRouter",
                )
            )
        if hf_key:
            self._providers.append(
                HuggingFaceClient(
                    hf_key,
                    os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"),
                )
            )
        self._providers.append(
            OllamaClient(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "mistral"),
            )
        )

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        for provider in self._providers:
            result = provider.complete(prompt, max_tokens)
            if result:
                return result
        return "AI analysis unavailable — trade execution remains unaffected."

    def explain_trade(
        self,
        pair: str,
        action: str,
        price: float,
        profit_pct: float,
        exit_reason: str,
    ) -> str:
        prompt = (
            "Explain this crypto trade in 2 short sentences for a beginner.\n"
            f"Pair: {pair}\nAction: {action}\nPrice: ${price:.4f}\n"
            f"Profit/Loss: {profit_pct:+.2f}%\nExit reason: {exit_reason}\n"
            "Be concise. Do not use jargon."
        )
        return self.complete(prompt, max_tokens=120)

    def market_sentiment(self, pair: str, rsi: float, trend: str) -> str:
        prompt = (
            f"Give a one-sentence market sentiment for {pair}.\n"
            f"RSI: {rsi:.1f}, Trend: {trend}.\n"
            "Is this a good time to enter a long trade? Answer in plain English."
        )
        return self.complete(prompt, max_tokens=80)
