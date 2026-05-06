"""Stock universe management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from tradingAgents.data.database.universe_repo import StockUniverseRepository
from tradingAgents.data.universe import get_universe, list_markets

router = APIRouter(prefix="/api/universe", tags=["universe"])


@router.get("/")
async def list_stock_universe(
    market: str | None = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    active_only: bool = Query(True),
    include_blacklisted: bool = Query(False),
):
    repo = StockUniverseRepository()
    return {
        "market": market,
        "total": await repo.count_symbols(
            market=market,
            active_only=active_only,
            include_blacklisted=include_blacklisted,
        ),
        "items": await repo.list_symbols(
            market=market,
            active_only=active_only,
            include_blacklisted=include_blacklisted,
            limit=limit,
        ),
    }


@router.post("/sync")
async def sync_stock_universe(
    market: str | None = Query(None),
    role: str = Query("all"),
    limit: int = Query(10000, ge=1, le=10000),
):
    markets = [market] if market else list(list_markets())
    repo = StockUniverseRepository()
    results = []
    for item_market in markets:
        rows = [
            {"symbol": symbol, "name": name, "source": "universe_resolver"}
            for symbol, name in get_universe(item_market, role=role, limit=limit, prefer_db=False)
        ]
        results.append(await repo.upsert_many(item_market, rows, source=f"resolver:{role}"))
    return {"results": results}


@router.get("/sync-runs")
async def list_universe_sync_runs(limit: int = Query(20, ge=1, le=100)):
    return {"runs": await StockUniverseRepository().recent_sync_runs(limit=limit)}
