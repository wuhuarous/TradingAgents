"""Readiness diagnostics for AI-assisted quantitative trading.

This module does not certify a strategy as profitable. It makes the
non-negotiable foundations visible: data, validation, risk, execution,
review, and AI reliability.
"""
from __future__ import annotations

from statistics import mean
from typing import Any

from tradingAgents.config.settings import settings
from tradingAgents.trader.account import VirtualAccount
from tradingAgents.trader.auto_strategy import QualityMomentumStrategy


def build_quant_readiness(
    account: VirtualAccount,
    strategy: QualityMomentumStrategy,
) -> dict[str, Any]:
    runs = strategy.recent_runs(limit=80)
    positions = list(account.positions.values())
    checks = [
        _data_reliability_check(runs),
        _strategy_validation_check(runs),
        _risk_control_check(account, strategy),
        _execution_check(),
        _review_learning_check(runs),
        _ai_reliability_check(),
    ]
    overall = round(mean(item["score"] for item in checks), 1) if checks else 0

    blockers = [
        issue
        for item in checks
        for issue in item["issues"]
        if item["status"] in {"blocked", "partial"}
    ][:8]
    next_actions = _next_actions(checks, runs, positions)

    return {
        "mode": "simulation_first",
        "overall_score": overall,
        "status": _status_from_score(overall),
        "target_annual_return": strategy.config.target_annual_return,
        "summary": {
            "run_count": len(runs),
            "position_count": len(positions),
            "current_return": round(account.total_pnl_pct, 4),
            "preferred_market_data_source": settings.preferred_market_data_source,
            "preferred_news_source": settings.preferred_news_source,
            "llm_provider": settings.llm_provider,
        },
        "checks": checks,
        "blockers": blockers,
        "next_actions": next_actions,
    }


def _data_reliability_check(runs: list[dict[str, Any]]) -> dict[str, Any]:
    configured_sources = 1
    if settings.tushare_token:
        configured_sources += 1
    if settings.alpha_vantage_api_key or settings.finnhub_api_key or settings.polygon_api_key:
        configured_sources += 1

    scored_candidates = [
        candidate
        for run in runs[:20]
        for candidate in run.get("top_candidates", [])
        if candidate.get("final_score", 0) > 0
    ]
    coverage_score = min(len(scored_candidates) * 2, 30)
    source_score = min(configured_sources * 20, 50)
    news_score = 20 if _has_news_source() else 8
    score = min(source_score + coverage_score + news_score, 100)

    issues = []
    if configured_sources < 2:
        issues.append("行情源缺少冗余，建议至少配置一个备用源")
    if not _has_news_source():
        issues.append("海外新闻源未配置密钥，港美股舆情覆盖会偏弱")
    if len(scored_candidates) < 20:
        issues.append("复盘样本太少，暂时无法判断数据稳定性")

    return _check(
        "data_reliability",
        "数据可信度",
        score,
        "行情、财务、新闻和舆情必须可追溯、可去重、可降级",
        issues,
    )


def _strategy_validation_check(runs: list[dict[str, Any]]) -> dict[str, Any]:
    run_count = len(runs)
    decision_count = sum(len(run.get("decisions", [])) for run in runs)
    score = min(run_count * 2.2 + decision_count * 3, 100)
    issues = []
    if run_count < 30:
        issues.append("模拟训练轮次不足 30，暂不适合根据收益调参")
    if decision_count < 20:
        issues.append("有效买卖决策样本不足，需要更多不同市场环境样本")
    if run_count and not any(run.get("review") for run in runs):
        issues.append("复盘记录缺少 review 字段，无法沉淀策略经验")

    return _check(
        "strategy_validation",
        "策略验证",
        score,
        "先用模拟盘和回测证明因子组合有稳定胜率，再谈自动交易",
        issues,
    )


def _risk_control_check(
    account: VirtualAccount,
    strategy: QualityMomentumStrategy,
) -> dict[str, Any]:
    cfg = strategy.config
    position_ratio_ok = 0 < cfg.position_ratio <= settings.single_position_max_ratio
    total_position_value = sum(
        float(pos.get("current_price", pos.get("avg_cost", 0)) or 0) * float(pos.get("quantity", 0) or 0)
        for pos in account.positions.values()
    )
    total_ratio = total_position_value / account.total_value if account.total_value else 0
    score = 35
    score += 20 if position_ratio_ok else 0
    score += 20 if cfg.stop_loss_pct <= 0.1 else 8
    score += 15 if cfg.max_positions <= 8 else 6
    score += 10 if total_ratio <= settings.total_position_max_ratio else 0

    issues = []
    if not position_ratio_ok:
        issues.append("单仓比例超过系统风控上限")
    if cfg.stop_loss_pct > 0.1:
        issues.append("止损阈值偏宽，容易扩大回撤")
    if total_ratio > settings.total_position_max_ratio:
        issues.append("总仓位超过系统风控上限")

    return _check(
        "risk_control",
        "风控约束",
        min(score, 100),
        "高收益目标必须先受仓位、止损、止盈和最大回撤约束",
        issues,
    )


def _execution_check() -> dict[str, Any]:
    score = 58
    issues = ["当前仍是模拟交易模式，实盘前还需要券商接口、滑点、成交回报和熔断处理"]
    if settings.scheduler_live_data_enabled:
        score += 12
    else:
        issues.append("定时任务默认未启用真实行情扫描，适合开发环境但不适合无人值守")
    return _check(
        "execution",
        "交易执行",
        score,
        "自动交易要保证订单幂等、失败重试、风控拦截和审计日志",
        issues,
    )


def _review_learning_check(runs: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = [run for run in runs if run.get("review")]
    lessons = [
        lesson
        for run in reviewed
        for lesson in run.get("review", {}).get("lessons", [])
    ]
    score = min(len(reviewed) * 2.5 + len(lessons) * 1.5, 100)
    issues = []
    if len(reviewed) < 20:
        issues.append("复盘样本不足，需要持续记录信号、买卖点和后续收益")
    if not lessons:
        issues.append("还没有形成可用于调参的复盘经验")
    return _check(
        "review_learning",
        "复盘学习",
        score,
        "每次决策都要回看收益、回撤、新闻变化和因子权重",
        issues,
    )


def _ai_reliability_check() -> dict[str, Any]:
    provider_key_ok = {
        "deepseek": bool(settings.deepseek_api_key),
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
    }.get(settings.llm_provider, False)
    score = 72 if provider_key_ok else 42
    issues = []
    if not provider_key_ok:
        issues.append("当前 LLM Provider 缺少可用密钥，深度分析会依赖规则降级")
    if settings.deep_think_model == settings.quick_think_model:
        issues.append("深度模型和快速模型相同，成本/质量分层不明显")

    return _check(
        "ai_reliability",
        "AI 稳定性",
        score,
        "AI 只做解释、归因和辅助判断，核心交易信号必须能规则化复现",
        issues,
    )


def _check(key: str, label: str, score: float, description: str, issues: list[str]) -> dict[str, Any]:
    clean_score = round(max(0, min(score, 100)), 1)
    return {
        "key": key,
        "label": label,
        "score": clean_score,
        "status": _status_from_score(clean_score),
        "description": description,
        "issues": issues,
    }


def _status_from_score(score: float) -> str:
    if score >= 75:
        return "ready"
    if score >= 45:
        return "partial"
    return "blocked"


def _has_news_source() -> bool:
    return bool(
        settings.alpha_vantage_api_key
        or settings.finnhub_api_key
        or settings.polygon_api_key
        or settings.newsapi_api_key
    )


def _next_actions(
    checks: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> list[str]:
    actions = []
    by_key = {item["key"]: item for item in checks}
    if by_key["data_reliability"]["status"] != "ready":
        actions.append("补齐行情/新闻备用源，并记录每个候选股的数据来源与更新时间")
    if by_key["strategy_validation"]["status"] != "ready":
        actions.append("连续运行模拟训练，至少积累 30 轮、20 条有效买卖样本")
    if by_key["review_learning"]["status"] != "ready":
        actions.append("把每次买入后的 1/5/20 日收益回填到复盘日志，用来校准权重")
    if by_key["execution"]["status"] != "ready":
        actions.append("实盘前增加订单幂等、成交回报、滑点模型和熔断开关")
    if not positions and runs:
        actions.append("当前没有持仓，可先降低模拟买入阈值做小样本压力测试")
    return actions[:5] or ["基础条件较完整，下一步重点做历史回测和样本外验证"]
