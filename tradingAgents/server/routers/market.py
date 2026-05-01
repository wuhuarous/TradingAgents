"""市场行情总览 — 指数、涨跌榜、热门股票"""
from fastapi import APIRouter, Query

from tradingAgents.engine.dataflows.interface import Market, StockQuote
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider

router = APIRouter(prefix="/api/market", tags=["market"])

_INDEX_MAP = {
    "a_stock": [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指"),
    ],
    "hk_stock": [
        ("^HSI", "恒生指数"),
        ("^HSCE", "国企指数"),
    ],
    "us_stock": [
        ("^GSPC", "标普500"),
        ("^IXIC", "纳斯达克"),
        ("^DJI", "道琼斯"),
    ],
}

_HOT_STOCKS = {
    "a_stock": [
        ("600519", "贵州茅台"), ("000858", "五粮液"), ("300750", "宁德时代"),
        ("601318", "中国平安"), ("000333", "美的集团"), ("002594", "比亚迪"),
        ("600036", "招商银行"), ("601012", "隆基绿能"),
    ],
    "hk_stock": [
        ("0700.HK", "腾讯控股"), ("9988.HK", "阿里巴巴"),
        ("3690.HK", "美团"), ("0941.HK", "中国移动"),
        ("1398.HK", "工商银行"), ("0388.HK", "港交所"),
    ],
    "us_stock": [
        ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet"),
        ("AMZN", "Amazon"), ("NVDA", "NVIDIA"), ("TSLA", "Tesla"),
        ("META", "Meta"), ("JPM", "JPMorgan"),
    ],
}


@router.get("/overview")
def get_market_overview(market: str = Query("a_stock")):
    """获取指定市场总览：指数 + 热门股票实时报价 + 排名"""
    mkt = Market(market)
    is_hk_us = market in ("hk_stock", "us_stock")

    # Indices
    indices = []
    for sym, name in _INDEX_MAP.get(market, []):
        try:
            q = _get_quote(sym, mkt, is_hk_us)
            indices.append({
                "symbol": sym, "name": name,
                "price": q.price, "change_pct": q.change_pct,
            })
        except Exception:
            indices.append({"symbol": sym, "name": name, "price": 0, "change_pct": 0})

    # Hot stocks with quotes
    hot_stocks = []
    for sym, name in _HOT_STOCKS.get(market, []):
        try:
            q = _get_quote(sym, mkt, is_hk_us)
            hot_stocks.append({
                "symbol": sym, "name": name,
                "price": q.price, "change_pct": q.change_pct,
                "volume": q.volume,
            })
        except Exception:
            hot_stocks.append({
                "symbol": sym, "name": name,
                "price": 0, "change_pct": 0, "volume": 0,
            })

    # Sort by change_pct for rankings
    gainers = sorted(
        [s for s in hot_stocks if s["change_pct"] > 0],
        key=lambda x: -x["change_pct"]
    )
    losers = sorted(
        [s for s in hot_stocks if s["change_pct"] < 0],
        key=lambda x: x["change_pct"]
    )

    return {
        "market": market,
        "indices": indices,
        "hot_stocks": hot_stocks,
        "top_gainers": gainers[:5],
        "top_losers": losers[:5],
    }


def _get_quote(symbol: str, market: Market, is_hk_us: bool) -> StockQuote:
    if is_hk_us:
        return YFinanceProvider().get_realtime_quote(symbol, market)
    return AStockProvider().get_realtime_quote(symbol, market)
