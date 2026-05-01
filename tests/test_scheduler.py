"""Tests for automated trading scheduler"""
import pytest
from tradingAgents.trader.scheduler.runner import TradingScheduler
from tradingAgents.trader.scheduler.jobs import (
    pre_market_analysis_job,
    market_open_trading_job,
    market_close_settlement_job,
    intraday_monitoring_job,
)


class TestTradingScheduler:
    def test_scheduler_initializes_with_jobs(self):
        sched = TradingScheduler()
        jobs = sched.list_jobs()
        assert len(jobs) >= 4

    def test_job_names_registered(self):
        sched = TradingScheduler()
        jobs = {j["name"] for j in sched.list_jobs()}
        assert "pre_market_analysis" in jobs
        assert "market_open_trading" in jobs
        assert "intraday_monitoring" in jobs
        assert "market_close_settlement" in jobs

    def test_start_stop(self):
        sched = TradingScheduler()
        assert sched.running is False
        sched.start()
        assert sched.running is True
        sched.stop()
        assert sched.running is False

    def test_list_jobs_returns_ids(self):
        sched = TradingScheduler()
        ids = {j["id"] for j in sched.list_jobs()}
        assert "pre_market_analysis" in ids
        assert "market_open_trading" in ids

    def test_run_job_valid(self):
        sched = TradingScheduler()
        result = sched.run_job("intraday_monitoring")
        assert result is not None
        assert result["status"] == "monitored"

    def test_run_job_by_id(self):
        sched = TradingScheduler()
        result = sched.run_job("pre_market_analysis")
        assert isinstance(result, list)  # pre_market_analysis_job returns list

    def test_run_unknown_job(self):
        sched = TradingScheduler()
        result = sched.run_job("nonexistent")
        assert result is None


class TestJobFunctions:
    def test_pre_market_returns_list(self):
        result = pre_market_analysis_job()
        assert isinstance(result, list)

    def test_market_open_returns_dict(self):
        result = market_open_trading_job()
        assert result["status"] == "executed"
        assert "timestamp" in result

    def test_market_close_returns_dict(self):
        result = market_close_settlement_job()
        assert result["status"] == "settled"

    def test_intraday_returns_dict(self):
        result = intraday_monitoring_job()
        assert result["status"] == "monitored"
