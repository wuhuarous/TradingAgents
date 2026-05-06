"""Portfolio snapshot endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from tradingAgents.data.database.portfolio_repo import PortfolioRepository
from tradingAgents.server.routers.account import get_loaded_account

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/snapshots")
async def list_portfolio_snapshots(limit: int = Query(200, ge=1, le=2000)):
    account = await get_loaded_account()
    account_id = getattr(account, "_account_id", None)
    return {
        "account_id": account_id,
        "snapshots": await PortfolioRepository().list_snapshots(account_id=account_id, limit=limit),
    }


@router.post("/snapshots")
async def create_portfolio_snapshot(source: str = Query("manual")):
    account = await get_loaded_account()
    account_id = getattr(account, "_account_id", None)
    if account_id is None:
        return {"created": False, "message": "account unavailable"}
    snapshot = await PortfolioRepository().add_snapshot(account_id, account.to_dict(), source=source)
    return {"created": True, "snapshot": snapshot}
