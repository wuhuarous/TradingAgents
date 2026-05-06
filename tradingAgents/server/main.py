"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradingAgents.server.routers import account, analysis, stocks, trading
from tradingAgents.server.routers import backtest, data_quality, factors, market, screener, news_router, settings_router
from tradingAgents.server.routers import portfolio, research, simulation, universe

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    return _scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    from tradingAgents.data.database.connection import init_pg
    from tradingAgents.data.database.clickhouse_schema import init_clickhouse
    from tradingAgents.trader.scheduler.runner import TradingScheduler

    try:
        await init_pg()
        logger.info("PostgreSQL initialized")
    except Exception as e:
        logger.warning("PostgreSQL init failed (server will start without DB): %s", e)
    try:
        init_clickhouse()
        logger.info("ClickHouse initialized")
    except Exception as e:
        logger.warning("ClickHouse init failed (server will start without CH): %s", e)

    _scheduler = TradingScheduler()
    try:
        _scheduler.start()
        logger.info("TradingScheduler started via lifespan")
    except Exception as e:
        logger.warning("Scheduler start failed: %s", e)
    yield
    if _scheduler:
        _scheduler.stop()
        logger.info("TradingScheduler stopped via lifespan")


app = FastAPI(title="TradingAgents API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(trading.router)
app.include_router(analysis.router)
app.include_router(stocks.router)
app.include_router(market.router)
app.include_router(screener.router)
app.include_router(news_router.router)
app.include_router(settings_router.router)
app.include_router(simulation.router)
app.include_router(universe.router)
app.include_router(portfolio.router)
app.include_router(factors.router)
app.include_router(data_quality.router)
app.include_router(backtest.router)
app.include_router(research.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- Scheduler API ----

@app.get("/api/scheduler/status")
def scheduler_status():
    if _scheduler is None:
        return {"running": False, "jobs": []}
    return {
        "running": _scheduler.running,
        "jobs": _scheduler.list_jobs(),
    }


@app.post("/api/scheduler/trigger/{job_id}")
def scheduler_trigger(job_id: str):
    if _scheduler is None:
        return {"error": "scheduler not started"}
    result = _scheduler.run_job(job_id)
    if result is None:
        return {"error": f"job '{job_id}' not found"}
    return result
