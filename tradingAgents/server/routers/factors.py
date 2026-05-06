"""Strategy factor score endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from tradingAgents.data.database.factor_repo import FactorScoreRepository

router = APIRouter(prefix="/api/strategy/factors", tags=["strategy-factors"])


@router.get("/")
async def list_factor_scores(
    market: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return {
        "market": market,
        "symbol": symbol,
        "items": await FactorScoreRepository().list_scores(
            market=market,
            symbol=symbol,
            limit=limit,
        ),
    }


@router.get("/latest")
async def latest_market_factor_scores(
    market: str = Query("a_stock"),
    limit: int = Query(20, ge=1, le=200),
):
    return {
        "market": market,
        "items": await FactorScoreRepository().latest_by_market(market=market, limit=limit),
    }
