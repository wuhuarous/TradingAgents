"""Market data sync — periodic writes of real-time quotes to ClickHouse"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingAgents.data.database.connection import get_ch_client
from tradingAgents.data.universe import get_universe_symbols
from tradingAgents.engine.dataflows.interface import Market

logger = logging.getLogger(__name__)
KLINE_DAILY_COLUMNS = [
    "symbol", "date", "open", "high", "low", "close", "volume",
    "ma5", "ma10", "ma20", "ma60",
    "macd", "macd_signal", "macd_hist", "rsi14",
    "k", "d", "j", "boll_upper", "boll_mid", "boll_lower",
]


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
            ch.insert("kline_daily", rows, column_names=KLINE_DAILY_COLUMNS)
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


def sync_a_stock_daily_full(
    limit: int | None = None,
    batch_size: int = 50,
    max_workers: int = 4,
    force: bool = False,
    min_rows: int = 200,
    sleep_seconds: float = 0.2,
    status_path: str | None = None,
    persist_universe: bool = False,
) -> dict[str, Any]:
    """Sync full A-share daily K-line data into ClickHouse in resumable batches.

    The function is intentionally conservative:
    - discovers all active A-share codes from AkShare;
    - skips symbols that already have enough daily rows unless ``force=True``;
    - writes a small JSON status file after every batch so long runs can be
      monitored and restarted safely.
    """
    started_at = datetime.utcnow()
    batch_size = max(1, int(batch_size or 50))
    max_workers = max(1, int(max_workers or 1))
    min_rows = max(1, int(min_rows or 200))
    status_file = Path(status_path) if status_path else None

    _ensure_clickhouse_schema()
    universe = discover_a_stock_universe()
    if limit:
        universe = universe[: max(1, int(limit))]

    coverage = _kline_daily_coverage()
    pending: list[tuple[str, str]] = []
    skipped = 0
    for symbol, name in universe:
        row_count = int(coverage.get(symbol, {}).get("rows") or 0)
        if not force and row_count >= min_rows:
            skipped += 1
            continue
        pending.append((symbol, name))

    status: dict[str, Any] = {
        "market": "a_stock",
        "status": "running",
        "started_at": started_at.isoformat(),
        "updated_at": started_at.isoformat(),
        "total": len(universe),
        "pending": len(pending),
        "skipped": skipped,
        "success": 0,
        "empty": 0,
        "failed": 0,
        "rows": 0,
        "inserted_batches": 0,
        "batch_size": batch_size,
        "max_workers": max_workers,
        "force": force,
        "min_rows": min_rows,
        "recent_errors": [],
    }
    _write_status(status_file, status)
    if persist_universe and universe:
        status["phase"] = "persist_universe"
        status["updated_at"] = datetime.utcnow().isoformat()
        _write_status(status_file, status)
        _persist_universe_best_effort(universe)
        status["phase"] = "sync_klines"
        status["updated_at"] = datetime.utcnow().isoformat()
        _write_status(status_file, status)

    ch = get_ch_client()
    for batch_index, batch in enumerate(_chunks(pending, batch_size), start=1):
        rows_to_insert: list[list[Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_fetch_kline_daily_rows, symbol, name): (symbol, name)
                for symbol, name in batch
            }
            for future in as_completed(futures):
                symbol, _ = futures[future]
                try:
                    item = future.result()
                except Exception as exc:
                    item = {"symbol": symbol, "status": "failed", "rows": 0, "error": str(exc)[:300]}

                item_status = str(item.get("status") or "failed")
                if item_status == "success":
                    status["success"] += 1
                    status["rows"] += int(item.get("rows") or 0)
                    rows_to_insert.extend(item.get("data_rows") or [])
                elif item_status == "empty":
                    status["empty"] += 1
                else:
                    status["failed"] += 1
                    errors = status.setdefault("recent_errors", [])
                    errors.append({
                        "symbol": symbol,
                        "error": item.get("error", "unknown error"),
                    })
                    status["recent_errors"] = errors[-20:]

        if rows_to_insert:
            ch.insert("kline_daily", rows_to_insert, column_names=KLINE_DAILY_COLUMNS)
            status["inserted_batches"] += 1

        status["updated_at"] = datetime.utcnow().isoformat()
        status["completed"] = status["success"] + status["empty"] + status["failed"] + status["skipped"]
        status["current_batch"] = batch_index
        _write_status(status_file, status)
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    status["status"] = "success" if status["failed"] == 0 else "partial"
    status["finished_at"] = datetime.utcnow().isoformat()
    status["completed"] = status["success"] + status["empty"] + status["failed"] + status["skipped"]
    _write_status(status_file, status)
    return status


def discover_a_stock_universe() -> list[tuple[str, str]]:
    """Return full A-share code/name pairs without applying strategy filters."""
    try:
        import akshare as ak

        df = ak.stock_info_a_code_name()
        if df is None or df.empty:
            return []
        symbol_col = _first_existing(df.columns, ("code", "代码", "symbol", "证券代码"))
        name_col = _first_existing(df.columns, ("name", "名称", "股票简称", "证券简称"))
        if not symbol_col:
            return []
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _, row in df.iterrows():
            symbol = str(row.get(symbol_col, "")).strip().zfill(6)
            name = str(row.get(name_col, "")).strip() if name_col else symbol
            if not symbol or not symbol.isdigit() or symbol in seen:
                continue
            seen.add(symbol)
            rows.append((symbol, name or symbol))
        return rows
    except Exception as exc:
        logger.warning("A-share universe discovery failed: %s", exc)
        return [
            (symbol, symbol)
            for symbol in get_universe_symbols("a_stock", role="all", limit=6000, prefer_db=False)
        ]


def _fetch_kline_daily_rows(symbol: str, name: str = "") -> dict[str, Any]:
    from tradingAgents.data.providers.a_stock import AStockProvider
    from tradingAgents.data.technical import calculate_indicators

    try:
        provider = AStockProvider()
        df = provider.get_historical(symbol, Market.A, period="1y")
        if df is None or df.empty:
            return {"symbol": symbol, "name": name, "status": "empty", "rows": 0}
        df = calculate_indicators(df)
        rows: list[list[Any]] = []
        for idx, row in df.iterrows():
            rows.append([
                symbol,
                idx.date() if hasattr(idx, "date") else str(idx)[:10],
                _float(row.get("开盘", row.get("Open", 0))),
                _float(row.get("最高", row.get("High", 0))),
                _float(row.get("最低", row.get("Low", 0))),
                _float(row.get("收盘", row.get("Close", 0))),
                max(0, int(_float(row.get("成交量", row.get("Volume", 0))))),
                _float(row.get("ma5", 0)),
                _float(row.get("ma10", 0)),
                _float(row.get("ma20", 0)),
                _float(row.get("ma60", 0)),
                _float(row.get("macd", 0)),
                _float(row.get("macd_signal", 0)),
                _float(row.get("macd_hist", 0)),
                _float(row.get("rsi14", 0)),
                _float(row.get("k", 0)),
                _float(row.get("d", 0)),
                _float(row.get("j", 0)),
                _float(row.get("boll_upper", 0)),
                _float(row.get("boll_mid", 0)),
                _float(row.get("boll_lower", 0)),
            ])
        return {
            "symbol": symbol,
            "name": name,
            "status": "success" if rows else "empty",
            "rows": len(rows),
            "data_rows": rows,
        }
    except Exception as exc:
        logger.warning("K-line full sync failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "name": name, "status": "failed", "rows": 0, "error": str(exc)[:300]}


def _kline_daily_coverage() -> dict[str, dict[str, Any]]:
    try:
        rows = get_ch_client().query("""
            SELECT symbol, count() AS rows, max(date) AS max_date
            FROM kline_daily
            GROUP BY symbol
        """).result_rows
        return {
            str(symbol): {"rows": int(row_count or 0), "max_date": str(max_date or "")}
            for symbol, row_count, max_date in rows
        }
    except Exception:
        return {}


def _persist_universe_best_effort(universe: list[tuple[str, str]]) -> None:
    try:
        from tradingAgents.data.database.universe_repo import StockUniverseRepository

        rows = [
            {
                "symbol": symbol,
                "name": name,
                "source": "akshare_full",
                "is_blacklisted": _is_special_treatment(name),
                "metadata": {"is_special_treatment": _is_special_treatment(name)},
            }
            for symbol, name in universe
        ]
        asyncio.run(StockUniverseRepository().upsert_many("a_stock", rows, source="akshare_full"))
    except Exception as exc:
        logger.warning("Persist stock universe failed: %s", exc)


def _ensure_clickhouse_schema() -> None:
    try:
        from tradingAgents.data.database.clickhouse_schema import init_clickhouse

        init_clickhouse()
    except Exception as exc:
        logger.warning("ClickHouse schema init skipped: %s", exc)


def _write_status(path: Path | None, status: dict[str, Any]) -> None:
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _chunks(values: list[tuple[str, str]], size: int):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _first_existing(columns, candidates: tuple[str, ...]) -> str | None:
    col_set = {str(col): col for col in columns}
    for candidate in candidates:
        if candidate in col_set:
            return col_set[candidate]
    return None


def _is_special_treatment(name: str) -> bool:
    text = (name or "").upper()
    return "ST" in text or "退" in text


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
