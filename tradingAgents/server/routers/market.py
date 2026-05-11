"""市场行情总览 — 指数、涨跌榜、热门股票（带缓存加速）"""
import asyncio
import contextlib
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from tradingAgents.data.cache import ttl_cache
from tradingAgents.data.database.data_quality_repo import persist_market_quotes_sync
from tradingAgents.data.storage.event_store import append_event, append_events
from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market, StockQuote
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider, _fetch_sina_indices
from tradingAgents.trader.trade_rules import is_limit_down, is_limit_up

router = APIRouter(prefix="/api/market", tags=["market"])

MARKET_CACHE_TTL = 60  # 行情总览缓存 1 分钟
SECTOR_CACHE_TTL = 300  # 板块数据稍慢，单独缓存 5 分钟

# A 股指数使用新浪指数代码
_SINA_INDEX_MAP = {
    "s_sh000001": "上证指数",
    "s_sz399001": "深证成指",
    "s_sz399006": "创业板指",
}

_INDEX_MAP = {
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

@router.get("/overview")
def get_market_overview(market: str = Query("a_stock")):
    """获取指定市场总览：指数 + 热门股票实时报价 + 排名"""
    return _get_market_overview_cached(market)


@ttl_cache(ttl=MARKET_CACHE_TTL)
def _get_market_overview_cached(market: str) -> dict:
    mkt = Market(market)

    indices = _get_indices(market, mkt)
    universe_stocks = _get_market_stock_snapshot(market, mkt)
    hot_stocks = _get_hot_stocks(market, mkt, universe_stocks)

    gainers = sorted(
        [s for s in universe_stocks if s["change_pct"] > 0],
        key=lambda x: -x["change_pct"]
    )
    losers = sorted(
        [s for s in universe_stocks if s["change_pct"] < 0],
        key=lambda x: x["change_pct"]
    )
    if not gainers and universe_stocks:
        gainers = sorted(universe_stocks, key=lambda x: x.get("change_pct", 0), reverse=True)
    if not losers and universe_stocks:
        losers = sorted(universe_stocks, key=lambda x: x.get("change_pct", 0))

    top_turnover = sorted(
        [s for s in universe_stocks if s.get("turnover", 0) > 0],
        key=lambda x: x.get("turnover", 0),
        reverse=True,
    )[:10]

    snapshot_time = datetime.now().isoformat(timespec="seconds")
    snapshot = {
        "market": market,
        "created_at": snapshot_time,
        "indices": indices,
        "breadth": _market_breadth(market, universe_stocks),
        "hot_sectors": _get_hot_sectors(market),
        "hot_stocks": hot_stocks,
        "top_gainers": gainers[:10],
        "top_losers": losers[:10],
        "top_turnover": top_turnover,
        "universe_count": len(universe_stocks),
        "data_note": "A股榜单来自全量实时快照；港美股受免费行情源限制，使用配置股票池。",
    }
    append_event("market_snapshot", snapshot)
    append_events("market_quote", [
        _quote_event(item, market, snapshot_time, "index")
        for item in indices
    ])
    quote_events = [
        _quote_event(item, market, snapshot_time, "stock")
        for item in hot_stocks
    ]
    append_events("market_quote", quote_events)
    persist_market_quotes_sync([
        _quote_event(item, market, snapshot_time, "index")
        for item in indices
    ] + quote_events)
    return snapshot


@router.websocket("/ws/{market}")
async def market_overview_ws(websocket: WebSocket, market: str):
    """Push market overview snapshots to the frontend."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(_get_market_overview_cached(market))
            await asyncio.sleep(8)
    except WebSocketDisconnect:
        return


def _get_indices(market: str, mkt: Market) -> list[dict]:
    # A 股指数使用新浪指数 API
    if market == "a_stock":
        return _get_a_indices()
    return _get_hk_us_indices(market, mkt)


def _get_a_indices() -> list[dict]:
    indices = []
    sina_data = _fetch_sina_indices(list(_SINA_INDEX_MAP.keys()))
    for code, name in _SINA_INDEX_MAP.items():
        d = sina_data.get(code)
        if d:
            indices.append({
                "symbol": code, "name": name,
                "price": round(d["price"], 2),
                "open": 0, "high": 0, "low": 0, "close": 0,
                "change_pct": round(d["change_pct"], 4),
                "change_amount": round(d["change_amount"], 2),
                "volume": d["volume"],
            })
        else:
            indices.append({"symbol": code, "name": name, "price": 0, "change_pct": 0})
    return indices


def _get_hk_us_indices(market: str, mkt: Market) -> list[dict]:
    indices = []
    for sym, name in _INDEX_MAP.get(market, []):
        try:
            q = _get_quote_fast(sym, mkt, market)
            indices.append({
                "symbol": sym, "name": name,
                "price": round(q.price, 2),
                "open": round(q.open, 2),
                "high": round(q.high, 2),
                "low": round(q.low, 2),
                "close": round(q.close, 2),
                "change_pct": round(q.change_pct, 4),
                "volume": q.volume,
            })
        except Exception:
            indices.append({"symbol": sym, "name": name, "price": 0, "change_pct": 0})
    return indices


def _get_market_stock_snapshot(market: str, mkt: Market) -> list[dict]:
    if market == "a_stock":
        return _get_all_a_stock_snapshot()
    return _get_hot_hk_us_stocks(market, mkt)


def _get_hot_stocks(market: str, mkt: Market, stocks: list[dict] | None = None) -> list[dict]:
    # A 股：从全量快照中按成交额动态生成活跃标的
    if market == "a_stock":
        source = stocks or _get_all_a_stock_snapshot()
        return sorted(
            [s for s in source if s.get("turnover", 0) > 0],
            key=lambda x: x.get("turnover", 0),
            reverse=True,
        )[:12]

    return _get_hot_hk_us_stocks(market, mkt)


def _get_all_a_stock_snapshot() -> list[dict]:
    provider = AStockProvider()
    full = provider._get_full_list()
    stocks = []
    for sym, d in full.items():
        item = _a_stock_row(sym, d)
        if item:
            stocks.append(item)
    return stocks


def _get_hot_a_stocks() -> list[dict]:
    """从全量缓存列表中查找热门 A 股"""
    provider = AStockProvider()
    full = provider._get_full_list()
    if not full:
        return _get_hot_hk_us_stocks("a_stock", Market.A)

    stocks = []
    for sym, name in get_universe("a_stock", role="hot"):
        try:
            d = full.get(sym)
            if not d:
                continue
            price = d.get("price", 0)
            prev_close = d.get("close", 0)
            stocks.append({
                "symbol": sym,
                "name": name,
                "price": round(price, 2),
                "open": round(d.get("open", 0), 2),
                "high": round(d.get("high", 0), 2),
                "low": round(d.get("low", 0), 2),
                "close": round(prev_close, 2),
                "change_pct": round((price - prev_close) / prev_close, 4) if prev_close else 0,
                "volume": d.get("volume", 0),
                "turnover": d.get("amount", 0),
                "pe": d.get("pe", 0),
            })
        except Exception:
            stocks.append({"symbol": sym, "name": name, "price": 0, "change_pct": 0, "volume": 0})
    return stocks


def _a_stock_row(symbol: str, d: dict[str, Any]) -> dict | None:
    try:
        price = float(d.get("price", 0) or 0)
        prev_close = float(d.get("close", 0) or 0)
        if price <= 0 or prev_close <= 0:
            return None
        return {
            "symbol": symbol,
            "name": str(d.get("name", "")) or symbol,
            "price": round(price, 2),
            "open": round(float(d.get("open", 0) or 0), 2),
            "high": round(float(d.get("high", 0) or 0), 2),
            "low": round(float(d.get("low", 0) or 0), 2),
            "close": round(prev_close, 2),
            "change_pct": round((price - prev_close) / prev_close, 4) if prev_close else 0,
            "volume": int(d.get("volume", 0) or 0),
            "turnover": float(d.get("amount", 0) or 0),
            "pe": float(d.get("pe", 0) or 0),
            "pb": float(d.get("pb", 0) or 0),
            "market_cap": float(d.get("market_cap", 0) or 0),
        }
    except Exception:
        return None


def _get_hot_hk_us_stocks(market: str, mkt: Market) -> list[dict]:
    stocks = []
    for sym, name in get_universe(market, role="hot"):
        try:
            q = _get_quote_fast(sym, mkt, market)
            stocks.append({
                "symbol": sym,
                "name": name,
                "price": round(q.price, 2),
                "open": round(q.open, 2),
                "high": round(q.high, 2),
                "low": round(q.low, 2),
                "close": round(q.close, 2),
                "change_pct": round(q.change_pct, 4),
                "volume": q.volume,
            })
        except Exception:
            stocks.append({"symbol": sym, "name": name, "price": 0, "change_pct": 0, "volume": 0})
    return stocks


def _market_breadth(market: str, stocks: list[dict]) -> dict:
    if not stocks:
        return {
            "total": 0,
            "up": 0,
            "down": 0,
            "flat": 0,
            "limit_up": 0,
            "limit_down": 0,
            "up_ratio": 0,
            "down_ratio": 0,
        }
    up = len([s for s in stocks if s.get("change_pct", 0) > 0])
    down = len([s for s in stocks if s.get("change_pct", 0) < 0])
    flat = len(stocks) - up - down
    limit_up = 0
    limit_down = 0
    if market == "a_stock":
        for s in stocks:
            if is_limit_up(s["symbol"], s.get("price", 0), s.get("close", 0), s.get("name", "")):
                limit_up += 1
            if is_limit_down(s["symbol"], s.get("price", 0), s.get("close", 0), s.get("name", "")):
                limit_down += 1
    total = len(stocks)
    return {
        "total": total,
        "up": up,
        "down": down,
        "flat": flat,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "up_ratio": round(up / total, 4) if total else 0,
        "down_ratio": round(down / total, 4) if total else 0,
    }


@ttl_cache(ttl=SECTOR_CACHE_TTL)
def _get_hot_sectors(market: str) -> list[dict]:
    if market != "a_stock":
        return []
    sectors: list[dict] = []
    sectors.extend(_fetch_ths_industry_sectors(limit=8))
    sectors.extend(_fetch_ths_concept_sectors(limit=8))
    seen = set()
    result = []
    for item in sorted(sectors, key=lambda x: x.get("change_pct", 0), reverse=True):
        key = (item.get("type"), item.get("name"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= 12:
            break
    return result


def _fetch_ths_industry_sectors(limit: int = 8) -> list[dict]:
    try:
        import akshare as ak

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.stock_board_industry_summary_ths()
        rows = []
        for _, row in df.head(limit).iterrows():
            rows.append({
                "type": "industry",
                "name": str(row.get("板块", "")),
                "change_pct": _pct(row.get("涨跌幅")),
                "net_inflow": _num(row.get("净流入")),
                "turnover": _num(row.get("总成交额")),
                "up_count": int(_num(row.get("上涨家数"))),
                "down_count": int(_num(row.get("下跌家数"))),
                "leader": str(row.get("领涨股", "")),
                "leader_price": _num(row.get("领涨股-最新价")),
                "leader_change_pct": _pct(row.get("领涨股-涨跌幅")),
                "source": "同花顺行业",
            })
        return [row for row in rows if row["name"]]
    except Exception:
        return []


def _fetch_ths_concept_sectors(limit: int = 8) -> list[dict]:
    try:
        import akshare as ak

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.stock_fund_flow_concept(symbol="即时")
        rows = []
        for _, row in df.head(limit).iterrows():
            rows.append({
                "type": "concept",
                "name": str(row.get("行业", "")),
                "change_pct": _pct(row.get("行业-涨跌幅")),
                "net_inflow": _num(row.get("净额")),
                "turnover": _num(row.get("流入资金")) + _num(row.get("流出资金")),
                "up_count": 0,
                "down_count": 0,
                "leader": str(row.get("领涨股", "")),
                "leader_price": _num(row.get("当前价")),
                "leader_change_pct": _pct(row.get("领涨股-涨跌幅")),
                "source": "同花顺概念资金流",
            })
        return [row for row in rows if row["name"]]
    except Exception:
        return []


def _num(value) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pct(value) -> float:
    return round(_num(value) / 100, 4)


def _get_quote_fast(symbol: str, mkt: Market, market: str) -> StockQuote:
    if market in ("hk_stock", "us_stock"):
        return YFinanceProvider().get_realtime_quote(symbol, mkt)
    return AStockProvider().get_realtime_quote(symbol, mkt)


def _quote_event(item: dict, market: str, created_at: str, asset_type: str) -> dict:
    return {
        "created_at": created_at,
        "market": market,
        "symbol": item.get("symbol", ""),
        "name": item.get("name", ""),
        "source": "market_overview",
        "asset_type": asset_type,
        "price": item.get("price", 0),
        "open": item.get("open", 0),
        "high": item.get("high", 0),
        "low": item.get("low", 0),
        "close": item.get("close", 0),
        "change_pct": item.get("change_pct", 0),
        "volume": item.get("volume", 0),
        "turnover": item.get("turnover", 0),
        "quality_score": 80 if item.get("price", 0) else 35,
    }
