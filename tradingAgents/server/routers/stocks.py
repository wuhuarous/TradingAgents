from fastapi import APIRouter, Query

from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.engine.dataflows.interface import Market

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/quote")
def get_quote(symbol: str, market: str = "a_stock"):
    provider = AStockProvider()
    quote = provider.get_realtime_quote(symbol, Market(market))
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
        "change_pct": quote.change_pct,
    }


@router.get("/search")
def search_stocks(keyword: str, market: str = "a_stock"):
    provider = AStockProvider()
    return provider.search_symbols(keyword, Market(market))
