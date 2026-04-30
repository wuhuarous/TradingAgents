"""Tests for market, fundamentals, and news analyst agents"""
from unittest.mock import MagicMock, patch
from tradingAgents.engine.agents.analysts.market import MarketAnalyst
from tradingAgents.engine.agents.analysts.fundamentals import FundamentalsAnalyst
from tradingAgents.engine.agents.analysts.news import NewsAnalyst
from tradingAgents.engine.agents.base import BaseAgent


class TestMarketAnalyst:
    def test_has_role(self):
        assert MarketAnalyst.role == "market_analyst"

    def test_inherits_base(self):
        assert issubclass(MarketAnalyst, BaseAgent)

    def test_system_prompt_set(self):
        assert "技术分析" in MarketAnalyst.system_prompt

    @patch("tradingAgents.engine.agents.analysts.market.get_quote")
    @patch("tradingAgents.engine.agents.analysts.market.get_stock_data")
    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_analyze_invokes_llm(self, mock_factory, mock_data, mock_quote):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"score": 7, "trend": "bullish"}'
        mock_factory.create_from_settings.return_value = mock_llm

        mock_quote.return_value = MagicMock(
            price=150.0, open=148.0, high=152.0, low=147.0,
            change_pct=0.02, volume=1000000
        )
        import pandas as pd
        mock_data.return_value = pd.DataFrame({
            "Open": [145, 146, 147, 148, 149],
            "Close": [148, 149, 150, 151, 152],
        })

        agent = MarketAnalyst()
        result = agent.analyze("AAPL", "us")
        assert result == {"score": 7, "trend": "bullish"}
        mock_llm.invoke.assert_called_once()


class TestFundamentalsAnalyst:
    def test_has_role(self):
        assert FundamentalsAnalyst.role == "fundamentals_analyst"

    def test_inherits_base(self):
        assert issubclass(FundamentalsAnalyst, BaseAgent)

    def test_system_prompt_set(self):
        assert "基本面" in FundamentalsAnalyst.system_prompt

    @patch("tradingAgents.engine.agents.analysts.fundamentals.get_financials")
    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_analyze_invokes_llm(self, mock_factory, mock_financials):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"score": 5, "valuation": "fair"}'
        mock_factory.create_from_settings.return_value = mock_llm

        mock_financials.return_value = {"pe_ratio": 15.0, "pb_ratio": 2.5}

        agent = FundamentalsAnalyst()
        result = agent.analyze("AAPL", "us")
        assert result == {"score": 5, "valuation": "fair"}
        mock_llm.invoke.assert_called_once()


class TestNewsAnalyst:
    def test_has_role(self):
        assert NewsAnalyst.role == "news_analyst"

    def test_inherits_base(self):
        assert issubclass(NewsAnalyst, BaseAgent)

    def test_system_prompt_set(self):
        assert "新闻" in NewsAnalyst.system_prompt

    @patch("tradingAgents.engine.agents.analysts.news.get_news")
    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_analyze_invokes_llm(self, mock_factory, mock_news):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"score": 6, "sentiment": "positive"}'
        mock_factory.create_from_settings.return_value = mock_llm

        mock_news.return_value = []

        agent = NewsAnalyst()
        result = agent.analyze("AAPL", "us")
        assert result == {"score": 6, "sentiment": "positive"}
        mock_llm.invoke.assert_called_once()
