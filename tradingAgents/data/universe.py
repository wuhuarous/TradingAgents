"""Central stock universe resolver.

Business code should not own ticker lists. It asks this module for a
market universe, while this module prefers provider data and falls back
to an editable JSON config when live universe discovery is unavailable.
"""
from __future__ import annotations

import json
import logging
import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any

import asyncpg

from tradingAgents.config.settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_MARKETS = ("a_stock", "hk_stock", "us_stock")
CONFIG_FIRST_ROLES = {"hot", "watchlist", "kline_sync"}
FULL_UNIVERSE_ROLES = {"all", "full", "universe"}


def get_universe(
    market: str,
    role: str = "simulation",
    limit: int | None = None,
    prefer_db: bool = True,
) -> list[tuple[str, str]]:
    """Return `(symbol, name)` pairs for a market and business role."""
    market = _normalize_market(market)
    configured_limit = _role_limit(role, market)
    effective_limit = limit if limit is not None else configured_limit

    if prefer_db and settings.stock_universe_prefer_db:
        rows = _load_db_universe(market, effective_limit)
        if rows:
            return rows

    configured = _configured_universe(market)
    rows: list[tuple[str, str]] = configured
    if settings.stock_universe_use_dynamic and market == "a_stock" and role not in CONFIG_FIRST_ROLES:
        dynamic_rows = _load_a_stock_universe()
        rows = configured + dynamic_rows if dynamic_rows else configured

    rows = _dedupe(rows)
    if effective_limit:
        return rows[:effective_limit]
    return rows


def get_universe_symbols(
    market: str,
    role: str = "simulation",
    limit: int | None = None,
    prefer_db: bool = True,
) -> list[str]:
    return [
        symbol
        for symbol, _ in get_universe(market, role=role, limit=limit, prefer_db=prefer_db)
    ]


def list_markets() -> tuple[str, ...]:
    return SUPPORTED_MARKETS


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    path = Path(settings.stock_universe_config)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Stock universe config unavailable: %s", exc)
        return {"markets": {}, "roles": {}}


@lru_cache(maxsize=1)
def _load_a_stock_universe() -> list[tuple[str, str]]:
    """Discover A-share universe through AkShare, with config fallback."""
    try:
        import akshare as ak

        df = ak.stock_info_a_code_name()
        if df is None or df.empty:
            return []
        symbol_col = _first_existing(df.columns, ("code", "代码", "symbol", "证券代码"))
        name_col = _first_existing(df.columns, ("name", "名称", "股票简称", "证券简称"))
        if not symbol_col:
            return []
        rows = []
        for _, row in df.iterrows():
            symbol = str(row.get(symbol_col, "")).strip().zfill(6)
            name = str(row.get(name_col, "")).strip() if name_col else symbol
            if symbol and symbol.isdigit() and not _is_low_quality_listing(name):
                rows.append((symbol, name or symbol))
        return rows
    except Exception as exc:
        logger.info("Dynamic A-share universe unavailable, using configured seed: %s", exc)
        return []


def _configured_universe(market: str) -> list[tuple[str, str]]:
    rows = []
    for item in _load_config().get("markets", {}).get(market, []):
        if isinstance(item, dict):
            symbol = str(item.get("symbol", "")).strip()
            name = str(item.get("name", "")).strip() or symbol
        elif isinstance(item, (list, tuple)) and item:
            symbol = str(item[0]).strip()
            name = str(item[1]).strip() if len(item) > 1 else symbol
        else:
            continue
        if symbol:
            rows.append((symbol, name))
    return rows


def _load_db_universe(market: str, limit: int | None) -> list[tuple[str, str]]:
    try:
        asyncio.get_running_loop()
        return []
    except RuntimeError:
        pass
    try:
        return asyncio.run(_load_db_universe_async(market, limit))
    except Exception as exc:
        logger.debug("Stock universe DB read unavailable: %s", exc)
        return []


async def _load_db_universe_async(market: str, limit: int | None) -> list[tuple[str, str]]:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        sql = """
            SELECT symbol, name
            FROM stock_universe
            WHERE market = $1
              AND is_active = true
              AND is_blacklisted = false
            ORDER BY quality_seed_score DESC, liquidity_rank ASC, id ASC
        """
        if limit is not None:
            rows = await conn.fetch(sql + " LIMIT $2", market, int(limit))
        else:
            rows = await conn.fetch(sql, market)
        return [(str(row["symbol"]), str(row["name"] or row["symbol"])) for row in rows]
    finally:
        await conn.close()


def _role_limit(role: str, market: str) -> int | None:
    if role in FULL_UNIVERSE_ROLES:
        return None
    value = _load_config().get("roles", {}).get(role, {}).get(market)
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _normalize_market(market: str) -> str:
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"Unsupported market: {market}")
    return market


def _dedupe(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    result = []
    for symbol, name in rows:
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append((symbol, name))
    return result


def _first_existing(columns, candidates: tuple[str, ...]) -> str | None:
    col_set = {str(col): col for col in columns}
    for candidate in candidates:
        if candidate in col_set:
            return col_set[candidate]
    return None


def _is_low_quality_listing(name: str) -> bool:
    normalized = (name or "").upper()
    return "ST" in normalized or "退" in normalized


def _asyncpg_dsn() -> str:
    return settings.postgresql_url.replace("postgresql+asyncpg://", "postgresql://", 1)
