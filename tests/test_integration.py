"""End-to-end integration tests: analysis -> decision -> trade -> risk control"""
import pytest
from tradingAgents.trader.account import VirtualAccount
from tradingAgents.trader.risk.manager import RiskManager
from tradingAgents.trader.strategy import StrategyEngine


class TestFullPipeline:
    def test_analysis_to_trade_flow(self):
        trader_decision = {
            "action": "buy",
            "quantity_pct": 0.2,
            "price_lower": 9.5,
            "price_upper": 10.5,
            "stop_loss": 9.0,
            "stop_loss_pct": 0.05,
            "take_profit": 11.5,
            "take_profit_pct": 0.10,
            "confidence": 0.75,
        }

        account = VirtualAccount(initial_capital=100000)
        plan = StrategyEngine.generate_plan(trader_decision, account.cash)
        assert plan["action"] == "buy"
        assert plan["quantity"] >= 100

        avg_price = (plan["price_range"][0] + plan["price_range"][1]) / 2
        order = account.buy("000001", "平安银行", avg_price, plan["quantity"], "AI推荐")
        assert order is not None
        assert "000001" in account.positions

        rm = RiskManager(daily_stop_loss_pct=0.05)
        result = rm.check_position("000001", avg_price, avg_price, plan["quantity"])
        assert result["action"] == "hold"

        result2 = rm.check_position("000001", avg_price, avg_price * 0.92, plan["quantity"])
        assert result2["stop_loss_triggered"] is True
        assert result2["action"] == "sell"

    def test_risk_manager_position_sizing(self):
        rm = RiskManager(single_position_max_pct=0.2, daily_stop_loss_pct=0.03)
        size = rm.calculate_position_size(100000, 50, risk_per_share=1.5)
        assert size * 50 <= 20000

    def test_multiple_trades_pnl_tracking(self):
        account = VirtualAccount(initial_capital=100000)
        account.buy("000001", "平安银行", 10, 2000, "")
        account.sell("000001", 12, 2000, "")
        assert account.total_pnl == 4000
        assert account.total_pnl_pct == pytest.approx(0.04)

    def test_buy_sell_roundtrip_updates_cash(self):
        account = VirtualAccount(initial_capital=100000)
        account.buy("AAPL", "Apple", 150, 100, "buy")
        cash_after_buy = account.cash
        account.sell("AAPL", 155, 100, "sell")
        assert account.cash > cash_after_buy
        assert "AAPL" not in account.positions

    def test_risk_halt_prevents_new_trades(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(-6000, 100000)
        assert rm.should_halt_trading() is True

    def test_risk_halt_resets_with_profit(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(2000, 100000)
        assert rm.should_halt_trading() is False

    def test_scheduler_jobs_all_registered(self):
        from tradingAgents.trader.scheduler.runner import TradingScheduler
        sched = TradingScheduler()
        jobs = {j["id"] for j in sched.list_jobs()}
        assert "pre_market_analysis" in jobs
        assert "market_open_trading" in jobs
        assert "intraday_monitoring" in jobs
        assert "market_close_settlement" in jobs

    def test_memory_review_roundtrip(self):
        import tempfile
        import os
        from tradingAgents.engine.agents.utils.memory import TradingMemory
        tmpdir = tempfile.mkdtemp()
        memory = TradingMemory(memory_dir=tmpdir)
        memory.record_decision({"symbol": "000001", "action": "buy", "score": 8})
        summary = memory.daily_review(
            account_summary={"total_value": 110000, "total_pnl_pct": 0.10},
            trades=[{"symbol": "000001", "pnl": 5000}, {"symbol": "000002", "pnl": -2000}],
        )
        assert "复盘" in summary
        assert "盈利: 1 笔" in summary
        assert "亏损: 1 笔" in summary

    def test_api_health_endpoint(self):
        from tradingAgents.server.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_api_account_endpoint(self):
        from tradingAgents.server.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/account/")
        assert response.status_code == 200
        data = response.json()
        assert "total_value" in data
        assert "cash" in data
