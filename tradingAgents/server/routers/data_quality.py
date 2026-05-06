"""Data quality and standardized data snapshot endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from tradingAgents.data.database.data_quality_repo import DataQualityRepository
from tradingAgents.data.database.market_sync import sync_kline_daily_batch
from tradingAgents.data.storage.event_store import database_status_async

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


@router.get("/status")
async def get_data_quality_status():
    repo_status = await DataQualityRepository().source_status()
    return {
        **repo_status,
        "event_store": await database_status_async(),
    }


@router.get("/news")
async def list_standardized_news(
    market: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return {
        "market": market,
        "symbol": symbol,
        "items": await DataQualityRepository().list_news(market=market, symbol=symbol, limit=limit),
    }


@router.get("/market-quotes")
async def list_market_quote_snapshots(
    market: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return {
        "market": market,
        "symbol": symbol,
        "items": await DataQualityRepository().list_market_quotes(market=market, symbol=symbol, limit=limit),
    }


@router.get("/financials")
async def list_financial_snapshots(
    market: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    return {
        "market": market,
        "symbol": symbol,
        "items": await DataQualityRepository().list_financials(market=market, symbol=symbol, limit=limit),
    }


@router.post("/sync-klines")
async def sync_daily_klines(
    market: str = Query("a_stock"),
    limit: int = Query(50, ge=1, le=6000),
    role: str = Query("all"),
):
    return await run_in_threadpool(sync_kline_daily_batch, market, limit, role)
