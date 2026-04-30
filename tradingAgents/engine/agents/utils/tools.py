"""Agent 工具函数 — 封装数据获取，供 Agent 调用"""
import pandas as pd

from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.providers.hk_us_stock import HKUSStockProvider
from tradingAgents.engine.dataflows.interface import Market


def _get_provider(market: Market):
    if market == Market.A:
        return AStockProvider()
    return HKUSStockProvider()


def get_stock_data(symbol: str, market: str = "us", period: str = "1mo") -> pd.DataFrame:
    m = Market(market)
    return _get_provider(m).get_historical(symbol, m, period)


def get_quote(symbol: str, market: str = "us"):
    m = Market(market)
    return _get_provider(m).get_realtime_quote(symbol, m)


def get_financials(symbol: str, market: str = "us") -> dict:
    m = Market(market)
    return _get_provider(m).get_financials(symbol, m)


def get_news(symbol: str, market: str = "us", limit: int = 10) -> list:
    m = Market(market)
    return _get_provider(m).get_news(symbol, m, limit)
