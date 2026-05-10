"""Repository for portfolio snapshots."""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import PortfolioSnapshot

CN_TZ = ZoneInfo("Asia/Shanghai")


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

    async def daily_pnl(
        self,
        account_id: int | None = None,
        days: int = 30,
        current_summary: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        snapshots = await self.list_snapshots(account_id=account_id, limit=max(days * 20, 200))
        latest_by_day: dict[str, dict[str, Any]] = {}
        for item in reversed(snapshots):
            day = _china_date_key(item.get("created_at"))
            if not day:
                continue
            latest_by_day[day] = item

        if current_summary:
            now = _china_date_key(None)
            latest_by_day[now] = {
                "created_at": None,
                "total_value": float(current_summary.get("total_value") or 0),
                "total_pnl": float(current_summary.get("total_pnl") or 0),
                "total_pnl_pct": float(current_summary.get("total_pnl_pct") or 0),
                "positions_count": len(current_summary.get("positions") or []),
                "source": "current_account",
            }

        rows = sorted(latest_by_day.items(), key=lambda item: item[0])[-days:]
        result: list[dict[str, Any]] = []
        prev_total_pnl: float | None = None
        for day, item in rows:
            total_pnl = float(item.get("total_pnl") or 0)
            daily_value = 0.0 if prev_total_pnl is None else total_pnl - prev_total_pnl
            total_value = float(item.get("total_value") or 0)
            prev_value = total_value - daily_value
            result.append({
                "date": day,
                "daily_pnl": round(daily_value, 2),
                "daily_pnl_pct": round(daily_value / prev_value, 6) if prev_value > 0 else 0.0,
                "total_pnl": round(total_pnl, 2),
                "total_value": round(total_value, 2),
                "total_pnl_pct": float(item.get("total_pnl_pct") or 0),
                "positions_count": int(item.get("positions_count") or 0),
                "source": item.get("source", ""),
            })
            prev_total_pnl = total_pnl
        return result

    async def performance_report(
        self,
        account_id: int | None = None,
        days: int = 180,
        current_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        daily = await self.daily_pnl(
            account_id=account_id,
            days=days,
            current_summary=current_summary,
        )
        monthly_map: dict[str, dict[str, Any]] = {}
        for point in daily:
            month = str(point.get("date") or "")[:7]
            if not month:
                continue
            bucket = monthly_map.setdefault(month, {
                "month": month,
                "pnl": 0.0,
                "trading_days": 0,
                "positive_days": 0,
                "negative_days": 0,
                "start_value": None,
                "end_value": 0.0,
                "max_daily_pnl": None,
                "min_daily_pnl": None,
            })
            daily_pnl = float(point.get("daily_pnl") or 0)
            total_value = float(point.get("total_value") or 0)
            if bucket["start_value"] is None:
                bucket["start_value"] = max(total_value - daily_pnl, 0)
            bucket["end_value"] = total_value
            bucket["pnl"] += daily_pnl
            bucket["trading_days"] += 1
            bucket["positive_days"] += 1 if daily_pnl > 0 else 0
            bucket["negative_days"] += 1 if daily_pnl < 0 else 0
            bucket["max_daily_pnl"] = daily_pnl if bucket["max_daily_pnl"] is None else max(bucket["max_daily_pnl"], daily_pnl)
            bucket["min_daily_pnl"] = daily_pnl if bucket["min_daily_pnl"] is None else min(bucket["min_daily_pnl"], daily_pnl)

        monthly = []
        for month in sorted(monthly_map):
            bucket = monthly_map[month]
            start_value = float(bucket.get("start_value") or 0)
            pnl = float(bucket.get("pnl") or 0)
            monthly.append({
                "month": bucket["month"],
                "pnl": round(pnl, 2),
                "return_pct": round(pnl / start_value, 6) if start_value > 0 else 0.0,
                "trading_days": bucket["trading_days"],
                "positive_days": bucket["positive_days"],
                "negative_days": bucket["negative_days"],
                "win_day_rate": round(bucket["positive_days"] / bucket["trading_days"], 4) if bucket["trading_days"] else 0.0,
                "start_value": round(start_value, 2),
                "end_value": round(float(bucket.get("end_value") or 0), 2),
                "max_daily_pnl": round(float(bucket.get("max_daily_pnl") or 0), 2),
                "min_daily_pnl": round(float(bucket.get("min_daily_pnl") or 0), 2),
            })

        total_pnl = sum(float(point.get("daily_pnl") or 0) for point in daily)
        positive_days = len([point for point in daily if float(point.get("daily_pnl") or 0) > 0])
        negative_days = len([point for point in daily if float(point.get("daily_pnl") or 0) < 0])
        return {
            "daily": daily,
            "monthly": monthly,
            "summary": {
                "days": len(daily),
                "total_pnl": round(total_pnl, 2),
                "positive_days": positive_days,
                "negative_days": negative_days,
                "win_day_rate": round(positive_days / len(daily), 4) if daily else 0.0,
                "latest_total_value": daily[-1].get("total_value", 0) if daily else 0,
                "latest_total_pnl": daily[-1].get("total_pnl", 0) if daily else 0,
                "latest_total_pnl_pct": daily[-1].get("total_pnl_pct", 0) if daily else 0,
            },
        }


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


def _china_date_key(value: str | None) -> str:
    if value:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return value[:10]
        if dt.tzinfo is not None:
            return dt.astimezone(CN_TZ).date().isoformat()
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.astimezone(CN_TZ).date().isoformat()
