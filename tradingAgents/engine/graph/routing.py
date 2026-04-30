"""条件路由 — 错误处理和流程控制"""


def should_continue(state: dict) -> str:
    """检查是否有错误，决定是否继续"""
    if state.get("error"):
        return "__end__"
    return "market_analysis"


def research_score_check(state: dict) -> str:
    """根据研究评分决定是否值得交易"""
    decision = state.get("research_decision", {})
    score = decision.get("final_score", 0)
    if score >= 6:
        return "risk_evaluation"
    return "__end__"
