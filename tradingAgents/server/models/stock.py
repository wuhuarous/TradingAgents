from typing import Optional

from pydantic import BaseModel, Field


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
    initial_capital: Optional[float] = None
    single_position_max_ratio: Optional[float] = None
    total_position_max_ratio: Optional[float] = None
    daily_stop_loss_ratio: Optional[float] = None
