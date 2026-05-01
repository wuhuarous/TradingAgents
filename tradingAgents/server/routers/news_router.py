"""新闻舆情聚合 — 国内外财经新闻 + 情绪分析"""
from fastapi import APIRouter, Query

from tradingAgents.data.news.domestic import fetch_domestic_news
from tradingAgents.data.news.international import fetch_global_news
from tradingAgents.data.social.sentiment import analyze_sentiment

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/")
def get_news(market: str = Query("a_stock"), limit: int = Query(30)):
    """获取聚合新闻列表，附带情绪标签"""
    items = []

    # Domestic news for A-shares
    if market == "a_stock":
        try:
            items.extend(fetch_domestic_news(limit=limit))
        except Exception:
            pass

    # Global/international news for all markets
    try:
        items.extend(fetch_global_news(limit=limit))
    except Exception:
        pass

    # Run sentiment analysis with caching-aware batching
    results = []
    for item in items[:limit]:
        sentiment = None
        text = f"{item.title} {item.content}" if item.content else item.title
        if text.strip():
            try:
                sentiment = analyze_sentiment(text)
            except Exception:
                sentiment = 0.0

        results.append({
            "title": item.title,
            "source": item.source or "财经媒体",
            "url": item.url or "",
            "sentiment": round(sentiment, 3) if sentiment is not None else None,
            "published_at": item.published_at.isoformat() if hasattr(item, 'published_at') else "",
        })

    # Sort: newest first
    results.sort(key=lambda x: x["published_at"], reverse=True)
    return results[:limit]
