"""基本面分析师 — 财务数据解读 + 估值分析"""
import json

from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.tools import get_financials
from tradingAgents.engine.agents.utils.structured import extract_json


class FundamentalsAnalyst(BaseAgent):
    role = "fundamentals_analyst"
    system_prompt = """你是一位基本面分析专家。根据财务数据评估公司价值，
关注 PE/PB/ROE/营收增长/负债率等指标，给出综合评分。

输出格式（JSON）：
{
    "score": 1-10,
    "valuation": "undervalued|fair|overvalued",
    "growth_outlook": "positive|neutral|negative",
    "key_metrics": {"pe": 数字, "pb": 数字, "roe": 数字, "revenue_growth": 数字},
    "risks": ["风险点1", "风险点2"],
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        financials = get_financials(symbol, market)
        context = (
            f"股票: {symbol}\n"
            f"财务数据:\n{json.dumps(financials, ensure_ascii=False, default=str)}\n"
        )
        resp = self.invoke("分析该股票的基本面并给出评分", context)
        return extract_json(resp)
