"""数据供应商注册表 — 按市场+数据类型映射免费数据源"""
from typing import Dict, Literal

DataSourceType = Literal["realtime", "historical", "financials", "news"]

VENDOR_REGISTRY: Dict[str, Dict[DataSourceType, str]] = {
    "a_stock": {
        "realtime": "akshare",
        "historical": "akshare",
        "financials": "akshare",
        "news": "akshare",
    },
    "hk_stock": {
        "realtime": "yfinance",
        "historical": "yfinance",
        "financials": "yfinance",
        "news": "yfinance",
    },
    "us_stock": {
        "realtime": "yfinance",
        "historical": "yfinance",
        "financials": "yfinance",
        "news": "yfinance",
    },
}
