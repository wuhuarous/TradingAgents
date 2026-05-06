from fastapi import APIRouter, Query, HTTPException

from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.cache import ttl_cache
from tradingAgents.data.technical import calculate_indicators, signal_summary

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

DETAIL_CACHE_TTL = 120


@router.get("/quote")
def get_quote(symbol: str, market: str = "a_stock"):
    mkt = Market(market)
    provider = _get_provider(market)
    quote = provider.get_realtime_quote(symbol, mkt)
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
    return _get_provider(market).search_symbols(keyword, Market(market))


@router.get("/detail")
def get_stock_detail(
    symbol: str = Query(..., min_length=1),
    market: str = Query("a_stock"),
    period: str = Query("3mo"),
):
    """个股详情：报价 + K线 + 基本面 + 财务"""
    return _get_detail_cached(symbol, market, period)


@ttl_cache(ttl=DETAIL_CACHE_TTL)
def _get_detail_cached(symbol: str, market: str, period: str) -> dict:
    mkt = Market(market)
    is_hk_us = market in ("hk_stock", "us_stock")

    try:
        quote = _get_provider(market).get_realtime_quote(symbol, mkt)
    except Exception as e:
        raise HTTPException(502, f"获取行情失败: {e}")

    kline_data = _get_kline(symbol, mkt, is_hk_us, period)
    financials = {}
    try:
        financials = _get_provider(market).get_financials(symbol, mkt)
    except Exception:
        pass

    # 技术指标信号
    signals = {}
    try:
        df = _get_provider(market).get_historical(symbol, mkt, period)
        if not df.empty:
            df_indicators = calculate_indicators(df)
            signals = signal_summary(df_indicators)
    except Exception:
        pass

    return {
        "symbol": symbol,
        "name": quote.name,
        "market": market,
        "price": quote.price,
        "change_pct": round(quote.change_pct, 4),
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "close": quote.close,
        "volume": quote.volume,
        "kline": kline_data,
        "fundamentals": financials,
        "financials": financials,
        "signals": signals,
    }


def _get_kline(symbol: str, mkt: Market, is_hk_us: bool, period: str) -> list[dict]:
    provider = _get_provider("hk_stock" if is_hk_us else "a_stock")
    df = provider.get_historical(symbol, mkt, period)

    if df is None or df.empty:
        return []

    points = []
    for idx, row in df.iterrows():
        try:
            points.append({
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx)[:10],
                "open": round(float(row.get("开盘", row.get("Open", 0))), 2),
                "high": round(float(row.get("最高", row.get("High", 0))), 2),
                "low": round(float(row.get("最低", row.get("Low", 0))), 2),
                "close": round(float(row.get("收盘", row.get("Close", 0))), 2),
                "volume": int(row.get("成交量", row.get("Volume", 0)) or 0),
            })
        except Exception:
            continue
    return points


def _get_provider(market: str):
    if market in ("hk_stock", "us_stock"):
        return YFinanceProvider()
    return AStockProvider()
