"""调度器运行器 — 轻量任务调度"""
from datetime import datetime
from typing import Callable, Optional

from tradingAgents.trader.scheduler.jobs import (
    intraday_monitoring_job,
    market_close_settlement_job,
    market_open_trading_job,
    pre_market_analysis_job,
)


class TradingScheduler:
    """轻量调度器 — 管理定时任务注册与手动触发"""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._running = False
        self._register_jobs()

    def _register_jobs(self):
        self.add_job(
            "pre_market_analysis",
            "pre_market_analysis",
            pre_market_analysis_job,
            cron="0 8 * * mon-fri",
        )
        self.add_job(
            "market_open_trading",
            "market_open_trading",
            market_open_trading_job,
            cron="30 9 * * mon-fri",
        )
        self.add_job(
            "intraday_monitoring",
            "intraday_monitoring",
            intraday_monitoring_job,
            cron="*/5 9-15 * * mon-fri",
        )
        self.add_job(
            "market_close_settlement",
            "market_close_settlement",
            market_close_settlement_job,
            cron="0 15 * * mon-fri",
        )

    def add_job(self, job_id: str, name: str, func: Callable, cron: str = ""):
        self._jobs[job_id] = {
            "id": job_id,
            "name": name,
            "func": func,
            "cron": cron,
            "next_run": None,
        }

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def list_jobs(self) -> list[dict]:
        return [
            {"id": j["id"], "name": j["name"], "cron": j["cron"]}
            for j in self._jobs.values()
        ]

    def run_job(self, job_id: str) -> Optional[dict]:
        """手动触发单个任务"""
        job = self._jobs.get(job_id)
        if job:
            return job["func"]()
        return None
