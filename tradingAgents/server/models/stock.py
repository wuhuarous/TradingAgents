from typing import Optional

from pydantic import BaseModel, Field


# ---- Market / Screener / News / Settings (unchanged) ----

class StockQuoteResponse(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    volume: int


class StockAnalysisRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    market: str = "a_stock"


class StockAnalysisResponse(BaseModel):
    symbol: str
    market: str
    analysis: dict
    trader_decision: dict


class MarketOverviewResponse(BaseModel):
    market: str
    indices: list[dict]
    top_gainers: list[dict]
    top_losers: list[dict]


class ScreenerRequest(BaseModel):
    market: str = "a_stock"
    min_roe: Optional[float] = None
    max_pe: Optional[float] = None
    max_pb: Optional[float] = None
    min_revenue_growth: Optional[float] = None
    sort_by: str = "roe"
    limit: int = 20


class NewsResponse(BaseModel):
    title: str
    source: str
    url: str
    sentiment: Optional[float] = None
    published_at: str


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deep_think_model: Optional[str] = None
    quick_think_model: Optional[str] = None
    preferred_market_data_source: Optional[str] = None
    preferred_news_source: Optional[str] = None
    tushare_token: Optional[str] = None
    alpha_vantage_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    newsapi_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    initial_capital: Optional[float] = None
    single_position_max_ratio: Optional[float] = None
    total_position_max_ratio: Optional[float] = None
    daily_stop_loss_ratio: Optional[float] = None


# ---- Stock Detail ----

class KlinePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockDetailResponse(BaseModel):
    symbol: str
    name: str
    market: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    close: float  # previous close
    volume: int
    kline: list[KlinePoint]
    fundamentals: dict
    financials: dict
