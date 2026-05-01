"""全局配置，从环境变量 + .env 文件加载"""
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    llm_provider: str = "deepseek"
    deep_think_model: str = "deepseek-chat"
    quick_think_model: str = "deepseek-chat"

    # Data
    tushare_token: str = ""

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Trading defaults
    initial_capital: float = 1_000_000
    single_position_max_ratio: float = 0.2
    total_position_max_ratio: float = 0.8
    daily_stop_loss_ratio: float = 0.03

    # Database
    postgresql_url: str = "postgresql+asyncpg://trading:trading@localhost:5432/trading"
    clickhouse_url: str = "http://localhost:8123"
    clickhouse_database: str = "trading"

    # Paths — resolved relative to project root
    data_dir: str = str(PROJECT_ROOT / "data" / "cache")
    memory_dir: str = str(PROJECT_ROOT / "memory")

    # Scheduler
    pre_market_analysis_time: str = "08:00"
    market_open_time: str = "09:30"
    market_close_time: str = "15:00"

settings = Settings()
