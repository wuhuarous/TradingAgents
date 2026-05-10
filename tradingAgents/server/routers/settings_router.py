"""系统配置读写 — LLM 模型、风控参数、数据源"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from tradingAgents.config.settings import settings
from tradingAgents.server.models.stock import SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "runtime_config.json"


def _load_runtime() -> dict:
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_runtime(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_effective(key: str, default=None):
    """runtime config overrides env/settings defaults"""
    runtime = _load_runtime()
    if key in runtime and runtime[key] not in (None, ""):
        return runtime[key]
    return getattr(settings, key, default)


@router.get("/")
def get_settings():
    """返回当前生效的全部配置"""
    return {
        "llm": {
            "provider": _get_effective("llm_provider", "deepseek"),
            "deepseek_api_key": mask_key(_get_effective("deepseek_api_key", "")),
            "openai_api_key": mask_key(_get_effective("openai_api_key", "")),
            "anthropic_api_key": mask_key(_get_effective("anthropic_api_key", "")),
            "deep_think_model": _get_effective("deep_think_model", "deepseek-v4-pro"),
            "quick_think_model": _get_effective("quick_think_model", "deepseek-v4-flash"),
        },
        "trading": {
            "initial_capital": _get_effective("initial_capital", 1_000_000),
            "single_position_max_ratio": _get_effective("single_position_max_ratio", 0.2),
            "total_position_max_ratio": _get_effective("total_position_max_ratio", 0.8),
            "daily_stop_loss_ratio": _get_effective("daily_stop_loss_ratio", 0.03),
        },
        "data": {
            "tushare_token": mask_key(_get_effective("tushare_token", "")),
            "alpha_vantage_api_key": mask_key(_get_effective("alpha_vantage_api_key", "")),
            "finnhub_api_key": mask_key(_get_effective("finnhub_api_key", "")),
            "polygon_api_key": mask_key(_get_effective("polygon_api_key", "")),
            "newsapi_api_key": mask_key(_get_effective("newsapi_api_key", "")),
            "tavily_api_key": mask_key(_get_effective("tavily_api_key", "")),
            "preferred_market_data_source": _get_effective("preferred_market_data_source", "auto"),
            "preferred_news_source": _get_effective("preferred_news_source", "auto"),
            "market_data_status": {
                "auto": "active",
                "akshare": "partial",
                "yfinance": "active_for_hk_us",
                "tushare": "configured_only",
            },
            "news_source_status": {
                "auto": "active",
                "alpha_vantage": "active_when_key_configured",
                "finnhub": "active_when_key_configured",
                "polygon": "active_when_key_configured",
                "newsapi": "active_when_key_configured",
                "tavily": "active_when_key_configured",
            },
        },
        "database": {
            "postgresql_url": mask_dsn(_get_effective("postgresql_url", "")),
            "clickhouse_url": mask_dsn(_get_effective("clickhouse_url", "")),
            "clickhouse_database": _get_effective("clickhouse_database", "tradingagents"),
            "clickhouse_user": _get_effective("clickhouse_user", "default"),
            "clickhouse_password": mask_key(_get_effective("clickhouse_password", "")),
            "config_hint": "数据库连接已统一建议放在项目根目录 .env；不要提交真实账号密码。",
        },
    }


@router.put("/")
def update_settings(body: SettingsUpdate):
    """更新配置并持久化到 runtime_config.json"""
    runtime = _load_runtime()
    payload = body.model_dump(exclude_none=True)
    if "initial_capital" in payload and payload["initial_capital"] <= 0:
        raise HTTPException(status_code=400, detail="初始资金必须大于 0")

    for key, value in payload.items():
        if value is not None:
            if isinstance(value, str) and "*" in value and (
                key.endswith("_api_key") or key.endswith("_token")
            ):
                continue
            runtime[key] = value
            if hasattr(settings, key):
                setattr(settings, key, value)
    _save_runtime(runtime)

    account_apply = None
    if "initial_capital" in payload:
        try:
            from tradingAgents.data.database.account_repo import AccountRepository

            account_apply = _run_async(
                AccountRepository().apply_initial_capital_if_unstarted(float(payload["initial_capital"]))
            )
        except Exception as exc:
            account_apply = {"applied": False, "reason": "account_update_failed", "error": str(exc)}

    message = "配置已保存，当前服务已生效"
    if account_apply:
        if account_apply.get("applied"):
            message = "配置已保存，初始资金已同步到当前空模拟账户"
        else:
            message = "配置已保存；当前账户已有持仓或订单，初始资金将在下次清空/新账户时生效"
    return {"success": True, "message": message, "account": account_apply}


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]


def mask_dsn(value: str) -> str:
    if not value:
        return ""
    if "@" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0] + "://" if "://" in prefix else ""
    return f"{scheme}****@{suffix}"


def _run_async(coro):
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("settings sync route cannot update account inside a running event loop")
