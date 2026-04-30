"""Tests for LLM multi-provider factory"""
import pytest
from engine.llm.factory import LLMFactory, LLMProvider


class TestLLMFactory:
    def test_create_deepseek_client(self):
        client = LLMFactory.create(
            LLMProvider.DEEPSEEK, api_key="test-key", model="deepseek-chat"
        )
        assert client is not None
        assert client.model_name == "deepseek-chat"

    def test_create_openai_client(self):
        client = LLMFactory.create(
            LLMProvider.OPENAI, api_key="test-key", model="gpt-4o"
        )
        assert client is not None
        assert client.model_name == "gpt-4o"

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError):
            LLMFactory.create("unsupported_provider", api_key="test", model="x")

    def test_create_from_settings_with_env_defaults(self, monkeypatch):
        monkeypatch.setattr("config.settings.settings.deepseek_api_key", "env-key")
        monkeypatch.setattr("config.settings.settings.llm_provider", "deepseek")
        monkeypatch.setattr("config.settings.settings.deep_think_model", "deepseek-reasoner")

        client = LLMFactory.create_from_settings()
        assert client is not None
        assert client.model_name == "deepseek-reasoner"

    def test_custom_temperature(self):
        client = LLMFactory.create(
            LLMProvider.OPENAI, api_key="test", model="gpt-4o", temperature=0.7
        )
        assert client.temperature == 0.7
