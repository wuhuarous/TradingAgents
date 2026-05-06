"""Persistence for Qlib data export runs."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import QlibDataExportRun


class QlibExportRepository:
    async def save_run(self, run: dict[str, Any]) -> dict[str, Any]:
        async with get_pg_session() as session:
            row = QlibDataExportRun(
                export_id=run["export_id"],
                market=run.get("market", ""),
                source=run.get("source", "clickhouse_kline_daily"),
                target_dir=run.get("target_dir", ""),
                status=run.get("status", "success"),
                symbol_count=int(run.get("symbol_count") or 0),
                row_count=int(run.get("row_count") or 0),
                calendar_count=int(run.get("calendar_count") or 0),
                start_date=run.get("start_date", ""),
                end_date=run.get("end_date", ""),
                message=run.get("message", ""),
                metadata_json=run.get("metadata", {}),
                started_at=run.get("started_at"),
                finished_at=run.get("finished_at"),
            )
            session.add(row)
            await session.commit()
            return _run_dict(row)

    async def list_runs(self, market: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(QlibDataExportRun)
            if market:
                stmt = stmt.where(QlibDataExportRun.market == market)
            stmt = stmt.order_by(QlibDataExportRun.finished_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_run_dict(row) for row in result.scalars().all()]


def _run_dict(row: QlibDataExportRun) -> dict[str, Any]:
    return {
        "export_id": row.export_id,
        "market": row.market,
        "source": row.source,
        "target_dir": row.target_dir,
        "status": row.status,
        "symbol_count": row.symbol_count,
        "row_count": row.row_count,
        "calendar_count": row.calendar_count,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "message": row.message,
        "metadata": row.metadata_json or {},
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }
