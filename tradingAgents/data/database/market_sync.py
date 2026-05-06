"""Market data sync — periodic writes of real-time quotes to ClickHouse"""
from __future__ import annotations

import logging
from typing import Any

from tradingAgents.data.database.connection import get_ch_client
from tradingAgents.data.universe import get_universe_symbols
from tradingAgents.engine.dataflows.interface import Market

logger = logging.getLogger(__name__)


def sync_market_quotes():
    """Batch-write A-stock market snapshots to ClickHouse"""
    from tradingAgents.data.providers.a_stock import AStockProvider

    try:
        provider = AStockProvider()
        full = provider._get_full_list()
        if not full:
            return

        ch = get_ch_client()
        rows = []
        for symbol, d in full.items():
            price = d.get("price", 0)
            prev_close = d.get("close", 0)
            change_pct = (price - prev_close) / prev_close if prev_close else 0
            rows.append([
                symbol,
                str(d.get("name", "")),
                "a_stock",
                price,
                d.get("open", 0),
                d.get("high", 0),
                d.get("low", 0),
                prev_close,
                d.get("volume", 0),
                d.get("amount", 0),
                round(change_pct, 6),
                d.get("pe", 0),
                d.get("pb", 0),
                d.get("market_cap", 0),
                d.get("turnover", 0),
            ])

        if rows:
            ch.insert("market_quotes", rows, column_names=[
                "symbol", "name", "market", "price", "open", "high", "low",
                "close", "volume", "amount", "change_pct", "pe", "pb",
                "market_cap", "turnover",
            ])
            logger.info("Synced %d A-stock quotes to ClickHouse", len(rows))
    except Exception as e:
        logger.warning("Market quote sync failed: %s", e)


def sync_kline_daily(symbol: str) -> dict[str, Any]:
    """Sync daily K-line with indicators to ClickHouse for a single symbol"""
    from tradingAgents.data.providers.a_stock import AStockProvider
    from tradingAgents.data.technical import calculate_indicators

    try:
        provider = AStockProvider()
        df = provider.get_historical(symbol, Market.A, period="1y")
        if df.empty:
            return {"symbol": symbol, "status": "empty", "rows": 0}

        df = calculate_indicators(df)
        ch = get_ch_client()
        rows = []
        for idx, row in df.iterrows():
            rows.append([
                symbol,
                idx.date() if hasattr(idx, "date") else str(idx)[:10],
                float(row.get("开盘", row.get("Open", 0)) or 0),
                float(row.get("最高", row.get("High", 0)) or 0),
                float(row.get("最低", row.get("Low", 0)) or 0),
                float(row.get("收盘", row.get("Close", 0)) or 0),
                int(row.get("成交量", row.get("Volume", 0)) or 0),
                float(row.get("ma5", 0) or 0),
                float(row.get("ma10", 0) or 0),
                float(row.get("ma20", 0) or 0),
                float(row.get("ma60", 0) or 0),
                float(row.get("macd", 0) or 0),
                float(row.get("macd_signal", 0) or 0),
                float(row.get("macd_hist", 0) or 0),
                float(row.get("rsi14", 0) or 0),
                float(row.get("k", 0) or 0),
                float(row.get("d", 0) or 0),
                float(row.get("j", 0) or 0),
                float(row.get("boll_upper", 0) or 0),
                float(row.get("boll_mid", 0) or 0),
                float(row.get("boll_lower", 0) or 0),
            ])

        if rows:
            ch.insert("kline_daily", rows, column_names=[
                "symbol", "date", "open", "high", "low", "close", "volume",
                "ma5", "ma10", "ma20", "ma60",
                "macd", "macd_signal", "macd_hist", "rsi14",
                "k", "d", "j", "boll_upper", "boll_mid", "boll_lower",
            ])
            logger.info("Synced K-line for %s: %d rows", symbol, len(rows))
        return {"symbol": symbol, "status": "success" if rows else "empty", "rows": len(rows)}
    except Exception as e:
        logger.warning("K-line sync failed for %s: %s", symbol, e)
        return {"symbol": symbol, "status": "failed", "rows": 0, "error": str(e)[:300]}


def sync_kline_daily_batch(
    market: str = "a_stock",
    limit: int = 50,
    role: str = "all",
) -> dict[str, Any]:
    """Sync daily K-line data for a batch from the centralized stock universe."""
    if market != "a_stock":
        return {
            "market": market,
            "status": "unsupported",
            "message": "当前批量日线入库先支持 A 股；港美股后续接入对应历史行情源。",
            "requested": 0,
            "success": 0,
            "failed": 0,
            "empty": 0,
            "rows": 0,
            "items": [],
        }

    symbols = get_universe_symbols(market, role=role, limit=max(1, limit))
    results = [sync_kline_daily(symbol) for symbol in symbols]
    success = [item for item in results if item.get("status") == "success"]
    failed = [item for item in results if item.get("status") == "failed"]
    empty = [item for item in results if item.get("status") == "empty"]
    return {
        "market": market,
        "status": "success" if not failed else "partial",
        "requested": len(symbols),
        "success": len(success),
        "failed": len(failed),
        "empty": len(empty),
        "rows": sum(int(item.get("rows") or 0) for item in results),
        "items": results[:200],
    }
