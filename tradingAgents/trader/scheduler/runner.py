"""调度器运行器 — APScheduler 集成自动交易"""
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from tradingAgents.config.settings import settings
from tradingAgents.data.universe import get_universe_symbols
from tradingAgents.trader.scheduler.jobs import (
    candidate_pool_refresh_job,
    intraday_monitoring_job,
    market_close_settlement_job,
    news_refresh_job,
    market_open_trading_job,
    pre_market_analysis_job,
    review_backfill_job,
    simulation_auto_cycle_job,
)
from tradingAgents.data.database.market_sync import sync_market_quotes, sync_kline_daily
from tradingAgents.utils.timezone import CN_TZ

logger = logging.getLogger(__name__)


def _sync_watchlist_klines():
    for sym in get_universe_symbols("a_stock", role="kline_sync"):
        try:
            sync_kline_daily(sym)
        except Exception:
            pass


class TradingScheduler:
    """基于 APScheduler 的自动交易调度器"""

    _instance: Optional["TradingScheduler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        job_stores = {"default": MemoryJobStore()}
        self._scheduler = BackgroundScheduler(
            jobstores=job_stores,
            timezone=CN_TZ,
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        self._jobs_config = self._build_jobs()

    def _build_jobs(self) -> list[dict]:
        return [
            {
                "id": "pre_market_analysis",
                "name": "盘前分析",
                "func": pre_market_analysis_job,
                "cron": f"{settings.pre_market_analysis_time.split(':')[1]} {settings.pre_market_analysis_time.split(':')[0]} * * mon-fri",
            },
            {
                "id": "market_open_trading",
                "name": "开盘交易",
                "func": market_open_trading_job,
                "cron": f"30 9 * * mon-fri",
            },
            {
                "id": "intraday_monitoring",
                "name": "盘中监控",
                "func": intraday_monitoring_job,
                "cron": "*/5 9-15 * * mon-fri",
            },
            {
                "id": "simulation_auto_cycle",
                "name": "模拟自动交易",
                "func": simulation_auto_cycle_job,
                "cron": "40 10,14 * * mon-fri",
            },
            {
                "id": "market_close_settlement",
                "name": "收盘结算",
                "func": market_close_settlement_job,
                "cron": "0 15 * * mon-fri",
            },
            {
                "id": "market_quote_sync",
                "name": "行情数据同步",
                "func": sync_market_quotes,
                "cron": "*/1 9-15 * * mon-fri",
            },
            {
                "id": "news_refresh",
                "name": "新闻资讯刷新",
                "func": news_refresh_job,
                "cron": "0 8-23 * * *",
            },
            {
                "id": "candidate_pool_refresh",
                "name": "全市场候选池刷新",
                "func": candidate_pool_refresh_job,
                "cron": "25 9 * * mon-fri",
            },
            {
                "id": "candidate_pool_refresh_1040",
                "name": "10:40 候选池刷新",
                "func": candidate_pool_refresh_job,
                "cron": "35 10 * * mon-fri",
            },
            {
                "id": "candidate_pool_refresh_1400",
                "name": "14:00 候选池刷新",
                "func": candidate_pool_refresh_job,
                "cron": "55 13 * * mon-fri",
            },
            {
                "id": "kline_daily_sync",
                "name": "日K线同步",
                "func": _sync_watchlist_klines,
                "cron": "30 15 * * mon-fri",
            },
            {
                "id": "review_backfill",
                "name": "复盘收益回填",
                "func": review_backfill_job,
                "cron": "45 15 * * mon-fri",
            },
        ]

    def start(self):
        for job_cfg in self._jobs_config:
            self._scheduler.add_job(
                func=job_cfg["func"],
                trigger=CronTrigger.from_crontab(job_cfg["cron"], timezone=CN_TZ),
                id=job_cfg["id"],
                name=job_cfg["name"],
                replace_existing=True,
            )
        self._scheduler.start()
        logger.info("TradingScheduler started with %d jobs", len(self._jobs_config))

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("TradingScheduler stopped")

    @property
    def running(self) -> bool:
        return self._scheduler.running

    def list_jobs(self) -> list[dict]:
        if self._scheduler.running:
            jobs = self._scheduler.get_jobs()
            return [
                {
                    "id": j.id,
                    "name": j.name,
                    "cron": str(j.trigger) if j.trigger else "manual",
                    "next_run": j.next_run_time.astimezone(CN_TZ).isoformat() if j.next_run_time else None,
                    "timezone": "Asia/Shanghai",
                }
                for j in jobs
            ]
        return [{"id": j["id"], "name": j["name"], "cron": j["cron"], "next_run": None, "timezone": "Asia/Shanghai"} for j in self._jobs_config]

    def run_job(self, job_id: str) -> Optional[dict]:
        for job_cfg in self._jobs_config:
            if job_cfg["id"] == job_id:
                try:
                    return job_cfg["func"]()
                except Exception as e:
                    logger.error("Job %s failed: %s", job_id, e)
                    return {"error": str(e)}
        return None
