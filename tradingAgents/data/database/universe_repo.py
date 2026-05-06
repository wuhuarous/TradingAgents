"""Repository for stock universe persistence."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import StockUniverse, StockUniverseSyncRun


class StockUniverseRepository:
    async def list_symbols(
        self,
        market: str | None = None,
        active_only: bool = True,
        include_blacklisted: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(StockUniverse)
            if market:
                stmt = stmt.where(StockUniverse.market == market)
            if active_only:
                stmt = stmt.where(StockUniverse.is_active.is_(True))
            if not include_blacklisted:
                stmt = stmt.where(StockUniverse.is_blacklisted.is_(False))
            stmt = (
                stmt.order_by(
                    StockUniverse.quality_seed_score.desc(),
                    StockUniverse.liquidity_rank.asc(),
                    StockUniverse.id.asc(),
                )
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_to_universe_dict(row) for row in result.scalars().all()]

    async def count_symbols(
        self,
        market: str | None = None,
        active_only: bool = True,
        include_blacklisted: bool = False,
    ) -> int:
        async with get_pg_session() as session:
            stmt = select(func.count()).select_from(StockUniverse)
            if market:
                stmt = stmt.where(StockUniverse.market == market)
            if active_only:
                stmt = stmt.where(StockUniverse.is_active.is_(True))
            if not include_blacklisted:
                stmt = stmt.where(StockUniverse.is_blacklisted.is_(False))
            return int((await session.execute(stmt)).scalar() or 0)

    async def upsert_many(
        self,
        market: str,
        rows: list[dict[str, Any]],
        source: str = "config",
    ) -> dict[str, Any]:
        started = datetime.utcnow()
        inserted = 0
        updated = 0
        async with get_pg_session() as session:
            for index, row in enumerate(rows):
                symbol = str(row.get("symbol", "")).strip()
                if not symbol:
                    continue
                result = await session.execute(
                    select(StockUniverse).where(
                        StockUniverse.market == market,
                        StockUniverse.symbol == symbol,
                    )
                )
                item = result.scalar_one_or_none()
                payload = {
                    "name": str(row.get("name", "")).strip() or symbol,
                    "exchange": str(row.get("exchange", "")).strip(),
                    "industry": str(row.get("industry", "")).strip(),
                    "source": str(row.get("source") or source),
                    "market_cap": _float(row.get("market_cap")),
                    "avg_turnover": _float(row.get("avg_turnover")),
                    "liquidity_rank": int(row.get("liquidity_rank") or index + 1),
                    "quality_seed_score": _float(row.get("quality_seed_score")),
                    "is_active": bool(row.get("is_active", True)),
                    "is_blacklisted": bool(row.get("is_blacklisted", False)),
                    "metadata_json": row.get("metadata") or {},
                }
                if item:
                    for key, value in payload.items():
                        setattr(item, key, value)
                    updated += 1
                else:
                    session.add(StockUniverse(market=market, symbol=symbol, **payload))
                    inserted += 1
            run = StockUniverseSyncRun(
                market=market,
                source=source,
                status="success",
                total=len(rows),
                inserted=inserted,
                updated=updated,
                started_at=started,
                finished_at=datetime.utcnow(),
            )
            session.add(run)
            await session.commit()
            return {
                "market": market,
                "source": source,
                "total": len(rows),
                "inserted": inserted,
                "updated": updated,
                "status": "success",
            }

    async def recent_sync_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            result = await session.execute(
                select(StockUniverseSyncRun)
                .order_by(StockUniverseSyncRun.started_at.desc())
                .limit(limit)
            )
            return [_to_sync_run_dict(row) for row in result.scalars().all()]


def _to_universe_dict(row: StockUniverse) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "name": row.name,
        "exchange": row.exchange,
        "industry": row.industry,
        "source": row.source,
        "market_cap": row.market_cap,
        "avg_turnover": row.avg_turnover,
        "liquidity_rank": row.liquidity_rank,
        "quality_seed_score": row.quality_seed_score,
        "is_active": row.is_active,
        "is_blacklisted": row.is_blacklisted,
        "metadata": row.metadata_json or {},
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _to_sync_run_dict(row: StockUniverseSyncRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "source": row.source,
        "status": row.status,
        "total": row.total,
        "inserted": row.inserted,
        "updated": row.updated,
        "message": row.message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
