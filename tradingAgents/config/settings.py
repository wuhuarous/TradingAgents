"""全局配置，从环境变量 + .env 文件加载"""
import json
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    llm_provider: str = "deepseek"
    deep_think_model: str = "deepseek-v4-pro"
    quick_think_model: str = "deepseek-v4-flash"

    # Data
    tushare_token: str = ""
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    polygon_api_key: str = ""
    newsapi_api_key: str = ""
    tavily_api_key: str = ""
    preferred_market_data_source: str = "auto"
    preferred_news_source: str = "auto"
    stock_universe_config: str = str(PROJECT_ROOT / "config" / "stock_universe.json")
    stock_universe_prefer_db: bool = True
    stock_universe_use_dynamic: bool = True

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Trading defaults
    initial_capital: float = 1_000_000
    single_position_max_ratio: float = 0.2
    total_position_max_ratio: float = 0.8
    daily_stop_loss_ratio: float = 0.03
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    transfer_fee_rate: float = 0.00001
    stamp_duty_rate: float = 0.0005
    a_share_t1_enabled: bool = True
    max_volume_participation_pct: float = 0.05

    # Database
    postgresql_url: str = ""
    clickhouse_url: str = ""
    clickhouse_database: str = "tradingagents"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # Paths — resolved relative to project root
    data_dir: str = str(PROJECT_ROOT / "data" / "cache")
    memory_dir: str = str(PROJECT_ROOT / "memory")

    # Scheduler
    pre_market_analysis_time: str = "08:00"
    market_open_time: str = "09:30"
    market_close_time: str = "15:00"
    scheduler_live_data_enabled: bool = False
    auto_simulation_enabled: bool = True
    auto_simulation_market: str = "a_stock"
    full_market_deep_scan_limit: int = 32

settings = Settings()

DATABASE_ENV_KEYS = {
    "postgresql_url",
    "clickhouse_url",
    "clickhouse_database",
    "clickhouse_user",
    "clickhouse_password",
}


def apply_file_overrides() -> None:
    """Apply optional local JSON config values without committing secrets."""
    for path in (
        PROJECT_ROOT / "settings.json",
        PROJECT_ROOT / "config" / "settings.local.json",
    ):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        overrides = _flatten_config(data)
        for key in DATABASE_ENV_KEYS:
            overrides.pop(key, None)
        _apply_overrides(overrides)


def apply_runtime_overrides() -> None:
    """Apply persisted runtime_config.json values to the in-process settings."""
    runtime_path = PROJECT_ROOT / "config" / "runtime_config.json"
    if not runtime_path.exists():
        return
    try:
        data = json.loads(runtime_path.read_text(encoding="utf-8"))
    except Exception:
        return
    for key in DATABASE_ENV_KEYS:
        data.pop(key, None)
    _apply_overrides(data)


def _flatten_config(data: dict) -> dict:
    flattened = dict(data)
    for section in ("database", "llm", "data", "trading", "server", "scheduler"):
        value = flattened.pop(section, None)
        if isinstance(value, dict):
            flattened.update(value)
    return flattened


def _apply_overrides(data: dict) -> None:
    for key, value in data.items():
        if isinstance(value, str) and "*" in value and (
            key.endswith("_api_key") or key.endswith("_token")
        ):
            continue
        if value not in (None, "") and hasattr(settings, key):
            setattr(settings, key, value)


apply_file_overrides()
apply_runtime_overrides()
