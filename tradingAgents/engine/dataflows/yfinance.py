"""yfinance 实现 — 港美股行情 + 财务 + 新闻"""
import logging
import pandas as pd
import yfinance as yf

from .interface import DataSourceProvider, Market, NewsItem, StockQuote

logger = logging.getLogger(__name__)


class YFinanceProvider(DataSourceProvider):
    def _get_ticker(self, symbol: str, market: Market) -> str:
        if market == Market.HK and not symbol.endswith(".HK"):
            return f"{symbol}.HK"
        return symbol

    def _safe_info(self, symbol: str, market: Market) -> dict:
        try:
            t = yf.Ticker(self._get_ticker(symbol, market))
            return t.info or {}
        except Exception as e:
            logger.warning("yfinance get_info failed for %s: %s", symbol, e)
            return {}

    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        info = self._safe_info(symbol, market)
        price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        return StockQuote(
            symbol=symbol,
            name=info.get("longName", info.get("shortName", "")),
            price=price,
            open=info.get("regularMarketOpen", 0),
            high=info.get("dayHigh", 0),
            low=info.get("dayLow", 0),
            close=info.get("previousClose", 0),
            volume=info.get("volume", 0),
            change_pct=price / info.get("previousClose", 1) - 1 if info.get("previousClose") else 0,
            market=market,
        )

    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        try:
            ticker_str = self._get_ticker(symbol, market)
            t = yf.Ticker(ticker_str)
            return t.history(period=period)
        except Exception as e:
            logger.warning("yfinance history failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_financials(self, symbol: str, market: Market) -> dict:
        info = self._safe_info(symbol, market)
        return {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
        }

    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        try:
            ticker_str = self._get_ticker(symbol, market)
            t = yf.Ticker(ticker_str)
            items = []
            for n in (t.news or [])[:limit]:
                items.append(NewsItem(
                    title=n.get("title", ""),
                    content=n.get("link", ""),
                    source=n.get("publisher", ""),
                    url=n.get("link", ""),
                ))
            return items
        except Exception as e:
            logger.warning("yfinance news failed for %s: %s", symbol, e)
            return []

    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        return []
