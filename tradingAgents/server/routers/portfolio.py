"""Portfolio snapshot endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from tradingAgents.data.database.portfolio_repo import PortfolioRepository
from tradingAgents.server.routers.account import get_account_summary_fast, get_loaded_account

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/snapshots")
async def list_portfolio_snapshots(limit: int = Query(200, ge=1, le=2000)):
    account_id, _ = await get_account_summary_fast()
    return {
        "account_id": account_id,
        "snapshots": await PortfolioRepository().list_snapshots(account_id=account_id, limit=limit),
    }


@router.get("/daily-pnl")
async def daily_portfolio_pnl(days: int = Query(30, ge=2, le=365)):
    account_id, summary = await get_account_summary_fast()
    return {
        "account_id": account_id,
        "days": days,
        "points": await PortfolioRepository().daily_pnl(
            account_id=account_id,
            days=days,
            current_summary=summary,
        ),
    }


@router.get("/report")
async def portfolio_report(days: int = Query(180, ge=7, le=730)):
    account_id, summary = await get_account_summary_fast()
    report = await PortfolioRepository().performance_report(
        account_id=account_id,
        days=days,
        current_summary=summary,
    )
    return {
        "account_id": account_id,
        "days": days,
        **report,
    }


@router.post("/snapshots")
async def create_portfolio_snapshot(source: str = Query("manual")):
    account = await get_loaded_account()
    account_id = getattr(account, "_account_id", None)
    if account_id is None:
        return {"created": False, "message": "account unavailable"}
    snapshot = await PortfolioRepository().add_snapshot(account_id, account.to_dict(), source=source)
    return {"created": True, "snapshot": snapshot}
