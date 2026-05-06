"""Social sentiment collection hooks.

Direct social APIs often need accounts or paid access. For now this module
uses Tavily as a search bridge when a Tavily key is configured, and marks the
records as social evidence with lower source weights.
"""
from __future__ import annotations

from tradingAgents.data.news.tavily import fetch_tavily_news
from tradingAgents.engine.dataflows.interface import NewsItem


def fetch_social_sentiment(
    symbol: str,
    name: str = "",
    market: str = "a_stock",
    limit: int = 6,
) -> list[NewsItem]:
    query = social_query(symbol, name, market)
    if not query:
        return []
    items = fetch_tavily_news(query, limit=limit * 2, time_range="week")
    return [
        NewsItem(
            title=item.title,
            content=item.content,
            source=f"社媒搜索 · {item.source}",
            url=item.url,
            sentiment=item.sentiment,
            published_at=item.published_at,
        )
        for item in items
        if _is_relevant(item, symbol, name)
    ][:limit]


def social_query(symbol: str, name: str = "", market: str = "a_stock") -> str:
    subject = f"{name} {symbol}".strip()
    if not subject:
        return ""
    if market == "a_stock":
        return f"{subject} 雪球 股吧 投资者 情绪 讨论 风险"
    if market == "hk_stock":
        return f"{subject} Xueqiu Futu Hong Kong stock investor sentiment discussion"
    return f"{subject} Reddit StockTwits investor sentiment discussion risk"


def _is_relevant(item: NewsItem, symbol: str, name: str) -> bool:
    text = f"{item.title} {item.content}".lower()
    tokens = [symbol.lower()]
    if name:
        tokens.append(name.lower())
    return any(token and token in text for token in tokens)
