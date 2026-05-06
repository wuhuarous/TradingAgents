"""Standardized news records and source quality scoring."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from urllib.parse import urlparse

from tradingAgents.engine.dataflows.interface import NewsItem

SOURCE_WEIGHTS = {
    "交易所公告": 1.0,
    "sec": 0.98,
    "公司公告": 0.95,
    "东方财富": 0.78,
    "新浪财经": 0.72,
    "财联社": 0.82,
    "富途": 0.72,
    "yahoo": 0.72,
    "alpha vantage": 0.82,
    "finnhub": 0.80,
    "polygon": 0.84,
    "newsapi": 0.66,
    "tavily": 0.62,
    "百度财经日历": 0.68,
    "社媒": 0.38,
}


def standardize_news_item(
    item: NewsItem,
    *,
    market: str,
    symbol: str = "",
    sentiment: float | None = None,
    relevance_query: str = "",
) -> dict:
    published_at = getattr(item, "published_at", None) or datetime.now()
    if published_at.tzinfo is not None:
        published_at = published_at.astimezone(timezone.utc).replace(tzinfo=None)
    fetched_at = datetime.now()
    source = item.source or "财经媒体"
    source_weight = source_quality(source)
    freshness_score = freshness_quality(published_at, fetched_at)
    relevance_score = relevance_quality(item, relevance_query or symbol)
    sentiment_score = sentiment if sentiment is not None else item.sentiment
    quality_score = round(
        source_weight * 45 + freshness_score * 30 + relevance_score * 25,
        2,
    )
    return {
        "market": market,
        "symbol": symbol,
        "title": item.title,
        "content": item.content,
        "source": source,
        "source_type": classify_source(source, item.url),
        "url": item.url or "",
        "published_at": published_at.isoformat(timespec="seconds"),
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "sentiment_score": round(sentiment_score, 3) if sentiment_score is not None else None,
        "relevance_score": round(relevance_score, 3),
        "freshness_score": round(freshness_score, 3),
        "source_weight": round(source_weight, 3),
        "quality_score": quality_score,
        "dedupe_key": dedupe_key(item),
    }


def source_quality(source: str) -> float:
    lower = source.lower()
    if "社媒" in source or any(k in lower for k in ["reddit", "stocktwits", "x.com", "twitter"]):
        return SOURCE_WEIGHTS["社媒"]
    for key, weight in SOURCE_WEIGHTS.items():
        if key.lower() in lower:
            return weight
    return 0.58


def freshness_quality(published_at: datetime, fetched_at: datetime | None = None) -> float:
    fetched = fetched_at or datetime.now()
    age_hours = max((fetched - published_at).total_seconds() / 3600, 0)
    return max(0.18, math.exp(-age_hours / 72))


def relevance_quality(item: NewsItem, query: str = "") -> float:
    if not query:
        return 0.62
    tokens = [t.lower() for t in query.replace("　", " ").split() if t.strip()]
    if not tokens:
        return 0.62
    text = f"{item.title} {item.content}".lower()
    hits = sum(1 for token in tokens if token in text)
    return min(1.0, 0.35 + hits / max(len(tokens), 1) * 0.65)


def classify_source(source: str, url: str = "") -> str:
    lower = f"{source} {url}".lower()
    if any(k in lower for k in ["sec.gov", "交易所", "公告"]):
        return "announcement"
    if any(k in lower for k in ["雪球", "股吧", "reddit", "stocktwits", "x.com", "twitter", "社媒"]):
        return "social"
    if "日历" in source:
        return "macro_calendar"
    if url:
        host = urlparse(url).netloc.lower()
        if host:
            return "media"
    return "media"


def dedupe_key(item: NewsItem) -> str:
    return f"{(item.title or '').strip().lower()}|{(item.url or '').strip().lower()}"
