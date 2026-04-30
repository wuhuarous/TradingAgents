"""保守风控师 — 低仓位 + 紧止损 + 快止盈"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class ConservativeDebater(BaseAgent):
    role = "conservative_risk"
    system_prompt = """你是保守风格的风控专家。你偏好低仓位、严格止损、
快速止盈、本金安全第一。

输出格式（JSON）：
{
    "position_pct": 0.0-1.0,
    "stop_loss_pct": 数字,
    "take_profit_pct": 数字,
    "reasoning": "理由"
}"""

    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从保守角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
