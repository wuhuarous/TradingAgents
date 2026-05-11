"""Simulation auto-trading endpoints."""
from fastapi import APIRouter, Query

from tradingAgents.server.routers.account import get_loaded_account
from tradingAgents.data.database.candidate_pool import (
    candidate_pool_status,
    list_candidate_pool,
    refresh_candidate_pool,
)
from tradingAgents.data.storage.event_store import database_status, read_events
from tradingAgents.data.universe import get_universe
from tradingAgents.trader.auto_strategy import QualityMomentumStrategy
from tradingAgents.trader.quant_readiness import build_quant_readiness
from tradingAgents.trader.review_backfill import backfill_review_returns

router = APIRouter(prefix="/api/simulation", tags=["simulation"])
strategy = QualityMomentumStrategy()


@router.get("/summary")
async def get_simulation_summary():
    return strategy.summary(await get_loaded_account())


@router.get("/readiness")
async def get_quant_readiness():
    return build_quant_readiness(await get_loaded_account(), strategy)


@router.get("/candidates")
def get_candidates(
    market: str = Query("a_stock"),
    limit: int = Query(10, ge=1, le=30),
    live: bool = Query(False),
):
    universe_total = len(get_universe(market, role="all", limit=None))
    return {
        "market": market,
        "mode": "live" if live else "fast",
        "universe_role": "all",
        "universe_total": universe_total,
        "candidates": (
            strategy.candidates(market=market, limit=limit)
            if live
            else strategy.fast_candidates(market=market, limit=limit)
        ),
    }


@router.get("/rankings")
def get_all_market_rankings(limit: int = Query(10, ge=1, le=20)):
    return strategy.all_market_rankings(limit=limit)


@router.post("/candidate-pool/refresh")
def refresh_simulation_candidate_pool(
    market: str = Query("a_stock"),
    limit: int = Query(800, ge=20, le=3000),
):
    return refresh_candidate_pool(market=market, max_candidates=limit)


@router.get("/candidate-pool")
def get_simulation_candidate_pool(
    market: str = Query("a_stock"),
    limit: int = Query(50, ge=1, le=500),
):
    return list_candidate_pool(market=market, limit=limit)


@router.get("/candidate-pool/status")
def get_simulation_candidate_pool_status(market: str = Query("a_stock")):
    return candidate_pool_status(market=market)


@router.post("/run")
async def run_simulation_cycle(market: str = Query("a_stock")):
    return await strategy.arun_cycle(await get_loaded_account(), market=market)


@router.get("/runs")
def get_recent_runs(limit: int = Query(20, ge=1, le=100)):
    return {
        "runs": strategy.recent_runs(limit=limit),
    }


@router.get("/events")
def get_simulation_events(
    kind: str = Query("news"),
    limit: int = Query(50, ge=1, le=500),
):
    return {"kind": kind, "events": read_events(kind, limit=limit)}


@router.get("/event-store/status")
def get_event_store_status():
    return database_status()


@router.post("/backfill-reviews")
def backfill_reviews(
    limit: int = Query(20, ge=1, le=100),
    force_latest: bool = Query(False),
):
    """Backfill current returns for past simulated candidates."""
    return backfill_review_returns(strategy.recent_runs(limit=limit), force_latest=force_latest)
