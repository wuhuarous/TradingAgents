"""Agent 基类 — 统一 LLM 调用、工具绑定、结构化输出"""
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tradingAgents.engine.llm.factory import LLMFactory


class BaseAgent:
    role: str = "base"
    system_prompt: str = ""

    def __init__(self, model_name: Optional[str] = None, temperature: float = 0.1):
        self.llm = LLMFactory.create_from_settings(model=model_name)
        self.llm.temperature = temperature

    def invoke(self, task: str, context: str = "") -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"## 角色\n{self.system_prompt}\n\n## 上下文\n{context}\n\n## 任务\n{task}"),
        ]
        resp = self.llm.invoke(messages)
        return resp.content
