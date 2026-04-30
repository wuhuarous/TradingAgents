"""数据源抽象接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class Market(str, Enum):
    A = "a_stock"
    HK = "hk_stock"
    US = "us_stock"


@dataclass
class StockQuote:
    symbol: str
    name: str = ""
    price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    change_pct: float = 0.0
    market: Market = Market.US
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NewsItem:
    title: str
    content: str = ""
    source: str = ""
    url: str = ""
    sentiment: Optional[float] = None
    published_at: datetime = field(default_factory=datetime.now)


class DataSourceProvider(ABC):
    """行情数据源抽象接口"""

    @abstractmethod
    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        ...

    @abstractmethod
    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        ...

    @abstractmethod
    def get_financials(self, symbol: str, market: Market) -> dict:
        ...

    @abstractmethod
    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        ...

    @abstractmethod
    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        ...
