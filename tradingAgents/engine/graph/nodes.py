"""LangGraph 节点 — 每个节点代表分析流程中的一步"""
from datetime import datetime
from typing import Any

from tradingAgents.engine.agents.analysts.fundamentals import FundamentalsAnalyst
from tradingAgents.engine.agents.analysts.market import MarketAnalyst
from tradingAgents.engine.agents.analysts.news import NewsAnalyst
from tradingAgents.engine.agents.manager import ResearchManager
from tradingAgents.engine.agents.researchers.bear import BearResearcher
from tradingAgents.engine.agents.researchers.bull import BullResearcher
from tradingAgents.engine.agents.risk_mgmt.aggressive import AggressiveDebater
from tradingAgents.engine.agents.risk_mgmt.conservative import ConservativeDebater
from tradingAgents.engine.agents.risk_mgmt.neutral import NeutralDebater
from tradingAgents.engine.agents.trader import TraderAgent
from tradingAgents.engine.agents.utils.tools import get_quote
from tradingAgents.engine.graph.state import AnalysisState


def fetch_data_node(state: AnalysisState) -> dict[str, Any]:
    """节点0: 获取行情数据"""
    try:
        quote = get_quote(state["symbol"], state["market"])
        return {"price": quote.price, "timestamp": quote.timestamp.isoformat()}
    except Exception as e:
        return {"error": str(e)}


def market_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点1: 市场技术分析"""
    agent = MarketAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"market_report": result}


def fundamentals_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点2: 基本面分析"""
    agent = FundamentalsAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"fundamentals_report": result}


def news_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点3: 新闻分析"""
    agent = NewsAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"news_report": result}


def bull_debate_node(state: AnalysisState) -> dict[str, Any]:
    """节点4: 多方辩论"""
    agent = BullResearcher()
    reports = (
        f"市场分析: {state.get('market_report', {})}\n"
        f"基本面: {state.get('fundamentals_report', {})}\n"
        f"新闻: {state.get('news_report', {})}"
    )
    result = agent.debate(reports)
    return {"bull_report": result}


def bear_debate_node(state: AnalysisState) -> dict[str, Any]:
    """节点5: 空方辩论"""
    agent = BearResearcher()
    reports = (
        f"市场分析: {state.get('market_report', {})}\n"
        f"基本面: {state.get('fundamentals_report', {})}\n"
        f"新闻: {state.get('news_report', {})}"
    )
    result = agent.debate(reports)
    return {"bear_report": result}


def research_manager_node(state: AnalysisState) -> dict[str, Any]:
    """节点6: 研究综合"""
    agent = ResearchManager()
    result = agent.decide(
        state["symbol"],
        {
            "market": state.get("market_report", {}),
            "fundamentals": state.get("fundamentals_report", {}),
            "news": state.get("news_report", {}),
        },
        state.get("bull_report", {}),
        state.get("bear_report", {}),
    )
    return {"research_decision": result}


def risk_evaluation_node(state: AnalysisState) -> dict[str, Any]:
    """节点7: 三方风控评估"""
    research = state.get("research_decision", {})
    aggressive = AggressiveDebater().evaluate(research)
    conservative = ConservativeDebater().evaluate(research)
    neutral = NeutralDebater().evaluate(research)
    return {"risk_evaluations": {
        "aggressive": aggressive,
        "conservative": conservative,
        "neutral": neutral,
    }}


def risk_consensus_node(state: AnalysisState) -> dict[str, Any]:
    """节点8: 风控参数共识（默认使用中性风格）"""
    evals = state.get("risk_evaluations", {})
    neutral = evals.get("neutral", {})
    return {"final_risk_params": neutral}


def trader_decision_node(state: AnalysisState) -> dict[str, Any]:
    """节点9: 交易员最终决策"""
    agent = TraderAgent()
    result = agent.decide(
        state["symbol"],
        state.get("price", 0),
        state.get("research_decision", {}),
        state.get("risk_evaluations", {}),
    )
    return {"trader_decision": result, "completed_at": datetime.now().isoformat()}
