"""Repository for strategy factor scores."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import FactorScore


class FactorScoreRepository:
    async def add_score(
        self,
        candidate: dict[str, Any],
        run_id: str = "",
        strategy: str = "quality_momentum",
    ) -> dict[str, Any]:
        scores = candidate.get("scores") or {}
        async with get_pg_session() as session:
            row = FactorScore(
                run_id=run_id,
                strategy=strategy,
                market=str(candidate.get("market", "")),
                symbol=str(candidate.get("symbol", "")),
                name=str(candidate.get("name", "")),
                action=str(candidate.get("action", "")),
                risk_level=str(candidate.get("risk_level", "")),
                price=_float(candidate.get("price")),
                change_pct=_float(candidate.get("change_pct")),
                final_score=_float(candidate.get("final_score")),
                quality_score=_float(scores.get("quality")),
                growth_score=_float(scores.get("growth")),
                valuation_score=_float(scores.get("valuation")),
                momentum_score=_float(scores.get("momentum")),
                sentiment_score=_float(scores.get("sentiment")),
                liquidity_score=_float(scores.get("liquidity")),
                risk_score=_float(scores.get("risk")),
                fundamentals=candidate.get("fundamentals") or {},
                technical=candidate.get("technical") or {},
                sentiment=candidate.get("sentiment") or {},
                trade_plan=candidate.get("trade_plan") or {},
                reasons=candidate.get("reasons") or [],
                warnings=candidate.get("warnings") or [],
                data_quality_score=_data_quality(candidate),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_factor_dict(row)

    async def list_scores(
        self,
        market: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(FactorScore)
            if market:
                stmt = stmt.where(FactorScore.market == market)
            if symbol:
                stmt = stmt.where(FactorScore.symbol == symbol)
            stmt = stmt.order_by(FactorScore.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_to_factor_dict(row) for row in result.scalars().all()]

    async def latest_by_market(self, market: str, limit: int = 20) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            result = await session.execute(
                select(FactorScore)
                .where(FactorScore.market == market)
                .order_by(FactorScore.created_at.desc(), FactorScore.final_score.desc())
                .limit(limit)
            )
            return [_to_factor_dict(row) for row in result.scalars().all()]


def _to_factor_dict(row: FactorScore) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "strategy": row.strategy,
        "market": row.market,
        "symbol": row.symbol,
        "name": row.name,
        "action": row.action,
        "risk_level": row.risk_level,
        "price": row.price,
        "change_pct": row.change_pct,
        "final_score": row.final_score,
        "scores": {
            "quality": row.quality_score,
            "growth": row.growth_score,
            "valuation": row.valuation_score,
            "momentum": row.momentum_score,
            "sentiment": row.sentiment_score,
            "liquidity": row.liquidity_score,
            "risk": row.risk_score,
        },
        "fundamentals": row.fundamentals or {},
        "technical": row.technical or {},
        "sentiment": row.sentiment or {},
        "trade_plan": row.trade_plan or {},
        "reasons": row.reasons or [],
        "warnings": row.warnings or [],
        "data_quality_score": row.data_quality_score,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _data_quality(candidate: dict[str, Any]) -> float:
    score = 35.0
    if candidate.get("price"):
        score += 20
    if candidate.get("fundamentals"):
        score += 15
    if candidate.get("technical"):
        score += 15
    sentiment = candidate.get("sentiment") or {}
    if sentiment.get("news_count", 0) > 0:
        score += 15
    return min(score, 100.0)


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
