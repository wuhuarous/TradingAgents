"""Local rule-based analysis fallback when LLM calls are unavailable."""
from __future__ import annotations

from tradingAgents.engine.agents.utils.tools import get_financials, get_news, get_quote, get_stock_data
from tradingAgents.data.social.sentiment import analyze_sentiment


def run_rule_based_analysis(symbol: str, market: str, error: str = "") -> dict:
    """Return a structured analysis without calling paid LLM APIs."""
    quote = _safe(lambda: get_quote(symbol, market), None)
    price = float(getattr(quote, "price", 0) or 0)
    change_pct = float(getattr(quote, "change_pct", 0) or 0)
    df = _safe(lambda: get_stock_data(symbol, market, period="3mo"), None)
    financials = _safe(lambda: get_financials(symbol, market), {}) or {}
    news_items = _safe(lambda: get_news(symbol, market, limit=10), []) or []

    market_report = _market_report(price, change_pct, df)
    fundamentals_report = _fundamentals_report(financials)
    news_report = _news_report(news_items)

    combined = (
        market_report["score"] * 0.35
        + fundamentals_report["score"] * 0.40
        + news_report["score"] * 0.25
    )
    decision = "buy" if combined >= 7.2 else "hold" if combined >= 4.8 else "sell"
    confidence = min(0.88, max(0.35, combined / 10))
    risk = _risk_params(price, decision)

    return {
        "market_report": market_report,
        "fundamentals_report": fundamentals_report,
        "news_report": news_report,
        "bull_report": {
            "overall_rating": round(max(combined, 1), 1),
            "bull_points": [
                {"point": "使用本地规则兜底，保留行情、财务和新闻三类证据", "confidence": confidence},
                {"point": f"技术面趋势为 {market_report['trend']}", "confidence": 0.6},
            ],
            "reasoning": "LLM 不可用时的本地规则多头视角。",
        },
        "bear_report": {
            "overall_rating": round(max(10 - combined, 1), 1),
            "bear_points": [
                {"point": "模型余额不足或配置不可用，结论置信度应降低", "confidence": 0.8},
                {"point": fundamentals_report["risks"][0] if fundamentals_report["risks"] else "需等待更多财务和新闻确认", "confidence": 0.55},
            ],
            "reasoning": "LLM 不可用时的本地规则空头视角。",
        },
        "research_decision": {
            "final_score": round(combined, 1),
            "decision": decision,
            "confidence": round(confidence, 2),
            "key_reasons": [
                market_report["reasoning"],
                fundamentals_report["reasoning"],
                news_report["reasoning"],
            ],
            "risk_summary": "本次为本地规则兜底分析，建议仅用于模拟与排查配置。",
            "fallback": True,
            "fallback_error": error,
        },
        "risk_evaluations": {
            "aggressive": {**risk, "reasoning": "激进方案：仅在模拟盘中小仓位试错。"},
            "neutral": {**risk, "reasoning": "中性方案：等待价格确认，严格执行止损。"},
            "conservative": {
                "position_pct": min(risk["position_pct"], 0.08),
                "stop_loss_pct": min(risk["stop_loss_pct"], 0.05),
                "take_profit_pct": risk["take_profit_pct"],
                "reasoning": "保守方案：LLM 不可用时降低仓位。",
            },
        },
        "final_risk_params": risk,
        "trader_decision": {
            "action": decision,
            "quantity_pct": risk["position_pct"] if decision == "buy" else 0,
            "price_lower": round(price * 0.985, 3) if price else 0,
            "price_upper": round(price * 1.015, 3) if price else 0,
            "stop_loss": round(price * (1 - risk["stop_loss_pct"]), 3) if price else 0,
            "stop_loss_pct": risk["stop_loss_pct"],
            "take_profit": round(price * (1 + risk["take_profit_pct"]), 3) if price else 0,
            "take_profit_pct": risk["take_profit_pct"],
            "max_hold_days": 20,
            "confidence": round(confidence, 2),
            "reasoning": "LLM 余额不足或不可用，已切换为本地规则分析。请在系统设置中配置可用模型后获得完整多智能体分析。",
            "fallback": True,
        },
    }


def _market_report(price: float, change_pct: float, df) -> dict:
    score = 5.0
    trend = "neutral"
    support = price * 0.95 if price else 0
    resistance = price * 1.08 if price else 0
    volume_signal = "normal"

    try:
        if df is not None and not df.empty:
            close = df["收盘"] if "收盘" in df.columns else df["Close"]
            volume = df["成交量"] if "成交量" in df.columns else df.get("Volume")
            latest = float(close.iloc[-1])
            ma20 = float(close.tail(20).mean())
            ma60 = float(close.tail(60).mean()) if len(close) >= 60 else ma20
            support = float(close.tail(20).min())
            resistance = float(close.tail(20).max())
            if latest > ma20 >= ma60:
                trend, score = "bullish", 7.2
            elif latest < ma20:
                trend, score = "bearish", 4.0
            if volume is not None and len(volume) >= 20:
                ratio = float(volume.iloc[-1] / volume.tail(20).mean())
                volume_signal = "increasing" if ratio > 1.3 else "decreasing" if ratio < 0.7 else "normal"
                score += 0.4 if ratio > 1.3 else 0
    except Exception:
        score += 0.5 if change_pct > 0 else -0.5 if change_pct < 0 else 0

    return {
        "score": round(max(1, min(10, score)), 1),
        "trend": trend,
        "support_level": round(support, 3),
        "resistance_level": round(resistance, 3),
        "volume_signal": volume_signal,
        "key_indicators": {"rsi": None, "macd_signal": "hold"},
        "reasoning": f"价格 {price:.3f}，涨跌幅 {change_pct:.2%}，趋势判断为 {trend}。",
    }


def _fundamentals_report(financials: dict) -> dict:
    pe = _num(financials, "pe", "pe_ratio", "forward_pe")
    pb = _num(financials, "pb", "pb_ratio")
    roe = _num(financials, "roe")
    growth = _num(financials, "revenue_growth")
    score = 5.0
    score += 1.2 if roe >= 0.12 else -0.6 if roe and roe < 0.06 else 0
    score += 1.0 if growth >= 0.15 else -0.8 if growth < -0.05 else 0
    score += 0.8 if 0 < pe <= 35 else -0.7 if pe > 70 else 0
    score += 0.4 if 0 < pb <= 5 else -0.4 if pb > 10 else 0
    risks = []
    if not financials:
        risks.append("财务数据缺失")
    if pe > 70:
        risks.append("估值偏高")
    if growth < 0:
        risks.append("营收增长为负")
    return {
        "score": round(max(1, min(10, score)), 1),
        "valuation": "fair" if 0 < pe <= 45 else "overvalued" if pe > 45 else "unknown",
        "growth_outlook": "positive" if growth > 0.1 else "negative" if growth < 0 else "neutral",
        "key_metrics": {"pe": pe, "pb": pb, "roe": roe, "revenue_growth": growth},
        "risks": risks or ["暂无明显基本面风险，仍需结合财报来源确认"],
        "reasoning": f"ROE {roe:.2%}，营收增长 {growth:.2%}，PE {pe:.1f}。",
    }


def _news_report(news_items: list) -> dict:
    scored = []
    for item in news_items:
        text = f"{getattr(item, 'title', '')} {getattr(item, 'content', '')}"
        scored.append(analyze_sentiment(text) if text.strip() else 0)
    avg = sum(scored) / len(scored) if scored else 0
    score = max(1, min(10, 5 + avg * 3 + min(len(scored), 5) * 0.15))
    sentiment = "positive" if avg > 0.15 else "negative" if avg < -0.15 else "neutral"
    return {
        "score": round(score, 1),
        "sentiment": sentiment,
        "key_events": [
            {
                "event": getattr(item, "title", "")[:80],
                "impact": "positive" if score > 6 else "negative" if score < 4 else "neutral",
                "importance": 3,
            }
            for item in news_items[:3]
        ],
        "reasoning": f"聚合 {len(news_items)} 条新闻，平均情绪 {avg:.2f}，整体 {sentiment}。",
    }


def _risk_params(price: float, decision: str) -> dict:
    position = 0.16 if decision == "buy" else 0
    return {"position_pct": position, "stop_loss_pct": 0.08, "take_profit_pct": 0.20}


def _safe(fn, fallback):
    try:
        return fn()
    except Exception:
        return fallback


def _num(data: dict, *keys: str) -> float:
    for key in keys:
        try:
            value = data.get(key)
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0
