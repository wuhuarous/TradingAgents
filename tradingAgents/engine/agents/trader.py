"""交易员 Agent — 综合决策 + 结构化输出 — 最终买卖建议"""
import json

from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class TraderAgent(BaseAgent):
    role = "trader"
    system_prompt = """你是一位专业交易员。综合研究报告和风控辩论结果，
做出最终交易决策。你必须给出具体的买入价格区间、仓位、止损线、止盈线。

输出格式（JSON）：
{
    "action": "buy|sell|hold",
    "quantity_pct": 0.0-1.0,
    "price_lower": 买入价格下限,
    "price_upper": 买入价格上限,
    "stop_loss": 止损价,
    "stop_loss_pct": 止损百分比,
    "take_profit": 止盈价,
    "take_profit_pct": 止盈百分比,
    "max_hold_days": 预期持有时长（交易日）,
    "confidence": 0.0-1.0,
    "reasoning": "决策理由"
}"""

    def decide(
        self,
        symbol: str,
        price: float,
        research_result: dict,
        risk_evaluations: dict,
    ) -> dict:
        context = f"""股票: {symbol}  当前价: {price}
研究报告: {json.dumps(research_result, ensure_ascii=False)}
风控评估:
- 激进: {json.dumps(risk_evaluations.get('aggressive', {}), ensure_ascii=False)}
- 保守: {json.dumps(risk_evaluations.get('conservative', {}), ensure_ascii=False)}
- 中性: {json.dumps(risk_evaluations.get('neutral', {}), ensure_ascii=False)}
"""
        resp = self.invoke("给出最终交易决策", context)
        return extract_json(resp)
