"""Tests for agent base class and utilities"""
import pytest
from unittest.mock import MagicMock, patch
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json, parse_rating


class TestStructuredOutput:
    def test_extract_json_from_text(self):
        result = extract_json('{"score": 8, "confidence": 0.9}')
        assert result == {"score": 8, "confidence": 0.9}

    def test_extract_json_mixed_with_text(self):
        text = "Here is the analysis:\n\n{\"score\": 7, \"reasoning\": \"bullish\"}\n\nDone."
        result = extract_json(text)
        assert result["score"] == 7
        assert result["reasoning"] == "bullish"

    def test_extract_json_none(self):
        assert extract_json("no json here") == {}

    def test_extract_json_nested(self):
        text = '{"data": {"score": 5}, "list": [1,2,3]}'
        result = extract_json(text)
        assert result["data"]["score"] == 5

    def test_parse_rating_full(self):
        result = parse_rating('{"score": 8, "confidence": 0.85, "reasoning": "strong buy"}')
        assert result["score"] == 8
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "strong buy"

    def test_parse_rating_clamps(self):
        result = parse_rating('{"score": 15, "confidence": 2.0}')
        assert result["score"] == 10
        assert result["confidence"] == 1.0

    def test_parse_rating_invalid_int(self):
        with pytest.raises((ValueError, TypeError)):
            parse_rating('{"score": "abc"}')

    def test_parse_rating_defaults(self):
        result = parse_rating("{}")
        assert result["score"] == 5
        assert result["confidence"] == 0.5


class TestBaseAgent:
    def test_role_default(self):
        assert BaseAgent.role == "base"

    def test_system_prompt_default(self):
        assert BaseAgent.system_prompt == ""

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_invoke_calls_llm(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "response text"
        mock_factory.create_from_settings.return_value = mock_llm

        agent = BaseAgent()
        result = agent.invoke("analyze AAPL", "market data here")

        assert result == "response text"
        mock_factory.create_from_settings.assert_called_once()

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_custom_model_name(self, mock_factory):
        mock_llm = MagicMock()
        mock_factory.create_from_settings.return_value = mock_llm

        agent = BaseAgent(model_name="gpt-4o")
        mock_factory.create_from_settings.assert_called_once_with(model="gpt-4o")

    @patch("tradingAgents.engine.agents.base.LLMFactory")
    def test_invoke_includes_system_prompt(self, mock_factory):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "ok"
        mock_factory.create_from_settings.return_value = mock_llm

        agent = BaseAgent()
        agent.system_prompt = "You are a stock analyst."
        agent.invoke("task")

        call_args = mock_llm.invoke.call_args[0][0]
        assert any("You are a stock analyst" in m.content for m in call_args)
