"""Small, failure-tolerant AI client for optional trade commentary.

The strategy must never depend on an LLM response to place or close a trade.
This module is therefore advisory-only: every provider failure falls through to
another provider and finally to a plain-text fallback.

Default order is free-first: Ollama (when reachable) → Groq free tier →
Hugging Face free tier → OpenRouter free models → plain text. Paid models are
skipped unless AI_ALLOW_PAID is enabled.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

PLAIN_TEXT_FALLBACK = "AI analysis unavailable — trade execution remains unaffected."
_TRUTHY = {"1", "true", "yes", "on"}


def allow_paid_providers() -> bool:
    """Paid models are opt-in so routine loops stay on free/local providers."""
    return os.getenv("AI_ALLOW_PAID", "").strip().lower() in _TRUTHY


def _cost_class_for_model(provider_name: str, model: str, *, local: bool = False) -> str:
    if local:
        return "free"
    lowered = f"{provider_name} {model}".lower()
    if ":free" in lowered or provider_name in {"Groq", "HuggingFace", "Ollama"}:
        return "free"
    if any(token in lowered for token in ("gpt-4", "gpt-5", "o1", "o3", "claude", "opus", "sonnet")):
        return "paid"
    return "low"


@dataclass(frozen=True)
class CompletionResult:
    """Commentary plus the provider/cost metadata operators need to control spend."""

    text: str
    provider: str
    cost_class: str
    cached: bool = False

    def log_line(self) -> str:
        cached = " cached" if self.cached else ""
        return f"provider={self.provider} cost_class={self.cost_class}{cached}"


class OpenAICompatibleClient:
    """Client for Groq/OpenRouter-style chat completion endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str, name: str, cost_class: str = "free"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name
        self.cost_class = cost_class

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

    name = "HuggingFace"
    cost_class = "free"

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

    name = "Ollama"
    cost_class = "free"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        """Cheap reachability probe so missing local Ollama does not stall the chain."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            return bool(response.ok)
        except Exception:
            return False

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
    """Advisory-only fallback chain: Ollama → Groq → HuggingFace → OpenRouter free."""

    def __init__(self):
        self._providers: list[object] | None = None
        self._static_providers: list[object] = []
        self._ollama = OllamaClient(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "mistral"),
        )
        groq_key = os.getenv("GROQ_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        hf_key = os.getenv("HUGGINGFACE_API_KEY", "")
        paid_ok = allow_paid_providers()

        if groq_key:
            groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            self._static_providers.append(
                OpenAICompatibleClient(
                    "https://api.groq.com/openai/v1",
                    groq_key,
                    groq_model,
                    "Groq",
                    cost_class=_cost_class_for_model("Groq", groq_model),
                )
            )
        if hf_key:
            self._static_providers.append(
                HuggingFaceClient(
                    hf_key,
                    os.getenv("HUGGINGFACE_MODEL", "HuggingFaceH4/zephyr-7b-beta"),
                )
            )
        if openrouter_key:
            openrouter_model = os.getenv(
                "OPENROUTER_MODEL",
                "meta-llama/llama-3.1-8b-instruct:free",
            )
            openrouter_free = ":free" in openrouter_model.lower()
            if openrouter_free or paid_ok:
                self._static_providers.append(
                    OpenAICompatibleClient(
                        "https://openrouter.ai/api/v1",
                        openrouter_key,
                        openrouter_model,
                        "OpenRouter",
                        cost_class=_cost_class_for_model("OpenRouter", openrouter_model),
                    )
                )
            else:
                logger.info(
                    "Skipping paid OpenRouter model %s; set AI_ALLOW_PAID=1 or use a :free model",
                    openrouter_model,
                )

    def _live_providers(self) -> list[object]:
        """Rebuild the live chain so a newly started Ollama instance is preferred."""
        if self._providers is not None:
            return self._providers
        providers: list[object] = []
        if self._ollama.available():
            providers.append(self._ollama)
        providers.extend(self._static_providers)
        return providers

    def complete_with_meta(self, prompt: str, max_tokens: int = 200) -> CompletionResult:
        """Return commentary and the provider/cost class used for this call."""
        if not isinstance(prompt, str) or not prompt.strip():
            result = CompletionResult(PLAIN_TEXT_FALLBACK, "none", "free")
            logger.info("AI %s", result.log_line())
            return result
        max_tokens = max(1, min(int(max_tokens), 2_000))
        for provider in self._live_providers():
            name = getattr(provider, "name", type(provider).__name__)
            cost_class = getattr(provider, "cost_class", "low")
            if cost_class == "paid" and not allow_paid_providers():
                logger.info("Skipping paid provider %s (AI_ALLOW_PAID is not set)", name)
                continue
            try:
                text = provider.complete(prompt, max_tokens)
            except Exception as exc:  # a custom provider must not break fallback
                logger.warning("%s provider failed: %s", name, exc)
                continue
            if isinstance(text, str) and text.strip():
                result = CompletionResult(text.strip(), name, cost_class)
                logger.info("AI %s", result.log_line())
                return result
        result = CompletionResult(PLAIN_TEXT_FALLBACK, "none", "free")
        logger.info("AI %s", result.log_line())
        return result

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        """Return commentary without allowing provider failures to escape."""
        return self.complete_with_meta(prompt, max_tokens).text

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
