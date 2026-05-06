"""Tavily news search provider."""
from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlparse

import requests

from tradingAgents.config.settings import settings
from tradingAgents.data.cache import ttl_cache
from tradingAgents.engine.dataflows.interface import NewsItem

logger = logging.getLogger(__name__)

NEWS_CACHE_TTL = 180


@ttl_cache(ttl=NEWS_CACHE_TTL)
def fetch_tavily_news(query: str, limit: int = 10, time_range: str = "week") -> list[NewsItem]:
    """Fetch recent news-like search results from Tavily.

    Tavily is used as a search layer, so it complements dedicated finance
    feeds rather than replacing exchange announcements or paid market data.
    """
    if not settings.tavily_api_key or not query.strip():
        return []

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {settings.tavily_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "topic": "news",
                "search_depth": "basic",
                "max_results": min(max(limit, 1), 20),
                "time_range": time_range,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return [_to_news_item(result) for result in resp.json().get("results", [])[:limit]]
    except Exception as exc:
        logger.debug("Tavily news failed for query=%s: %s", query, exc)
        return []


def tavily_market_query(market: str) -> str:
    if market == "a_stock":
        return "A股 财经 股票 市场 财报 监管 并购 回购 最新新闻"
    if market == "hk_stock":
        return "港股 恒生指数 公司业绩 监管 回购 最新财经新闻"
    return "US stock market earnings guidance SEC regulation buyback latest financial news"


def tavily_stock_query(symbol: str, name: str = "", market: str = "a_stock") -> str:
    subject = f"{name} {symbol}".strip()
    if market == "a_stock":
        return f"{subject} 股票 财报 业绩 监管 公告 新闻"
    if market == "hk_stock":
        return f"{subject} Hong Kong stock earnings regulation news"
    return f"{subject} stock earnings guidance SEC regulation news"


def _to_news_item(result: dict) -> NewsItem:
    url = str(result.get("url", ""))
    content = str(result.get("content", ""))
    title = str(result.get("title", "")) or content[:80]
    published_at = _parse_date(result.get("published_date") or result.get("publishedAt"))
    source = _source_from_url(url)
    score = result.get("score")
    suffix = f" · {score:.2f}" if isinstance(score, (int, float)) else ""
    return NewsItem(
        title=title,
        content=content,
        source=f"Tavily · {source}{suffix}".strip(" ·"),
        url=url,
        published_at=published_at,
    )


def _source_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.replace("www.", "")
        return host or "web"
    except Exception:
        return "web"


def _parse_date(value) -> datetime:
    if not value:
        return datetime.now()
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return datetime.now()
