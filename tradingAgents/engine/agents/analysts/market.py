"""市场技术分析师 — 量价分析 + 技术指标 + 趋势判断"""
from tradingAgents.engine.agents.base import BaseAgent
from tradingAgents.engine.agents.utils.tools import get_quote, get_stock_data
from tradingAgents.engine.agents.utils.structured import extract_json


class MarketAnalyst(BaseAgent):
    role = "market_analyst"
    system_prompt = """你是一位资深技术分析师。根据提供的股票量价数据和技术指标，
分析当前趋势、支撑阻力位、成交量信号，给出评分。

输出格式（JSON）：
{
    "score": 1-10,
    "trend": "bullish|bearish|neutral",
    "support_level": 数字,
    "resistance_level": 数字,
    "volume_signal": "increasing|decreasing|normal",
    "key_indicators": {"rsi": 数字, "macd_signal": "buy|sell|hold"},
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        quote = get_quote(symbol, market)
        df = get_stock_data(symbol, market, period="1mo")

        context = (
            f"股票: {symbol}\n"
            f"最新价: {quote.price}\n"
            f"开盘: {quote.open}  最高: {quote.high}  最低: {quote.low}\n"
            f"涨跌幅: {quote.change_pct:.2%}\n"
            f"成交量: {quote.volume}\n\n"
            f"近期行情（最近5日）:\n"
            f"{df.tail(5).to_string() if not df.empty else '数据不可用'}\n"
        )
        resp = self.invoke("分析该股票的技术面走势并给出评分", context)
        return extract_json(resp)
