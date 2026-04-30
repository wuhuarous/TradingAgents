"""国内财经新闻 — 东方财富 + 财联社"""
import logging
from tradingAgents.engine.dataflows.interface import NewsItem

logger = logging.getLogger(__name__)


def fetch_domestic_news(limit: int = 20) -> list[NewsItem]:
    items = []
    try:
        import akshare as ak
        df = ak.stock_info_global_em()
        for _, row in df.head(limit).iterrows():
            items.append(NewsItem(
                title=str(row.get("标题", "")),
                content=str(row.get("摘要", "")),
                source="东方财富",
                url=str(row.get("链接", "")),
            ))
    except Exception as e:
        logger.warning("Domestic news fetch failed: %s", e)
    return items


def fetch_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
        items = []
        for _, row in df.head(limit).iterrows():
            items.append(NewsItem(
                title=str(row.get("标题", "")),
                content=str(row.get("内容", "")),
                source="东方财富",
            ))
        return items
    except Exception as e:
        logger.warning("Stock news fetch failed for %s: %s", symbol, e)
        return []
