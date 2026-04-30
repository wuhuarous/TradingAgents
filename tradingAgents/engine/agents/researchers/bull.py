"""多方研究员 — 为看涨辩护，挖掘正面因素"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class BullResearcher(BaseAgent):
    role = "bull_researcher"
    system_prompt = """你是一位多方研究员，负责为看涨观点辩护。
基于分析师报告，找出支撑买入的关键论据，并对每个看涨因素给出置信度。

输出格式（JSON）：
{
    "bull_points": [{"point": "理由", "confidence": 0.0-1.0}],
    "overall_rating": 1-10,
    "reasoning": "中文分析理由"
}"""

    def debate(self, analyst_reports: str) -> dict:
        context = f"分析师报告汇总:\n{analyst_reports}"
        resp = self.invoke("从多方角度论证，找出支持买入的理由", context)
        return extract_json(resp)
