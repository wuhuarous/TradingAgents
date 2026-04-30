"""LangGraph 主工作流 — 编排完整分析流程"""
from langgraph.graph import END, StateGraph

from tradingAgents.engine.graph.nodes import (
    bear_debate_node,
    bull_debate_node,
    fetch_data_node,
    fundamentals_analysis_node,
    market_analysis_node,
    news_analysis_node,
    research_manager_node,
    risk_consensus_node,
    risk_evaluation_node,
    trader_decision_node,
)
from tradingAgents.engine.graph.routing import research_score_check
from tradingAgents.engine.graph.state import AnalysisState


def build_analysis_graph() -> StateGraph:
    """构建分析工作流图

    流程: fetch → [market, fundamentals, news] (并行)
           → [bull, bear] (并行)
           → research_manager → risk_eval → risk_consensus → trader → END
    """
    graph = StateGraph(AnalysisState)

    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("market_analysis", market_analysis_node)
    graph.add_node("fundamentals_analysis", fundamentals_analysis_node)
    graph.add_node("news_analysis", news_analysis_node)
    graph.add_node("bull_debate", bull_debate_node)
    graph.add_node("bear_debate", bear_debate_node)
    graph.add_node("research_manager", research_manager_node)
    graph.add_node("risk_evaluation", risk_evaluation_node)
    graph.add_node("risk_consensus", risk_consensus_node)
    graph.add_node("trader_decision", trader_decision_node)

    graph.set_entry_point("fetch_data")

    graph.add_edge("fetch_data", "market_analysis")
    graph.add_edge("fetch_data", "fundamentals_analysis")
    graph.add_edge("fetch_data", "news_analysis")

    graph.add_edge("market_analysis", "bull_debate")
    graph.add_edge("fundamentals_analysis", "bull_debate")
    graph.add_edge("news_analysis", "bull_debate")
    graph.add_edge("market_analysis", "bear_debate")
    graph.add_edge("fundamentals_analysis", "bear_debate")
    graph.add_edge("news_analysis", "bear_debate")

    graph.add_edge("bull_debate", "research_manager")
    graph.add_edge("bear_debate", "research_manager")

    graph.add_conditional_edges(
        "research_manager",
        research_score_check,
        {"risk_evaluation": "risk_evaluation", "__end__": END},
    )

    graph.add_edge("risk_evaluation", "risk_consensus")
    graph.add_edge("risk_consensus", "trader_decision")
    graph.add_edge("trader_decision", END)

    return graph


def run_analysis(symbol: str, market: str = "us") -> dict:
    """运行完整分析流程，返回最终状态"""
    graph = build_analysis_graph()
    app = graph.compile()

    initial_state: AnalysisState = {
        "symbol": symbol,
        "market": market,
        "price": 0.0,
        "timestamp": "",
        "market_report": {},
        "fundamentals_report": {},
        "news_report": {},
        "bull_report": {},
        "bear_report": {},
        "research_decision": {},
        "risk_evaluations": {},
        "final_risk_params": {},
        "trader_decision": {},
        "error": None,
        "completed_at": None,
    }

    result = app.invoke(initial_state)
    return result
