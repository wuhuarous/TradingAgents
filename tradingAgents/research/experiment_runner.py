"""Strategy experiment runner with parameter trials and out-of-sample scoring."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from tradingAgents.research.qlib_adapter import QlibAdapter
from tradingAgents.trader.backtest import BacktestConfig, BaselineMomentumBacktester, ShortTerm100BacktestStrategy


@dataclass
class ResearchExperimentConfig:
    strategy: str = "baseline_momentum"
    market: str = "a_stock"
    period: str = "1y"
    initial_cash: float = 1_000_000
    universe_limit: int = 200
    top_n_options: list[int] = field(default_factory=lambda: [3, 5])
    rebalance_options: list[int] = field(default_factory=lambda: [10, 20])
    lookback_short_options: list[int] = field(default_factory=lambda: [20])
    lookback_long_options: list[int] = field(default_factory=lambda: [60])
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    min_fee: float = 5.0


class ResearchExperimentRunner:
    strategy_name = "baseline_momentum"

    def __init__(self, qlib_adapter: QlibAdapter | None = None):
        self._qlib = qlib_adapter or QlibAdapter()

    def run_grid(self, config: ResearchExperimentConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        experiment_id = f"exp{started_at.strftime('%Y%m%d%H%M%S%f')}"
        qlib_status = self._qlib.status()
        warnings: list[str] = []
        if not qlib_status.available:
            warnings.append(qlib_status.message)
        warnings.append("当前实验使用本地研究引擎；Qlib 安装后可用于更专业的因子实验与组合回测。")

        trials: list[dict[str, Any]] = []
        backtester = ShortTerm100BacktestStrategy() if config.strategy == "short_term_100" else BaselineMomentumBacktester()
        combos = list(itertools.product(
            config.top_n_options,
            config.rebalance_options,
            config.lookback_short_options,
            config.lookback_long_options,
        ))
        for idx, (top_n, rebalance_days, lookback_short, lookback_long) in enumerate(combos, start=1):
            if lookback_short >= lookback_long:
                continue
            trial_started = datetime.utcnow()
            bt_config = BacktestConfig(
                strategy=config.strategy,
                market=config.market,
                period=config.period,
                initial_cash=config.initial_cash,
                universe_limit=config.universe_limit,
                top_n=min(top_n, config.universe_limit),
                rebalance_days=rebalance_days,
                lookback_short=lookback_short,
                lookback_long=lookback_long,
                fee_rate=config.fee_rate,
                slippage_rate=config.slippage_rate,
                min_fee=config.min_fee,
            )
            result = backtester.run(bt_config)
            split = _split_metrics(result.get("equity_curve", []), config.initial_cash)
            score = _trial_score(split["valid"], split["test"], result.get("metrics", {}))
            trial_id = f"{experiment_id}_t{idx:02d}"
            trial_warnings = list(result.get("warnings", []))
            trial_warnings.append("本地研究实验已计入手续费、滑点、A股涨跌停、T+1、停牌/无成交和成交量参与上限；Qlib 用于更专业的因子实验与组合回测。")
            trials.append({
                "trial_id": trial_id,
                "experiment_id": experiment_id,
                "backtest_run_id": result.get("run_id", ""),
                "engine": qlib_status.engine,
                "strategy": config.strategy,
                "market": config.market,
                "status": result.get("status", "success"),
                "params": result.get("params", {}),
                "train_metrics": split["train"],
                "valid_metrics": split["valid"],
                "test_metrics": split["test"],
                "overall_metrics": result.get("metrics", {}),
                "score": round(score, 6),
                "data_coverage": _data_coverage(result.get("equity_curve", []), config.period),
                "warnings": trial_warnings[:20],
                "backtest_result": result,
                "started_at": trial_started,
                "finished_at": datetime.utcnow(),
            })

        trials.sort(key=lambda item: item["score"], reverse=True)
        best = trials[0] if trials else {}
        finished_at = datetime.utcnow()
        return {
            "experiment_id": experiment_id,
            "engine": qlib_status.engine,
            "qlib": qlib_status.as_dict(),
            "strategy": config.strategy,
            "market": config.market,
            "period": config.period,
            "status": "success" if trials else "failed",
            "params": {
                "universe_limit": config.universe_limit,
                "strategy": config.strategy,
                "top_n_options": config.top_n_options,
                "rebalance_options": config.rebalance_options,
                "lookback_short_options": config.lookback_short_options,
                "lookback_long_options": config.lookback_long_options,
                "fee_rate": config.fee_rate,
                "slippage_rate": config.slippage_rate,
                "min_fee": config.min_fee,
                "qlib_portfolio_config": self._qlib.build_portfolio_config({
                    "initial_cash": config.initial_cash,
                    "top_n": best.get("params", {}).get("top_n", 5),
                    "min_fee": config.min_fee,
                }),
            },
            "metrics": {
                "trial_count": len(trials),
                "best_score": best.get("score", 0),
                "best_trial_id": best.get("trial_id", ""),
                "best_test_annual_return": best.get("test_metrics", {}).get("annual_return", 0),
                "best_test_max_drawdown": best.get("test_metrics", {}).get("max_drawdown", 0),
                "best_test_sharpe": best.get("test_metrics", {}).get("sharpe", 0),
            },
            "train_range": _range_for(best, "train"),
            "valid_range": _range_for(best, "valid"),
            "test_range": _range_for(best, "test"),
            "warnings": warnings,
            "best_trial_id": best.get("trial_id", ""),
            "trials": trials,
            "started_at": started_at,
            "finished_at": finished_at,
        }


def _split_metrics(equity_curve: list[dict[str, Any]], initial_cash: float) -> dict[str, dict[str, Any]]:
    if not equity_curve:
        empty = _empty_segment()
        return {"train": empty, "valid": empty, "test": empty}
    n = len(equity_curve)
    train_end = max(int(n * 0.6), 1)
    valid_end = max(int(n * 0.8), train_end + 1)
    return {
        "train": _segment_metrics(equity_curve[:train_end], initial_cash),
        "valid": _segment_metrics(equity_curve[train_end:valid_end], equity_curve[train_end - 1]["total_value"]),
        "test": _segment_metrics(equity_curve[valid_end:], equity_curve[valid_end - 1]["total_value"] if valid_end < n else equity_curve[-1]["total_value"]),
    }


def _segment_metrics(points: list[dict[str, Any]], starting_value: float) -> dict[str, Any]:
    if not points:
        return _empty_segment()
    values = pd.Series([float(point.get("total_value") or 0) for point in points], dtype="float64")
    values = values[values > 0]
    if values.empty or starting_value <= 0:
        return _empty_segment()
    returns = values.pct_change().dropna()
    total_return = values.iloc[-1] / starting_value - 1
    years = max(len(values) / 252, 1 / 252)
    annual_return = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1
    running_peak = values.cummax()
    drawdowns = values / running_peak - 1
    sharpe = 0.0
    if len(returns) > 2 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * math.sqrt(252))
    return {
        "start": points[0].get("date").isoformat() if hasattr(points[0].get("date"), "isoformat") else str(points[0].get("date")),
        "end": points[-1].get("date").isoformat() if hasattr(points[-1].get("date"), "isoformat") else str(points[-1].get("date")),
        "days": len(values),
        "total_return": round(float(total_return), 6),
        "annual_return": round(float(annual_return), 6),
        "max_drawdown": round(float(drawdowns.min()), 6),
        "sharpe": round(float(sharpe), 4),
    }


def _trial_score(valid: dict[str, Any], test: dict[str, Any], overall: dict[str, Any]) -> float:
    test_return = float(test.get("annual_return") or 0)
    valid_return = float(valid.get("annual_return") or 0)
    test_drawdown = abs(float(test.get("max_drawdown") or 0))
    overall_drawdown = abs(float(overall.get("max_drawdown") or 0))
    sharpe = float(test.get("sharpe") or 0)
    return test_return * 0.55 + valid_return * 0.20 + sharpe * 0.05 - test_drawdown * 0.15 - overall_drawdown * 0.05


def _data_coverage(equity_curve: list[dict[str, Any]], period: str) -> float:
    expected = {"3mo": 63, "6mo": 126, "1y": 252}.get(period, 252)
    return round(min(len(equity_curve) / expected, 1.0), 4)


def _range_for(best: dict[str, Any], key: str) -> dict[str, Any]:
    metrics = best.get(f"{key}_metrics", {}) if best else {}
    return {"start": metrics.get("start"), "end": metrics.get("end"), "days": metrics.get("days", 0)}


def _empty_segment() -> dict[str, Any]:
    return {
        "start": None,
        "end": None,
        "days": 0,
        "total_return": 0.0,
        "annual_return": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
    }
