"""Thin Qlib integration boundary.

The project uses Qlib as the preferred professional research engine, but Qlib
is an optional local dependency. This adapter keeps the rest of the app useful
when Qlib is not installed, while making the missing capability explicit.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QlibStatus:
    available: bool
    engine: str
    message: str
    module_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "engine": self.engine,
            "message": self.message,
            "module_path": self.module_path,
        }


class QlibAdapter:
    default_provider_uri = "~/.qlib/qlib_data/cn_data"

    def status(self) -> QlibStatus:
        spec = importlib.util.find_spec("qlib")
        if spec is None:
            local_path = r"D:\project\qlib"
            if os.path.isdir(local_path):
                return QlibStatus(
                    available=False,
                    engine="local_research_baseline",
                    module_path=local_path,
                    message="检测到本地 Qlib 源码目录，但当前 Python 环境未安装 qlib 包；先使用本地研究基线，安装后可切换 Qlib 专业回测。",
                )
            return QlibStatus(
                available=False,
                engine="local_research_baseline",
                message="当前 Python 环境未安装 qlib；先使用本地研究基线。",
            )
        return QlibStatus(
            available=True,
            engine="qlib",
            module_path=spec.origin or "",
            message="Qlib 可用，可以运行专业实验工作流。",
        )

    def provider_uri(self, provider_uri: str | None = None) -> str:
        return provider_uri or os.environ.get("QLIB_PROVIDER_URI") or self.default_provider_uri

    def data_status(self, provider_uri: str | None = None) -> dict[str, Any]:
        uri = self.provider_uri(provider_uri)
        path = Path(uri).expanduser()
        calendar = path / "calendars" / "day.txt"
        instruments = path / "instruments"
        features = path / "features"
        available = path.exists() and calendar.exists() and instruments.exists() and features.exists()
        return {
            "provider_uri": str(path),
            "available": available,
            "calendar": calendar.exists(),
            "instruments": instruments.exists(),
            "features": features.exists(),
            "message": "Qlib 标准数据已就绪" if available else "Qlib 标准数据未就绪，需要先准备数据。",
        }

    def prepare_cn_data(self, provider_uri: str | None = None) -> dict[str, Any]:
        status = self.status()
        if not status.available:
            return {**status.as_dict(), "data": self.data_status(provider_uri)}
        uri = self.provider_uri(provider_uri)
        path = Path(uri).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        from qlib.constant import REG_CN
        from qlib.tests.data import GetData

        GetData().qlib_data(target_dir=str(path), region=REG_CN, exists_skip=True)
        return {
            **status.as_dict(),
            "data": self.data_status(str(path)),
        }

    def build_portfolio_config(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the Qlib backtest config shape we will use once qlib is enabled."""
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
                    "topk": int(params.get("top_n", 5)),
                    "n_drop": int(params.get("n_drop", 1)),
                },
            },
            "backtest": {
                "account": float(params.get("initial_cash", 1_000_000)),
                "exchange_kwargs": {
                    "freq": "day",
                    "limit_threshold": float(params.get("limit_threshold", 0.095)),
                    "deal_price": params.get("deal_price", "close"),
                    "open_cost": float(params.get("open_cost", 0.0005)),
                    "close_cost": float(params.get("close_cost", 0.0015)),
                    "min_cost": float(params.get("min_fee", 5.0)),
                },
            },
        }
