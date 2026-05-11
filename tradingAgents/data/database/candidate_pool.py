"""Candidate pool built from full-market lightweight signals."""
from __future__ import annotations

import json
import logging
import math
import threading
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from tradingAgents.data.database.connection import get_ch_client
from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market

logger = logging.getLogger(__name__)
_CH_LOCK = threading.RLock()

CANDIDATE_COLUMNS = [
    "snapshot_id", "market", "symbol", "name", "signal_score", "price",
    "change_pct", "volume", "amount", "market_cap", "limit_up_30d",
    "double_volume_30d", "breakout", "volume_ratio", "close_position",
    "reasons", "warnings", "updated_at",
]


def refresh_candidate_pool(market: str = "a_stock", max_candidates: int = 800) -> dict[str, Any]:
    """Refresh the full-market lightweight candidate pool.

    This scans the entire A-share universe with cheap local/one-shot data only:
    realtime quote snapshot + ClickHouse daily bars. Expensive news, financials
    and LLM analysis are deliberately left to the later deep-scoring stage.
    """
    started_at = datetime.now()
    if market != "a_stock":
        return {
            "market": market,
            "status": "unsupported",
            "message": "候选池轻扫描当前先支持 A 股。",
            "total": 0,
            "selected": 0,
        }

    _ensure_schema()
    universe = get_universe(market, role="all", limit=None)
    universe_names = {symbol: name for symbol, name in universe}
    quotes = _load_a_stock_quotes()
    histories = _load_recent_kline_features(days=130)

    rows: list[list[Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, (symbol, name) in enumerate(universe):
        quote = quotes.get(symbol, {})
        hist = histories.get(symbol, {})
        item = _score_light_candidate(symbol, quote.get("name") or name, quote, hist, index)
        if not item:
            continue
        candidates.append(item)

    candidates.sort(key=lambda item: item["signal_score"], reverse=True)
    selected = candidates[: max(1, int(max_candidates or 800))]
    snapshot_id = started_at.strftime("%Y%m%d%H%M%S")
    for item in selected:
        rows.append([
            snapshot_id,
            market,
            item["symbol"],
            item.get("name") or universe_names.get(item["symbol"], item["symbol"]),
            float(item.get("signal_score") or 0),
            float(item.get("price") or 0),
            float(item.get("change_pct") or 0),
            int(float(item.get("volume") or 0)),
            float(item.get("amount") or 0),
            float(item.get("market_cap") or 0),
            1 if item.get("limit_up_30d") else 0,
            1 if item.get("double_volume_30d") else 0,
            1 if item.get("breakout") else 0,
            float(item.get("volume_ratio") or 0),
            float(item.get("close_position") or 0),
            json.dumps(item.get("reasons") or [], ensure_ascii=False),
            json.dumps(item.get("warnings") or [], ensure_ascii=False),
            started_at,
        ])

    if rows:
        with _CH_LOCK:
            get_ch_client().insert("candidate_pool", rows, column_names=CANDIDATE_COLUMNS)

    elapsed = (datetime.now() - started_at).total_seconds()
    return {
        "market": market,
        "status": "success",
        "snapshot_id": snapshot_id,
        "total": len(universe),
        "quote_coverage": len(quotes),
        "history_coverage": len(histories),
        "scored": len(candidates),
        "selected": len(selected),
        "elapsed_seconds": round(elapsed, 3),
        "top": selected[:10],
    }


def list_candidate_pool(market: str = "a_stock", limit: int = 50) -> dict[str, Any]:
    _ensure_schema()
    snapshot_id = latest_snapshot_id(market)
    if not snapshot_id:
        return {
            "market": market,
            "snapshot_id": "",
            "candidates": [],
            "summary": {"selected": 0, "updated_at": None},
        }
    with _CH_LOCK:
        rows = get_ch_client().query(f"""
            SELECT
                symbol, name, signal_score, price, change_pct, volume, amount,
                market_cap, limit_up_30d, double_volume_30d, breakout,
                volume_ratio, close_position, reasons, warnings, updated_at
            FROM candidate_pool
            WHERE market = {_sql_quote(market)}
              AND snapshot_id = {_sql_quote(snapshot_id)}
            ORDER BY signal_score DESC
            LIMIT {int(max(1, limit))}
        """).result_rows
    candidates = [_row_to_candidate(market, snapshot_id, row) for row in rows]
    updated_at = candidates[0].get("updated_at") if candidates else None
    return {
        "market": market,
        "snapshot_id": snapshot_id,
        "candidates": candidates,
        "summary": {
            "selected": len(candidates),
            "updated_at": updated_at,
        },
    }


def latest_candidate_symbols(
    market: str = "a_stock",
    limit: int = 80,
    tradable_only: bool = False,
) -> list[tuple[str, str]]:
    data = list_candidate_pool(market=market, limit=max(limit * 3, limit))
    candidates = data.get("candidates", [])
    if tradable_only:
        candidates = [
            item for item in candidates
            if not any("接近涨停" in str(warning) for warning in item.get("warnings", []))
            and not any("接近跌停" in str(warning) for warning in item.get("warnings", []))
        ]
    return [
        (str(item.get("symbol")), str(item.get("name") or item.get("symbol")))
        for item in candidates[:limit]
        if item.get("symbol")
    ]


def candidate_pool_status(market: str = "a_stock") -> dict[str, Any]:
    _ensure_schema()
    with _CH_LOCK:
        rows = get_ch_client().query(f"""
            SELECT
                snapshot_id,
                count() AS selected,
                max(updated_at) AS updated_at,
                max(signal_score) AS top_score,
                avg(signal_score) AS avg_score
            FROM candidate_pool
            WHERE market = {_sql_quote(market)}
            GROUP BY snapshot_id
            ORDER BY updated_at DESC
            LIMIT 1
        """).result_rows
    if not rows:
        return {
            "market": market,
            "available": False,
            "snapshot_id": "",
            "selected": 0,
            "updated_at": None,
        }
    snapshot_id, selected, updated_at, top_score, avg_score = rows[0]
    return {
        "market": market,
        "available": True,
        "snapshot_id": str(snapshot_id),
        "selected": int(selected or 0),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
        "top_score": round(float(top_score or 0), 2),
        "avg_score": round(float(avg_score or 0), 2),
    }


def latest_snapshot_id(market: str = "a_stock") -> str:
    with _CH_LOCK:
        rows = get_ch_client().query(f"""
            SELECT snapshot_id
            FROM candidate_pool
            WHERE market = {_sql_quote(market)}
            ORDER BY updated_at DESC
            LIMIT 1
        """).result_rows
    return str(rows[0][0]) if rows else ""


def _score_light_candidate(
    symbol: str,
    name: str,
    quote: dict[str, Any],
    hist: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    price = _float(quote.get("price"))
    prev_close = _float(quote.get("close") or hist.get("last_close"))
    volume = _float(quote.get("volume") or hist.get("last_volume"))
    amount = _float(quote.get("amount") or volume * price)
    market_cap = _float(quote.get("market_cap"))
    high = _float(quote.get("high") or price)
    low = _float(quote.get("low") or price)
    pe = _float(quote.get("pe"))
    pb = _float(quote.get("pb"))
    if price <= 0 or volume <= 0:
        return None

    change_pct = (price / prev_close - 1) if prev_close > 0 else _float(quote.get("change_pct"))
    limit_up_30d = bool(hist.get("limit_up_30d"))
    double_volume_30d = bool(hist.get("double_volume_30d"))
    volume_ratio = _float(hist.get("volume_ratio"))
    high_20 = _float(hist.get("high_20"))
    ma5 = _float(hist.get("ma5"))
    ma10 = _float(hist.get("ma10"))
    breakout = bool(high_20 > 0 and price >= high_20 * 0.995)
    close_position = (price - low) / (high - low) if high > low else 1.0
    small_cap = 0 < market_cap <= 100
    tradable = price > 0 and volume > 0 and not _is_special_treatment(name)

    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0
    if limit_up_30d:
        score += 22
        reasons.append("30 日内有涨停")
    if double_volume_30d:
        score += 16
        reasons.append("30 日内有倍量")
    if small_cap:
        score += 10
        reasons.append("市值 100 亿以内")
    if breakout:
        score += 16
        reasons.append("接近/突破 20 日前高")
    if price >= max(ma5, ma10, 0):
        score += 10
        reasons.append("站上短线均线")
    if volume_ratio >= 1.5:
        score += min(volume_ratio, 4) * 4
        reasons.append(f"量能放大 {volume_ratio:.1f}x")
    if change_pct >= 0:
        score += min(change_pct * 100, 8)
    else:
        score += max(change_pct * 100, -8)
    if amount > 0:
        score += min(math.log10(max(amount, 1)) * 2.2, 18)
    if 0 < pe <= 60:
        score += 3
    if 0 < pb <= 8:
        score += 3
    score += max(0, 8 - index / 900)

    if not limit_up_30d and not double_volume_30d:
        score -= 16
        warnings.append("近期无涨停/倍量，降低优先级")
    if not tradable:
        score -= 30
        warnings.append("ST/退市风险或不可交易")
    if change_pct >= _limit_pct(symbol) * 0.98:
        score -= 10
        warnings.append("接近涨停，后续交易层禁止追买")
    if change_pct <= -_limit_pct(symbol) * 0.98:
        score -= 10
        warnings.append("接近跌停，后续交易层限制卖出")

    if score < 20:
        return None
    return {
        "symbol": symbol,
        "name": name,
        "signal_score": round(max(score, 0), 3),
        "price": round(price, 3),
        "change_pct": round(change_pct, 6),
        "volume": volume,
        "amount": amount,
        "market_cap": market_cap,
        "limit_up_30d": limit_up_30d,
        "double_volume_30d": double_volume_30d,
        "breakout": breakout,
        "volume_ratio": round(volume_ratio, 3),
        "close_position": round(close_position, 3),
        "reasons": reasons,
        "warnings": warnings,
    }


def _load_a_stock_quotes() -> dict[str, dict[str, Any]]:
    try:
        from tradingAgents.data.providers.a_stock import AStockProvider

        return AStockProvider()._get_full_list() or {}
    except Exception as exc:
        logger.warning("Realtime full quote snapshot failed, fallback to ClickHouse: %s", exc)
    try:
        with _CH_LOCK:
            rows = get_ch_client().query("""
                SELECT
                    symbol,
                    argMax(name, timestamp) AS name,
                    argMax(price, timestamp) AS price,
                    argMax(close, timestamp) AS close,
                    argMax(high, timestamp) AS high,
                    argMax(low, timestamp) AS low,
                    argMax(volume, timestamp) AS volume,
                    argMax(amount, timestamp) AS amount,
                    argMax(pe, timestamp) AS pe,
                    argMax(pb, timestamp) AS pb,
                    argMax(market_cap, timestamp) AS market_cap
                FROM market_quotes
                WHERE market = 'a_stock'
                GROUP BY symbol
            """).result_rows
        return {
            str(row[0]): {
                "name": row[1],
                "price": row[2],
                "close": row[3],
                "high": row[4],
                "low": row[5],
                "volume": row[6],
                "amount": row[7],
                "pe": row[8],
                "pb": row[9],
                "market_cap": row[10],
            }
            for row in rows
        }
    except Exception:
        return {}


def _load_recent_kline_features(days: int = 130) -> dict[str, dict[str, Any]]:
    try:
        with _CH_LOCK:
            ch = get_ch_client()
            rows = ch.query("SELECT max(date) FROM kline_daily").result_rows
        max_date = rows[0][0] if rows and rows[0] else None
        if not max_date:
            return {}
        start_date = max_date - timedelta(days=max(days, 60))
        with _CH_LOCK:
            df = get_ch_client().query_df(f"""
                SELECT symbol, date, high, low, close, volume, ma5, ma10
                FROM kline_daily
                WHERE date >= toDate('{start_date.isoformat()}')
                ORDER BY symbol, date
            """)
        if df is None or df.empty:
            return {}
        features: dict[str, dict[str, Any]] = {}
        for symbol, group in df.groupby("symbol"):
            g = group.sort_values("date").tail(60)
            close = pd.to_numeric(g["close"], errors="coerce").dropna()
            volume = pd.to_numeric(g["volume"], errors="coerce").dropna()
            high = pd.to_numeric(g["high"], errors="coerce").dropna()
            if close.empty:
                continue
            returns = close.pct_change().fillna(0)
            avg_vol = float(volume.tail(31).iloc[:-1].mean()) if len(volume) >= 31 else float(volume.mean() or 0)
            max_ratio = float((volume.tail(30) / avg_vol).max()) if avg_vol > 0 else 0
            features[str(symbol)] = {
                "last_close": float(close.iloc[-1]),
                "last_volume": float(volume.iloc[-1]) if not volume.empty else 0,
                "limit_up_30d": bool(returns.tail(30).ge(_limit_pct(str(symbol))).any()),
                "double_volume_30d": max_ratio >= 2,
                "volume_ratio": max_ratio,
                "high_20": float(high.tail(20).max()) if not high.empty else 0,
                "ma5": _float(g["ma5"].iloc[-1]) if "ma5" in g.columns and len(g) else 0,
                "ma10": _float(g["ma10"].iloc[-1]) if "ma10" in g.columns and len(g) else 0,
            }
        return features
    except Exception as exc:
        logger.warning("Load recent kline features failed: %s", exc)
        return {}


def _row_to_candidate(market: str, snapshot_id: str, row: tuple[Any, ...]) -> dict[str, Any]:
    (
        symbol, name, signal_score, price, change_pct, volume, amount,
        market_cap, limit_up_30d, double_volume_30d, breakout,
        volume_ratio, close_position, reasons, warnings, updated_at,
    ) = row
    return {
        "snapshot_id": snapshot_id,
        "market": market,
        "symbol": str(symbol),
        "name": str(name),
        "signal_score": round(float(signal_score or 0), 3),
        "price": float(price or 0),
        "change_pct": float(change_pct or 0),
        "volume": int(volume or 0),
        "amount": float(amount or 0),
        "market_cap": float(market_cap or 0),
        "limit_up_30d": bool(limit_up_30d),
        "double_volume_30d": bool(double_volume_30d),
        "breakout": bool(breakout),
        "volume_ratio": float(volume_ratio or 0),
        "close_position": float(close_position or 0),
        "reasons": _json_list(reasons),
        "warnings": _json_list(warnings),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
    }


def _ensure_schema() -> None:
    from tradingAgents.data.database.clickhouse_schema import init_clickhouse

    with _CH_LOCK:
        init_clickhouse()


def _json_list(value: Any) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _is_special_treatment(name: str) -> bool:
    text = (name or "").upper()
    return "ST" in text or "退" in text


def _limit_pct(symbol: str) -> float:
    return 0.195 if str(symbol).startswith(("300", "301", "688")) else 0.095


def _float(value: Any) -> float:
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _sql_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"
