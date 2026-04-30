"""研究管理员 — 汇总辩论结果，给出综合评估"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.structured import extract_json


class ResearchManager(BaseAgent):
    role = "research_manager"
    system_prompt = """你是研究管理员。综合多方和空方的辩论结果，评估各方论据质量，
合并分析师评分与辩论结果，输出最终综合评分和决策建议。

输出格式（JSON）：
{
    "final_score": 1-10,
    "decision": "buy|hold|sell",
    "confidence": 0.0-1.0,
    "key_reasons": ["理由1", "理由2", "理由3"],
    "risk_summary": "风险概述"
}"""

    def decide(
        self,
        symbol: str,
        analyst_reports: dict,
        bull_report: dict,
        bear_report: dict,
    ) -> dict:
        import json

        context = f"""股票: {symbol}
分析师评分: {json.dumps(analyst_reports, ensure_ascii=False)}
多方观点: {json.dumps(bull_report, ensure_ascii=False)}
空方观点: {json.dumps(bear_report, ensure_ascii=False)}
"""
        resp = self.invoke("综合各方观点，给出最终交易建议", context)
        return extract_json(resp)
