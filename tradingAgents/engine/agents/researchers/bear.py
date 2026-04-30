"""空方研究员 — 为看跌辩护，挖掘风险因素"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class BearResearcher(BaseAgent):
    role = "bear_researcher"
    system_prompt = """你是一位空方研究员，负责揭示风险和负面因素。
基于分析师报告，找出支撑卖出/观望的关键论据，并对每个风险因素给出置信度。

输出格式（JSON）：
{
    "bear_points": [{"point": "风险", "confidence": 0.0-1.0}],
    "overall_rating": 1-10,
    "reasoning": "中文分析理由"
}"""

    def debate(self, analyst_reports: str) -> dict:
        context = f"分析师报告汇总:\n{analyst_reports}"
        resp = self.invoke("从空方角度论证，找出反对买入的风险和理由", context)
        return extract_json(resp)
