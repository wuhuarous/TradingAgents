"""港美股数据 — yfinance 包装 + 供应商工厂"""
from tradingAgents.engine.dataflows.interface import DataSourceProvider, Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider


class HKUSStockProvider(YFinanceProvider):
    """直接继承 YFinanceProvider，无额外覆盖"""
    pass


def get_provider(market: Market) -> DataSourceProvider:
    """根据市场获取对应的数据供应商"""
    if market == Market.A:
        from tradingAgents.data.providers.a_stock import AStockProvider
        return AStockProvider()
    return HKUSStockProvider()
