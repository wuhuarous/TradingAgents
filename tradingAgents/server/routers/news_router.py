"""新闻舆情聚合 — 多源财经新闻 + 情绪分析（带缓存）"""
from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from tradingAgents.data.cache import ttl_cache
from tradingAgents.data.database.data_quality_repo import DataQualityRepository
from tradingAgents.data.database.data_quality_repo import persist_news_items_sync
from tradingAgents.data.news.domestic import fetch_domestic_news
from tradingAgents.data.news.international import fetch_global_news
from tradingAgents.data.news.quality import standardize_news_item
from tradingAgents.data.social.sources import fetch_social_sentiment
from tradingAgents.data.social.sentiment import analyze_sentiment
from tradingAgents.data.storage.event_store import append_events

router = APIRouter(prefix="/api/news", tags=["news"])

NEWS_CACHE_TTL = 120


@router.get("/")
async def get_news(
    market: str = Query("a_stock"),
    limit: int = Query(30),
    symbol: str = Query(""),
    name: str = Query(""),
    refresh: bool = Query(False),
):
    """获取聚合新闻列表，多源覆盖 + 情绪分析"""
    if not refresh:
        stored = await DataQualityRepository().list_news(market=market, symbol=symbol or None, limit=limit)
        if stored:
            return [_stored_news_to_feed(item) for item in stored]
    if symbol:
        return await run_in_threadpool(_get_stock_news_cached, market, symbol, name, limit)
    return await run_in_threadpool(_get_news_cached, market, limit)


@ttl_cache(ttl=NEWS_CACHE_TTL)
def _get_news_cached(market: str, limit: int) -> list[dict]:
    items = []

    # 国内新闻（多源：东方财富 + 新浪 + 百度）
    if market == "a_stock":
        try:
            items.extend(fetch_domestic_news(limit=limit))
        except Exception:
            pass

    # 全球新闻（yfinance + 东方财富全球 + 富途）
    try:
        items.extend(fetch_global_news(limit=limit))
    except Exception:
        pass

    items = _dedupe(items)
    return _format_news_results(items, market, limit)


@ttl_cache(ttl=NEWS_CACHE_TTL)
def _get_stock_news_cached(market: str, symbol: str, name: str, limit: int) -> list[dict]:
    items = []
    if market == "a_stock":
        try:
            from tradingAgents.data.news.domestic import fetch_stock_news

            items.extend(fetch_stock_news(symbol, limit=limit))
        except Exception:
            pass
    try:
        items.extend(fetch_social_sentiment(symbol, name, market, limit=max(3, limit // 3)))
    except Exception:
        pass
    items = _dedupe(items)
    return _format_news_results(items, market, limit, symbol=symbol, relevance_query=f"{name} {symbol}")


def _format_news_results(
    items: list,
    market: str,
    limit: int,
    *,
    symbol: str = "",
    relevance_query: str = "",
) -> list[dict]:
    results = []
    for item in items[:limit]:
        sentiment = None
        text = f"{item.title} {item.content}" if item.content else item.title
        if text.strip():
            try:
                sentiment = analyze_sentiment(text)
            except Exception:
                sentiment = 0.0

        standardized = standardize_news_item(
            item,
            market=market,
            symbol=symbol,
            sentiment=sentiment,
            relevance_query=relevance_query,
        )
        results.append({
            "title": item.title,
            "source": item.source or "财经媒体",
            "url": item.url or "",
            "sentiment": round(sentiment, 3) if sentiment is not None else None,
            "published_at": standardized["published_at"],
            "quality_score": standardized["quality_score"],
            "source_type": standardized["source_type"],
            "standardized": standardized,
        })

    results.sort(key=lambda x: x["published_at"], reverse=True)
    results = results[:limit]
    standardized_rows = [row["standardized"] for row in results]
    append_events("news", standardized_rows)
    persist_news_items_sync(standardized_rows)
    return results


def _dedupe(items: list) -> list:
    seen = set()
    deduped = []
    for item in items:
        key = (str(item.title).strip().lower(), str(item.url).strip().lower())
        if not item.title or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _stored_news_to_feed(item: dict) -> dict:
    sentiment = item.get("sentiment_score")
    return {
        "title": item.get("title", ""),
        "source": item.get("source", "") or "财经媒体",
        "url": item.get("url", "") or "",
        "sentiment": round(float(sentiment or 0), 3) if sentiment is not None else None,
        "published_at": item.get("published_at") or item.get("created_at"),
        "quality_score": item.get("quality_score", 0),
        "source_type": item.get("source_type", ""),
        "standardized": item,
    }
