"""新闻分析师 — 新闻事件对股价影响评估"""
import json

from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.tools import get_news
from tradingAgents.engine.agents.utils.structured import extract_json


class NewsAnalyst(BaseAgent):
    role = "news_analyst"
    system_prompt = """你是一位财经新闻分析专家。根据最新新闻事件分析对股价的潜在影响，
关注政策变化、业绩公告、行业动态、市场情绪等。

输出格式（JSON）：
{
    "score": 1-10, 和
    "sentiment": "positive|neutral|negative",
    "key_events": [{"event": "事件描述", "impact": "positive|negative|neutral", "importance": 1-5}],
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        news_items = get_news(symbol, market, limit=10)
        context = (
            f"股票: {symbol}\n"
            f"最新新闻:\n"
            f"{json.dumps([{'title': n.title, 'source': n.source} for n in news_items], ensure_ascii=False)}\n"
        )
        resp = self.invoke("分析这些新闻对股价的影响并给出评分", context)
        return extract_json(resp)
