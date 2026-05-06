"""Tests for virtual account, position/order managers, and strategy"""
from datetime import datetime, timedelta

import pytest
from tradingAgents.trader.account import VirtualAccount
from tradingAgents.trader.position import PositionManager
from tradingAgents.trader.order import OrderManager, OrderStatus
from tradingAgents.trader.strategy import StrategyEngine
from tradingAgents.trader.trade_rules import compute_trade_costs


def make_buy_orders_previous_day(acc: VirtualAccount) -> None:
    for order in acc.orders:
        if order.get("action") == "buy":
            order["timestamp"] = (datetime.now() - timedelta(days=1)).isoformat()
    for symbol in list(acc.positions.keys()):
        acc.positions[symbol]["available_quantity"] = acc._available_sell_quantity(symbol)


class TestVirtualAccount:
    def test_initial_capital(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.initial_capital == 100000
        assert acc.cash == 100000
        assert acc.total_value == 100000

    def test_total_value_includes_positions(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.positions["000001"] = {
            "name": "平安", "quantity": 1000,
            "avg_cost": 10.0, "current_price": 12.0,
        }
        assert acc.total_value == 100000 + 12000

    def test_total_pnl(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.positions["000001"] = {
            "name": "平安", "quantity": 1000,
            "avg_cost": 10.0, "current_price": 12.0,
        }
        assert acc.total_pnl == 12000
        assert acc.total_pnl_pct == pytest.approx(0.12)

    def test_can_buy_with_sufficient_cash(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.can_buy(price=50, quantity=1000) is True

    def test_cannot_buy_with_insufficient_cash(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.can_buy(price=200, quantity=1000) is False

    def test_buy_updates_cash_and_positions(self):
        acc = VirtualAccount(initial_capital=100000)
        order = acc.buy("000001", "平安银行", 10.0, 1000, "测试买入")
        assert order is not None
        assert order["action"] == "buy"
        costs = compute_trade_costs("buy", "a_stock", 10.0, 1000)
        assert acc.cash == pytest.approx(100000 + costs.cash_delta)
        assert "000001" in acc.positions
        assert acc.positions["000001"]["quantity"] == 1000

    def test_buy_average_cost_update(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安", 10.0, 1000, "")
        acc.buy("000001", "平安", 12.0, 500, "")
        assert acc.positions["000001"]["quantity"] == 1500
        c1 = compute_trade_costs("buy", "a_stock", 10.0, 1000)
        c2 = compute_trade_costs("buy", "a_stock", 12.0, 500)
        assert acc.positions["000001"]["avg_cost"] == pytest.approx((abs(c1.cash_delta) + abs(c2.cash_delta)) / 1500)

    def test_buy_insufficient_cash_returns_none(self):
        acc = VirtualAccount(initial_capital=1000)
        order = acc.buy("000001", "平安", 10.0, 1000, "")
        assert order is None

    def test_sell_updates_cash_and_positions(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安银行", 10.0, 1000, "")
        make_buy_orders_previous_day(acc)
        order = acc.sell("000001", 12.0, 500, "测试卖出")
        assert order is not None
        assert order["action"] == "sell"
        costs = compute_trade_costs("sell", "a_stock", 12.0, 500)
        assert order["revenue"] == pytest.approx(costs.cash_delta)
        assert acc.positions["000001"]["quantity"] == 500

    def test_sell_removes_zero_position(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安", 10.0, 1000, "")
        make_buy_orders_previous_day(acc)
        acc.sell("000001", 12.0, 1000, "")
        assert "000001" not in acc.positions

    def test_a_share_t1_blocks_same_day_sell(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安", 10.0, 1000, "")
        order = acc.sell("000001", 12.0, 1000, "")
        assert order is None
        assert acc.positions["000001"]["available_quantity"] == 0

    def test_sell_unknown_symbol_returns_none(self):
        acc = VirtualAccount(initial_capital=100000)
        order = acc.sell("UNKNOWN", 10.0, 100, "")
        assert order is None

    def test_get_position_summary(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安", 10.0, 1000, "")
        summary = acc.get_position_summary()
        assert len(summary) == 1
        assert summary[0]["symbol"] == "000001"
        assert summary[0]["pnl_pct"] < 0

    def test_to_dict(self):
        acc = VirtualAccount(initial_capital=50000)
        d = acc.to_dict()
        assert d["initial_capital"] == 50000
        assert d["cash"] == 50000
        assert d["total_value"] == 50000
        assert d["total_pnl"] == 0

    def test_orders_tracked(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安", 10.0, 1000, "reason1")
        make_buy_orders_previous_day(acc)
        acc.sell("000001", 12.0, 500, "reason2")
        assert len(acc.orders) == 2
        assert len(acc.trade_log) == 2


class TestPositionManager:
    def test_update_adds_position(self):
        pm = PositionManager()
        pm.update("000001", "平安", 1000, 10.0)
        assert pm.get("000001") == {
            "name": "平安", "quantity": 1000, "current_price": 10.0,
        }

    def test_update_removes_zero(self):
        pm = PositionManager()
        pm.update("000001", "平安", 1000, 10.0)
        pm.update("000001", "平安", 0, 10.0)
        assert pm.get("000001") is None

    def test_all_returns_copy(self):
        pm = PositionManager()
        pm.update("000001", "平安", 1000, 10.0)
        result = pm.all()
        assert "000001" in result
        result["000001"]["quantity"] = 999
        assert pm.get("000001")["quantity"] == 1000


class TestOrderManager:
    def test_add_sets_id_and_status(self):
        om = OrderManager()
        om.add({"symbol": "AAPL", "action": "buy"})
        assert om.orders[0]["id"] == 1
        assert om.orders[0]["status"] == OrderStatus.FILLED

    def test_history_respects_limit(self):
        om = OrderManager()
        for i in range(10):
            om.add({"symbol": f"S{i}"})
        assert len(om.history(5)) == 5
        assert len(om.history(20)) == 10


class TestStrategyEngine:
    def test_generate_buy_plan(self):
        decision = {
            "action": "buy", "quantity_pct": 0.6,
            "price_lower": 48.0, "price_upper": 52.0,
            "stop_loss": 45.0, "take_profit": 60.0,
            "confidence": 0.8,
        }
        plan = StrategyEngine.generate_plan(decision, 100000)
        assert plan["action"] == "buy"
        assert plan["budget"] == 60000
        assert plan["price_range"] == [48.0, 52.0]
        assert plan["quantity"] > 0

    def test_generate_hold_plan(self):
        decision = {"action": "hold", "quantity_pct": 0, "confidence": 0.3}
        plan = StrategyEngine.generate_plan(decision, 100000)
        assert plan["action"] == "hold"
        assert plan["quantity"] == 0

    def test_generate_plan_min_quantity(self):
        decision = {
            "action": "buy", "quantity_pct": 0.01,
            "price_lower": 50.0, "price_upper": 55.0,
            "stop_loss": 45, "take_profit": 65, "confidence": 0.5,
        }
        plan = StrategyEngine.generate_plan(decision, 100000)
        assert plan["quantity"] >= 100
