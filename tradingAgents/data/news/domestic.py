"""国内财经新闻 — 东方财富 + 新浪 + 百度 + 财联社"""
import logging
from datetime import datetime
from tradingAgents.data.cache import ttl_cache
from tradingAgents.config.settings import settings
from tradingAgents.data.news.tavily import fetch_tavily_news, tavily_market_query
from tradingAgents.engine.dataflows.interface import NewsItem

logger = logging.getLogger(__name__)

NEWS_CACHE_TTL = 120  # 新闻列表缓存 2 分钟


def _make_item(
    title: str,
    content: str = "",
    source: str = "",
    url: str = "",
    published_at: datetime | None = None,
) -> NewsItem:
    return NewsItem(
        title=str(title),
        content=str(content),
        source=str(source),
        url=str(url),
        published_at=published_at or datetime.now(),
    )


@ttl_cache(ttl=NEWS_CACHE_TTL)
def fetch_domestic_news(limit: int = 20) -> list[NewsItem]:
    """聚合国内财经新闻，按来源优先级合并"""
    sources: list[list[NewsItem]] = []
    preferred = settings.preferred_news_source

    if preferred == "tavily":
        sources.append(fetch_tavily_news(tavily_market_query("a_stock"), limit=limit))

    # 1. 东方财富全球快讯
    sources.append(_fetch_eastmoney(limit))

    # 2. 新浪财经快讯
    sources.append(_fetch_sina(limit))

    # 3. 百度财经日历
    sources.append(_fetch_baidu_news(limit))

    # 4. Tavily 搜索补充，适合主动补足近期新闻
    if preferred == "auto":
        sources.append(fetch_tavily_news(tavily_market_query("a_stock"), limit=limit))

    return _mix_sources(sources, limit)


def _fetch_eastmoney(limit: int) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_em()
        for _, row in df.head(limit).iterrows():
            items.append(_make_item(
                title=str(row.get("标题", "")),
                content=str(row.get("摘要", "")),
                source="东方财富",
                url=str(row.get("链接", "")),
            ))
    except Exception as e:
        logger.debug("EastMoney news failed: %s", e)
    return items


def _fetch_sina(limit: int) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_sina()
        for _, row in df.head(limit).iterrows():
            content = str(row.get("内容", row.get("content", "")))
            title = str(row.get("标题", row.get("title", ""))) or _title_from_content(content)
            items.append(_make_item(
                title=title,
                content=content,
                source="新浪财经",
                url=str(row.get("链接", row.get("url", ""))),
                published_at=_parse_datetime(row.get("时间")),
            ))
    except Exception as e:
        logger.debug("Sina finance news failed: %s", e)
    return items


def _fetch_baidu_news(limit: int) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.news_economic_baidu()
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                event = str(row.get("事件", row.get("event", "")))
                region = str(row.get("地区", row.get("region", "")))
                date = str(row.get("日期", ""))
                time_text = str(row.get("时间", ""))
                actual = str(row.get("公布", ""))
                forecast = str(row.get("预期", ""))
                previous = str(row.get("前值", ""))
                content = f"{region} {event} 公布:{actual} 预期:{forecast} 前值:{previous}".strip()
                items.append(_make_item(
                    title=event,
                    content=content,
                    source=f"百度财经日历 {date} {time_text}".strip(),
                    url=str(row.get("url", row.get("链接", ""))),
                    published_at=_parse_datetime(f"{date} {time_text}"),
                ))
    except Exception as e:
        logger.debug("Baidu economic news failed: %s", e)
    return items


def _title_from_content(content: str) -> str:
    text = content.strip()
    if not text:
        return ""
    if text.startswith("【") and "】" in text:
        return text[1:text.index("】")].strip()
    return text[:80]


def _parse_datetime(value) -> datetime:
    if not value:
        return datetime.now()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len(fmt)], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.now()


def _mix_sources(sources: list[list[NewsItem]], limit: int) -> list[NewsItem]:
    """Round-robin sources so one feed cannot hide all the others."""
    mixed: list[NewsItem] = []
    seen = set()
    max_len = max((len(items) for items in sources), default=0)
    for idx in range(max_len):
        for items in sources:
            if idx >= len(items):
                continue
            item = items[idx]
            key = (item.title.strip().lower(), item.url.strip().lower())
            if not item.title or key in seen:
                continue
            seen.add(key)
            mixed.append(item)
            if len(mixed) >= limit:
                return mixed
    return mixed


@ttl_cache(ttl=NEWS_CACHE_TTL * 2)
def fetch_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    """个股新闻聚合：东方财富个股新闻"""
    items = []
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
        for _, row in df.head(limit).iterrows():
            items.append(_make_item(
                title=str(row.get("标题", "")),
                content=str(row.get("内容", "")),
                source="东方财富",
                url=str(row.get("链接", "")),
            ))
    except Exception as e:
        logger.debug("Stock news fetch failed for %s: %s", symbol, e)
    return items
