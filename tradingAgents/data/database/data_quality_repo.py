"""Repositories for standardized data snapshots and source quality."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import (
    DataSourceQuality,
    FinancialSnapshot,
    MarketQuoteSnapshot,
    NewsItemRecord,
)

logger = logging.getLogger(__name__)


class DataQualityRepository:
    async def add_news_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        async with get_pg_session() as session:
            for item in items:
                if not item.get("title"):
                    continue
                market = str(item.get("market", ""))
                symbol = str(item.get("symbol", ""))
                dedupe_key = str(item.get("dedupe_key") or item.get("url") or item.get("title", ""))[:255]
                result = await session.execute(
                    select(NewsItemRecord).where(
                        NewsItemRecord.market == market,
                        NewsItemRecord.symbol == symbol,
                        NewsItemRecord.dedupe_key == dedupe_key,
                    )
                )
                row = result.scalar_one_or_none()
                values = {
                    "title": str(item.get("title", "")),
                    "content": str(item.get("content", "")),
                    "source": str(item.get("source", ""))[:120],
                    "source_type": str(item.get("source_type", ""))[:40],
                    "url": str(item.get("url", "")),
                    "sentiment_score": _float(item.get("sentiment_score")),
                    "relevance_score": _float(item.get("relevance_score")),
                    "freshness_score": _float(item.get("freshness_score")),
                    "source_weight": _float(item.get("source_weight")),
                    "quality_score": _float(item.get("quality_score")),
                    "published_at": _dt(item.get("published_at")),
                    "fetched_at": _dt(item.get("fetched_at")),
                    "raw_payload": item,
                    "updated_at": datetime.utcnow(),
                }
                if row:
                    for key, value in values.items():
                        setattr(row, key, value)
                else:
                    row = NewsItemRecord(
                        market=market,
                        symbol=symbol,
                        dedupe_key=dedupe_key,
                        **values,
                    )
                    session.add(row)
                await self._touch_source_quality(
                    session,
                    source=values["source"] or "unknown",
                    category="news" if values["source_type"] != "social" else "social",
                    source_type=values["source_type"],
                    quality_score=values["quality_score"],
                    freshness_score=values["freshness_score"],
                    success=True,
                )
                stored.append(_news_dict(row))
            await session.commit()
        return stored

    async def add_market_quotes(self, quotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[MarketQuoteSnapshot] = []
        async with get_pg_session() as session:
            for quote in quotes:
                row = MarketQuoteSnapshot(
                    market=str(quote.get("market", "")),
                    symbol=str(quote.get("symbol", "")),
                    name=str(quote.get("name", "")),
                    source=str(quote.get("source", ""))[:120],
                    asset_type=str(quote.get("asset_type", "stock"))[:30],
                    price=_float(quote.get("price")),
                    open=_float(quote.get("open")),
                    high=_float(quote.get("high")),
                    low=_float(quote.get("low")),
                    close=_float(quote.get("close")),
                    change_pct=_float(quote.get("change_pct")),
                    volume=_float(quote.get("volume")),
                    turnover=_float(quote.get("turnover")),
                    quality_score=_float(quote.get("quality_score")),
                    raw_payload=quote,
                    created_at=_dt(quote.get("created_at")) or datetime.utcnow(),
                )
                session.add(row)
                rows.append(row)
                await self._touch_source_quality(
                    session,
                    source=row.source or "unknown",
                    category="market_quote",
                    source_type=row.asset_type,
                    quality_score=row.quality_score,
                    freshness_score=1.0 if row.price > 0 else 0.2,
                    success=row.price > 0,
                    error="" if row.price > 0 else "empty_quote",
                )
            await session.commit()
            return [_quote_dict(row) for row in rows]

    async def add_financial_snapshot(
        self,
        *,
        market: str,
        symbol: str,
        metrics: dict[str, Any],
        source: str = "strategy_financials",
        fiscal_period: str = "",
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        quality_score = _financial_quality(metrics)
        async with get_pg_session() as session:
            row = FinancialSnapshot(
                market=market,
                symbol=symbol,
                source=source,
                fiscal_period=fiscal_period,
                metrics=metrics or {},
                quality_score=quality_score,
                raw_payload=raw_payload or metrics or {},
            )
            session.add(row)
            await self._touch_source_quality(
                session,
                source=source,
                category="financial",
                source_type="fundamental",
                quality_score=quality_score,
                freshness_score=1.0 if metrics else 0.2,
                success=bool(metrics),
                error="" if metrics else "empty_financials",
            )
            await session.commit()
            await session.refresh(row)
            return _financial_dict(row)

    async def list_news(self, market: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(NewsItemRecord)
            if market:
                stmt = stmt.where(NewsItemRecord.market == market)
            if symbol:
                stmt = stmt.where(NewsItemRecord.symbol == symbol)
            stmt = stmt.order_by(NewsItemRecord.published_at.desc().nullslast(), NewsItemRecord.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_news_dict(row) for row in result.scalars().all()]

    async def list_market_quotes(self, market: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(MarketQuoteSnapshot)
            if market:
                stmt = stmt.where(MarketQuoteSnapshot.market == market)
            if symbol:
                stmt = stmt.where(MarketQuoteSnapshot.symbol == symbol)
            stmt = stmt.order_by(MarketQuoteSnapshot.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_quote_dict(row) for row in result.scalars().all()]

    async def list_financials(self, market: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(FinancialSnapshot)
            if market:
                stmt = stmt.where(FinancialSnapshot.market == market)
            if symbol:
                stmt = stmt.where(FinancialSnapshot.symbol == symbol)
            stmt = stmt.order_by(FinancialSnapshot.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_financial_dict(row) for row in result.scalars().all()]

    async def source_status(self) -> dict[str, Any]:
        async with get_pg_session() as session:
            sources = (await session.execute(
                select(DataSourceQuality).order_by(DataSourceQuality.updated_at.desc())
            )).scalars().all()
            counts = {}
            for model, name in (
                (NewsItemRecord, "news"),
                (MarketQuoteSnapshot, "market_quote"),
                (FinancialSnapshot, "financial"),
            ):
                counts[name] = int((await session.execute(select(func.count()).select_from(model))).scalar() or 0)
            return {
                "counts": counts,
                "sources": [_source_dict(row) for row in sources],
            }

    async def _touch_source_quality(
        self,
        session,
        *,
        source: str,
        category: str,
        source_type: str = "",
        quality_score: float = 0,
        freshness_score: float = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        result = await session.execute(
            select(DataSourceQuality).where(
                DataSourceQuality.source == source,
                DataSourceQuality.category == category,
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = DataSourceQuality(source=source, category=category, source_type=source_type)
            session.add(row)
        success_count = int(row.success_count or 0)
        failure_count = int(row.failure_count or 0)
        total_before = max(success_count + failure_count, 0)
        total_after = total_before + 1
        if success:
            row.success_count = success_count + 1
            row.failure_count = failure_count
            row.last_success_at = now
            row.last_error = ""
        else:
            row.success_count = success_count
            row.failure_count = failure_count + 1
            row.last_failure_at = now
            row.last_error = error[:500]
        row.source_type = source_type or row.source_type
        row.quality_score = round(((_float(row.quality_score) * total_before) + quality_score) / total_after, 2)
        row.freshness_score = round(((_float(row.freshness_score) * total_before) + freshness_score * 100) / total_after, 2)
        attempts = max(int(row.success_count or 0) + int(row.failure_count or 0), 1)
        row.reliability_score = round(row.success_count / attempts * 100, 2)
        row.updated_at = now


def persist_news_items_sync(items: list[dict[str, Any]]) -> None:
    _run_best_effort(DataQualityRepository().add_news_items(items), "news")


def persist_market_quotes_sync(quotes: list[dict[str, Any]]) -> None:
    _run_best_effort(DataQualityRepository().add_market_quotes(quotes), "market_quotes")


def persist_financial_snapshot_sync(
    *,
    market: str,
    symbol: str,
    metrics: dict[str, Any],
    source: str = "strategy_financials",
    fiscal_period: str = "",
    raw_payload: dict[str, Any] | None = None,
) -> None:
    _run_best_effort(
        DataQualityRepository().add_financial_snapshot(
            market=market,
            symbol=symbol,
            metrics=metrics,
            source=source,
            fiscal_period=fiscal_period,
            raw_payload=raw_payload,
        ),
        "financial_snapshot",
    )


def _run_best_effort(coro, label: str) -> None:
    try:
        asyncio.get_running_loop()
        coro.close()
        return
    except RuntimeError:
        pass
    try:
        asyncio.run(coro)
    except Exception as exc:
        logger.debug("Standardized data persistence failed for %s: %s", label, exc)


def _news_dict(row: NewsItemRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "title": row.title,
        "content": row.content,
        "source": row.source,
        "source_type": row.source_type,
        "url": row.url,
        "sentiment_score": row.sentiment_score,
        "relevance_score": row.relevance_score,
        "freshness_score": row.freshness_score,
        "source_weight": row.source_weight,
        "quality_score": row.quality_score,
        "published_at": _iso(row.published_at),
        "fetched_at": _iso(row.fetched_at),
        "created_at": _iso(row.created_at),
    }


def _quote_dict(row: MarketQuoteSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "name": row.name,
        "source": row.source,
        "asset_type": row.asset_type,
        "price": row.price,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "change_pct": row.change_pct,
        "volume": row.volume,
        "turnover": row.turnover,
        "quality_score": row.quality_score,
        "created_at": _iso(row.created_at),
    }


def _financial_dict(row: FinancialSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "source": row.source,
        "fiscal_period": row.fiscal_period,
        "metrics": row.metrics or {},
        "quality_score": row.quality_score,
        "created_at": _iso(row.created_at),
    }


def _source_dict(row: DataSourceQuality) -> dict[str, Any]:
    return {
        "source": row.source,
        "category": row.category,
        "source_type": row.source_type,
        "quality_score": row.quality_score,
        "reliability_score": row.reliability_score,
        "freshness_score": row.freshness_score,
        "success_count": row.success_count,
        "failure_count": row.failure_count,
        "last_success_at": _iso(row.last_success_at),
        "last_failure_at": _iso(row.last_failure_at),
        "last_error": row.last_error,
        "updated_at": _iso(row.updated_at),
    }


def _financial_quality(metrics: dict[str, Any]) -> float:
    if not metrics:
        return 25.0
    required = ("pe", "pb", "roe", "revenue_growth", "net_profit_growth")
    coverage = sum(1 for key in required if metrics.get(key) not in (None, "", 0))
    return round(min(45 + coverage / len(required) * 50, 95), 2)


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
