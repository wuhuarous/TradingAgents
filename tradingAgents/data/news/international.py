"""国际财经新闻 — yfinance"""
import logging
from tradingAgents.engine.dataflows.interface import NewsItem
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider

logger = logging.getLogger(__name__)

_MAJOR_TICKERS = ["^GSPC", "^DJI", "^IXIC", "^HSI"]


def fetch_global_news(limit: int = 20) -> list[NewsItem]:
    provider = YFinanceProvider()
    items = []
    for ticker in _MAJOR_TICKERS:
        try:
            news = provider.get_news(ticker, limit=5)
            items.extend(news)
        except Exception as e:
            logger.warning("Global news fetch failed for %s: %s", ticker, e)
    return items[:limit]
