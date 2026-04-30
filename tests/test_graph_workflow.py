"""Tests for LangGraph analysis workflow"""
from unittest.mock import MagicMock, patch

import pytest

from tradingAgents.engine.graph.state import AnalysisState
from tradingAgents.engine.graph.routing import research_score_check, should_continue
from tradingAgents.engine.graph.workflow import build_analysis_graph


class TestAnalysisState:
    def test_state_keys(self):
        state: AnalysisState = {
            "symbol": "AAPL",
            "market": "us",
            "price": 0.0,
            "timestamp": "",
            "market_report": {},
            "fundamentals_report": {},
            "news_report": {},
            "bull_report": {},
            "bear_report": {},
            "research_decision": {},
            "risk_evaluations": {},
            "final_risk_params": {},
            "trader_decision": {},
            "error": None,
            "completed_at": None,
        }
        assert state["symbol"] == "AAPL"
        assert state["market"] == "us"


class TestRouting:
    def test_should_continue_no_error(self):
        result = should_continue({"error": None})
        assert result == "market_analysis"

    def test_should_continue_with_error(self):
        result = should_continue({"error": "Connection refused"})
        assert result == "__end__"

    def test_research_score_high_enough(self):
        result = research_score_check({"research_decision": {"final_score": 7}})
        assert result == "risk_evaluation"

    def test_research_score_too_low(self):
        result = research_score_check({"research_decision": {"final_score": 4}})
        assert result == "__end__"

    def test_research_score_boundary(self):
        result = research_score_check({"research_decision": {"final_score": 6}})
        assert result == "risk_evaluation"

    def test_research_score_missing(self):
        result = research_score_check({})
        assert result == "__end__"


class TestGraphStructure:
    def test_build_returns_state_graph(self):
        from langgraph.graph import StateGraph

        graph = build_analysis_graph()
        assert isinstance(graph, StateGraph)

    def test_all_nodes_registered(self):
        graph = build_analysis_graph()
        app = graph.compile()
        nodes = list(app.get_graph().nodes.keys())
        expected = [
            "__start__",
            "fetch_data",
            "market_analysis",
            "fundamentals_analysis",
            "news_analysis",
            "bull_debate",
            "bear_debate",
            "research_manager",
            "risk_evaluation",
            "risk_consensus",
            "trader_decision",
        ]
        for node in expected:
            assert node in nodes, f"Missing node: {node}"

    def test_entry_point_set(self):
        graph = build_analysis_graph()
        app = graph.compile()
        nodes = app.get_graph().nodes
        assert "__start__" in nodes


class TestGraphNodes:
    @patch("tradingAgents.engine.graph.nodes.get_quote")
    def test_fetch_data_node(self, mock_quote):
        from datetime import datetime

        from tradingAgents.engine.graph.nodes import fetch_data_node

        mock_quote.return_value = MagicMock(price=150.0, timestamp=datetime(2024, 1, 15, 10, 0, 0))
        state = {"symbol": "AAPL", "market": "us"}
        result = fetch_data_node(state)
        assert result["price"] == 150.0
        assert result.get("timestamp") is not None

    @patch("tradingAgents.engine.graph.nodes.get_quote")
    def test_fetch_data_node_error(self, mock_quote):
        from tradingAgents.engine.graph.nodes import fetch_data_node

        mock_quote.side_effect = RuntimeError("API error")
        state = {"symbol": "UNKNOWN", "market": "us"}
        result = fetch_data_node(state)
        assert "error" in result

    @patch("tradingAgents.engine.agents.analysts.market.get_quote")
    @patch("tradingAgents.engine.agents.analysts.market.get_stock_data")
    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_market_analysis_node(self, mock_factory, mock_data, mock_quote):
        from datetime import datetime
        from tradingAgents.engine.graph.nodes import market_analysis_node

        mock_quote.return_value = MagicMock(price=150.0, open=148.0,
            high=152.0, low=147.0, change_pct=0.02, volume=1000000,
            timestamp=datetime.now())
        import pandas as pd
        mock_data.return_value = pd.DataFrame({
            "Open": [145, 146, 147, 148, 149],
            "Close": [148, 149, 150, 151, 152],
        })
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"score": 7, "trend": "bullish"}'
        mock_factory.create_from_settings.return_value = mock_llm

        state = {"symbol": "AAPL", "market": "us"}
        result = market_analysis_node(state)
        assert result["market_report"]["score"] == 7

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_bull_debate_node(self, mock_factory):
        from tradingAgents.engine.graph.nodes import bull_debate_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"bull_points": [], "overall_rating": 8}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        state = {
            "symbol": "AAPL",
            "market_report": {"score": 7},
            "fundamentals_report": {"score": 8},
            "news_report": {"score": 6},
        }
        result = bull_debate_node(state)
        assert result["bull_report"]["overall_rating"] == 8

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_risk_evaluation_node(self, mock_factory):
        from tradingAgents.engine.graph.nodes import risk_evaluation_node

        responses = [
            '{"position_pct": 0.8, "stop_loss_pct": 10, "take_profit_pct": 30, "reasoning": "激进"}',
            '{"position_pct": 0.2, "stop_loss_pct": 3, "take_profit_pct": 8, "reasoning": "保守"}',
            '{"position_pct": 0.5, "stop_loss_pct": 5, "take_profit_pct": 15, "reasoning": "中性"}',
        ]
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=r) for r in responses
        ]
        mock_factory.create_from_settings.return_value = mock_llm

        state = {"research_decision": {"final_score": 7}}
        result = risk_evaluation_node(state)
        assert "aggressive" in result["risk_evaluations"]
        assert "conservative" in result["risk_evaluations"]
        assert "neutral" in result["risk_evaluations"]
        assert result["risk_evaluations"]["aggressive"]["position_pct"] == 0.8
        assert result["risk_evaluations"]["conservative"]["position_pct"] == 0.2

    def test_risk_consensus_node(self):
        from tradingAgents.engine.graph.nodes import risk_consensus_node

        state = {
            "risk_evaluations": {
                "neutral": {"position_pct": 0.5, "stop_loss_pct": 5},
            }
        }
        result = risk_consensus_node(state)
        assert result["final_risk_params"]["position_pct"] == 0.5

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_trader_decision_node(self, mock_factory):
        from tradingAgents.engine.graph.nodes import trader_decision_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"action": "buy", "quantity_pct": 0.6, '
            '"price_lower": 148.0, "price_upper": 152.0, '
            '"stop_loss": 140.0, "stop_loss_pct": 5.3, '
            '"take_profit": 170.0, "take_profit_pct": 13.3, '
            '"max_hold_days": 20, "confidence": 0.8, '
            '"reasoning": "综合看多"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        state = {
            "symbol": "AAPL",
            "price": 150.0,
            "research_decision": {"final_score": 7},
            "risk_evaluations": {},
        }
        result = trader_decision_node(state)
        assert result["trader_decision"]["action"] == "buy"
        assert result.get("completed_at") is not None
