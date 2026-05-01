"""多供应商LLM工厂 — 统一创建 DeepSeek/OpenAI/Anthropic 客户端

所有供应商均使用 OpenAI 兼容 API 格式，因此统一使用 langchain_openai.ChatOpenAI，
仅 base_url 不同。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from langchain_openai import ChatOpenAI


class LLMProvider(str, Enum):
    """支持的 LLM 供应商枚举"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMFactory:
    """LLM 客户端工厂，支持多供应商创建"""

    _PROVIDER_BASE_URLS = {
        LLMProvider.DEEPSEEK: "https://api.deepseek.com",
        LLMProvider.OPENAI: "https://api.openai.com/v1",
        LLMProvider.ANTHROPIC: "https://api.anthropic.com",
    }

    @staticmethod
    def create(
        provider: LLMProvider,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
    ) -> ChatOpenAI:
        """创建指定供应商的 LLM 客户端

        Args:
            provider: 供应商枚举值
            api_key: API 密钥
            model: 模型名称
            base_url: 自定义 base_url，若不传则使用供应商默认值
            temperature: 推理温度，默认 0.1

        Returns:
            ChatOpenAI 实例

        Raises:
            ValueError: 不支持的供应商
        """
        if provider not in LLMFactory._PROVIDER_BASE_URLS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported: {[p.value for p in LLMFactory._PROVIDER_BASE_URLS]}"
            )

        default_url = LLMFactory._PROVIDER_BASE_URLS[provider]
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or default_url,
            temperature=temperature,
        )

    @staticmethod
    def create_from_settings(model: Optional[str] = None) -> ChatOpenAI:
        """从全局 settings 创建默认客户端

        Args:
            model: 可选，覆盖 settings 中的模型名称

        Returns:
            ChatOpenAI 实例
        """
        from tradingAgents.config.settings import settings

        provider = LLMProvider(settings.llm_provider)
        key_attr = f"{provider.value}_api_key"
        api_key = getattr(settings, key_attr, "")
        if not api_key:
            raise ValueError(
                f"LLM provider '{provider.value}' selected but no API key configured. "
                f"Set {provider.value.upper()}_API_KEY in .env"
            )
        return LLMFactory.create(
            provider=provider,
            api_key=api_key,
            model=model or settings.deep_think_model,
        )
