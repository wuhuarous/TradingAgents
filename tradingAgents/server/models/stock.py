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
