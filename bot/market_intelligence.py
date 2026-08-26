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

import requests

logger = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
BINANCE_OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"
DEFAULT_DECISION_PATH = "bot/user_data/market_intelligence.json"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_RSS_URLS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


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


def _llm_settings() -> tuple[str, str, str]:
    base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
    return base.rstrip("/"), key, model


def classify_news(snapshot: MarketSnapshot) -> tuple[str, bool, float, str, str]:
    """Ask an OpenAI-compatible model for structured risk classification.

    The model is explicitly not asked for a trade, price prediction, leverage,
    or position size. If credentials are absent, deterministic risk remains the
    only decision source.
    """
    base, key, model = _llm_settings()
    deterministic_level, deterministic_allow, deterministic_reason = deterministic_risk(snapshot)
    if deterministic_level in {"high", "elevated"}:
        return deterministic_level, False, 1.0, deterministic_reason, "deterministic"
    if not key or not snapshot.news:
        return deterministic_level, deterministic_allow, 0.5, deterministic_reason, "deterministic"

    articles = "\n".join(f"- {item.title} | {item.source} | {item.published_at}" for item in snapshot.news[:30])
    user_payload = {
        "market": asdict(snapshot),
        "articles": articles,
        "instruction": "Classify only near-term market risk for long entries. Do not forecast a price and do not propose a trade.",
    }
    schema = {
        "type": "object",
        "properties": {
            "risk_level": {"type": "string", "enum": ["normal", "guarded", "elevated", "high"]},
            "allow_long_entries": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 500},
        },
        "required": ["risk_level", "allow_long_entries", "confidence", "reason"],
        "additionalProperties": False,
    }
    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=20,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a market-risk classifier. Return JSON only. You are not a trader. Never recommend a buy, sell, leverage, or position size."},
                    {"role": "user", "content": json.dumps(user_payload, separators=(",", ":"))},
                ],
                "response_format": {"type": "json_schema", "json_schema": {"name": "market_risk", "strict": True, "schema": schema}},
                "max_completion_tokens": 500,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        model_risk = str(result["risk_level"])
        if model_risk not in {"normal", "guarded", "elevated", "high"}:
            raise ValueError("LLM returned an invalid risk level")
        confidence = min(1.0, max(0.0, float(result["confidence"])))
        risk_order = {"normal": 0, "guarded": 1, "elevated": 2, "high": 3}
        risk = max((deterministic_level, model_risk), key=lambda level: risk_order[level])
        allow = deterministic_allow and bool(result["allow_long_entries"]) and risk not in {"high", "elevated"} and confidence >= 0.60
        reason = str(result["reason"])[:500]
        if deterministic_reason and deterministic_level != "normal":
            reason = f"{deterministic_reason}; {reason}"
        return risk, allow, confidence, reason, model
    except Exception as exc:
        risk, allow, reason = deterministic_risk(snapshot)
        return risk, allow, 0.0, f"LLM unavailable; deterministic fallback: {reason}", "deterministic-fallback"


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
    risk, allow, confidence, reason, model = classify_news(market)
    generated = _now()
    ttl_raw = os.getenv("INTELLIGENCE_TTL_SECONDS", "1800")
    try:
        ttl_seconds = min(86_400, max(60, int(ttl_raw)))
    except ValueError:
        ttl_seconds = 1_800
    expires = generated.timestamp() + ttl_seconds
    digest = hashlib.sha256(json.dumps(asdict(market), sort_keys=True).encode()).hexdigest()[:16]
    return IntelligenceDecision(
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
