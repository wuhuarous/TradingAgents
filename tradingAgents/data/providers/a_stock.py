"""A股数据源 — AkShare 免费接口，BaoStock 备用"""
import logging
import pandas as pd
from datetime import datetime

from tradingAgents.engine.dataflows.interface import DataSourceProvider, Market, NewsItem, StockQuote

logger = logging.getLogger(__name__)


class AStockProvider(DataSourceProvider):
    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol]
            if row.empty:
                return self._get_quote_baostock(symbol)
            r = row.iloc[0]
            return StockQuote(
                symbol=symbol,
                name=str(r.get("名称", "")),
                price=float(r["最新价"]),
                open=float(r["今开"]),
                high=float(r["最高"]),
                low=float(r["最低"]),
                close=float(r.get("昨收", 0)),
                volume=int(r.get("成交量", 0)),
                change_pct=float(r["涨跌幅"]) / 100,
                market=Market.A,
            )
        except Exception as e:
            logger.warning("AkShare realtime quote failed for %s: %s", symbol, e)
            return self._get_quote_baostock(symbol)

    def _get_quote_baostock(self, symbol: str) -> StockQuote:
        try:
            import baostock as bs
            bs.login()
            code = f"sz.{symbol}" if symbol.startswith(("0", "3")) else f"sh.{symbol}"
            rs = bs.query_stock_basic(code)
            bs.logout()
            return StockQuote(symbol=symbol, name=code, market=Market.A)
        except Exception as e:
            logger.warning("BaoStock basic query failed for %s: %s", symbol, e)
            return StockQuote(symbol=symbol, market=Market.A)

    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            return df.tail(30 if period == "1mo" else 5)
        except Exception as e:
            logger.warning("AkShare history failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_financials(self, symbol: str, market: Market) -> dict:
        try:
            import akshare as ak
            df = ak.stock_financial_abstract(symbol=symbol)
            if df is None or df.empty:
                return {}
            latest = df.iloc[0]
            return {
                "pe_ratio": latest.get("市盈率"),
                "pb_ratio": latest.get("市净率"),
                "market_cap": latest.get("总市值"),
                "revenue": latest.get("营业总收入"),
                "net_income": latest.get("归母净利润"),
                "roe": latest.get("净资产收益率"),
            }
        except Exception as e:
            logger.warning("AkShare financials failed for %s: %s", symbol, e)
            return {}

    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=symbol)
            items = []
            for _, row in df.head(limit).iterrows():
                items.append(NewsItem(
                    title=str(row.get("标题", "")),
                    content=str(row.get("内容", "")),
                    source="东方财富",
                    url=str(row.get("链接", "")),
                ))
            return items
        except Exception as e:
            logger.warning("AkShare news failed for %s: %s", symbol, e)
            return []

    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            matches = df[df["名称"].str.contains(keyword) | df["代码"].str.contains(keyword)]
            return [{"symbol": str(r["代码"]), "name": str(r["名称"])} for _, r in matches.head(20).iterrows()]
        except Exception as e:
            logger.warning("AkShare symbol search failed for %s: %s", keyword, e)
            return []
