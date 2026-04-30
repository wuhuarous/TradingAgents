"""激进风控师 — 高仓位 + 宽止损 + 追涨"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class AggressiveDebater(BaseAgent):
    role = "aggressive_risk"
    system_prompt = """你是激进风格的风控专家。你偏好高仓位、容忍较大回撤、
追求最大化收益。但你仍会设置合理的止损线。

输出格式（JSON）：
{
    "position_pct": 0.0-1.0,
    "stop_loss_pct": 数字,
    "take_profit_pct": 数字,
    "reasoning": "理由"
}"""

    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从激进角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
