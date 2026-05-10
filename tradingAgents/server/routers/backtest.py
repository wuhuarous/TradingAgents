"""Backtest endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from tradingAgents.data.database.backtest_repo import BacktestRepository
from tradingAgents.data.database.research_repo import ResearchRepository
from tradingAgents.trader.backtest import BacktestConfig, BaselineMomentumBacktester, ShortTerm100BacktestStrategy

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


@router.post("/run")
async def run_backtest(
    strategy: str = Query("baseline_momentum", pattern="^(baseline_momentum|short_term_100)$"),
    market: str = Query("a_stock"),
    period: str = Query("1y", pattern="^(3mo|6mo|1y)$"),
    initial_cash: float = Query(1_000_000, gt=0),
    universe_limit: int = Query(200, ge=5, le=6000),
    top_n: int = Query(5, ge=1, le=20),
    rebalance_days: int = Query(20, ge=5, le=60),
):
    if top_n > universe_limit:
        raise HTTPException(status_code=400, detail="top_n 不能大于 universe_limit")
    config = BacktestConfig(
        strategy=strategy,
        market=market,
        period=period,
        initial_cash=initial_cash,
        universe_limit=universe_limit,
        top_n=top_n,
        rebalance_days=rebalance_days,
    )
    try:
        backtester = ShortTerm100BacktestStrategy() if strategy == "short_term_100" else BaselineMomentumBacktester()
        result = await run_in_threadpool(backtester.run, config)
        saved = await BacktestRepository().save_result(result)
        await ResearchRepository().add_backtest_to_leaderboard(saved)
        return saved
    except Exception as exc:
        logger.exception("Backtest failed")
        raise HTTPException(status_code=500, detail=f"回测执行失败: {exc}") from exc


@router.get("/runs")
async def list_backtest_runs(
    market: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    return {
        "market": market,
        "runs": await BacktestRepository().list_runs(market=market, limit=limit),
    }


@router.get("/runs/{run_id}")
async def get_backtest_run(run_id: str):
    result = await BacktestRepository().get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    return result
