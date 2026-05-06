"""智能选股 — 基于多项财务指标筛选"""
import logging
from fastapi import APIRouter

from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.server.models.stock import ScreenerRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screener", tags=["screener"])

@router.post("/screen")
def screen_stocks(req: ScreenerRequest):
    """根据财务指标筛选股票，返回排序后的 Top N"""
    mkt = Market(req.market)
    is_hk_us = req.market in ("hk_stock", "us_stock")

    results = []
    for symbol, name in get_universe(req.market, role="screener"):
        try:
            fin = _get_financials(symbol, mkt, is_hk_us)
            if not fin:
                continue

            pe = fin.get("pe") or 9999
            pb = fin.get("pb") or 9999
            roe = fin.get("roe") or 0
            rev_growth = fin.get("revenue_growth") or 0

            if req.max_pe and pe > req.max_pe:
                continue
            if req.max_pb and pb > req.max_pb:
                continue
            if req.min_roe and roe < req.min_roe:
                continue
            if req.min_revenue_growth and rev_growth < req.min_revenue_growth:
                continue

            results.append({
                "symbol": symbol,
                "name": name,
                "pe": round(pe, 2) if pe != 9999 else None,
                "pb": round(pb, 2) if pb != 9999 else None,
                "roe": round(roe * 100, 1) if roe else None,
                "revenue_growth": round(rev_growth * 100, 1) if rev_growth else None,
                "market_cap": fin.get("market_cap"),
                "dividend_yield": fin.get("dividend_yield"),
            })
        except Exception as e:
            logger.debug("Screener skip %s: %s", symbol, e)
            continue

    if not results:
        return {"market": req.market, "results": [], "count": 0}

    # Sort
    sort_map = {
        "roe": lambda x: x["roe"] or 0,
        "pe": lambda x: -(x["pe"] or 9999),
        "pb": lambda x: -(x["pb"] or 9999),
        "revenue_growth": lambda x: x["revenue_growth"] or 0,
    }
    key_fn = sort_map.get(req.sort_by, sort_map["roe"])
    results.sort(key=key_fn, reverse=True)

    return {
        "market": req.market,
        "results": results[: req.limit],
        "count": len(results[: req.limit]),
    }


def _get_financials(symbol: str, market: Market, is_hk_us: bool) -> dict:
    if is_hk_us:
        return YFinanceProvider().get_financials(symbol, market)
    return AStockProvider().get_financials(symbol, market)
