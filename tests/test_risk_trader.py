"""Tests for risk management debaters and trader agent"""
from unittest.mock import MagicMock, patch
from tradingAgents.engine.agents.risk_mgmt.aggressive import AggressiveDebater
from tradingAgents.engine.agents.risk_mgmt.conservative import ConservativeDebater
from tradingAgents.engine.agents.risk_mgmt.neutral import NeutralDebater
from tradingAgents.engine.agents.trader import TraderAgent
from tradingAgents.engine.agents.base import BaseAgent


class TestAggressiveDebater:
    def test_has_role(self):
        assert AggressiveDebater.role == "aggressive_risk"

    def test_inherits_base(self):
        assert issubclass(AggressiveDebater, BaseAgent)

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_evaluate_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"position_pct": 0.8, "stop_loss_pct": 10, '
            '"take_profit_pct": 30, "reasoning": "高赔率机会"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = AggressiveDebater()
        result = agent.evaluate({"final_score": 8, "decision": "buy"})
        assert result["position_pct"] == 0.8
        assert result["stop_loss_pct"] == 10
        mock_llm.invoke.assert_called_once()


class TestConservativeDebater:
    def test_has_role(self):
        assert ConservativeDebater.role == "conservative_risk"

    def test_inherits_base(self):
        assert issubclass(ConservativeDebater, BaseAgent)

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_evaluate_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"position_pct": 0.2, "stop_loss_pct": 3, '
            '"take_profit_pct": 8, "reasoning": "保守配置"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = ConservativeDebater()
        result = agent.evaluate({"final_score": 6, "decision": "hold"})
        assert result["position_pct"] == 0.2
        assert result["stop_loss_pct"] == 3
        mock_llm.invoke.assert_called_once()


class TestNeutralDebater:
    def test_has_role(self):
        assert NeutralDebater.role == "neutral_risk"

    def test_inherits_base(self):
        assert issubclass(NeutralDebater, BaseAgent)

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_evaluate_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"position_pct": 0.5, "stop_loss_pct": 5, '
            '"take_profit_pct": 15, "reasoning": "平衡配置"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = NeutralDebater()
        result = agent.evaluate({"final_score": 7, "decision": "buy"})
        assert result["position_pct"] == 0.5
        assert result["stop_loss_pct"] == 5
        mock_llm.invoke.assert_called_once()


class TestTraderAgent:
    def test_has_role(self):
        assert TraderAgent.role == "trader"

    def test_inherits_base(self):
        assert issubclass(TraderAgent, BaseAgent)

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_decide_returns_full_decision(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"action": "buy", "quantity_pct": 0.6, '
            '"price_lower": 148.0, "price_upper": 152.0, '
            '"stop_loss": 140.0, "stop_loss_pct": 5.3, '
            '"take_profit": 170.0, "take_profit_pct": 13.3, '
            '"max_hold_days": 20, "confidence": 0.8, '
            '"reasoning": "技术面和基本面共振"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = TraderAgent()
        result = agent.decide(
            symbol="AAPL",
            price=150.0,
            research_result={"final_score": 7, "decision": "buy"},
            risk_evaluations={
                "aggressive": {"position_pct": 0.8},
                "conservative": {"position_pct": 0.2},
                "neutral": {"position_pct": 0.5},
            },
        )
        assert result["action"] == "buy"
        assert result["quantity_pct"] == 0.6
        assert result["price_lower"] == 148.0
        assert result["confidence"] == 0.8
        mock_llm.invoke.assert_called_once()

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_decide_handles_missing_risk_eval(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"action": "hold", "quantity_pct": 0.0, '
            '"price_lower": 0, "price_upper": 0, '
            '"stop_loss": 0, "stop_loss_pct": 0, '
            '"take_profit": 0, "take_profit_pct": 0, '
            '"max_hold_days": 0, "confidence": 0.3, '
            '"reasoning": "风控数据不完整"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = TraderAgent()
        result = agent.decide(
            symbol="AAPL",
            price=150.0,
            research_result={"final_score": 5},
            risk_evaluations={},
        )
        assert result["action"] == "hold"
        mock_llm.invoke.assert_called_once()
