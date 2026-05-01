"""Tests for AI dynamic risk control engine"""
import pytest
from tradingAgents.trader.risk.stop_loss import (
    StopLossResult,
    evaluate_stop_loss,
    evaluate_take_profit,
)
from tradingAgents.trader.risk.position_sizer import calculate_position_size
from tradingAgents.trader.risk.manager import RiskManager


class TestStopLoss:
    def test_triggered_when_loss_exceeds(self):
        result = evaluate_stop_loss(avg_cost=10.0, current_price=9.5, hard_stop_pct=0.03)
        assert result.triggered is True
        assert result.stop_price == 9.7

    def test_not_triggered_within_threshold(self):
        result = evaluate_stop_loss(avg_cost=10.0, current_price=9.9, hard_stop_pct=0.03)
        assert result.triggered is False

    def test_ai_stop_price_override(self):
        result = evaluate_stop_loss(avg_cost=10.0, current_price=9.6, hard_stop_pct=0.03, ai_stop_price=9.5)
        assert result.stop_price == 9.5
        assert result.triggered is False

    def test_pnl_pct_calculation(self):
        result = evaluate_stop_loss(avg_cost=10.0, current_price=11.0)
        assert result.current_pnl_pct == pytest.approx(0.1)

    def test_zero_cost_handled(self):
        result = evaluate_stop_loss(avg_cost=0, current_price=10.0)
        assert result.current_pnl_pct == 0


class TestTakeProfit:
    def test_fixed_target_triggered(self):
        assert evaluate_take_profit(avg_cost=10.0, current_price=10.6, take_profit_pct=0.05) is True

    def test_fixed_target_not_triggered(self):
        assert evaluate_take_profit(avg_cost=10.0, current_price=10.3, take_profit_pct=0.05) is False

    def test_trailing_stop_triggered(self):
        """从最高点 12.0 回撤到 11.5 (>2%), 触发移动止盈"""
        assert evaluate_take_profit(
            avg_cost=10.0, current_price=11.5,
            trailing_pct=0.02, highest_price=12.0,
        ) is True

    def test_trailing_not_triggered_small_drop(self):
        assert evaluate_take_profit(
            avg_cost=10.0, current_price=10.3,
            trailing_pct=0.02, highest_price=10.5,
        ) is False

    def test_zero_cost_no_trigger(self):
        assert evaluate_take_profit(avg_cost=0, current_price=10.0) is False


class TestPositionSizer:
    def test_respects_max_position_pct(self):
        size = calculate_position_size(account_value=100000, price=50, risk_per_share=2, max_position_pct=0.2)
        assert size * 50 <= 100000 * 0.2

    def test_minimum_100_shares(self):
        size = calculate_position_size(account_value=10000, price=5, risk_per_share=0.5)
        assert size >= 100

    def test_round_to_100(self):
        size = calculate_position_size(account_value=100000, price=50, risk_per_share=2)
        assert size % 100 == 0

    def test_zero_price_safe(self):
        size = calculate_position_size(account_value=100000, price=0, risk_per_share=2)
        assert size >= 100


class TestRiskManager:
    def test_stop_loss_triggered_when_loss_exceeds_threshold(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=9.5, quantity=1000
        )
        assert result["stop_loss_triggered"] is True

    def test_stop_loss_not_triggered_within_threshold(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=9.9, quantity=1000
        )
        assert result["stop_loss_triggered"] is False

    def test_position_sizer_respects_max_ratio(self):
        rm = RiskManager(single_position_max_pct=0.2)
        size = rm.calculate_position_size(
            account_value=100000, price=50, risk_per_share=2
        )
        assert size * 50 <= 100000 * 0.2

    def test_daily_drawdown_triggers_halt(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(-6000, 100000)
        assert rm.should_halt_trading() is True

    def test_daily_drawdown_not_triggered(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(-3000, 100000)
        assert rm.should_halt_trading() is False

    def test_positive_pnl_never_halts(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(5000, 100000)
        assert rm.should_halt_trading() is False

    def test_dynamic_params_adjusts_for_volatility(self):
        rm = RiskManager(daily_stop_loss_pct=0.03, single_position_max_pct=0.2)
        params = rm.get_dynamic_params(volatility=0.5)
        assert params["stop_loss_pct"] > 0.03
        assert params["position_max_pct"] < 0.2

    def test_dynamic_params_caps_stop_loss(self):
        rm = RiskManager(daily_stop_loss_pct=0.03, single_position_max_pct=0.2)
        params = rm.get_dynamic_params(volatility=5.0)
        assert params["stop_loss_pct"] <= 0.10

    def test_take_profit_action(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=10.6, quantity=1000
        )
        assert result["take_profit_triggered"] is True
        assert result["action"] == "sell"

    def test_hold_action_when_no_trigger(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=10.2, quantity=1000
        )
        assert result["action"] == "hold"
