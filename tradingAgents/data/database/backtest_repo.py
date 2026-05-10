"""Repository for persisted backtest runs."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import BacktestEquityCurve, BacktestRun, BacktestTrade


class BacktestRepository:
    async def save_result(self, result: dict[str, Any]) -> dict[str, Any]:
        async with get_pg_session() as session:
            run = BacktestRun(
                run_id=result["run_id"],
                strategy=result.get("strategy", "baseline_momentum"),
                market=result.get("market", ""),
                period=result.get("period", ""),
                status=result.get("status", "success"),
                initial_cash=_float(result.get("initial_cash")),
                final_value=_float(result.get("final_value")),
                total_return=_float(result.get("metrics", {}).get("total_return")),
                annual_return=_float(result.get("metrics", {}).get("annual_return")),
                max_drawdown=_float(result.get("metrics", {}).get("max_drawdown")),
                sharpe=_float(result.get("metrics", {}).get("sharpe")),
                win_rate=_float(result.get("metrics", {}).get("win_rate")),
                trade_count=len(result.get("trades", [])),
                params=result.get("params", {}),
                metrics=result.get("metrics", {}),
                warnings=result.get("warnings", []),
                started_at=result.get("started_at"),
                finished_at=result.get("finished_at"),
            )
            session.add(run)
            for trade in result.get("trades", []):
                session.add(BacktestTrade(
                    run_id=result["run_id"],
                    trade_date=trade.get("date"),
                    symbol=trade.get("symbol", ""),
                    name=trade.get("name", ""),
                    action=_trade_action(trade.get("action", "")),
                    price=_float(trade.get("price")),
                    quantity=_float(trade.get("quantity")),
                    amount=_float(trade.get("amount")),
                    fee=_float(trade.get("fee")),
                    reason=trade.get("reason", ""),
                ))
            for point in result.get("equity_curve", []):
                session.add(BacktestEquityCurve(
                    run_id=result["run_id"],
                    trade_date=point.get("date"),
                    cash=_float(point.get("cash")),
                    positions_value=_float(point.get("positions_value")),
                    total_value=_float(point.get("total_value")),
                    daily_return=_float(point.get("daily_return")),
                    drawdown=_float(point.get("drawdown")),
                    positions=point.get("positions", {}),
                ))
            await session.commit()
            return await self.get_run(result["run_id"]) or result

    async def list_runs(self, market: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(BacktestRun)
            if market:
                stmt = stmt.where(BacktestRun.market == market)
            stmt = stmt.order_by(BacktestRun.finished_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_run_dict(row) for row in result.scalars().all()]

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with get_pg_session() as session:
            run = (await session.execute(
                select(BacktestRun).where(BacktestRun.run_id == run_id)
            )).scalar_one_or_none()
            if run is None:
                return None
            trades = (await session.execute(
                select(BacktestTrade)
                .where(BacktestTrade.run_id == run_id)
                .order_by(BacktestTrade.trade_date.asc(), BacktestTrade.id.asc())
            )).scalars().all()
            curve = (await session.execute(
                select(BacktestEquityCurve)
                .where(BacktestEquityCurve.run_id == run_id)
                .order_by(BacktestEquityCurve.trade_date.asc())
            )).scalars().all()
            payload = _run_dict(run)
            payload["trades"] = [_trade_dict(row) for row in trades]
            payload["equity_curve"] = [_curve_dict(row) for row in curve]
            return payload


def _run_dict(row: BacktestRun) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "strategy": row.strategy,
        "market": row.market,
        "period": row.period,
        "status": row.status,
        "initial_cash": row.initial_cash,
        "final_value": row.final_value,
        "metrics": row.metrics or {},
        "params": row.params or {},
        "warnings": row.warnings or [],
        "trade_count": row.trade_count,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _trade_dict(row: BacktestTrade) -> dict[str, Any]:
    return {
        "date": row.trade_date.isoformat() if row.trade_date else None,
        "symbol": row.symbol,
        "name": row.name,
        "action": row.action,
        "price": row.price,
        "quantity": row.quantity,
        "amount": row.amount,
        "fee": row.fee,
        "reason": row.reason,
    }


def _curve_dict(row: BacktestEquityCurve) -> dict[str, Any]:
    return {
        "date": row.trade_date.isoformat() if row.trade_date else None,
        "cash": row.cash,
        "positions_value": row.positions_value,
        "total_value": row.total_value,
        "daily_return": row.daily_return,
        "drawdown": row.drawdown,
        "positions": row.positions or {},
    }


def _trade_action(value: Any) -> str:
    action = str(value or "").upper()
    if action == "BUY_BLOCKED":
        return "BUY_BLOCK"
    if action == "SELL_BLOCKED":
        return "SELL_BLOCK"
    return action[:10]


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
