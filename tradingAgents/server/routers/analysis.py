from fastapi import APIRouter, HTTPException

from tradingAgents.engine.graph.workflow import run_analysis
from tradingAgents.server.models.stock import StockAnalysisRequest, StockAnalysisResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/run", response_model=StockAnalysisResponse)
def run_stock_analysis(req: StockAnalysisRequest):
    try:
        result = run_analysis(req.symbol, req.market)
        return StockAnalysisResponse(
            symbol=req.symbol,
            market=req.market,
            analysis={
                "market": result.get("market_report"),
                "fundamentals": result.get("fundamentals_report"),
                "news": result.get("news_report"),
                "research_decision": result.get("research_decision"),
                "risk_evaluations": result.get("risk_evaluations"),
            },
            trader_decision=result.get("trader_decision", {}),
        )
    except Exception as e:
        raise HTTPException(500, f"分析失败: {e}")
