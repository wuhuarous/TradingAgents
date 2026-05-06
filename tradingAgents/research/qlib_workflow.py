"""Qlib professional workflow runner."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingAgents.research.qlib_adapter import QlibAdapter


@dataclass
class QlibWorkflowConfig:
    provider_uri: str | None = None
    experiment_name: str = "tradingagents_qlib_csi300"
    initial_cash: float = 100_000_000
    top_n: int = 50
    n_drop: int = 5
    limit_threshold: float = 0.095
    open_cost: float = 0.0005
    close_cost: float = 0.0015
    min_fee: float = 5.0
    download_data: bool = False
    num_threads: int = 4


class QlibWorkflowRunner:
    strategy_name = "qlib_csi300_gbdt_topk"

    def __init__(self, adapter: QlibAdapter | None = None):
        self._adapter = adapter or QlibAdapter()

    def run_csi300_gbdt(self, config: QlibWorkflowConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        experiment_id = f"qlib{started_at.strftime('%Y%m%d%H%M%S%f')}"
        status = self._adapter.status()
        if not status.available:
            return self._failed(experiment_id, started_at, status.message, config)

        data_status = self._adapter.data_status(config.provider_uri)
        if not data_status["available"]:
            if not config.download_data:
                return self._failed(
                    experiment_id,
                    started_at,
                    "Qlib 标准数据未就绪；请先调用数据准备接口，或在运行实验时启用 download_data。",
                    config,
                    data_status=data_status,
                )
            prepared = self._adapter.prepare_cn_data(config.provider_uri)
            data_status = prepared.get("data", data_status)
            if not data_status.get("available"):
                return self._failed(experiment_id, started_at, "Qlib 数据准备失败。", config, data_status=data_status)

        try:
            result = self._run_workflow(experiment_id, started_at, config, data_status)
            return result
        except Exception as exc:
            return self._failed(
                experiment_id,
                started_at,
                f"Qlib 实验执行失败: {type(exc).__name__}: {str(exc)[:500]}",
                config,
                data_status=data_status,
            )

    def _run_workflow(
        self,
        experiment_id: str,
        started_at: datetime,
        config: QlibWorkflowConfig,
        data_status: dict[str, Any],
    ) -> dict[str, Any]:
        import qlib
        from qlib.constant import REG_CN
        from qlib.tests.config import CSI300_BENCH, CSI300_GBDT_TASK
        from qlib.utils import flatten_dict, init_instance_by_config
        from qlib.workflow import R
        from qlib.workflow.record_temp import PortAnaRecord, SigAnaRecord, SignalRecord

        provider_uri = data_status["provider_uri"]
        recorder_uri = str(Path("memory") / "qlib_experiments")
        qlib.init(
            provider_uri=provider_uri,
            region=REG_CN,
            exp_manager={
                "class": "MLflowExpManager",
                "module_path": "qlib.workflow.expm",
                "kwargs": {
                    "uri": f"file:{Path(recorder_uri).resolve()}",
                    "default_exp_name": config.experiment_name,
                },
            },
        )

        task = copy.deepcopy(CSI300_GBDT_TASK)
        task["model"]["kwargs"]["num_threads"] = max(1, min(config.num_threads, 16))
        model = init_instance_by_config(task["model"])
        dataset = init_instance_by_config(task["dataset"])
        portfolio_config = self._portfolio_config(config, model, dataset, CSI300_BENCH)

        with R.start(experiment_name=config.experiment_name, recorder_name=experiment_id):
            R.log_params(**flatten_dict(task))
            R.log_params(**flatten_dict({"tradingagents": self._params(config)}))
            model.fit(dataset)
            R.save_objects(**{"params.pkl": model})

            recorder = R.get_recorder()
            SignalRecord(model, dataset, recorder).generate()
            SigAnaRecord(recorder).generate()
            PortAnaRecord(recorder, portfolio_config, "day").generate()
            metrics = _json_safe(recorder.list_metrics())
            recorder_id = getattr(recorder, "id", "")

        train_range = _segment_range(task, "train")
        valid_range = _segment_range(task, "valid")
        test_range = _segment_range(task, "test")
        overall_metrics = _extract_qlib_metrics(metrics)
        test_metrics = {
            "annual_return": overall_metrics.get("annual_return", 0),
            "max_drawdown": overall_metrics.get("max_drawdown", 0),
            "sharpe": overall_metrics.get("information_ratio", overall_metrics.get("sharpe", 0)),
            "information_ratio": overall_metrics.get("information_ratio", 0),
            "excess_return": overall_metrics.get("excess_return", 0),
        }
        score = _qlib_score(test_metrics, overall_metrics)
        trial_id = f"{experiment_id}_qlib"
        finished_at = datetime.utcnow()
        return {
            "experiment_id": experiment_id,
            "engine": "qlib",
            "qlib": {
                **self._adapter.status().as_dict(),
                "provider_uri": provider_uri,
                "recorder_uri": recorder_uri,
                "recorder_id": recorder_id,
            },
            "strategy": self.strategy_name,
            "market": "a_stock",
            "period": "2008-2020",
            "status": "success",
            "params": {
                **self._params(config),
                "qlib_task": _json_safe(task),
                "qlib_portfolio_config": self._adapter.build_portfolio_config({
                    "initial_cash": config.initial_cash,
                    "top_n": config.top_n,
                    "n_drop": config.n_drop,
                    "limit_threshold": config.limit_threshold,
                    "open_cost": config.open_cost,
                    "close_cost": config.close_cost,
                    "min_fee": config.min_fee,
                }),
            },
            "metrics": {
                "best_score": score,
                "best_trial_id": trial_id,
                "qlib_raw_metrics": metrics,
                **overall_metrics,
            },
            "train_range": train_range,
            "valid_range": valid_range,
            "test_range": test_range,
            "warnings": [
                "Qlib 专业实验已启用标准组合回测配置，包含涨跌停阈值、开平仓成本和最低佣金。",
                "当前第一版使用 Qlib 自带 CSI300/Alpha158/LightGBM 示例任务，下一步替换为本项目沉淀的因子和新闻情绪特征。",
            ],
            "best_trial_id": trial_id,
            "trials": [{
                "trial_id": trial_id,
                "experiment_id": experiment_id,
                "backtest_run_id": "",
                "engine": "qlib",
                "strategy": self.strategy_name,
                "market": "a_stock",
                "status": "success",
                "params": self._params(config),
                "train_metrics": {"days": train_range.get("days", 0)},
                "valid_metrics": {"days": valid_range.get("days", 0)},
                "test_metrics": test_metrics,
                "overall_metrics": overall_metrics,
                "score": score,
                "data_coverage": 1.0,
                "warnings": [],
                "started_at": started_at,
                "finished_at": finished_at,
            }],
            "started_at": started_at,
            "finished_at": finished_at,
        }

    def _portfolio_config(self, config: QlibWorkflowConfig, model: Any, dataset: Any, benchmark: str) -> dict[str, Any]:
        return {
            "executor": {
                "class": "SimulatorExecutor",
                "module_path": "qlib.backtest.executor",
                "kwargs": {
                    "time_per_step": "day",
                    "generate_portfolio_metrics": True,
                },
            },
            "strategy": {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy.signal_strategy",
                "kwargs": {
                    "signal": (model, dataset),
                    "topk": config.top_n,
                    "n_drop": config.n_drop,
                },
            },
            "backtest": {
                "start_time": "2017-01-01",
                "end_time": "2020-08-01",
                "account": config.initial_cash,
                "benchmark": benchmark,
                "exchange_kwargs": {
                    "freq": "day",
                    "limit_threshold": config.limit_threshold,
                    "deal_price": "close",
                    "open_cost": config.open_cost,
                    "close_cost": config.close_cost,
                    "min_cost": config.min_fee,
                },
            },
        }

    def _params(self, config: QlibWorkflowConfig) -> dict[str, Any]:
        return {
            "provider_uri": self._adapter.provider_uri(config.provider_uri),
            "experiment_name": config.experiment_name,
            "initial_cash": config.initial_cash,
            "top_n": config.top_n,
            "n_drop": config.n_drop,
            "limit_threshold": config.limit_threshold,
            "open_cost": config.open_cost,
            "close_cost": config.close_cost,
            "min_fee": config.min_fee,
            "download_data": config.download_data,
            "num_threads": config.num_threads,
        }

    def _failed(
        self,
        experiment_id: str,
        started_at: datetime,
        message: str,
        config: QlibWorkflowConfig,
        data_status: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        finished_at = datetime.utcnow()
        return {
            "experiment_id": experiment_id,
            "engine": "qlib",
            "qlib": {
                **self._adapter.status().as_dict(),
                "data": data_status or self._adapter.data_status(config.provider_uri),
            },
            "strategy": self.strategy_name,
            "market": "a_stock",
            "period": "2008-2020",
            "status": "failed",
            "params": self._params(config),
            "metrics": {"best_score": 0, "best_trial_id": ""},
            "train_range": {},
            "valid_range": {},
            "test_range": {},
            "warnings": [message],
            "best_trial_id": "",
            "trials": [],
            "started_at": started_at,
            "finished_at": finished_at,
        }


def _segment_range(task: dict[str, Any], segment: str) -> dict[str, Any]:
    start, end = task["dataset"]["kwargs"]["segments"][segment]
    return {"start": start, "end": end, "days": 0}


def _extract_qlib_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "annual_return": _find_metric(metrics, ("annualized_return", "annual_return")),
        "max_drawdown": _find_metric(metrics, ("max_drawdown",)),
        "information_ratio": _find_metric(metrics, ("information_ratio", "ir")),
        "sharpe": _find_metric(metrics, ("sharpe",)),
        "excess_return": _find_metric(metrics, ("excess_return", "return")),
        "win_rate": 0.0,
    }


def _find_metric(metrics: dict[str, Any], needles: tuple[str, ...]) -> float:
    for key, value in metrics.items():
        lowered = str(key).lower()
        if any(needle in lowered for needle in needles):
            number = _to_float(value)
            if number is not None:
                return number
    return 0.0


def _qlib_score(test_metrics: dict[str, Any], overall: dict[str, Any]) -> float:
    annual = float(test_metrics.get("annual_return") or overall.get("annual_return") or 0)
    drawdown = abs(float(test_metrics.get("max_drawdown") or overall.get("max_drawdown") or 0))
    ir = float(test_metrics.get("information_ratio") or overall.get("information_ratio") or 0)
    return round(annual * 0.55 + ir * 0.10 - drawdown * 0.35, 6)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _to_float(value: Any) -> float | None:
    if hasattr(value, "item"):
        value = value.item()
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        return None
    return None
