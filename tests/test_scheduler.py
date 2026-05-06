"""Tests for automated trading scheduler"""
import pytest
from tradingAgents.trader.scheduler.runner import TradingScheduler
from tradingAgents.trader.scheduler.jobs import (
    pre_market_analysis_job,
    market_open_trading_job,
    market_close_settlement_job,
    intraday_monitoring_job,
    review_backfill_job,
)


class TestTradingScheduler:
    def test_scheduler_initializes_with_jobs(self):
        sched = TradingScheduler()
        jobs = sched.list_jobs()
        assert len(jobs) >= 4

    def test_job_names_registered(self):
        sched = TradingScheduler()
        ids = {j["id"] for j in sched.list_jobs()}
        assert "pre_market_analysis" in ids
        assert "market_open_trading" in ids
        assert "intraday_monitoring" in ids
        assert "market_close_settlement" in ids
        assert "review_backfill" in ids

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
        assert result["status"] in ("monitored", "no_positions")

    def test_run_job_by_id(self):
        sched = TradingScheduler()
        result = sched.run_job("pre_market_analysis")
        assert isinstance(result, dict)  # pre_market_analysis_job returns dict with status

    def test_run_unknown_job(self):
        sched = TradingScheduler()
        result = sched.run_job("nonexistent")
        assert result is None


class TestJobFunctions:
    def test_pre_market_returns_dict(self):
        result = pre_market_analysis_job()
        assert isinstance(result, dict)
        assert "status" in result

    def test_market_open_returns_dict(self):
        result = market_open_trading_job()
        assert result["status"] in ("executed", "no_plans")
        assert "timestamp" in result

    def test_market_close_returns_dict(self):
        result = market_close_settlement_job()
        assert result["status"] in ("settled", "no_positions")

    def test_intraday_returns_dict(self):
        result = intraday_monitoring_job()
        assert result["status"] in ("monitored", "no_positions")

    def test_review_backfill_returns_dict(self):
        result = review_backfill_job()
        assert result["status"] == "completed"
        assert "count" in result
