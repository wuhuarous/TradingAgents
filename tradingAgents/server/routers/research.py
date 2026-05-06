"""Research experiment and strategy leaderboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from tradingAgents.data.database.backtest_repo import BacktestRepository
from tradingAgents.data.database.qlib_export_repo import QlibExportRepository
from tradingAgents.data.database.research_repo import ResearchRepository
from tradingAgents.research.experiment_runner import ResearchExperimentConfig, ResearchExperimentRunner
from tradingAgents.research.qlib_adapter import QlibAdapter
from tradingAgents.research.qlib_data_exporter import QlibDataExporter, QlibExportConfig
from tradingAgents.research.qlib_workflow import QlibWorkflowConfig, QlibWorkflowRunner

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/qlib/status")
async def qlib_status():
    adapter = QlibAdapter()
    return {
        **adapter.status().as_dict(),
        "data": adapter.data_status(),
    }


@router.get("/qlib/data-status")
async def qlib_data_status(provider_uri: str | None = Query(None)):
    return QlibAdapter().data_status(provider_uri)


@router.post("/qlib/prepare-data")
async def prepare_qlib_data(provider_uri: str | None = Query(None)):
    return await run_in_threadpool(QlibAdapter().prepare_cn_data, provider_uri)


@router.get("/qlib/project-data-status")
async def project_qlib_data_status(
    market: str = Query("a_stock"),
    target_dir: str = Query("memory/qlib_data/a_stock_custom"),
):
    exporter = QlibDataExporter()
    return {
        "market": market,
        "source": exporter.source_status(market=market),
        "target": exporter.status(target_dir=target_dir),
        "exports": await QlibExportRepository().list_runs(market=market, limit=10),
    }


@router.post("/qlib/export-project-data")
async def export_project_data_to_qlib(
    market: str = Query("a_stock"),
    target_dir: str = Query("memory/qlib_data/a_stock_custom"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(500, ge=1, le=6000),
    min_rows: int = Query(30, ge=5, le=2000),
    overwrite: bool = Query(False),
):
    config = QlibExportConfig(
        market=market,
        target_dir=target_dir,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        min_rows=min_rows,
        overwrite=overwrite,
    )
    result = await run_in_threadpool(QlibDataExporter().export_from_clickhouse, config)
    return await QlibExportRepository().save_run(result)


@router.post("/experiments/run-grid")
async def run_parameter_grid(
    market: str = Query("a_stock"),
    period: str = Query("1y", pattern="^(3mo|6mo|1y)$"),
    initial_cash: float = Query(1_000_000, gt=0),
    universe_limit: int = Query(200, ge=5, le=6000),
    top_n_options: str = Query("3,5"),
    rebalance_options: str = Query("10,20"),
    lookback_short_options: str = Query("20"),
    lookback_long_options: str = Query("60"),
    fee_rate: float = Query(0.0005, ge=0, le=0.02),
    slippage_rate: float = Query(0.0005, ge=0, le=0.02),
    min_fee: float = Query(5.0, ge=0, le=100),
):
    top_ns = _parse_int_list(top_n_options, minimum=1, maximum=20)
    rebalances = _parse_int_list(rebalance_options, minimum=5, maximum=60)
    lookback_shorts = _parse_int_list(lookback_short_options, minimum=5, maximum=120)
    lookback_longs = _parse_int_list(lookback_long_options, minimum=20, maximum=240)
    trial_count = len(top_ns) * len(rebalances) * len(lookback_shorts) * len(lookback_longs)
    if trial_count > 24:
        raise HTTPException(status_code=400, detail="参数组合过多，请控制在 24 组以内")

    config = ResearchExperimentConfig(
        market=market,
        period=period,
        initial_cash=initial_cash,
        universe_limit=universe_limit,
        top_n_options=top_ns,
        rebalance_options=rebalances,
        lookback_short_options=lookback_shorts,
        lookback_long_options=lookback_longs,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        min_fee=min_fee,
    )
    result = await run_in_threadpool(ResearchExperimentRunner().run_grid, config)
    backtest_repo = BacktestRepository()
    for trial in result.get("trials", []):
        backtest_result = trial.pop("backtest_result", None)
        if backtest_result:
            await backtest_repo.save_result(backtest_result)
    return await ResearchRepository().save_experiment(result)


@router.post("/experiments/run-qlib")
async def run_qlib_experiment(
    provider_uri: str | None = Query(None),
    experiment_name: str = Query("tradingagents_qlib_csi300"),
    initial_cash: float = Query(100_000_000, gt=0),
    top_n: int = Query(50, ge=1, le=200),
    n_drop: int = Query(5, ge=0, le=50),
    limit_threshold: float = Query(0.095, ge=0, le=0.30),
    open_cost: float = Query(0.0005, ge=0, le=0.02),
    close_cost: float = Query(0.0015, ge=0, le=0.05),
    min_fee: float = Query(5.0, ge=0, le=100),
    download_data: bool = Query(False),
    num_threads: int = Query(4, ge=1, le=16),
):
    config = QlibWorkflowConfig(
        provider_uri=provider_uri,
        experiment_name=experiment_name,
        initial_cash=initial_cash,
        top_n=top_n,
        n_drop=n_drop,
        limit_threshold=limit_threshold,
        open_cost=open_cost,
        close_cost=close_cost,
        min_fee=min_fee,
        download_data=download_data,
        num_threads=num_threads,
    )
    result = await run_in_threadpool(QlibWorkflowRunner().run_csi300_gbdt, config)
    return await ResearchRepository().save_experiment(result)


@router.get("/experiments")
async def list_experiments(
    market: str | None = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    return {
        "market": market,
        "experiments": await ResearchRepository().list_experiments(market=market, limit=limit),
    }


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    result = await ResearchRepository().get_experiment(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="策略实验不存在")
    return result


@router.get("/leaderboard")
async def leaderboard(
    market: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    return {
        "market": market,
        "items": await ResearchRepository().leaderboard(market=market, limit=limit),
    }


def _parse_int_list(value: str, minimum: int, maximum: int) -> list[int]:
    items: list[int] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = int(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"参数不是整数: {raw}") from exc
        if parsed < minimum or parsed > maximum:
            raise HTTPException(status_code=400, detail=f"参数超出范围: {raw}")
        if parsed not in items:
            items.append(parsed)
    if not items:
        raise HTTPException(status_code=400, detail="参数列表不能为空")
    return items
