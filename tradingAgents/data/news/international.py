"""国际财经新闻 — 多源聚合 + 可选海外 API"""
import logging
from datetime import datetime, timedelta

import requests

from tradingAgents.config.settings import settings
from tradingAgents.data.cache import ttl_cache
from tradingAgents.data.news.tavily import fetch_tavily_news, tavily_market_query
from tradingAgents.engine.dataflows.interface import NewsItem
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider

logger = logging.getLogger(__name__)

NEWS_CACHE_TTL = 120

_MAJOR_TICKERS = ["^GSPC", "^DJI", "^IXIC", "^HSI"]


@ttl_cache(ttl=NEWS_CACHE_TTL)
def fetch_global_news(limit: int = 20) -> list[NewsItem]:
    """聚合全球财经新闻：yfinance + 东方财富全球 + 富途 + 可选海外 API"""
    items: list[NewsItem] = []
    preferred = settings.preferred_news_source

    source_map = {
        "alpha_vantage": _fetch_alpha_vantage_news,
        "finnhub": _fetch_finnhub_news,
        "polygon": _fetch_polygon_news,
        "newsapi": _fetch_newsapi,
        "tavily": lambda l: fetch_tavily_news(tavily_market_query("us_stock"), limit=l),
    }

    if preferred in source_map:
        items.extend(source_map[preferred](limit))

    # 1. Paid/API sources first when configured.
    if preferred == "auto":
        items.extend(_fetch_alpha_vantage_news(limit))
        items.extend(_fetch_finnhub_news(limit))
        items.extend(_fetch_polygon_news(limit))
        items.extend(_fetch_newsapi(limit))
        items.extend(fetch_tavily_news(tavily_market_query("us_stock"), limit=limit))

    # 2. Yahoo Finance 全球新闻
    items.extend(_fetch_yahoo_global(limit))

    # 3. 东方财富全球快讯（已含国际财经）
    items.extend(_fetch_eastmoney_global(limit))

    # 4. 富途全球快讯
    items.extend(_fetch_futu_global(limit))

    return _dedupe(items)[:limit]


def _fetch_yahoo_global(limit: int) -> list[NewsItem]:
    items = []
    provider = YFinanceProvider()
    for ticker in _MAJOR_TICKERS:
        try:
            news = provider.get_news(ticker, limit=5)
            items.extend(news)
            if len(items) >= limit:
                break
        except Exception as e:
            logger.debug("Yahoo global news failed for %s: %s", ticker, e)
    return items[:limit]


def _fetch_eastmoney_global(limit: int) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_em()
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                items.append(NewsItem(
                    title=str(row.get("标题", "")),
                    content=str(row.get("摘要", "")),
                    source="东方财富·全球",
                    url=str(row.get("链接", "")),
                ))
    except Exception as e:
        logger.debug("EastMoney global news failed: %s", e)
    return items


def _fetch_futu_global(limit: int) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_futu()
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                items.append(NewsItem(
                    title=str(row.get("标题", row.get("title", ""))),
                    content=str(row.get("摘要", row.get("content", ""))),
                    source="富途牛牛",
                    url=str(row.get("链接", row.get("url", ""))),
                ))
    except Exception as e:
        logger.debug("Futu global news failed: %s", e)
    return items


def _fetch_alpha_vantage_news(limit: int) -> list[NewsItem]:
    if not settings.alpha_vantage_api_key:
        return []
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "financial_markets,earnings,technology",
                "sort": "LATEST",
                "limit": min(limit, 50),
                "apikey": settings.alpha_vantage_api_key,
            },
            timeout=8,
        )
        data = resp.json()
        items = []
        for article in data.get("feed", [])[:limit]:
            items.append(NewsItem(
                title=str(article.get("title", "")),
                content=str(article.get("summary", "")),
                source=f"Alpha Vantage · {article.get('source', '')}".strip(" ·"),
                url=str(article.get("url", "")),
                sentiment=_float(article.get("overall_sentiment_score")),
            ))
        return items
    except Exception as e:
        logger.debug("Alpha Vantage news failed: %s", e)
        return []


def _fetch_finnhub_news(limit: int) -> list[NewsItem]:
    if not settings.finnhub_api_key:
        return []
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": settings.finnhub_api_key},
            timeout=8,
        )
        items = []
        for article in resp.json()[:limit]:
            items.append(NewsItem(
                title=str(article.get("headline", "")),
                content=str(article.get("summary", "")),
                source=f"Finnhub · {article.get('source', '')}".strip(" ·"),
                url=str(article.get("url", "")),
            ))
        return items
    except Exception as e:
        logger.debug("Finnhub news failed: %s", e)
        return []


def _fetch_polygon_news(limit: int) -> list[NewsItem]:
    if not settings.polygon_api_key:
        return []
    try:
        resp = requests.get(
            "https://api.polygon.io/v2/reference/news",
            params={"limit": min(limit, 50), "apiKey": settings.polygon_api_key},
            timeout=8,
        )
        items = []
        for article in resp.json().get("results", [])[:limit]:
            items.append(NewsItem(
                title=str(article.get("title", "")),
                content=str(article.get("description", "")),
                source=f"Polygon · {article.get('publisher', {}).get('name', '')}".strip(" ·"),
                url=str(article.get("article_url", "")),
            ))
        return items
    except Exception as e:
        logger.debug("Polygon news failed: %s", e)
        return []


def _fetch_newsapi(limit: int) -> list[NewsItem]:
    if not settings.newsapi_api_key:
        return []
    try:
        since = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": "(stock market OR earnings OR Nasdaq OR S&P 500)",
                "from": since,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": min(limit, 50),
                "apiKey": settings.newsapi_api_key,
            },
            timeout=8,
        )
        items = []
        for article in resp.json().get("articles", [])[:limit]:
            items.append(NewsItem(
                title=str(article.get("title", "")),
                content=str(article.get("description", "")),
                source=f"NewsAPI · {article.get('source', {}).get('name', '')}".strip(" ·"),
                url=str(article.get("url", "")),
            ))
        return items
    except Exception as e:
        logger.debug("NewsAPI failed: %s", e)
        return []


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.title.strip().lower(), item.url.strip().lower())
        if not item.title or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
