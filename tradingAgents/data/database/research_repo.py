"""Persistence for strategy research experiments and leaderboards."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import StrategyExperiment, StrategyLeaderboard, StrategyParamTrial


class ResearchRepository:
    async def save_experiment(self, experiment: dict[str, Any]) -> dict[str, Any]:
        async with get_pg_session() as session:
            row = StrategyExperiment(
                experiment_id=experiment["experiment_id"],
                engine=experiment.get("engine", "local_research_baseline"),
                strategy=experiment.get("strategy", "baseline_momentum"),
                market=experiment.get("market", ""),
                period=experiment.get("period", ""),
                status=experiment.get("status", "success"),
                train_range=experiment.get("train_range", {}),
                valid_range=experiment.get("valid_range", {}),
                test_range=experiment.get("test_range", {}),
                params=experiment.get("params", {}),
                metrics=experiment.get("metrics", {}),
                warnings=experiment.get("warnings", []),
                best_trial_id=experiment.get("best_trial_id", ""),
                started_at=experiment.get("started_at"),
                finished_at=experiment.get("finished_at"),
            )
            session.add(row)
            for trial in experiment.get("trials", []):
                trial_row = StrategyParamTrial(
                    trial_id=trial["trial_id"],
                    experiment_id=experiment["experiment_id"],
                    backtest_run_id=trial.get("backtest_run_id", ""),
                    engine=trial.get("engine", experiment.get("engine", "")),
                    strategy=trial.get("strategy", experiment.get("strategy", "")),
                    market=trial.get("market", experiment.get("market", "")),
                    status=trial.get("status", "success"),
                    params=trial.get("params", {}),
                    train_metrics=trial.get("train_metrics", {}),
                    valid_metrics=trial.get("valid_metrics", {}),
                    test_metrics=trial.get("test_metrics", {}),
                    overall_metrics=trial.get("overall_metrics", {}),
                    score=_float(trial.get("score")),
                    data_coverage=_float(trial.get("data_coverage")),
                    warnings=trial.get("warnings", []),
                    started_at=trial.get("started_at"),
                    finished_at=trial.get("finished_at"),
                )
                session.add(trial_row)
                session.add(_leaderboard_row(experiment, trial))
            await session.commit()
            return await self.get_experiment(experiment["experiment_id"]) or experiment

    async def list_experiments(self, market: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(StrategyExperiment)
            if market:
                stmt = stmt.where(StrategyExperiment.market == market)
            stmt = stmt.order_by(StrategyExperiment.finished_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_experiment_dict(row) for row in result.scalars().all()]

    async def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        async with get_pg_session() as session:
            exp = (await session.execute(
                select(StrategyExperiment).where(StrategyExperiment.experiment_id == experiment_id)
            )).scalar_one_or_none()
            if exp is None:
                return None
            trials = (await session.execute(
                select(StrategyParamTrial)
                .where(StrategyParamTrial.experiment_id == experiment_id)
                .order_by(StrategyParamTrial.score.desc())
            )).scalars().all()
            payload = _experiment_dict(exp)
            payload["trials"] = [_trial_dict(row) for row in trials]
            return payload

    async def leaderboard(self, market: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        async with get_pg_session() as session:
            stmt = select(StrategyLeaderboard)
            if market:
                stmt = stmt.where(StrategyLeaderboard.market == market)
            stmt = stmt.order_by(StrategyLeaderboard.score.desc(), StrategyLeaderboard.updated_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_leaderboard_dict(row) for row in result.scalars().all()]


def _leaderboard_row(experiment: dict[str, Any], trial: dict[str, Any]) -> StrategyLeaderboard:
    overall = trial.get("overall_metrics", {}) or {}
    test = trial.get("test_metrics", {}) or {}
    return StrategyLeaderboard(
        market=trial.get("market", experiment.get("market", "")),
        strategy=trial.get("strategy", experiment.get("strategy", "")),
        engine=trial.get("engine", experiment.get("engine", "")),
        experiment_id=experiment["experiment_id"],
        trial_id=trial["trial_id"],
        backtest_run_id=trial.get("backtest_run_id", ""),
        score=_float(trial.get("score")),
        annual_return=_float(overall.get("annual_return")),
        max_drawdown=_float(overall.get("max_drawdown")),
        sharpe=_float(overall.get("sharpe")),
        win_rate=_float(overall.get("win_rate")),
        test_annual_return=_float(test.get("annual_return")),
        test_max_drawdown=_float(test.get("max_drawdown")),
        test_sharpe=_float(test.get("sharpe")),
        data_coverage=_float(trial.get("data_coverage")),
        params=trial.get("params", {}),
        metrics={
            "train": trial.get("train_metrics", {}),
            "valid": trial.get("valid_metrics", {}),
            "test": test,
            "overall": overall,
        },
    )


def _experiment_dict(row: StrategyExperiment) -> dict[str, Any]:
    return {
        "experiment_id": row.experiment_id,
        "engine": row.engine,
        "strategy": row.strategy,
        "market": row.market,
        "period": row.period,
        "status": row.status,
        "train_range": row.train_range or {},
        "valid_range": row.valid_range or {},
        "test_range": row.test_range or {},
        "params": row.params or {},
        "metrics": row.metrics or {},
        "warnings": row.warnings or [],
        "best_trial_id": row.best_trial_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _trial_dict(row: StrategyParamTrial) -> dict[str, Any]:
    return {
        "trial_id": row.trial_id,
        "experiment_id": row.experiment_id,
        "backtest_run_id": row.backtest_run_id,
        "engine": row.engine,
        "strategy": row.strategy,
        "market": row.market,
        "status": row.status,
        "params": row.params or {},
        "train_metrics": row.train_metrics or {},
        "valid_metrics": row.valid_metrics or {},
        "test_metrics": row.test_metrics or {},
        "overall_metrics": row.overall_metrics or {},
        "score": row.score,
        "data_coverage": row.data_coverage,
        "warnings": row.warnings or [],
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _leaderboard_dict(row: StrategyLeaderboard) -> dict[str, Any]:
    return {
        "market": row.market,
        "strategy": row.strategy,
        "engine": row.engine,
        "experiment_id": row.experiment_id,
        "trial_id": row.trial_id,
        "backtest_run_id": row.backtest_run_id,
        "score": row.score,
        "annual_return": row.annual_return,
        "max_drawdown": row.max_drawdown,
        "sharpe": row.sharpe,
        "win_rate": row.win_rate,
        "test_annual_return": row.test_annual_return,
        "test_max_drawdown": row.test_max_drawdown,
        "test_sharpe": row.test_sharpe,
        "data_coverage": row.data_coverage,
        "params": row.params or {},
        "metrics": row.metrics or {},
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
