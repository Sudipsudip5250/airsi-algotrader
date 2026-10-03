"""Bounded market intelligence for AIRSI AlgoTrader.

This module is intentionally outside the strategy's candle calculations. A
separate worker collects public market/news context and writes a short-lived
JSON decision snapshot. The strategy can only use that snapshot as a global
risk-off veto; the LLM cannot place orders, choose pairs, set leverage, or
increase position size.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
BINANCE_OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"
DEFAULT_DECISION_PATH = "bot/user_data/market_intelligence.json"
DEFAULT_MODEL = ""
DEFAULT_RSS_URLS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]
_TRUTHY = {"1", "true", "yes", "on"}
_PAID_MODEL_MARKERS = ("gpt-4", "gpt-5", "o1", "o3", "claude", "opus", "sonnet")


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str
    language: str = ""


@dataclass(frozen=True)
class MarketSnapshot:
    collected_at: str
    btc_change_1h: float | None = None
    btc_change_24h: float | None = None
    btc_change_7d: float | None = None
    total_market_cap_change_24h: float | None = None
    btc_funding_rate: float | None = None
    btc_open_interest: float | None = None
    news: list[NewsItem] = field(default_factory=list)


@dataclass(frozen=True)
class IntelligenceDecision:
    generated_at: str
    expires_at: str
    allow_long_entries: bool
    risk_level: str
    confidence: float
    reason: str
    source_count: int
    news_count: int
    model: str
    snapshot_hash: str
    errors: list[str] = field(default_factory=list)


class IntelligenceError(RuntimeError):
    """Raised when required market-intelligence data cannot be collected."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _get_json(url: str, params: dict[str, Any], timeout: float = 10.0) -> Any:
    response = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "AIRSI-AlgoTrader/1.0"})
    response.raise_for_status()
    return response.json()


def fetch_gdelt_news(query: str = "bitcoin OR ethereum OR crypto", timespan: str = "1h", maxrecords: int = 40) -> list[NewsItem]:
    """Fetch recent article metadata from the public GDELT DOC API."""
    payload = _get_json(
        GDELT_URL,
        {
            "query": f"({query})",
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "timespan": timespan,
            "sort": "datedesc",
        },
    )
    if not isinstance(payload, dict):
        raise IntelligenceError("GDELT returned a non-object payload")

    items: list[NewsItem] = []
    for article in payload.get("articles", []):
        if not isinstance(article, dict):
            continue
        title = str(article.get("title", "")).strip()
        url = str(article.get("url", "")).strip()
        if not title or not url:
            continue
        items.append(
            NewsItem(
                title=title[:400],
                url=url[:1000],
                source=str(article.get("domain", "unknown"))[:200],
                published_at=str(article.get("seendate", ""))[:40],
                language=str(article.get("language", ""))[:40],
            )
        )
    return items


def fetch_rss_news(feed_urls: list[str]) -> list[NewsItem]:
    """Fetch simple RSS/Atom feeds without adding a feed-parser dependency."""
    items: list[NewsItem] = []
    for feed_url in feed_urls:
        try:
            response = requests.get(feed_url, timeout=10, headers={"User-Agent": "AIRSI-AlgoTrader/1.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (OSError, ET.ParseError, requests.RequestException) as exc:
            logger.warning("RSS feed failed (%s): %s", feed_url, exc)
            continue
        for entry in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            def text(*tags: str) -> str:
                for tag in tags:
                    child = entry.find(tag)
                    if child is not None and child.text:
                        return child.text.strip()
                return ""

            title = text("title", "{http://www.w3.org/2005/Atom}title")
            link = text("link", "{http://www.w3.org/2005/Atom}link")
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                link = str(atom_link.attrib.get("href", "")) if atom_link is not None else ""
            if title and link:
                items.append(NewsItem(title[:400], link[:1000], feed_url[:200], text("pubDate", "published", "updated")[:40]))
    return items


def _optional_float(value: Any) -> float | None:
    """Convert a provider value to a finite float or return ``None``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fetch_market_snapshot() -> MarketSnapshot:
    """Collect public market context used by the deterministic gate."""
    market_rows = _get_json(
        COINGECKO_URL,
        {
            "vs_currency": "usd",
            "ids": "bitcoin,ethereum",
            "price_change_percentage": "1h,24h,7d",
            "per_page": 2,
            "page": 1,
        },
    )
    if not isinstance(market_rows, list):
        raise IntelligenceError("CoinGecko markets returned a non-list payload")
    bitcoin = next((row for row in market_rows if isinstance(row, dict) and row.get("id") == "bitcoin"), None)
    global_payload = _get_json(COINGECKO_GLOBAL_URL, {})
    global_market = global_payload.get("data") if isinstance(global_payload, dict) else None
    funding = _get_json(BINANCE_FUNDING_URL, {"symbol": "BTCUSDT"})
    open_interest = _get_json(BINANCE_OI_URL, {"symbol": "BTCUSDT"})
    if not isinstance(bitcoin, dict) or not isinstance(global_market, dict):
        raise IntelligenceError("Required market data is missing")
    if not isinstance(funding, dict) or not isinstance(open_interest, dict):
        raise IntelligenceError("Required derivatives data is malformed")
    return MarketSnapshot(
        collected_at=_iso(_now()),
        btc_change_1h=_optional_float(bitcoin.get("price_change_percentage_1h_in_currency")),
        btc_change_24h=_optional_float(bitcoin.get("price_change_percentage_24h_in_currency")),
        btc_change_7d=_optional_float(bitcoin.get("price_change_percentage_7d_in_currency")),
        total_market_cap_change_24h=_optional_float(global_market.get("market_cap_change_percentage_24h_usd")),
        btc_funding_rate=_optional_float(funding.get("lastFundingRate")),
        btc_open_interest=_optional_float(open_interest.get("openInterest")),
    )


def deterministic_risk(snapshot: MarketSnapshot) -> tuple[str, bool, str]:
    """Apply a transparent risk-off policy before consulting the LLM.

    A decision cannot be permissive without the two core market inputs. This
    keeps provider outages and malformed payloads fail-closed rather than
    silently turning into a normal-risk decision.
    """
    reasons: list[str] = []
    missing: list[str] = []
    score = 0
    if snapshot.btc_change_24h is None:
        missing.append("BTC 24h movement")
    else:
        if snapshot.btc_change_24h <= -4:
            score += 2
            reasons.append("BTC 24h move is below -4%")
        elif snapshot.btc_change_24h <= -2:
            score += 1
            reasons.append("BTC 24h move is below -2%")
    if snapshot.btc_change_1h is not None and snapshot.btc_change_1h <= -1.5:
        score += 1
        reasons.append("BTC 1h move is sharply negative")
    if snapshot.total_market_cap_change_24h is None:
        missing.append("total market capitalization movement")
    elif snapshot.total_market_cap_change_24h <= -4:
        score += 1
        reasons.append("total crypto market capitalization is down more than 4% in 24h")
    if missing:
        reasons.append(f"missing {', '.join(missing)}")
        return "high", False, "; ".join(reasons) + "; fail-safe veto is active"
    if snapshot.btc_funding_rate is not None and abs(snapshot.btc_funding_rate) >= 0.0008:
        score += 1
        reasons.append("BTC funding rate is unusually large")
    if score >= 3:
        return "high", False, "; ".join(reasons)
    if score == 2:
        return "elevated", False, "; ".join(reasons)
    if score == 1:
        return "guarded", True, "; ".join(reasons)
    return "normal", True, "No deterministic risk-off threshold was triggered"


def _allow_paid() -> bool:
    return os.getenv("AI_ALLOW_PAID", "").strip().lower() in _TRUTHY


def _hostname(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = urlparse(text).hostname
    return (host or "").lower().rstrip(".")


def _host_is(value: str, *domains: str) -> bool:
    """True when the URL hostname is exactly a domain or a subdomain of it."""
    host = _hostname(value)
    if not host:
        return False
    for domain in domains:
        needle = domain.lower().rstrip(".")
        if host == needle or host.endswith("." + needle):
            return True
    return False


def _looks_paid(base: str, model: str) -> bool:
    model_l = (model or "").lower()
    if ":free" in model_l or model_l == "openrouter/free":
        return False
    if "pollinations" in (base or "").lower():
        return False
    if _host_is(base, "openai.com"):
        return True
    return any(marker in model_l for marker in _PAID_MODEL_MARKERS)


def _llm_candidates() -> list[tuple[str, str, str, str, str]]:
    """Return ordered (provider, base, key, model, cost_class) candidates.

    API-only, no local daemon. Order: custom LLM_API_* -> Groq ->
    Gemini -> OpenRouter :free -> Pollinations keyless (free-trial last resort).
    Paid entries are filtered unless AI_ALLOW_PAID=1.
    """
    paid_ok = _allow_paid()
    candidates: list[tuple[str, str, str, str, str]] = []

    base = os.getenv("LLM_API_BASE", "").strip()
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip()
    if key and base:
        if _looks_paid(base, model) and not paid_ok:
            logger.info(
                "Skipping paid intelligence LLM base=%s model=%s cost_class=paid "
                "(set AI_ALLOW_PAID=1 to enable); trying next provider",
                base,
                model or "(unset)",
            )
        else:
            if _looks_paid(base, model):
                cost = "paid"
            elif _host_is(base, "groq.com", "googleapis.com") or ":free" in model.lower() or "pollinations" in base.lower():
                cost = "free"
            else:
                cost = "low"
            candidates.append(("custom", base.rstrip("/"), key, model or "openai/gpt-oss-20b", cost))

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        # Deprecated 08/16/26: llama-3.1-8b-instant, llama-3.3-70b-versatile.
        groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
        candidates.append(("Groq", "https://api.groq.com/openai/v1", groq_key, groq_model, "free"))

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        candidates.append((
            "Gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            gemini_key,
            gemini_model,
            "free",
        ))

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        or_model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
        is_free = ":free" in or_model.lower() or or_model == "openrouter/free"
        if is_free or paid_ok:
            candidates.append((
                "OpenRouter",
                "https://openrouter.ai/api/v1",
                openrouter_key,
                or_model,
                "free" if is_free else "paid",
            ))

    # Keyless last resort for free trial — anon ~1 req/15s, commentary-grade.
    if os.getenv("POLLINATIONS_DISABLED", "").strip().lower() not in _TRUTHY:
        poll_model = os.getenv("POLLINATIONS_MODEL", "openai").strip() or "openai"
        candidates.append((
            "Pollinations",
            "https://text.pollinations.ai/openai",
            "",
            poll_model,
            "free",
        ))

    return candidates


def _llm_settings() -> tuple[str, str, str, str]:
    """Return base, key, model, cost_class for first candidate. Empty key = deterministic-only.

    Keeps backward-compat single-tuple signature. Pollinations returns key=""
    but is still a usable keyless candidate — callers must check base/model,
    not just key. Use _llm_candidates() for full chain.
    """
    candidates = _llm_candidates()
    # Prefer keyed providers first; Pollinations keyless is last resort.
    for provider, base, key, model, cost in candidates:
        if key:
            logger.info("Intelligence LLM provider=%s cost_class=%s model=%s", provider, cost, model)
            return base, key, model, cost
    for provider, base, key, model, cost in candidates:
        if provider == "Pollinations":
            logger.info("Intelligence LLM provider=Pollinations cost_class=free model=%s (keyless fallback)", model)
            return base, key, model, cost
    return "", "", "", "free"


def _normalize_risk(value: object) -> str:
    """Map model variants (Low/moderate/Medium...) to strict enum."""
    text = str(value or "").strip().lower()
    mapping = {
        "low": "normal", "minimal": "normal", "none": "normal", "neutral": "normal",
        "moderate": "guarded", "medium": "guarded", "caution": "guarded",
        "normal": "normal", "guarded": "guarded", "elevated": "elevated", "high": "high",
    }
    return mapping.get(text, "")


def _parse_confidence(value: object) -> float:
    try:
        return min(1.0, max(0.0, float(str(value).strip().rstrip("%"))))
    except (TypeError, ValueError):
        lowered = str(value or "").strip().lower()
        return {"low": 0.3, "medium": 0.55, "moderate": 0.55, "high": 0.8}.get(lowered, 0.0)


def _parse_risk_json(content: str) -> dict[str, object]:
    """Parse LLM risk JSON robustly: strip fences, extract {...}, reject quota text.

    Falls back to field-level extraction when the model output is truncated
    (reasoning models can exhaust the token budget mid-string).
    """
    import re

    text = (content or "").strip()
    lowered = text.lower()
    for marker in ("reached its budget", "raise the key budget", "rate limit", "too many requests"):
        if marker in lowered:
            raise ValueError(f"LLM returned quota/error text: {text[:120]}")
    if text.startswith("```"):
        # strip ```json ... ``` fences (Gemini often wraps)
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    if "{" in text and "}" in text:
        text = text[text.index("{"):text.rindex("}") + 1]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("LLM JSON is not an object")
    except json.JSONDecodeError:
        pass
    # Truncated output: extract fields individually, tolerate a cut-off reason.
    fields: dict[str, object] = {}
    risk_match = re.search(r'"risk_level"\s*:\s*"([^"]*)', text)
    allow_match = re.search(r'"allow_long_entries"\s*:\s*(true|false)', text, re.IGNORECASE)
    conf_match = re.search(r'"confidence"\s*:\s*"?([0-9]*\.?[0-9]+|low|medium|moderate|high)', text, re.IGNORECASE)
    reason_match = re.search(r'"reason"\s*:\s*"([\s\S]*)', text)
    if not risk_match or not allow_match:
        raise ValueError(f"LLM JSON unrecoverable (truncated): {text[:160]}")
    fields["risk_level"] = risk_match.group(1)
    fields["allow_long_entries"] = allow_match.group(1).lower() == "true"
    conf_raw = conf_match.group(1) if conf_match else "0.0"
    try:
        fields["confidence"] = float(conf_raw)
    except (TypeError, ValueError):
        fields["confidence"] = conf_raw
    reason = reason_match.group(1) if reason_match else ""
    # Strip a trailing partial escape / cut-off tail.
    reason = re.sub(r'\\?$', '', reason).strip()
    fields["reason"] = reason[:280]
    return fields


def classify_news(snapshot: MarketSnapshot) -> tuple[str, bool, float, str, str]:
    """Ask an OpenAI-compatible model for structured risk classification.

    Tries candidates in order: custom -> Groq -> Gemini -> OpenRouter :free
    -> Pollinations keyless. The model is explicitly not asked for a trade,
    price prediction, leverage, or position size. If all fail, deterministic
    risk remains the only decision source.
    """
    deterministic_level, deterministic_allow, deterministic_reason = deterministic_risk(snapshot)
    if deterministic_level in {"high", "elevated"}:
        return deterministic_level, False, 1.0, deterministic_reason, "deterministic"
    if not snapshot.news:
        return deterministic_level, deterministic_allow, 0.5, deterministic_reason, "deterministic"

    candidates = _llm_candidates()
    # Keyed first, Pollinations keyless last.
    ordered = [c for c in candidates if c[2]] + [c for c in candidates if not c[2]]
    if not ordered:
        return deterministic_level, deterministic_allow, 0.5, deterministic_reason, "deterministic"

    # Compact payload: Groq free tier rejects oversized requests (HTTP 413) and
    # every provider bills per input token. Send numerics + a short headline
    # list only — never the full news objects (asdict(snapshot) embeds them all).
    compact_market = {
        "btc_change_1h": snapshot.btc_change_1h,
        "btc_change_24h": snapshot.btc_change_24h,
        "btc_change_7d": snapshot.btc_change_7d,
        "total_market_cap_change_24h": snapshot.total_market_cap_change_24h,
        "btc_funding_rate": snapshot.btc_funding_rate,
        "btc_open_interest": snapshot.btc_open_interest,
        "news_count": len(snapshot.news),
    }
    headlines: list[str] = []
    for item in snapshot.news[:12]:
        title = (item.title or "")[:150]
        source = (item.source or "")[:60]
        if title:
            headlines.append(f"- {title} | {source}")
    articles = "\n".join(headlines)
    user_payload = {
        "market": compact_market,
        "articles": articles,
        "instruction": "Classify only near-term market risk for long entries. Do not forecast a price and do not propose a trade.",
    }
    schema = {
        "type": "object",
        "properties": {
            "risk_level": {"type": "string", "enum": ["normal", "guarded", "elevated", "high"]},
            "allow_long_entries": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 280},
        },
        "required": ["risk_level", "allow_long_entries", "confidence", "reason"],
        "additionalProperties": False,
    }
    last_exc: Exception | None = None
    for provider, base, key, model, cost_class in ordered:
        content = ""
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            system_msg = "You are a market-risk classifier. Return JSON only with keys risk_level (one of: normal, guarded, elevated, high), allow_long_entries (boolean), confidence (number 0-1), reason (string). You are not a trader. Never recommend a buy, sell, leverage, or position size."
            user_msg = json.dumps(user_payload, separators=(",", ":"))
            # Groq gpt-oss intermittently 400s strict json_schema; plain
            # json_object works reliably there, so lead with it for Groq.
            attempts = ("plain", "schema") if provider == "Groq" else ("schema", "plain")
            content = ""
            attempt_exc: Exception | None = None
            for mode in attempts:
                try:
                    body: dict[str, object] = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_completion_tokens": 1500,
                    }
                    if mode == "schema":
                        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "market_risk", "strict": True, "schema": schema}}
                    else:
                        body["response_format"] = {"type": "json_object"}
                    response = requests.post(
                        f"{base}/chat/completions",
                        headers=headers,
                        timeout=30,
                        json=body,
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    break
                except Exception as mode_exc:
                    attempt_exc = mode_exc
                    logger.warning("Intelligence LLM %s %s mode failed, retrying: %s", provider, mode, mode_exc)
            else:
                raise attempt_exc or RuntimeError("LLM attempts exhausted")
            result = _parse_risk_json(content)
            model_risk = _normalize_risk(result.get("risk_level"))
            if not model_risk:
                raise ValueError(f"LLM returned invalid risk level: {result.get('risk_level')}")
            confidence = _parse_confidence(result.get("confidence"))
            risk_order = {"normal": 0, "guarded": 1, "elevated": 2, "high": 3}
            risk = max((deterministic_level, model_risk), key=lambda level: risk_order[level])
            allow = deterministic_allow and bool(result["allow_long_entries"]) and risk not in {"high", "elevated"} and confidence >= 0.60
            reason = str(result.get("reason", ""))[:280]
            if deterministic_reason and deterministic_level != "normal":
                reason = f"{deterministic_reason}; {reason}"
            logger.info("Intelligence LLM provider=%s cost_class=%s model=%s", provider, cost_class, model)
            return risk, allow, confidence, reason, f"{provider}:{model}"
        except Exception as exc:
            last_exc = exc
            logger.warning("Intelligence LLM %s failed, trying next: %s", provider, exc)
            continue
    risk, allow, reason = deterministic_risk(snapshot)
    detail = f": {last_exc}" if last_exc else ""
    return risk, allow, 0.0, f"LLM unavailable; deterministic fallback: {reason}{detail}", "deterministic-fallback"


def create_decision() -> IntelligenceDecision:
    errors: list[str] = []
    try:
        market = fetch_market_snapshot()
    except Exception as exc:
        errors.append(f"market data: {type(exc).__name__}: {exc}")
        return fail_safe_decision(errors)
    try:
        news = fetch_gdelt_news()
    except Exception as exc:
        errors.append(f"news data: {type(exc).__name__}: {exc}")
        news = []
    configured_feeds = os.getenv("NEWS_RSS_URLS")
    rss_urls = [item.strip() for item in configured_feeds.split(",") if item.strip()] if configured_feeds else DEFAULT_RSS_URLS
    if rss_urls:
        try:
            news.extend(fetch_rss_news(rss_urls))
        except Exception as exc:
            errors.append(f"rss data: {type(exc).__name__}: {exc}")
    unique_news = list({item.url: item for item in news}.values())
    market = MarketSnapshot(**{**asdict(market), "news": unique_news})
    started = _now()
    risk, allow, confidence, reason, model = classify_news(market)
    latency_ms = int((_now() - started).total_seconds() * 1000)
    generated = _now()
    ttl_raw = os.getenv("INTELLIGENCE_TTL_SECONDS", "1800")
    try:
        ttl_seconds = min(86_400, max(60, int(ttl_raw)))
    except ValueError:
        ttl_seconds = 1_800
    expires = generated.timestamp() + ttl_seconds
    digest = hashlib.sha256(json.dumps(asdict(market), sort_keys=True).encode()).hexdigest()[:16]
    decision = IntelligenceDecision(
        generated_at=_iso(generated),
        expires_at=_iso(datetime.fromtimestamp(expires, timezone.utc)),
        allow_long_entries=allow,
        risk_level=risk,
        confidence=confidence,
        reason=reason,
        source_count=1 + len({item.source for item in unique_news}),
        news_count=len(unique_news),
        model=model,
        snapshot_hash=digest,
        errors=errors,
    )
    # Best-effort self-tracking for future improvement. Never blocks veto.
    try:
        from ai_tracker import log_ai_decision

        provider = model.split(":", 1)[0] if ":" in model else model
        log_ai_decision(
            agent="risk-guard",
            provider=provider,
            model=model,
            cost_class="free",
            snapshot_hash=digest,
            market={
                "btc_change_1h": market.btc_change_1h,
                "btc_change_24h": market.btc_change_24h,
                "btc_change_7d": market.btc_change_7d,
                "total_market_cap_change_24h": market.total_market_cap_change_24h,
                "btc_funding_rate": market.btc_funding_rate,
                "btc_open_interest": market.btc_open_interest,
                "news_count": len(unique_news),
                "source_count": 1 + len({item.source for item in unique_news}),
            },
            action={
                "allow_long_entries": allow,
                "risk_level": risk,
                "confidence": confidence,
                "reason": reason,
            },
            latency_ms=latency_ms,
            errors=errors,
        )
    except Exception:
        pass
    return decision


def fail_safe_decision(errors: list[str]) -> IntelligenceDecision:
    generated = _now()
    expires = generated.timestamp() + 300
    return IntelligenceDecision(
        generated_at=_iso(generated),
        expires_at=_iso(datetime.fromtimestamp(expires, timezone.utc)),
        allow_long_entries=False,
        risk_level="high",
        confidence=1.0,
        reason="Market intelligence unavailable; fail-safe veto is active",
        source_count=0,
        news_count=0,
        model="none",
        snapshot_hash="unavailable",
        errors=errors,
    )


def write_decision(decision: IntelligenceDecision, path: str | Path = DEFAULT_DECISION_PATH) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(asdict(decision), handle, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_decision(path: str | Path = DEFAULT_DECISION_PATH, now: datetime | None = None) -> IntelligenceDecision | None:
    """Read a complete, timezone-aware, unexpired decision snapshot."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        decision = IntelligenceDecision(**payload)
        expiry = datetime.fromisoformat(decision.expires_at)
        generated = datetime.fromisoformat(decision.generated_at)
        if expiry.tzinfo is None or generated.tzinfo is None:
            return None
        if not isinstance(decision.allow_long_entries, bool):
            return None
        if decision.risk_level not in {"normal", "guarded", "elevated", "high"}:
            return None
        if not 0.0 <= decision.confidence <= 1.0 or not math.isfinite(decision.confidence):
            return None
        if decision.source_count < 0 or decision.news_count < 0:
            return None
        if any(not isinstance(error, str) for error in decision.errors):
            return None
        reference = (now or _now()).astimezone(timezone.utc)
        if expiry.astimezone(timezone.utc) <= reference:
            return None
        return decision
    except (OSError, ValueError, TypeError, OverflowError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the AIRSI AlgoTrader market-intelligence decision")
    parser.add_argument("--once", action="store_true", help="Refresh once and exit")
    parser.add_argument("--interval", type=int, default=900, help="Seconds between refreshes")
    parser.add_argument("--output", default=os.getenv("INTELLIGENCE_DECISION_PATH", DEFAULT_DECISION_PATH))
    args = parser.parse_args()
    while True:
        decision = create_decision()
        write_decision(decision, args.output)
        print(json.dumps(asdict(decision), sort_keys=True))
        if args.once:
            return 0
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
