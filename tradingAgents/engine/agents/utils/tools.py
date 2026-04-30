"""Agent 工具函数 — 封装数据获取，供 Agent 调用"""
import pandas as pd

from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.providers.hk_us_stock import HKUSStockProvider
from tradingAgents.engine.dataflows.interface import Market

_MARKET_ALIASES = {
    "a": Market.A,
    "hk": Market.HK,
    "us": Market.US,
    "a_stock": Market.A,
    "hk_stock": Market.HK,
    "us_stock": Market.US,
}


def _resolve_market(market: str) -> Market:
    if market in _MARKET_ALIASES:
        return _MARKET_ALIASES[market]
    return Market(market)


def _get_provider(market: Market):
    if market == Market.A:
        return AStockProvider()
    return HKUSStockProvider()


def get_stock_data(symbol: str, market: str = "us", period: str = "1mo") -> pd.DataFrame:
    m = _resolve_market(market)
    return _get_provider(m).get_historical(symbol, m, period)


def get_quote(symbol: str, market: str = "us"):
    m = _resolve_market(market)
    return _get_provider(m).get_realtime_quote(symbol, m)


def get_financials(symbol: str, market: str = "us") -> dict:
    m = _resolve_market(market)
    return _get_provider(m).get_financials(symbol, m)


def get_news(symbol: str, market: str = "us", limit: int = 10) -> list:
    m = _resolve_market(market)
    return _get_provider(m).get_news(symbol, m, limit)
