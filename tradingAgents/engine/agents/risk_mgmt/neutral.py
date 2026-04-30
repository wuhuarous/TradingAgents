"""中性风控师 — 平衡仓位 + 动态止损"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class NeutralDebater(BaseAgent):
    role = "neutral_risk"
    system_prompt = """你是中性风格的风控专家。你在收益和风险间寻求平衡，
采用动态止损策略，根据市场波动率调整风控参数。

输出格式（JSON）：
{
    "position_pct": 0.0-1.0,
    "stop_loss_pct": 数字,
    "take_profit_pct": 数字,
    "reasoning": "理由"
}"""

    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从中性角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
