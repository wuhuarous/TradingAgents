"""Tests for data source interface and providers"""
import os
import pytest
import pandas as pd
from tradingAgents.engine.dataflows.interface import DataSourceProvider, StockQuote, Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.providers.hk_us_stock import HKUSStockProvider, get_provider

network = pytest.mark.skipif(
    os.environ.get("SKIP_NETWORK", "") == "1",
    reason="network tests disabled (SKIP_NETWORK=1)",
)


class TestStockQuote:
    def test_defaults(self):
        sq = StockQuote(symbol="TEST", market=Market.US)
        assert sq.name == ""
        assert sq.price == 0.0

    def test_market_enum_values(self):
        assert Market.A == "a_stock"
        assert Market.HK == "hk_stock"
        assert Market.US == "us_stock"


class TestYFinanceUnit:
    """Pure unit tests — no network needed"""

    def test_implements_interface(self):
        assert isinstance(YFinanceProvider(), DataSourceProvider)

    def test_search_symbols_returns_list(self):
        results = YFinanceProvider().search_symbols("AAPL", Market.US)
        assert isinstance(results, list)

    def test_hk_ticker_suffix(self):
        provider = YFinanceProvider()
        assert provider._get_ticker("0700", Market.HK) == "0700.HK"
        assert provider._get_ticker("AAPL", Market.US) == "AAPL"
        assert provider._get_ticker("0700.HK", Market.HK) == "0700.HK"


@network
class TestYFinanceNetwork:
    """Integration tests — require network to Yahoo Finance"""

    def test_get_realtime_quote(self):
        quote = YFinanceProvider().get_realtime_quote("AAPL", Market.US)
        assert isinstance(quote, StockQuote)
        assert quote.symbol == "AAPL"
        assert quote.market == Market.US
        # price might be 0 if API rate-limited, but type must be correct

    def test_get_historical(self):
        df = YFinanceProvider().get_historical("AAPL", Market.US, period="5d")
        assert isinstance(df, pd.DataFrame)
        # DataFrame may be empty if API rate-limited, but must be a DataFrame

    def test_get_financials(self):
        data = YFinanceProvider().get_financials("AAPL", Market.US)
        assert isinstance(data, dict)
        assert "pe_ratio" in data

    def test_hk_stock_quote(self):
        quote = YFinanceProvider().get_realtime_quote("0700", Market.HK)
        assert isinstance(quote, StockQuote)
        assert quote.symbol == "0700"
        assert quote.market == Market.HK

    def test_yfinance_error_yields_default_quote(self):
        quote = YFinanceProvider().get_realtime_quote("ZZZ_UNKNOWN_999", Market.US)
        assert isinstance(quote, StockQuote)
        assert quote.symbol == "ZZZ_UNKNOWN_999"


class TestAStockUnit:
    """Pure unit tests for A-stock provider — no network needed"""

    def test_implements_interface(self):
        assert isinstance(AStockProvider(), DataSourceProvider)

    def test_financials_returns_dict(self):
        data = AStockProvider().get_financials("000001", Market.A)
        assert isinstance(data, dict)

    def test_news_returns_list(self):
        items = AStockProvider().get_news("000001", Market.A)
        assert isinstance(items, list)

    def test_search_returns_list(self):
        results = AStockProvider().search_symbols("平安", Market.A)
        assert isinstance(results, list)

    def test_error_fallback_default_quote(self):
        quote = AStockProvider().get_realtime_quote("999999", Market.A)
        assert isinstance(quote, StockQuote)
        assert quote.symbol == "999999"
        assert quote.market == Market.A


@network
class TestAStockNetwork:
    """Integration tests — require network to AkShare"""

    def test_get_realtime_quote(self):
        quote = AStockProvider().get_realtime_quote("000001", Market.A)
        assert isinstance(quote, StockQuote)
        assert quote.symbol == "000001"
        assert quote.market == Market.A

    def test_get_historical(self):
        df = AStockProvider().get_historical("000001", Market.A, period="5d")
        assert isinstance(df, pd.DataFrame)


class TestProviderFactory:
    def test_get_provider_a_stock(self):
        provider = get_provider(Market.A)
        assert isinstance(provider, (AStockProvider, DataSourceProvider))

    def test_get_provider_hk(self):
        provider = get_provider(Market.HK)
        assert isinstance(provider, (HKUSStockProvider, DataSourceProvider))

    def test_get_provider_us(self):
        provider = get_provider(Market.US)
        assert isinstance(provider, (HKUSStockProvider, DataSourceProvider))
