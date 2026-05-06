"""Repository for portfolio snapshots."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import PortfolioSnapshot


class PortfolioRepository:
    async def add_snapshot(
        self,
        account_id: int,
        account_summary: dict[str, Any],
        source: str = "manual",
    ) -> dict[str, Any]:
        positions = account_summary.get("positions") or []
        async with get_pg_session() as session:
            snapshot = PortfolioSnapshot(
                account_id=account_id,
                source=source,
                cash=float(account_summary.get("cash") or 0),
                positions_value=float(account_summary.get("positions_value") or 0),
                total_value=float(account_summary.get("total_value") or 0),
                total_pnl=float(account_summary.get("total_pnl") or 0),
                total_pnl_pct=float(account_summary.get("total_pnl_pct") or 0),
                positions_count=len(positions),
                payload=account_summary,
            )
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)
            return _to_snapshot_dict(snapshot)

    async def list_snapshots(self, account_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(PortfolioSnapshot)
            if account_id is not None:
                stmt = stmt.where(PortfolioSnapshot.account_id == account_id)
            stmt = stmt.order_by(PortfolioSnapshot.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_to_snapshot_dict(row) for row in result.scalars().all()]


def _to_snapshot_dict(row: PortfolioSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "source": row.source,
        "cash": row.cash,
        "positions_value": row.positions_value,
        "total_value": row.total_value,
        "total_pnl": row.total_pnl,
        "total_pnl_pct": row.total_pnl_pct,
        "positions_count": row.positions_count,
        "payload": row.payload or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
