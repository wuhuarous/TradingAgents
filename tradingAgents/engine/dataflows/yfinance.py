"""yfinance 实现 — 港美股行情 + 财务 + 新闻（带缓存 + 重试 + 限流处理）

缓存使用模块级函数，确保不同实例间共享缓存。
"""
import logging
import time
import pandas as pd
import yfinance as yf

from tradingAgents.data.cache import ttl_cache, retry_on_error
from .interface import DataSourceProvider, Market, NewsItem, StockQuote

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL = 300        # 行情缓存 5 分钟
FINANCIALS_CACHE_TTL = 1800  # 财务数据缓存 30 分钟
NEWS_CACHE_TTL = 300         # 新闻缓存 5 分钟
MAX_BACKOFF = 60             # 最大退避秒数

# ---- 模块级限流状态 ----
_last_request_time: float = 0
_min_interval: float = 0.3
_rate_limit_backoff: float = 0


def _ticker_str(symbol: str, market: Market) -> str:
    if market == Market.HK and not symbol.endswith(".HK"):
        return f"{symbol}.HK"
    return symbol


def _throttle():
    """请求限流：确保两次请求间隔 >= _min_interval，遇限流则退避"""
    global _last_request_time, _rate_limit_backoff
    now = time.time()
    if _rate_limit_backoff > 0:
        if now - _last_request_time < _rate_limit_backoff:
            sleep_s = _rate_limit_backoff - (now - _last_request_time)
            if sleep_s > 0:
                logger.debug("Rate limit backoff: sleeping %.1fs", sleep_s)
                time.sleep(sleep_s)
    elif now - _last_request_time < _min_interval:
        time.sleep(_min_interval - (now - _last_request_time))
    _last_request_time = time.time()


@retry_on_error(max_retries=3, base_delay=2.0)
def _fetch_info(symbol: str, market: Market) -> dict:
    """模块级函数：带重试获取 yfinance info（所有实例共享缓存）"""
    global _rate_limit_backoff
    _throttle()
    try:
        t = yf.Ticker(_ticker_str(symbol, market))
        info = t.info or {}
    except Exception as e:
        msg = str(e)[:120]
        if "Too Many Requests" in msg or "Rate limited" in msg:
            _rate_limit_backoff = min(_rate_limit_backoff * 2 + 2 if _rate_limit_backoff else 5, MAX_BACKOFF)
            logger.warning("yfinance rate limited, backoff=%.1fs", _rate_limit_backoff)
        raise
    if _rate_limit_backoff > 0:
        _rate_limit_backoff = max(_rate_limit_backoff - 1, 0)
    return info


@ttl_cache(ttl=QUOTE_CACHE_TTL)
def _cached_info(symbol: str, market: Market) -> dict:
    return _fetch_info(symbol, market)


class YFinanceProvider(DataSourceProvider):

    @staticmethod
    def _get_ticker(symbol: str, market: Market) -> str:
        return _ticker_str(symbol, market)

    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        info = _cached_info(symbol, market)
        price = float(info.get("currentPrice", info.get("regularMarketPrice", 0) or 0))
        prev_close = float(info.get("previousClose", 0) or 0)
        return StockQuote(
            symbol=symbol,
            name=str(info.get("longName", info.get("shortName", ""))),
            price=price,
            open=float(info.get("regularMarketOpen", 0) or 0),
            high=float(info.get("dayHigh", 0) or 0),
            low=float(info.get("dayLow", 0) or 0),
            close=prev_close,
            volume=int(info.get("volume", 0) or 0),
            change_pct=(price - prev_close) / prev_close if prev_close else 0,
            market=market,
        )

    @retry_on_error(max_retries=2, base_delay=1.0)
    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        _throttle()
        try:
            t = yf.Ticker(_ticker_str(symbol, market))
            df = t.history(period=period)
            return df if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning("yfinance history failed for %s: %s", symbol, e)
            return pd.DataFrame()

    @ttl_cache(ttl=FINANCIALS_CACHE_TTL, skip_first_arg=True)
    def get_financials(self, symbol: str, market: Market) -> dict:
        info = _cached_info(symbol, market)
        return {
            "pe_ratio": _float(info.get("trailingPE")),
            "forward_pe": _float(info.get("forwardPE")),
            "pb_ratio": _float(info.get("priceToBook")),
            "market_cap": _float(info.get("marketCap")),
            "revenue": _float(info.get("totalRevenue")),
            "net_income": _float(info.get("netIncomeToCommon")),
            "roe": _float(info.get("returnOnEquity")),
            "debt_to_equity": _float(info.get("debtToEquity")),
            "dividend_yield": _float(info.get("dividendYield")),
            "revenue_growth": _float(info.get("revenueGrowth")),
        }

    @ttl_cache(ttl=NEWS_CACHE_TTL, skip_first_arg=True)
    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        _throttle()
        try:
            t = yf.Ticker(_ticker_str(symbol, market))
            items = []
            for n in (t.news or [])[:limit]:
                items.append(NewsItem(
                    title=str(n.get("title", "")),
                    content=str(n.get("link", "")),
                    source=str(n.get("publisher", "")),
                    url=str(n.get("link", "")),
                ))
            return items
        except Exception as e:
            logger.debug("yfinance news failed for %s: %s", symbol, e)
            return []

    @ttl_cache(ttl=QUOTE_CACHE_TTL, skip_first_arg=True)
    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        _throttle()
        try:
            t = yf.Ticker(keyword)
            info = t.info or {}
            name = info.get("longName", info.get("shortName", ""))
            if name:
                return [{"symbol": keyword, "name": str(name)}]
            return []
        except Exception:
            return []


def _float(val) -> float | None:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None
