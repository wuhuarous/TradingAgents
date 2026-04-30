"""Tests for bull/bear researchers and research manager"""
from unittest.mock import MagicMock, patch
from tradingAgents.engine.agents.researchers.bull import BullResearcher
from tradingAgents.engine.agents.researchers.bear import BearResearcher
from tradingAgents.engine.agents.manager import ResearchManager
from tradingAgents.engine.agents.base import BaseAgent


class TestBullResearcher:
    def test_has_role(self):
        assert BullResearcher.role == "bull_researcher"

    def test_inherits_base(self):
        assert issubclass(BullResearcher, BaseAgent)

    def test_system_prompt_set(self):
        assert "多方" in BullResearcher.system_prompt

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_debate_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"bull_points": [{"point": "强营收", "confidence": 0.8}], '
            '"overall_rating": 8, "reasoning": "基本面扎实"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = BullResearcher()
        result = agent.debate("市场评分7，基本面评分8")
        assert result["overall_rating"] == 8
        assert len(result["bull_points"]) == 1
        mock_llm.invoke.assert_called_once()


class TestBearResearcher:
    def test_has_role(self):
        assert BearResearcher.role == "bear_researcher"

    def test_inherits_base(self):
        assert issubclass(BearResearcher, BaseAgent)

    def test_system_prompt_set(self):
        assert "空方" in BearResearcher.system_prompt

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_debate_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"bear_points": [{"point": "高估值", "confidence": 0.7}], '
            '"overall_rating": 3, "reasoning": "估值偏高"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = BearResearcher()
        result = agent.debate("市场评分7，基本面评分8")
        assert result["overall_rating"] == 3
        assert len(result["bear_points"]) == 1
        mock_llm.invoke.assert_called_once()


class TestResearchManager:
    def test_has_role(self):
        assert ResearchManager.role == "research_manager"

    def test_inherits_base(self):
        assert issubclass(ResearchManager, BaseAgent)

    def test_system_prompt_set(self):
        assert "研究管理员" in ResearchManager.system_prompt

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_decide_returns_dict(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"final_score": 7, "decision": "buy", "confidence": 0.75, '
            '"key_reasons": ["营收增长", "估值合理"], "risk_summary": "宏观不确定性"}'
        )
        mock_factory.create_from_settings.return_value = mock_llm

        agent = ResearchManager()
        result = agent.decide(
            symbol="AAPL",
            analyst_reports={"market": 7, "fundamentals": 8, "news": 6},
            bull_report={"overall_rating": 8},
            bear_report={"overall_rating": 3},
        )
        assert result["final_score"] == 7
        assert result["decision"] == "buy"
        assert result["confidence"] == 0.75
        mock_llm.invoke.assert_called_once()
