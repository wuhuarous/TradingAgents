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
            "deep_think_model": _get_effective("deep_think_model", "deepseek-chat"),
            "quick_think_model": _get_effective("quick_think_model", "deepseek-chat"),
        },
        "trading": {
            "initial_capital": _get_effective("initial_capital", 1_000_000),
            "single_position_max_ratio": _get_effective("single_position_max_ratio", 0.2),
            "total_position_max_ratio": _get_effective("total_position_max_ratio", 0.8),
            "daily_stop_loss_ratio": _get_effective("daily_stop_loss_ratio", 0.03),
        },
        "data": {
            "tushare_token": mask_key(_get_effective("tushare_token", "")),
        },
    }


@router.put("/")
def update_settings(body: SettingsUpdate):
    """更新配置并持久化到 runtime_config.json"""
    runtime = _load_runtime()
    for key, value in body.model_dump(exclude_none=True).items():
        if value is not None:
            runtime[key] = value
    _save_runtime(runtime)
    return {"success": True, "message": "配置已保存，重启服务生效"}


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]
