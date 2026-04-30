"""LangGraph 状态定义"""
from typing import Optional, TypedDict


class AnalysisState(TypedDict):
    symbol: str
    market: str          # "a_stock" | "hk_stock" | "us_stock"
    price: float
    timestamp: str       # ISO format

    # Analyst reports
    market_report: dict
    fundamentals_report: dict
    news_report: dict

    # Debate results
    bull_report: dict
    bear_report: dict
    research_decision: dict

    # Risk evaluations
    risk_evaluations: dict
    final_risk_params: dict

    # Final decision
    trader_decision: dict

    # Metadata
    error: Optional[str]
    completed_at: Optional[str]
