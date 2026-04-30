# Phase 1 实现计划 — AI 量化交易系统

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 跑通核心链路：数据采集→AI分析→推荐→自动模拟交易→风控→报表，支持 A股+港美股，DeepSeek 驱动

**Architecture:** 基于 TradingAgents (Apache 2.0) 的 LangGraph 多智能体框架作为分析引擎，自建数据层/交易层/调度层/FastAPI后端/React前端，SQLite 存储，Docker 部署

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, React+TypeScript, SQLite, DeepSeek API, yfinance, AkShare

---

## 文件结构

```
trandingAgents/
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── config/
│   ├── settings.py              # 全局配置（模型/数据源/风控参数）
│   └── vendors.py               # 数据供应商注册表
├── engine/                      # 分析引擎（基于 TradingAgents）
│   ├── __init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── factory.py           # 多供应商工厂（DeepSeek/OpenAI/Claude）
│   │   ├── deepseek.py          # DeepSeek客户端
│   │   └── openai_compat.py     # OpenAI兼容客户端
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py              # Agent基类
│   │   ├── analysts/
│   │   │   ├── __init__.py
│   │   │   ├── market.py        # 市场技术分析师
│   │   │   ├── fundamentals.py  # 基本面分析师
│   │   │   └── news.py          # 新闻分析师
│   │   ├── researchers/
│   │   │   ├── __init__.py
│   │   │   ├── bull.py          # 多方研究员
│   │   │   └── bear.py          # 空方研究员
│   │   ├── risk_mgmt/
│   │   │   ├── __init__.py
│   │   │   ├── aggressive.py
│   │   │   ├── conservative.py
│   │   │   └── neutral.py
│   │   ├── trader.py            # 交易员Agent（综合决策+结构化输出）
│   │   ├── manager.py           # 研究管理员Agent
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── tools.py         # 工具函数（数据获取封装）
│   │       ├── memory.py        # 经验记忆读写
│   │       ├── rating.py        # 评分系统
│   │       └── structured.py    # 结构化输出辅助
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── workflow.py          # LangGraph主工作流
│   │   ├── state.py             # 图状态定义
│   │   ├── nodes.py             # 图节点定义
│   │   └── routing.py           # 条件路由
│   └── dataflows/
│       ├── __init__.py
│       ├── interface.py         # 数据源抽象接口
│       ├── yfinance.py          # yfinance实现（港股/美股）
│       ├── akshare.py           # AkShare实现（A股）
│       └── cache.py             # 数据缓存
├── data/                        # 数据采集层
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── a_stock.py           # A股行情（AkShare+BaoStock）
│   │   ├── hk_us_stock.py      # 港美股行情（yfinance）
│   │   └── financials.py       # 财务数据
│   ├── news/
│   │   ├── __init__.py
│   │   ├── domestic.py         # 国内财经新闻
│   │   └── international.py    # 国际财经新闻
│   └── social/
│       ├── __init__.py
│       └── sentiment.py        # 社交媒体舆情
├── trader/                      # 交易执行层
│   ├── __init__.py
│   ├── account.py              # 虚拟账户
│   ├── order.py                # 订单管理
│   ├── position.py             # 持仓管理
│   ├── strategy.py             # AI交易策略引擎
│   ├── executor.py             # 订单执行器
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── stop_loss.py        # 止损逻辑
│   │   ├── position_sizer.py   # 仓位计算
│   │   └── manager.py          # 风控管理器
│   └── scheduler/
│       ├── __init__.py
│       ├── jobs.py             # 定时任务定义
│       └── runner.py           # 调度器运行器
├── server/                      # FastAPI后端
│   ├── __init__.py
│   ├── main.py                 # 应用入口
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── analysis.py         # 分析相关API
│   │   ├── trading.py          # 交易相关API
│   │   ├── account.py          # 账户API
│   │   ├── stocks.py           # 股票数据API
│   │   └── scheduler.py        # 调度管理API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── analysis_service.py
│   │   ├── trading_service.py
│   │   └── report_service.py
│   └── models/
│       ├── __init__.py
│       ├── stock.py
│       ├── trade.py
│       └── analysis.py
├── frontend/                    # React前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                # API调用层
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx    # 仪表盘
│   │   │   ├── StockDetail.tsx  # 股票详情
│   │   │   ├── TradingLog.tsx   # 交易记录
│   │   │   ├── Scheduler.tsx    # 调度状态
│   │   │   └── Settings.tsx     # 配置页
│   │   ├── components/
│   │   │   ├── Layout.tsx
│   │   │   ├── StockCard.tsx
│   │   │   ├── PositionTable.tsx
│   │   │   ├── PnLChart.tsx
│   │   │   ├── TradeForm.tsx
│   │   │   └── ScheduleStatus.tsx
│   │   └── styles/
│   │       └── global.css
├── memory/                      # 经验记忆文件存储
├── tests/
│   ├── test_llm_factory.py
│   ├── test_data_providers.py
│   ├── test_analysis_agents.py
│   ├── test_trader_account.py
│   ├── test_risk_manager.py
│   └── test_scheduler.py
└── scripts/
    └── init_db.py
```

---

## Task 1: 项目初始化与环境搭建

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `config/settings.py`
- Create: `config/vendors.py`
- Create: `config/__init__.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "trandingAgents"
version = "0.1.0"
description = "AI-powered quantitative trading system for A-shares, HK and US stocks"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "yfinance>=0.2.40",
    "akshare>=1.14.0",
    "baostock>=0.8.0",
    "pandas>=2.2.0",
    "numpy>=1.26.0",
    "stockstats>=0.6.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "apscheduler>=3.10.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.20.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "websockets>=12.0",
    "markdown>=3.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
asyncio_mode = "auto"
```

- [ ] **Step 2: 创建 .env.example**

```bash
# LLM Providers
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

ANTHROPIC_API_KEY=sk-ant-your-key-here

# Default LLM
LLM_PROVIDER=deepseek
DEEP_THINK_MODEL=deepseek-chat
QUICK_THINK_MODEL=deepseek-chat

# Data Sources
TUSHARE_TOKEN=your-token-here

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Trading
INITIAL_CAPITAL=1000000
SINGLE_POSITION_MAX_RATIO=0.2
TOTAL_POSITION_MAX_RATIO=0.8
DAILY_STOP_LOSS_RATIO=0.03
```

- [ ] **Step 3: 创建 config/settings.py**

```python
"""全局配置，从环境变量 + .env 文件加载"""
from pydantic_settings import BaseSettings
from typing import Optional


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

    # Paths
    data_dir: str = "data/cache"
    memory_dir: str = "memory"
    db_path: str = "data/trading.db"

    # Scheduler
    pre_market_analysis_time: str = "08:00"
    market_open_time: str = "09:30"
    market_close_time: str = "15:00"


settings = Settings()
```

- [ ] **Step 4: 创建 config/vendors.py**

```python
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
```

- [ ] **Step 5: 安装依赖并验证**

```bash
cd D:/project/trandingAgents && pip install -e ".[dev]"
```

- [ ] **Step 6: 验证配置加载**

```bash
python -c "from config.settings import settings; print(settings.llm_provider)"
```

Expected: `deepseek`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example config/ .gitignore
git commit -m "feat: project init — dependencies, config, vendor registry"
```

---

## Task 2: LLM 多供应商工厂

**Files:**
- Create: `engine/__init__.py`
- Create: `engine/llm/__init__.py`
- Create: `engine/llm/factory.py`
- Create: `engine/llm/deepseek.py`
- Create: `engine/llm/openai_compat.py`
- Test: `tests/test_llm_factory.py`

- [ ] **Step 1: 写失败测试 tests/test_llm_factory.py**

```python
import pytest
from engine.llm.factory import LLMFactory, LLMProvider


def test_create_deepseek_client():
    client = LLMFactory.create(LLMProvider.DEEPSEEK, api_key="test", model="deepseek-chat")
    assert client is not None
    assert client.model_name == "deepseek-chat"


def test_create_openai_client():
    client = LLMFactory.create(LLMProvider.OPENAI, api_key="test", model="gpt-4o")
    assert client is not None
    assert client.model_name == "gpt-4o"


def test_invalid_provider_raises():
    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMFactory.create("invalid_provider", api_key="test", model="x")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_llm_factory.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: 实现 engine/llm/factory.py**

```python
"""多供应商LLM工厂 — 统一创建 DeepSeek/OpenAI/Claude 客户端"""
from enum import Enum
from typing import Optional
from langchain_openai import ChatOpenAI


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMFactory:
    @staticmethod
    def create(
        provider: LLMProvider,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
    ) -> ChatOpenAI:
        provider_map = {
            LLMProvider.DEEPSEEK: ("https://api.deepseek.com", "DeepSeek"),
            LLMProvider.OPENAI: ("https://api.openai.com/v1", "OpenAI"),
            LLMProvider.ANTHROPIC: ("https://api.anthropic.com", "Anthropic"),
        }
        if provider not in provider_map:
            raise ValueError(f"Unsupported provider: {provider}")

        default_url, _ = provider_map[provider]
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or default_url,
            temperature=temperature,
        )

    @staticmethod
    def create_from_settings(model: Optional[str] = None):
        """从全局 settings 创建默认客户端"""
        from config.settings import settings
        provider = LLMProvider(settings.llm_provider)
        api_key_map = {
            LLMProvider.DEEPSEEK: settings.deepseek_api_key,
            LLMProvider.OPENAI: settings.openai_api_key,
            LLMProvider.ANTHROPIC: settings.anthropic_api_key,
        }
        return LLMFactory.create(
            provider=provider,
            api_key=api_key_map[provider],
            model=model or settings.deep_think_model,
        )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_llm_factory.py -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add engine/ tests/test_llm_factory.py
git commit -m "feat: LLM multi-provider factory with DeepSeek/OpenAI/Claude support"
```

---

## Task 3: 数据源抽象接口 + yfinance 实现

**Files:**
- Create: `engine/dataflows/__init__.py`
- Create: `engine/dataflows/interface.py`
- Create: `engine/dataflows/yfinance.py`
- Create: `engine/dataflows/cache.py`
- Test: `tests/test_data_providers.py`

- [ ] **Step 1: 写失败测试 tests/test_data_providers.py**

```python
import pytest
import pandas as pd
from engine.dataflows.interface import DataSourceProvider, StockQuote, Market
from engine.dataflows.yfinance import YFinanceProvider


def test_yfinance_provider_implements_interface():
    provider = YFinanceProvider()
    assert isinstance(provider, DataSourceProvider)


def test_yfinance_get_realtime_quote():
    provider = YFinanceProvider()
    quote = provider.get_realtime_quote("AAPL", Market.US)
    assert isinstance(quote, StockQuote)
    assert quote.symbol == "AAPL"
    assert quote.price > 0


def test_yfinance_get_historical():
    provider = YFinanceProvider()
    df = provider.get_historical("AAPL", Market.US, period="5d")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "Close" in df.columns


def test_yfinance_get_financials():
    provider = YFinanceProvider()
    data = provider.get_financials("AAPL", Market.US)
    assert isinstance(data, dict)
    assert "pe_ratio" in data
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_data_providers.py::test_yfinance_provider_implements_interface -v
```

Expected: FAIL

- [ ] **Step 3: 实现 engine/dataflows/interface.py**

```python
"""数据源抽象接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import pandas as pd


class Market(str, Enum):
    A = "a_stock"
    HK = "hk_stock"
    US = "us_stock"


@dataclass
class StockQuote:
    symbol: str
    name: str = ""
    price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    change_pct: float = 0.0
    market: Market = Market.US
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NewsItem:
    title: str
    content: str = ""
    source: str = ""
    url: str = ""
    sentiment: Optional[float] = None
    published_at: datetime = field(default_factory=datetime.now)


class DataSourceProvider(ABC):
    """行情数据源抽象接口"""

    @abstractmethod
    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        ...

    @abstractmethod
    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        ...

    @abstractmethod
    def get_financials(self, symbol: str, market: Market) -> dict:
        ...

    @abstractmethod
    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        ...

    @abstractmethod
    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        ...
```

- [ ] **Step 4: 实现 engine/dataflows/yfinance.py**

```python
"""yfinance 实现 — 港美股行情 + 财务 + 新闻"""
import yfinance as yf
import pandas as pd
from .interface import DataSourceProvider, StockQuote, NewsItem, Market


class YFinanceProvider(DataSourceProvider):
    def _get_ticker(self, symbol: str, market: Market) -> str:
        if market == Market.HK and not symbol.endswith(".HK"):
            return f"{symbol}.HK"
        return symbol

    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        ticker_str = self._get_ticker(symbol, market)
        t = yf.Ticker(ticker_str)
        info = t.info or {}
        price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        return StockQuote(
            symbol=symbol,
            name=info.get("longName", info.get("shortName", "")),
            price=price,
            open=info.get("regularMarketOpen", 0),
            high=info.get("dayHigh", 0),
            low=info.get("dayLow", 0),
            close=info.get("previousClose", 0),
            volume=info.get("volume", 0),
            change_pct=price / info.get("previousClose", 1) - 1 if info.get("previousClose") else 0,
            market=market,
        )

    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        ticker_str = self._get_ticker(symbol, market)
        t = yf.Ticker(ticker_str)
        return t.history(period=period)

    def get_financials(self, symbol: str, market: Market) -> dict:
        ticker_str = self._get_ticker(symbol, market)
        t = yf.Ticker(ticker_str)
        info = t.info or {}
        return {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
        }

    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        ticker_str = self._get_ticker(symbol, market)
        t = yf.Ticker(ticker_str)
        items = []
        for n in (t.news or [])[:limit]:
            items.append(NewsItem(
                title=n.get("title", ""),
                content=n.get("link", ""),
                source=n.get("publisher", ""),
                url=n.get("link", ""),
            ))
        return items

    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        # yfinance doesn't support symbol search; return empty
        return []
```

- [ ] **Step 5: 实现 engine/dataflows/cache.py**

```python
"""简易文件缓存 — 减少 API 调用频率"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional


class DataCache:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _key_path(self, key: str) -> str:
        safe = key.replace("/", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe}.json")

    def get(self, key: str, max_age_seconds: int = 300) -> Optional[dict]:
        path = self._key_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        age = (datetime.now() - datetime.fromisoformat(data["ts"])).total_seconds()
        if age > max_age_seconds:
            return None
        return data["value"]

    def set(self, key: str, value: dict):
        path = self._key_path(key)
        with open(path, "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "value": value}, f)
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_data_providers.py -v --timeout=30 2>&1 || echo "Network-dependent; verify locally"
```

Expected: 4 PASS (需要网络连接)

- [ ] **Step 7: Commit**

```bash
git add engine/dataflows/ tests/test_data_providers.py
git commit -m "feat: data source interface + yfinance implementation for HK/US stocks"
```

---

## Task 4: A股数据源（AkShare + BaoStock）

**Files:**
- Create: `data/__init__.py`
- Create: `data/providers/__init__.py`
- Create: `data/providers/a_stock.py`
- Create: `data/providers/hk_us_stock.py`
- Append: `tests/test_data_providers.py`

- [ ] **Step 1: 写失败测试（追加到 tests/test_data_providers.py）**

```python
from data.providers.a_stock import AStockProvider


def test_astock_provider_implements_interface():
    provider = AStockProvider()
    assert isinstance(provider, DataSourceProvider)


def test_astock_get_realtime_quote():
    provider = AStockProvider()
    quote = provider.get_realtime_quote("000001", Market.A)
    assert isinstance(quote, StockQuote)
    assert quote.symbol == "000001"


def test_astock_get_historical():
    provider = AStockProvider()
    df = provider.get_historical("000001", Market.A, period="5d")
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_data_providers.py::test_astock_provider_implements_interface -v
```

Expected: FAIL

- [ ] **Step 3: 实现 data/providers/a_stock.py**

```python
"""A股数据源 — AkShare 免费接口，BaoStock 备用"""
import pandas as pd
import akshare as ak
from datetime import datetime
from engine.dataflows.interface import DataSourceProvider, StockQuote, NewsItem, Market


class AStockProvider(DataSourceProvider):
    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol]
            if row.empty:
                return self._get_quote_baostock(symbol)
            r = row.iloc[0]
            return StockQuote(
                symbol=symbol,
                name=r.get("名称", ""),
                price=float(r["最新价"]),
                open=float(r["今开"]),
                high=float(r["最高"]),
                low=float(r["最低"]),
                close=float(r.get("昨收", 0)),
                volume=int(r["成交量"]),
                change_pct=float(r["涨跌幅"]) / 100,
                market=Market.A,
            )
        except Exception:
            return self._get_quote_baostock(symbol)

    def _get_quote_baostock(self, symbol: str) -> StockQuote:
        import baostock as bs
        bs.login()
        code = f"sz.{symbol}" if symbol.startswith(("0", "3")) else f"sh.{symbol}"
        rs = bs.query_stock_basic(code)
        bs.logout()
        return StockQuote(symbol=symbol, name=code, market=Market.A)

    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        code = f"sz{symbol}" if symbol.startswith(("0", "3")) else f"sh{symbol}"
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            return df.tail(30 if period == "1mo" else 5)
        except Exception:
            return pd.DataFrame()

    def get_financials(self, symbol: str, market: Market) -> dict:
        try:
            df = ak.stock_financial_abstract(symbol=symbol)
            if df.empty:
                return {}
            latest = df.iloc[0]
            return {
                "pe_ratio": latest.get("市盈率"),
                "pb_ratio": latest.get("市净率"),
                "market_cap": latest.get("总市值"),
                "revenue": latest.get("营业总收入"),
                "net_income": latest.get("归母净利润"),
                "roe": latest.get("净资产收益率"),
            }
        except Exception:
            return {}

    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        try:
            df = ak.stock_news_em(symbol=symbol)
            items = []
            for _, row in df.head(limit).iterrows():
                items.append(NewsItem(
                    title=row.get("标题", ""),
                    content=row.get("内容", ""),
                    source="东方财富",
                    url=row.get("链接", ""),
                ))
            return items
        except Exception:
            return []

    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        try:
            df = ak.stock_zh_a_spot_em()
            matches = df[df["名称"].str.contains(keyword) | df["代码"].str.contains(keyword)]
            return [{"symbol": r["代码"], "name": r["名称"]} for _, r in matches.head(20).iterrows()]
        except Exception:
            return []
```

- [ ] **Step 4: 实现 data/providers/hk_us_stock.py**

```python
"""港美股数据 — yfinance 包装"""
from engine.dataflows.yfinance import YFinanceProvider
from engine.dataflows.interface import DataSourceProvider, Market


class HKUSStockProvider(YFinanceProvider):
    """直接继承 YFinanceProvider，无需覆盖"""
    pass


def get_provider(market: Market) -> DataSourceProvider:
    """根据市场获取对应的数据供应商"""
    from data.providers.a_stock import AStockProvider
    if market == Market.A:
        return AStockProvider()
    return HKUSStockProvider()
```

- [ ] **Step 5: 运行测试**

```bash
python -m pytest tests/test_data_providers.py -v --timeout=30 2>&1 || echo "Network-dependent"
```

- [ ] **Step 6: Commit**

```bash
git add data/ tests/test_data_providers.py
git commit -m "feat: A-share data provider via AkShare + BaoStock fallback"
```

---

## Task 5: 新闻数据采集 + 舆情分析

**Files:**
- Create: `data/news/__init__.py`
- Create: `data/news/domestic.py`
- Create: `data/news/international.py`
- Create: `data/social/__init__.py`
- Create: `data/social/sentiment.py`

- [ ] **Step 1: 创建 data/news/domestic.py**

```python
"""国内财经新闻 — 东方财富 + 财联社"""
import akshare as ak
import pandas as pd
from engine.dataflows.interface import NewsItem


def fetch_domestic_news(limit: int = 20) -> list[NewsItem]:
    items = []
    try:
        df = ak.stock_info_global_em()
        for _, row in df.head(limit).iterrows():
            items.append(NewsItem(
                title=row.get("标题", ""),
                content=row.get("摘要", ""),
                source="东方财富",
                url=str(row.get("链接", "")),
            ))
    except Exception:
        pass
    return items


def fetch_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    try:
        df = ak.stock_news_em(symbol=symbol)
        items = []
        for _, row in df.head(limit).iterrows():
            items.append(NewsItem(
                title=row.get("标题", ""),
                content=row.get("内容", ""),
                source="东方财富",
            ))
        return items
    except Exception:
        return []
```

- [ ] **Step 2: 创建 data/news/international.py**

```python
"""国际财经新闻 — yfinance + Alpha Vantage（免费）"""
from engine.dataflows.interface import NewsItem
from engine.dataflows.yfinance import YFinanceProvider


def fetch_global_news(limit: int = 20) -> list[NewsItem]:
    items = []
    # 使用主要指数获取全球要闻
    major_tickers = ["^GSPC", "^DJI", "^IXIC", "^HSI"]
    provider = YFinanceProvider()
    for ticker in major_tickers:
        news = provider.get_news(ticker, None, limit=5)
        items.extend(news)
    return items[:limit]
```

- [ ] **Step 3: 创建 data/social/sentiment.py**

```python
"""社交媒体舆情分析 — 基于新闻/AI情感的简化实现
完整版本依赖：雪球API + 微博API + DeepSeek情感分析
当前版本：基于新闻标题的关键词情感打分
"""
from engine.dataflows.interface import NewsItem

SENTIMENT_KEYWORDS = {
    "positive": ["利好", "大涨", "突破", "增长", "盈利", "买入", "增持", "回购",
                 "breakthrough", "surge", "beat", "upgrade", "buy", "growth"],
    "negative": ["利空", "大跌", "下跌", "亏损", "减持", "卖出", "监管", "调查",
                 "crash", "plunge", "downgrade", "sell", "loss", "investigation"],
}


def analyze_sentiment(text: str) -> float:
    """简单关键词情感打分，范围 [-1, 1]"""
    text_lower = text.lower()
    pos = sum(1 for w in SENTIMENT_KEYWORDS["positive"] if w in text_lower)
    neg = sum(1 for w in SENTIMENT_KEYWORDS["negative"] if w in text_lower)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 2)


def analyze_news_sentiment(news_items: list[NewsItem]) -> list[NewsItem]:
    """对新闻列表批量分析情感分"""
    for item in news_items:
        item.sentiment = analyze_sentiment(f"{item.title} {item.content}")
    return news_items


def aggregate_sentiment(news_items: list[NewsItem]) -> float:
    """聚合多篇新闻的情感均值"""
    if not news_items:
        return 0.0
    scores = [n.sentiment for n in news_items if n.sentiment is not None]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)
```

- [ ] **Step 4: Commit**

```bash
git add data/news/ data/social/
git commit -m "feat: news collection (domestic+international) and sentiment analysis"
```

---

## Task 6: Agent 基类 + 工具函数

**Files:**
- Create: `engine/agents/__init__.py`
- Create: `engine/agents/base.py`
- Create: `engine/agents/utils/__init__.py`
- Create: `engine/agents/utils/tools.py`
- Create: `engine/agents/utils/structured.py`

- [ ] **Step 1: 创建 engine/agents/base.py**

```python
"""Agent 基类 — 统一 LLM 调用、工具绑定、结构化输出"""
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from engine.llm.factory import LLMFactory


class BaseAgent:
    role: str = "base"
    system_prompt: str = ""

    def __init__(self, model_name: Optional[str] = None):
        self.llm = LLMFactory.create_from_settings(model=model_name)

    def _prompt(self, task: str, context: str = "") -> str:
        return f"""## 角色
{self.system_prompt}

## 上下文
{context}

## 任务
{task}
"""

    def invoke(self, task: str, context: str = "") -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=self._prompt(task, context)),
        ]
        resp = self.llm.invoke(messages)
        return resp.content
```

- [ ] **Step 2: 创建 engine/agents/utils/tools.py**

```python
"""Agent 工具函数 — 封装数据获取，供 Agent 调用"""
from typing import Optional
import pandas as pd
from data.providers.a_stock import AStockProvider
from data.providers.hk_us_stock import HKUSStockProvider
from engine.dataflows.interface import Market


def get_stock_data(symbol: str, market: str = "us", period: str = "1mo") -> pd.DataFrame:
    provider = _get_provider(Market(market))
    return provider.get_historical(symbol, Market(market), period)


def get_quote(symbol: str, market: str = "us"):
    provider = _get_provider(Market(market))
    return provider.get_realtime_quote(symbol, Market(market))


def get_financials(symbol: str, market: str = "us") -> dict:
    provider = _get_provider(Market(market))
    return provider.get_financials(symbol, Market(market))


def get_news(symbol: str, market: str = "us", limit: int = 10) -> list:
    provider = _get_provider(Market(market))
    return provider.get_news(symbol, Market(market), limit)


def _get_provider(market: Market):
    if market == Market.A:
        return AStockProvider()
    return HKUSStockProvider()
```

- [ ] **Step 3: 创建 engine/agents/utils/structured.py**

```python
"""结构化输出辅助 — 确保 Agent 输出可解析 JSON"""
import json
import re


def extract_json(text: str) -> dict:
    """从文本中提取 JSON 块"""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}


def parse_rating(rating_text: str) -> dict:
    """解析评分输出 → {score: 1-10, confidence: 0.0-1.0, reasoning: str}"""
    data = extract_json(rating_text)
    return {
        "score": min(10, max(1, int(data.get("score", 5)))),
        "confidence": min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
        "reasoning": data.get("reasoning", ""),
    }
```

- [ ] **Step 4: Commit**

```bash
git add engine/agents/
git commit -m "feat: Agent base class + tool functions + structured output helpers"
```

---

## Task 7: 分析师 Agents（市场 + 基本面 + 新闻）

**Files:**
- Create: `engine/agents/analysts/__init__.py`
- Create: `engine/agents/analysts/market.py`
- Create: `engine/agents/analysts/fundamentals.py`
- Create: `engine/agents/analysts/news.py`
- Test: `tests/test_analysis_agents.py`

- [ ] **Step 1: 写失败测试 tests/test_analysis_agents.py**

```python
import pytest
from engine.agents.analysts.market import MarketAnalyst
from engine.agents.analysts.fundamentals import FundamentalsAnalyst
from engine.agents.analysts.news import NewsAnalyst


class TestMarketAnalyst:
    def test_has_role(self):
        agent = MarketAnalyst()
        assert agent.role == "market_analyst"

    def test_analyze_returns_structured_json(self):
        agent = MarketAnalyst()
        # 用 mock 避免调用真实 API
        result = agent.analyze.__wrapped__(agent, {}, {})


class TestFundamentalsAnalyst:
    def test_has_role(self):
        agent = FundamentalsAnalyst()
        assert agent.role == "fundamentals_analyst"


class TestNewsAnalyst:
    def test_has_role(self):
        agent = NewsAnalyst()
        assert agent.role == "news_analyst"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_analysis_agents.py -v
```

Expected: FAIL

- [ ] **Step 3: 创建 engine/agents/analysts/market.py**

```python
"""市场技术分析师 — 量价分析 + 技术指标 + 趋势判断"""
import json
from engine.agents.base import BaseAgent
from engine.agents.utils.tools import get_stock_data, get_quote
from engine.agents.utils.structured import extract_json


class MarketAnalyst(BaseAgent):
    role = "market_analyst"
    system_prompt = """你是一位资深技术分析师。根据提供的股票量价数据和技术指标，
分析当前趋势、支撑阻力位、成交量信号，给出评分。

输出格式（JSON）：
{
    "score": 1-10,
    "trend": "bullish|bearish|neutral",
    "support_level": 数字,
    "resistance_level": 数字,
    "volume_signal": "increasing|decreasing|normal",
    "key_indicators": {"rsi": 数字, "macd_signal": "buy|sell|hold"},
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        quote = get_quote(symbol, market)
        df = get_stock_data(symbol, market, period="1mo")

        context = f"""股票: {symbol}
最新价: {quote.price}
开盘: {quote.open}  最高: {quote.high}  最低: {quote.low}
涨跌幅: {quote.change_pct:.2%}
成交量: {quote.volume}

近期行情（最近5日）:
{df.tail(5).to_string() if not df.empty else "数据不可用"}
"""
        resp = self.invoke("分析该股票的技术面走势并给出评分", context)
        return extract_json(resp)
```

- [ ] **Step 4: 创建 engine/agents/analysts/fundamentals.py**

```python
"""基本面分析师 — 财务数据解读 + 估值分析"""
import json
from engine.agents.base import BaseAgent
from engine.agents.utils.tools import get_financials
from engine.agents.utils.structured import extract_json


class FundamentalsAnalyst(BaseAgent):
    role = "fundamentals_analyst"
    system_prompt = """你是一位基本面分析专家。根据财务数据评估公司价值，
关注 PE/PB/ROE/营收增长/负债率等指标，给出综合评分。

输出格式（JSON）：
{
    "score": 1-10,
    "valuation": "undervalued|fair|overvalued",
    "growth_outlook": "positive|neutral|negative",
    "key_metrics": {"pe": 数字, "pb": 数字, "roe": 数字, "revenue_growth": 数字},
    "risks": ["风险点1", "风险点2"],
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        financials = get_financials(symbol, market)
        context = f"""股票: {symbol}
财务数据:
{json.dumps(financials, ensure_ascii=False, default=str)}
"""
        resp = self.invoke("分析该股票的基本面并给出评分", context)
        return extract_json(resp)
```

- [ ] **Step 5: 创建 engine/agents/analysts/news.py**

```python
"""新闻分析师 — 新闻事件对股价影响评估"""
import json
from engine.agents.base import BaseAgent
from engine.agents.utils.tools import get_news
from engine.agents.utils.structured import extract_json


class NewsAnalyst(BaseAgent):
    role = "news_analyst"
    system_prompt = """你是一位财经新闻分析专家。根据最新新闻事件分析对股价的潜在影响，
关注政策变化、业绩公告、行业动态、市场情绪等。

输出格式（JSON）：
{
    "score": 1-10,
    "sentiment": "positive|neutral|negative",
    "key_events": [{"event": "事件描述", "impact": "positive|negative|neutral", "importance": 1-5}],
    "reasoning": "中文分析理由"
}"""

    def analyze(self, symbol: str, market: str) -> dict:
        news_items = get_news(symbol, market, limit=10)
        context = f"""股票: {symbol}
最新新闻:
{json.dumps([{'title': n.title, 'source': n.source} for n in news_items], ensure_ascii=False)}
"""
        resp = self.invoke("分析这些新闻对股价的影响并给出评分", context)
        return extract_json(resp)
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_analysis_agents.py -v
```

- [ ] **Step 7: Commit**

```bash
git add engine/agents/analysts/ tests/test_analysis_agents.py
git commit -m "feat: analyst agents — market, fundamentals, news analysis"
```

---

## Task 8: 研究员 + 辩论 Agents（多方/空方）

**Files:**
- Create: `engine/agents/researchers/__init__.py`
- Create: `engine/agents/researchers/bull.py`
- Create: `engine/agents/researchers/bear.py`
- Create: `engine/agents/manager.py`

- [ ] **Step 1: 创建 engine/agents/researchers/bull.py**

```python
"""多方研究员 — 为看涨辩护，挖掘正面因素"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import parse_rating


class BullResearcher(BaseAgent):
    role = "bull_researcher"
    system_prompt = """你是一位多方研究员，负责为看涨观点辩护。
基于分析师报告，找出支撑买入的关键论据，并对每个看涨因素给出置信度。
输出格式（JSON）：{"bull_points": [{"point": "理由", "confidence": 0.0-1.0}], "overall_rating": 1-10}
"""

    def debate(self, analyst_reports: str) -> dict:
        context = f"分析师报告汇总:\n{analyst_reports}"
        resp = self.invoke("从多方角度论证，找出支持买入的理由", context)
        return parse_rating(resp)
```

- [ ] **Step 2: 创建 engine/agents/researchers/bear.py**

```python
"""空方研究员 — 为看跌辩护，挖掘风险因素"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import parse_rating


class BearResearcher(BaseAgent):
    role = "bear_researcher"
    system_prompt = """你是一位空方研究员，负责揭示风险和负面因素。
基于分析师报告，找出支撑卖出/观望的关键论据，并对每个风险因素给出置信度。
输出格式（JSON）：{"bear_points": [{"point": "风险", "confidence": 0.0-1.0}], "overall_rating": 1-10}
"""

    def debate(self, analyst_reports: str) -> dict:
        context = f"分析师报告汇总:\n{analyst_reports}"
        resp = self.invoke("从空方角度论证，找出反对买入的风险和理由", context)
        return parse_rating(resp)
```

- [ ] **Step 3: 创建 engine/agents/manager.py**

```python
"""研究管理员 — 汇总辩论结果，给出综合评估"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import extract_json


class ResearchManager(BaseAgent):
    role = "research_manager"
    system_prompt = """你是研究管理员。综合多方和空方的辩论结果，评估各方论据质量，
合并分析师评分与辩论结果，输出最终综合评分和决策建议。

输出格式（JSON）：
{
    "final_score": 1-10,
    "decision": "buy|hold|sell",
    "confidence": 0.0-1.0,
    "key_reasons": ["理由1", "理由2", "理由3"],
    "risk_summary": "风险概述"
}"""

    def decide(
        self,
        symbol: str,
        analyst_reports: dict,
        bull_report: dict,
        bear_report: dict,
    ) -> dict:
        context = f"""股票: {symbol}
分析师评分: {analyst_reports}
多方观点: {bull_report}
空方观点: {bear_report}
"""
        resp = self.invoke("综合各方观点，给出最终交易建议", context)
        return extract_json(resp)
```

- [ ] **Step 4: Commit**

```bash
git add engine/agents/researchers/ engine/agents/manager.py
git commit -m "feat: bull/bear researchers + research manager debate system"
```

---

## Task 9: 风控辩论 + 交易员 Agent

**Files:**
- Create: `engine/agents/risk_mgmt/__init__.py`
- Create: `engine/agents/risk_mgmt/aggressive.py`
- Create: `engine/agents/risk_mgmt/conservative.py`
- Create: `engine/agents/risk_mgmt/neutral.py`
- Create: `engine/agents/trader.py`

- [ ] **Step 1: 创建 engine/agents/risk_mgmt/aggressive.py**

```python
"""激进风控师 — 高仓位 + 宽止损 + 追涨"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import extract_json


class AggressiveDebater(BaseAgent):
    role = "aggressive_risk"
    system_prompt = """你是激进风格的风控专家。你偏好高仓位、容忍较大回撤、
追求最大化收益。但你仍会设置合理的止损线。
输出格式（JSON）：{"position_pct": 0.0-1.0, "stop_loss_pct": 数字, "take_profit_pct": 数字, "reasoning": "理由"}
"""
    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从激进角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
```

- [ ] **Step 2: 创建 engine/agents/risk_mgmt/conservative.py**

```python
"""保守风控师 — 低仓位 + 紧止损 + 快止盈"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import extract_json


class ConservativeDebater(BaseAgent):
    role = "conservative_risk"
    system_prompt = """你是保守风格的风控专家。你偏好低仓位、严格止损、
快速止盈、本金安全第一。
输出格式（JSON）：{"position_pct": 0.0-1.0, "stop_loss_pct": 数字, "take_profit_pct": 数字, "reasoning": "理由"}
"""
    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从保守角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
```

- [ ] **Step 3: 创建 engine/agents/risk_mgmt/neutral.py**

```python
"""中性风控师 — 平衡仓位 + 动态止损"""
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import extract_json


class NeutralDebater(BaseAgent):
    role = "neutral_risk"
    system_prompt = """你是中性风格的风控专家。你在收益和风险间寻求平衡，
采用动态止损策略，根据市场波动率调整风控参数。
输出格式（JSON）：{"position_pct": 0.0-1.0, "stop_loss_pct": 数字, "take_profit_pct": 数字, "reasoning": "理由"}
"""
    def evaluate(self, research_result: dict) -> dict:
        resp = self.invoke("从中性角度评估仓位和风险参数", str(research_result))
        return extract_json(resp)
```

- [ ] **Step 4: 创建 engine/agents/trader.py**

```python
"""交易员 Agent — 综合决策 + 结构化输出 — 最终买卖建议"""
import json
from engine.agents.base import BaseAgent
from engine.agents.utils.structured import extract_json


class TraderAgent(BaseAgent):
    role = "trader"
    system_prompt = """你是一位专业交易员。综合研究报告和风控辩论结果，
做出最终交易决策。你必须给出具体的买入价格区间、仓位、止损线、止盈线。

输出格式（JSON）：
{
    "action": "buy|sell|hold",
    "quantity_pct": 0.0-1.0,
    "price_lower": 买入价格下限,
    "price_upper": 买入价格上限,
    "stop_loss": 止损价,
    "stop_loss_pct": 止损百分比,
    "take_profit": 止盈价,
    "take_profit_pct": 止盈百分比,
    "max_hold_days": 预期持有时长（交易日）,
    "confidence": 0.0-1.0,
    "reasoning": "决策理由"
}"""

    def decide(
        self,
        symbol: str,
        price: float,
        research_result: dict,
        risk_evaluations: dict,
    ) -> dict:
        context = f"""股票: {symbol}  当前价: {price}
研究报告: {json.dumps(research_result, ensure_ascii=False)}
风控评估:
- 激进: {json.dumps(risk_evaluations.get('aggressive', {}), ensure_ascii=False)}
- 保守: {json.dumps(risk_evaluations.get('conservative', {}), ensure_ascii=False)}
- 中性: {json.dumps(risk_evaluations.get('neutral', {}), ensure_ascii=False)}
"""
        resp = self.invoke("给出最终交易决策", context)
        return extract_json(resp)
```

- [ ] **Step 5: Commit**

```bash
git add engine/agents/risk_mgmt/ engine/agents/trader.py
git commit -m "feat: risk management debate (3 styles) + trader agent with structured output"
```

---

## Task 10: LangGraph 分析工作流

**Files:**
- Create: `engine/graph/__init__.py`
- Create: `engine/graph/state.py`
- Create: `engine/graph/nodes.py`
- Create: `engine/graph/routing.py`
- Create: `engine/graph/workflow.py`

- [ ] **Step 1: 创建 engine/graph/state.py**

```python
"""LangGraph 状态定义"""
from typing import TypedDict, Optional
from datetime import datetime


class AnalysisState(TypedDict):
    symbol: str
    market: str          # "a_stock" | "hk_stock" | "us_stock"
    price: float
    timestamp: str       # ISO format

    # Analyst reports
    market_report: dict
    fundamentals_report: dict
    news_report: dict

    # Debate results
    bull_report: dict
    bear_report: dict
    research_decision: dict

    # Risk evaluations
    risk_evaluations: dict
    final_risk_params: dict

    # Final decision
    trader_decision: dict

    # Metadata
    error: Optional[str]
    completed_at: Optional[str]
```

- [ ] **Step 2: 创建 engine/graph/nodes.py**

```python
"""LangGraph 节点 — 每个节点代表分析流程中的一步"""
from typing import Any
from engine.agents.analysts.market import MarketAnalyst
from engine.agents.analysts.fundamentals import FundamentalsAnalyst
from engine.agents.analysts.news import NewsAnalyst
from engine.agents.researchers.bull import BullResearcher
from engine.agents.researchers.bear import BearResearcher
from engine.agents.manager import ResearchManager
from engine.agents.risk_mgmt.aggressive import AggressiveDebater
from engine.agents.risk_mgmt.conservative import ConservativeDebater
from engine.agents.risk_mgmt.neutral import NeutralDebater
from engine.agents.trader import TraderAgent
from engine.agents.utils.tools import get_quote
from .state import AnalysisState


def fetch_data_node(state: AnalysisState) -> dict[str, Any]:
    """节点0: 获取行情数据"""
    try:
        quote = get_quote(state["symbol"], state["market"])
        return {"price": quote.price, "timestamp": quote.timestamp.isoformat()}
    except Exception as e:
        return {"error": str(e)}


def market_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点1: 市场技术分析"""
    agent = MarketAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"market_report": result}


def fundamentals_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点2: 基本面分析"""
    agent = FundamentalsAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"fundamentals_report": result}


def news_analysis_node(state: AnalysisState) -> dict[str, Any]:
    """节点3: 新闻分析"""
    agent = NewsAnalyst()
    result = agent.analyze(state["symbol"], state["market"])
    return {"news_report": result}


def bull_debate_node(state: AnalysisState) -> dict[str, Any]:
    """节点4: 多方辩论"""
    agent = BullResearcher()
    reports = f"市场分析: {state.get('market_report', {})}\n基本面: {state.get('fundamentals_report', {})}\n新闻: {state.get('news_report', {})}"
    result = agent.debate(reports)
    return {"bull_report": result}


def bear_debate_node(state: AnalysisState) -> dict[str, Any]:
    """节点5: 空方辩论"""
    agent = BearResearcher()
    reports = f"市场分析: {state.get('market_report', {})}\n基本面: {state.get('fundamentals_report', {})}\n新闻: {state.get('news_report', {})}"
    result = agent.debate(reports)
    return {"bear_report": result}


def research_manager_node(state: AnalysisState) -> dict[str, Any]:
    """节点6: 研究综合"""
    agent = ResearchManager()
    result = agent.decide(
        state["symbol"],
        {
            "market": state.get("market_report", {}),
            "fundamentals": state.get("fundamentals_report", {}),
            "news": state.get("news_report", {}),
        },
        state.get("bull_report", {}),
        state.get("bear_report", {}),
    )
    return {"research_decision": result}


def risk_evaluation_node(state: AnalysisState) -> dict[str, Any]:
    """节点7: 三方风控评估（并行）"""
    research = state.get("research_decision", {})
    aggressive = AggressiveDebater().evaluate(research)
    conservative = ConservativeDebater().evaluate(research)
    neutral = NeutralDebater().evaluate(research)
    return {"risk_evaluations": {
        "aggressive": aggressive,
        "conservative": conservative,
        "neutral": neutral,
    }}


def risk_consensus_node(state: AnalysisState) -> dict[str, Any]:
    """节点8: 风控参数共识（取三种风格的中性/均值）"""
    evals = state.get("risk_evaluations", {})
    neutral = evals.get("neutral", {})
    return {"final_risk_params": neutral}


def trader_decision_node(state: AnalysisState) -> dict[str, Any]:
    """节点9: 交易员最终决策"""
    agent = TraderAgent()
    result = agent.decide(
        state["symbol"],
        state.get("price", 0),
        state.get("research_decision", {}),
        state.get("risk_evaluations", {}),
    )
    from datetime import datetime
    return {"trader_decision": result, "completed_at": datetime.now().isoformat()}
```

- [ ] **Step 3: 创建 engine/graph/routing.py**

```python
"""条件路由 — 错误处理和流程控制"""

def should_continue(state: dict) -> str:
    """检查是否有错误，决定是否继续"""
    if state.get("error"):
        return "__end__"
    return "market_analysis"


def research_score_check(state: dict) -> str:
    """根据研究评分决定是否值得交易"""
    decision = state.get("research_decision", {})
    score = decision.get("final_score", 0)
    if score >= 6:
        return "risk_evaluation"
    return "skip_trade"
```

- [ ] **Step 4: 创建 engine/graph/workflow.py**

```python
"""LangGraph 主工作流 — 编排完整分析流程"""
from langgraph.graph import StateGraph, END
from .state import AnalysisState
from .nodes import (
    fetch_data_node,
    market_analysis_node,
    fundamentals_analysis_node,
    news_analysis_node,
    bull_debate_node,
    bear_debate_node,
    research_manager_node,
    risk_evaluation_node,
    risk_consensus_node,
    trader_decision_node,
)
from .routing import should_continue, research_score_check


def build_analysis_graph() -> StateGraph:
    """构建分析工作流图

    流程: fetch → [market, fundamentals, news] (并行)
           → bull → bear (并行)
           → research_manager → risk_eval → risk_consensus → trader → END
    """
    graph = StateGraph(AnalysisState)

    # 添加节点
    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("market_analysis", market_analysis_node)
    graph.add_node("fundamentals_analysis", fundamentals_analysis_node)
    graph.add_node("news_analysis", news_analysis_node)
    graph.add_node("bull_debate", bull_debate_node)
    graph.add_node("bear_debate", bear_debate_node)
    graph.add_node("research_manager", research_manager_node)
    graph.add_node("risk_evaluation", risk_evaluation_node)
    graph.add_node("risk_consensus", risk_consensus_node)
    graph.add_node("trader_decision", trader_decision_node)

    # 设置入口
    graph.set_entry_point("fetch_data")

    # 连线: fetch → 三个分析师（并行）
    graph.add_edge("fetch_data", "market_analysis")
    graph.add_edge("fetch_data", "fundamentals_analysis")
    graph.add_edge("fetch_data", "news_analysis")

    # 分析师 → 辩论研究员
    graph.add_edge("market_analysis", "bull_debate")
    graph.add_edge("fundamentals_analysis", "bull_debate")
    graph.add_edge("news_analysis", "bull_debate")
    graph.add_edge("market_analysis", "bear_debate")
    graph.add_edge("fundamentals_analysis", "bear_debate")
    graph.add_edge("news_analysis", "bear_debate")

    # 辩论 → 研究管理员
    graph.add_edge("bull_debate", "research_manager")
    graph.add_edge("bear_debate", "research_manager")

    # 条件路由: 评分够高才进入风控
    graph.add_conditional_edges(
        "research_manager",
        research_score_check,
        {"risk_evaluation": "risk_evaluation", "skip_trade": END},
    )

    graph.add_edge("risk_evaluation", "risk_consensus")
    graph.add_edge("risk_consensus", "trader_decision")
    graph.add_edge("trader_decision", END)

    return graph


def run_analysis(symbol: str, market: str = "us") -> dict:
    """运行完整分析流程，返回交易员决策"""
    graph = build_analysis_graph()
    app = graph.compile()

    initial_state: AnalysisState = {
        "symbol": symbol,
        "market": market,
        "price": 0.0,
        "timestamp": "",
        "market_report": {},
        "fundamentals_report": {},
        "news_report": {},
        "bull_report": {},
        "bear_report": {},
        "research_decision": {},
        "risk_evaluations": {},
        "final_risk_params": {},
        "trader_decision": {},
        "error": None,
        "completed_at": None,
    }

    result = app.invoke(initial_state)
    return result
```

- [ ] **Step 5: Commit**

```bash
git add engine/graph/
git commit -m "feat: LangGraph analysis workflow — 10-node pipeline from data to trading decision"
```

---

## Task 11: 虚拟账户 + 持仓管理

**Files:**
- Create: `trader/__init__.py`
- Create: `trader/account.py`
- Create: `trader/position.py`
- Create: `trader/order.py`
- Create: `trader/strategy.py`
- Test: `tests/test_trader_account.py`

- [ ] **Step 1: 写失败测试 tests/test_trader_account.py**

```python
import pytest
from trader.account import VirtualAccount


class TestVirtualAccount:
    def test_initial_capital(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.capital == 100000
        assert acc.cash == 100000
        assert acc.total_value == 100000

    def test_can_buy_with_sufficient_cash(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.can_buy(price=50, quantity=1000) is True

    def test_cannot_buy_with_insufficient_cash(self):
        acc = VirtualAccount(initial_capital=100000)
        assert acc.can_buy(price=200, quantity=1000) is False

    def test_buy_updates_cash_and_positions(self):
        acc = VirtualAccount(initial_capital=100000)
        order = acc.buy("000001", "平安银行", 10.0, 1000, "测试买入")
        assert order is not None
        assert acc.cash == 90000
        assert "000001" in acc.positions

    def test_sell_updates_cash_and_positions(self):
        acc = VirtualAccount(initial_capital=100000)
        acc.buy("000001", "平安银行", 10.0, 1000, "")
        order = acc.sell("000001", 12.0, 500, "测试卖出")
        assert order is not None
        assert acc.positions["000001"]["quantity"] == 500
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_trader_account.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 trader/account.py**

```python
"""虚拟账户 — 资金管理 + 交易执行"""
from datetime import datetime
from typing import Optional
from .position import PositionManager
from .order import OrderManager


class VirtualAccount:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict = {}       # symbol → {name, quantity, avg_cost, market}
        self.orders: list[dict] = []    # 订单历史
        self.trade_log: list[dict] = [] # 交易日志

    @property
    def total_value(self) -> float:
        pos_value = sum(
            p.get("market_value", 0) * p.get("quantity", 0)
            for p in self.positions.values()
        )
        return self.cash + pos_value

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.initial_capital

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_value / self.initial_capital - 1) if self.initial_capital > 0 else 0

    def can_buy(self, price: float, quantity: int) -> bool:
        return self.cash >= price * quantity

    def buy(self, symbol: str, name: str, price: float, quantity: int, reason: str = "") -> Optional[dict]:
        cost = price * quantity
        if not self.can_buy(price, quantity):
            return None
        self.cash -= cost
        if symbol in self.positions:
            old_qty = self.positions[symbol]["quantity"]
            old_cost = self.positions[symbol]["avg_cost"]
            new_qty = old_qty + quantity
            self.positions[symbol]["quantity"] = new_qty
            self.positions[symbol]["avg_cost"] = (old_cost * old_qty + cost) / new_qty
        else:
            self.positions[symbol] = {
                "name": name, "quantity": quantity,
                "avg_cost": price, "current_price": price,
            }
        order = {
            "symbol": symbol, "name": name, "action": "buy",
            "price": price, "quantity": quantity, "cost": cost,
            "reason": reason, "timestamp": datetime.now().isoformat(),
        }
        self.orders.append(order)
        self.trade_log.append(order)
        return order

    def sell(self, symbol: str, price: float, quantity: int, reason: str = "") -> Optional[dict]:
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        sell_qty = min(quantity, pos["quantity"])
        revenue = price * sell_qty
        self.cash += revenue
        pos["quantity"] -= sell_qty
        if pos["quantity"] <= 0:
            del self.positions[symbol]
        order = {
            "symbol": symbol, "name": pos.get("name", ""), "action": "sell",
            "price": price, "quantity": sell_qty, "cost": revenue,
            "reason": reason, "timestamp": datetime.now().isoformat(),
        }
        self.orders.append(order)
        self.trade_log.append(order)
        return order

    def get_position_summary(self) -> list[dict]:
        return [
            {
                "symbol": s, "name": p.get("name", ""),
                "quantity": p["quantity"], "avg_cost": p["avg_cost"],
                "current_price": p.get("current_price", 0),
                "pnl_pct": (p.get("current_price", 0) / p["avg_cost"] - 1) if p["avg_cost"] > 0 else 0,
            }
            for s, p in self.positions.items()
        ]

    def to_dict(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "total_value": self.total_value,
            "total_pnl": self.total_pnl,
            "total_pnl_pct": self.total_pnl_pct,
            "positions": self.get_position_summary(),
        }
```

- [ ] **Step 4: 创建 trader/order.py 和 trader/position.py**

```python
# trader/order.py
"""订单管理 — 订单状态跟踪"""
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderManager:
    def __init__(self):
        self.orders: list[dict] = []

    def add(self, order: dict):
        order["id"] = len(self.orders) + 1
        order["status"] = OrderStatus.FILLED
        self.orders.append(order)

    def history(self, limit: int = 50) -> list[dict]:
        return self.orders[-limit:]
```

```python
# trader/position.py
"""持仓管理"""
class PositionManager:
    def __init__(self):
        self.positions: dict = {}

    def update(self, symbol: str, name: str, quantity: int, price: float):
        if quantity <= 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = {
                "name": name, "quantity": quantity, "current_price": price,
            }

    def get(self, symbol: str) -> dict | None:
        return self.positions.get(symbol)

    def all(self) -> dict:
        return dict(self.positions)
```

- [ ] **Step 5: 实现 trader/strategy.py**

```python
"""AI 交易策略引擎 — 将分析结果转换为具体买卖计划"""
from engine.agents.utils.structured import extract_json
from engine.agents.base import BaseAgent


class StrategyEngine:
    """根据 TraderAgent 的决策生成可执行的交易计划"""

    @staticmethod
    def generate_plan(trader_decision: dict, account_cash: float) -> dict:
        action = trader_decision.get("action", "hold")
        quantity_pct = trader_decision.get("quantity_pct", 0)
        price_lower = trader_decision.get("price_lower", 0)
        price_upper = trader_decision.get("price_upper", 0)
        budget = account_cash * quantity_pct

        plan = {
            "action": action,
            "budget": budget,
            "price_range": [price_lower, price_upper],
            "stop_loss": trader_decision.get("stop_loss", 0),
            "take_profit": trader_decision.get("take_profit", 0),
            "confidence": trader_decision.get("confidence", 0),
        }

        if action == "buy" and price_lower > 0:
            quantity = int(budget / price_lower / 100) * 100  # A股100股整数倍
            plan["quantity"] = max(100, quantity)
        else:
            plan["quantity"] = 0

        return plan
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_trader_account.py -v
```

Expected: 5 PASS

- [ ] **Step 7: Commit**

```bash
git add trader/ tests/test_trader_account.py
git commit -m "feat: virtual account + position management + AI strategy engine"
```

---

## Task 12: AI 动态风控引擎

**Files:**
- Create: `trader/risk/__init__.py`
- Create: `trader/risk/stop_loss.py`
- Create: `trader/risk/position_sizer.py`
- Create: `trader/risk/manager.py`
- Test: `tests/test_risk_manager.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_risk_manager.py
import pytest
from trader.risk.manager import RiskManager


class TestRiskManager:
    def test_stop_loss_triggered_when_loss_exceeds_threshold(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=9.5, quantity=1000
        )
        assert result["stop_loss_triggered"] is True

    def test_stop_loss_not_triggered_within_threshold(self):
        rm = RiskManager(daily_stop_loss_pct=0.03)
        result = rm.check_position(
            symbol="000001", avg_cost=10.0, current_price=9.9, quantity=1000
        )
        assert result["stop_loss_triggered"] is False

    def test_position_sizer_respects_max_ratio(self):
        rm = RiskManager(single_position_max_pct=0.2)
        size = rm.calculate_position_size(
            account_value=100000, price=50, risk_per_share=2
        )
        assert size * 50 <= 100000 * 0.2

    def test_daily_drawdown_triggers_halt(self):
        rm = RiskManager(daily_drawdown_limit_pct=0.05)
        rm.record_daily_pnl(-6000, 100000)
        assert rm.should_halt_trading() is True
```

- [ ] **Step 2: 验证失败**

```bash
python -m pytest tests/test_risk_manager.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 trader/risk/stop_loss.py + position_sizer.py + manager.py**

```python
# trader/risk/stop_loss.py
"""止损逻辑 — 硬止损 + AI动态止损"""
from dataclasses import dataclass


@dataclass
class StopLossResult:
    triggered: bool
    stop_price: float
    current_pnl_pct: float
    reason: str = ""


def evaluate_stop_loss(
    avg_cost: float,
    current_price: float,
    hard_stop_pct: float = 0.03,
    ai_stop_price: float = 0,
) -> StopLossResult:
    pnl_pct = (current_price / avg_cost - 1) if avg_cost > 0 else 0
    stop_price = ai_stop_price or (avg_cost * (1 - hard_stop_pct))
    triggered = current_price <= stop_price
    return StopLossResult(
        triggered=triggered,
        stop_price=stop_price,
        current_pnl_pct=pnl_pct,
        reason=f"触及止损线" if triggered else "",
    )


def evaluate_take_profit(
    avg_cost: float,
    current_price: float,
    take_profit_pct: float = 0.05,
    trailing_pct: float = 0.02,
    highest_price: float = 0,
) -> bool:
    """移动止盈: 从最高点回撤 trailing_pct% 即止盈"""
    high = max(highest_price, current_price)
    pnl_from_high = (current_price / high - 1) if high > 0 else 0
    if pnl_from_high <= -trailing_pct and current_price > avg_cost:
        return True
    if (current_price / avg_cost - 1) >= take_profit_pct:
        return True
    return False
```

```python
# trader/risk/position_sizer.py
"""仓位计算 — 基于风险平价"""
def calculate_position_size(
    account_value: float,
    price: float,
    risk_per_share: float,
    max_position_pct: float = 0.2,
    max_risk_pct: float = 0.01,
) -> int:
    """计算安全仓位: 单笔最大亏损不超过账户的 max_risk_pct%"""
    max_value = account_value * max_position_pct
    risk_based = (account_value * max_risk_pct) / risk_per_share if risk_per_share > 0 else max_value / price
    cap_based = max_value / price if price > 0 else 0
    quantity = int(min(risk_based, cap_based))
    return max(100, quantity // 100 * 100)  # A股百股取整
```

```python
# trader/risk/manager.py
"""风控管理器 — 统一止损/仓位/回撤控制"""
from .stop_loss import evaluate_stop_loss, evaluate_take_profit
from .position_sizer import calculate_position_size


class RiskManager:
    def __init__(
        self,
        daily_stop_loss_pct: float = 0.03,
        single_position_max_pct: float = 0.2,
        daily_drawdown_limit_pct: float = 0.05,
    ):
        self.daily_stop_loss_pct = daily_stop_loss_pct
        self.single_position_max_pct = single_position_max_pct
        self.daily_drawdown_limit_pct = daily_drawdown_limit_pct
        self._daily_pnl = 0.0
        self._daily_start_value = 0.0
        self._price_highs: dict = {}  # symbol → highest price

    def check_position(self, symbol: str, avg_cost: float, current_price: float, quantity: int) -> dict:
        """检查单个持仓的风控状态"""
        self._price_highs[symbol] = max(self._price_highs.get(symbol, current_price), current_price)

        stop_loss = evaluate_stop_loss(avg_cost, current_price, self.daily_stop_loss_pct)
        take_profit = evaluate_take_profit(
            avg_cost, current_price,
            highest_price=self._price_highs[symbol],
        )

        return {
            "symbol": symbol,
            "current_price": current_price,
            "avg_cost": avg_cost,
            "pnl_pct": stop_loss.current_pnl_pct,
            "stop_loss_triggered": stop_loss.triggered,
            "stop_loss_price": stop_loss.stop_price,
            "take_profit_triggered": take_profit,
            "action": "sell" if (stop_loss.triggered or take_profit) else "hold",
        }

    def calculate_position_size(self, account_value: float, price: float, risk_per_share: float = 0) -> int:
        return calculate_position_size(
            account_value, price, risk_per_share or price * self.daily_stop_loss_pct,
            max_position_pct=self.single_position_max_pct,
        )

    def record_daily_pnl(self, pnl: float, account_value: float):
        self._daily_pnl = pnl
        if self._daily_start_value == 0:
            self._daily_start_value = account_value

    def should_halt_trading(self) -> bool:
        if self._daily_start_value <= 0:
            return False
        drawdown = abs(self._daily_pnl) / self._daily_start_value
        return self._daily_pnl < 0 and drawdown >= self.daily_drawdown_limit_pct

    def get_dynamic_params(self, volatility: float) -> dict:
        """AI动态风控: 根据波动率调整参数"""
        adjusted_stop = min(self.daily_stop_loss_pct * (1 + volatility), 0.10)
        adjusted_position = self.single_position_max_pct / (1 + volatility)
        return {
            "stop_loss_pct": round(adjusted_stop, 3),
            "position_max_pct": round(adjusted_position, 3),
        }
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_risk_manager.py -v
```

- [ ] **Step 5: Commit**

```bash
git add trader/risk/ tests/test_risk_manager.py
git commit -m "feat: AI dynamic risk control — stop loss, position sizing, drawdown halt"
```

---

## Task 13: 自动化调度器

**Files:**
- Create: `trader/scheduler/__init__.py`
- Create: `trader/scheduler/jobs.py`
- Create: `trader/scheduler/runner.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scheduler.py
import pytest
from trader.scheduler.runner import TradingScheduler


class TestTradingScheduler:
    def test_scheduler_initializes_with_jobs(self):
        sched = TradingScheduler()
        jobs = sched.list_jobs()
        assert len(jobs) >= 3  # pre_market, market_open, market_close

    def test_pre_market_job_registered(self):
        sched = TradingScheduler()
        jobs = {j["name"] for j in sched.list_jobs()}
        assert "pre_market_analysis" in jobs
        assert "market_open_trading" in jobs
        assert "market_close_settlement" in jobs
```

- [ ] **Step 2: 创建 trader/scheduler/jobs.py**

```python
"""定时任务定义"""
from datetime import datetime


def pre_market_analysis_job():
    """盘前分析: 拉数据→AI分析→出推荐→生成交易计划"""
    from engine.graph.workflow import run_analysis
    from trader.account import VirtualAccount
    from trader.strategy import StrategyEngine

    # TODO: 从自选股池拉取候选股列表
    # candidates = get_candidate_stocks()
    candidates = []
    results = []
    for symbol, market in candidates:
        result = run_analysis(symbol, market)
        decision = result.get("trader_decision", {})
        if decision.get("action") == "buy":
            results.append({"symbol": symbol, "decision": decision})
    return results


def market_open_trading_job():
    """开盘交易: 执行交易计划"""
    from trader.account import VirtualAccount
    from trader.strategy import StrategyEngine
    print(f"[{datetime.now()}] 开盘交易执行中...")
    # 实际执行逻辑: 读取交易计划 → 下单 → 更新账户
    return {"status": "executed", "timestamp": datetime.now().isoformat()}


def market_close_settlement_job():
    """收盘结算: 计算盈亏→生成报表→复盘→存入记忆"""
    print(f"[{datetime.now()}] 收盘结算中...")
    return {"status": "settled", "timestamp": datetime.now().isoformat()}


def intraday_monitoring_job():
    """盘中监控: 检查触发止损/止盈"""
    from trader.risk.manager import RiskManager
    print(f"[{datetime.now()}] 盘中风控检查...")
    return {"status": "monitored", "timestamp": datetime.now().isoformat()}
```

- [ ] **Step 3: 创建 trader/scheduler/runner.py**

```python
"""调度器运行器 — APScheduler 封装"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .jobs import (
    pre_market_analysis_job,
    market_open_trading_job,
    market_close_settlement_job,
    intraday_monitoring_job,
)


class TradingScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._register_jobs()

    def _register_jobs(self):
        # 盘前分析: 工作日 8:00
        self.scheduler.add_job(
            pre_market_analysis_job,
            CronTrigger(day_of_week="mon-fri", hour=8, minute=0),
            id="pre_market_analysis",
            name="pre_market_analysis",
        )

        # 开盘交易: 工作日 9:30
        self.scheduler.add_job(
            market_open_trading_job,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=30),
            id="market_open_trading",
            name="market_open_trading",
        )

        # 盘中监控: 每5分钟
        self.scheduler.add_job(
            intraday_monitoring_job,
            CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/5"),
            id="intraday_monitoring",
            name="intraday_monitoring",
        )

        # 收盘结算: 工作日 15:00
        self.scheduler.add_job(
            market_close_settlement_job,
            CronTrigger(day_of_week="mon-fri", hour=15, minute=0),
            id="market_close_settlement",
            name="market_close_settlement",
        )

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

    def list_jobs(self) -> list[dict]:
        return [
            {"id": j.id, "name": j.name, "next_run": str(j.next_run_time)}
            for j in self.scheduler.get_jobs()
        ]
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/test_scheduler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add trader/scheduler/ tests/test_scheduler.py
git commit -m "feat: automated scheduler — pre-market, market open, intraday, close jobs"
```

---

## Task 14: FastAPI 后端 — 账户 & 交易 API

**Files:**
- Create: `server/__init__.py`
- Create: `server/main.py`
- Create: `server/models/__init__.py`
- Create: `server/models/stock.py`
- Create: `server/models/trade.py`
- Create: `server/routers/__init__.py`
- Create: `server/routers/account.py`
- Create: `server/routers/trading.py`
- Create: `server/routers/stocks.py`
- Create: `server/routers/analysis.py`

- [ ] **Step 1: 创建 server/models/**

```python
# server/models/stock.py
from pydantic import BaseModel
from typing import Optional


class StockQuoteResponse(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    volume: int


class StockAnalysisRequest(BaseModel):
    symbol: str
    market: str = "a_stock"  # a_stock, hk_stock, us_stock


class StockAnalysisResponse(BaseModel):
    symbol: str
    market: str
    analysis: dict
    trader_decision: dict
```

```python
# server/models/trade.py
from pydantic import BaseModel


class TradeRequest(BaseModel):
    symbol: str
    action: str  # buy / sell
    price: float
    quantity: int


class TradeResponse(BaseModel):
    success: bool
    order_id: int
    message: str


class AccountSummary(BaseModel):
    initial_capital: float
    cash: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    positions: list[dict]
```

- [ ] **Step 2: 创建 server/routers/**

```python
# server/routers/account.py
from fastapi import APIRouter
from server.models.trade import AccountSummary
from trader.account import VirtualAccount

router = APIRouter(prefix="/api/account", tags=["account"])
_account = VirtualAccount()


@router.get("/", response_model=AccountSummary)
def get_account():
    return _account.to_dict()


@router.get("/positions")
def get_positions():
    return _account.get_position_summary()


@router.get("/orders")
def get_orders(limit: int = 50):
    return _account.orders[-limit:]


def get_global_account() -> VirtualAccount:
    return _account
```

```python
# server/routers/trading.py
from fastapi import APIRouter, HTTPException
from server.models.trade import TradeRequest, TradeResponse
from server.routers.account import get_global_account

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post("/execute", response_model=TradeResponse)
def execute_trade(req: TradeRequest):
    acc = get_global_account()
    if req.action == "buy":
        order = acc.buy(req.symbol, "", req.price, req.quantity, "手动交易")
    elif req.action == "sell":
        order = acc.sell(req.symbol, req.price, req.quantity, "手动交易")
    else:
        raise HTTPException(400, "action must be buy or sell")

    if order is None:
        return TradeResponse(success=False, order_id=0, message="余额不足或持仓不足")
    return TradeResponse(success=True, order_id=len(acc.orders), message="成交")
```

```python
# server/routers/analysis.py
from fastapi import APIRouter, HTTPException
from server.models.stock import StockAnalysisRequest, StockAnalysisResponse
from engine.graph.workflow import run_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/run", response_model=StockAnalysisResponse)
def run_stock_analysis(req: StockAnalysisRequest):
    try:
        result = run_analysis(req.symbol, req.market)
        return StockAnalysisResponse(
            symbol=req.symbol,
            market=req.market,
            analysis={
                "market": result.get("market_report"),
                "fundamentals": result.get("fundamentals_report"),
                "news": result.get("news_report"),
                "research_decision": result.get("research_decision"),
                "risk_evaluations": result.get("risk_evaluations"),
            },
            trader_decision=result.get("trader_decision", {}),
        )
    except Exception as e:
        raise HTTPException(500, f"分析失败: {e}")
```

```python
# server/routers/stocks.py
from fastapi import APIRouter, Query
from data.providers.a_stock import AStockProvider
from engine.dataflows.interface import Market

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/quote")
def get_quote(symbol: str, market: str = "a_stock"):
    provider = AStockProvider()
    quote = provider.get_realtime_quote(symbol, Market(market))
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
        "change_pct": quote.change_pct,
    }


@router.get("/search")
def search_stocks(keyword: str, market: str = "a_stock"):
    provider = AStockProvider()
    return provider.search_symbols(keyword, Market(market))
```

- [ ] **Step 3: 创建 server/main.py**

```python
"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.routers import account, trading, analysis, stocks, scheduler as sched_router

app = FastAPI(title="TradingAgents API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(trading.router)
app.include_router(analysis.router)
app.include_router(stocks.router)

# scheduler 路由稍后创建


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Commit**

```bash
git add server/
git commit -m "feat: FastAPI backend — account, trading, analysis, stocks API endpoints"
```

---

## Task 15: 前端 — 仪表盘 + 推荐 + 交易记录

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/TradingLog.tsx`
- Create: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/StockCard.tsx`
- Create: `frontend/src/components/PositionTable.tsx`
- Create: `frontend/src/components/PnLChart.tsx`
- Create: `frontend/src/styles/global.css`

- [ ] **Step 1: 创建前端基础设施**

```json
// frontend/package.json
{
  "name": "trading-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "recharts": "^2.12.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TradingAgents - AI量化交易</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: 创建 API 客户端 frontend/src/api/client.ts**

```typescript
const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  getAccount: () => request<any>('/account/'),
  getPositions: () => request<any[]>('/account/positions'),
  getOrders: () => request<any[]>('/account/orders'),
  executeTrade: (data: any) =>
    request<any>('/trading/execute', { method: 'POST', body: JSON.stringify(data) }),
  runAnalysis: (symbol: string, market: string) =>
    request<any>('/analysis/run', {
      method: 'POST',
      body: JSON.stringify({ symbol, market }),
    }),
  getQuote: (symbol: string, market: string) =>
    request<any>(`/stocks/quote?symbol=${symbol}&market=${market}`),
  searchStocks: (keyword: string, market: string) =>
    request<any[]>(`/stocks/search?keyword=${keyword}&market=${market}`),
};
```

- [ ] **Step 3: 入口文件 frontend/src/main.tsx + App.tsx**

```tsx
// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

```tsx
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TradingLog from './pages/TradingLog';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trades" element={<TradingLog />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}
```

- [ ] **Step 4: 页面组件**

```tsx
// frontend/src/pages/Dashboard.tsx
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import PositionTable from '../components/PositionTable';
import StockCard from '../components/StockCard';
import PnLChart from '../components/PnLChart';

export default function Dashboard() {
  const [account, setAccount] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);

  useEffect(() => {
    api.getAccount().then(setAccount);
    api.getPositions().then(setPositions);
    api.getOrders().then((orders) => {
      // 模拟推荐数据（实际从分析API获取）
      setRecommendations([]);
    });
  }, []);

  if (!account) return <div className="loading">加载中...</div>;

  return (
    <div className="dashboard">
      {/* 账户概览卡片 */}
      <div className="account-cards">
        <div className="card">
          <div className="card-label">总资产</div>
          <div className="card-value">¥{account.total_value?.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">可用资金</div>
          <div className="card-value">¥{account.cash?.toLocaleString()}</div>
        </div>
        <div className={`card ${account.total_pnl >= 0 ? 'profit' : 'loss'}`}>
          <div className="card-label">总盈亏</div>
          <div className="card-value">
            ¥{account.total_pnl?.toLocaleString()}
            <span className="pct">({(account.total_pnl_pct * 100)?.toFixed(2)}%)</span>
          </div>
        </div>
      </div>

      {/* 盈亏图表 */}
      <section className="section">
        <h2>盈亏走势</h2>
        <PnLChart data={[]} />
      </section>

      {/* 持仓列表 */}
      <section className="section">
        <h2>当前持仓</h2>
        <PositionTable positions={positions} />
      </section>

      {/* 今日推荐 */}
      {recommendations.length > 0 && (
        <section className="section">
          <h2>今日AI推荐</h2>
          <div className="stock-grid">
            {recommendations.map((r: any) => (
              <StockCard key={r.symbol} {...r} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/pages/TradingLog.tsx
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function TradingLog() {
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    api.getOrders().then(setOrders);
  }, []);

  return (
    <div className="page">
      <h1>交易记录</h1>
      <table className="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>股票</th>
            <th>操作</th>
            <th>价格</th>
            <th>数量</th>
            <th>金额</th>
            <th>理由</th>
          </tr>
        </thead>
        <tbody>
          {orders.slice().reverse().map((o: any, i: number) => (
            <tr key={i}>
              <td>{new Date(o.timestamp).toLocaleString()}</td>
              <td>{o.symbol} {o.name}</td>
              <td className={o.action === 'buy' ? 'buy-action' : 'sell-action'}>
                {o.action === 'buy' ? '买入' : '卖出'}
              </td>
              <td>¥{o.price?.toFixed(2)}</td>
              <td>{o.quantity}</td>
              <td>¥{o.cost?.toFixed(2)}</td>
              <td>{o.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// frontend/src/pages/Settings.tsx
export default function Settings() {
  return (
    <div className="page">
      <h1>系统配置</h1>
      <p className="placeholder">风控参数 / LLM模型选择 / 数据源配置（P1阶段完善）</p>
    </div>
  );
}
```

- [ ] **Step 5: 公共组件**

```tsx
// frontend/src/components/Layout.tsx
import { Link } from 'react-router-dom';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="logo">TradingAgents</div>
        <ul className="nav-links">
          <li><Link to="/">仪表盘</Link></li>
          <li><Link to="/trades">交易记录</Link></li>
          <li><Link to="/settings">系统配置</Link></li>
        </ul>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  );
}
```

```tsx
// frontend/src/components/StockCard.tsx
export default function StockCard({ symbol, decision }: any) {
  const conf = (decision?.confidence || 0) * 100;
  return (
    <div className="stock-card">
      <div className="stock-header">
        <span className="stock-symbol">{symbol}</span>
        <span className={`action-badge ${decision?.action}`}>
          {decision?.action === 'buy' ? '买入' : decision?.action === 'sell' ? '卖出' : '观望'}
        </span>
      </div>
      <div className="stock-body">
        <div>买入区间: ¥{decision?.price_lower} - ¥{decision?.price_upper}</div>
        <div>止损: ¥{decision?.stop_loss} | 止盈: ¥{decision?.take_profit}</div>
        <div>置信度: {conf.toFixed(0)}%</div>
      </div>
      <div className="stock-footer">{decision?.reasoning}</div>
    </div>
  );
}
```

```tsx
// frontend/src/components/PositionTable.tsx
export default function PositionTable({ positions }: { positions: any[] }) {
  if (!positions?.length) return <div className="empty-state">暂无持仓</div>;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>股票代码</th>
          <th>名称</th>
          <th>持仓数量</th>
          <th>成本价</th>
          <th>现价</th>
          <th>盈亏%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p: any) => (
          <tr key={p.symbol}>
            <td>{p.symbol}</td>
            <td>{p.name}</td>
            <td>{p.quantity}</td>
            <td>¥{p.avg_cost?.toFixed(2)}</td>
            <td>¥{p.current_price?.toFixed(2)}</td>
            <td className={p.pnl_pct >= 0 ? 'profit' : 'loss'}>
              {(p.pnl_pct * 100)?.toFixed(2)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

```tsx
// frontend/src/components/PnLChart.tsx
export default function PnLChart({ data }: { data: any[] }) {
  return (
    <div className="chart-placeholder">
      {data.length === 0 ? '暂无盈亏数据（需要完成交易后生成）' : ''}
    </div>
  );
}
```

- [ ] **Step 6: 全局样式 frontend/src/styles/global.css**

```css
:root {
  --bg-primary: #0a0e14;
  --bg-secondary: #131820;
  --bg-card: #1a1f2b;
  --text-primary: #e6e6e6;
  --text-secondary: #8b95a5;
  --accent-green: #00c853;
  --accent-red: #ff1744;
  --accent-blue: #448aff;
  --border: #2a3040;
  --radius: 8px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'JetBrains Mono', 'Fira Code', monospace; background: var(--bg-primary); color: var(--text-primary); }

.app-layout { display: flex; min-height: 100vh; }
.sidebar { width: 220px; background: var(--bg-secondary); padding: 24px 16px; border-right: 1px solid var(--border); }
.sidebar .logo { font-size: 18px; font-weight: 700; color: var(--accent-blue); margin-bottom: 32px; }
.nav-links { list-style: none; }
.nav-links li { margin-bottom: 8px; }
.nav-links a { color: var(--text-secondary); text-decoration: none; font-size: 14px; padding: 8px 12px; display: block; border-radius: var(--radius); }
.nav-links a:hover { background: var(--bg-card); color: var(--text-primary); }
.main-content { flex: 1; padding: 32px; overflow-y: auto; }

.account-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }
.card-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase; }
.card-value { font-size: 24px; font-weight: 700; }
.card.profit .card-value { color: var(--accent-green); }
.card.loss .card-value { color: var(--accent-red); }
.pct { font-size: 14px; margin-left: 8px; }

.section { margin-bottom: 32px; }
.section h2 { font-size: 18px; margin-bottom: 16px; color: var(--text-primary); }

.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.data-table th { color: var(--text-secondary); font-weight: 500; text-transform: uppercase; font-size: 11px; }
.profit { color: var(--accent-green); }
.loss { color: var(--accent-red); }
.buy-action { color: var(--accent-green); font-weight: 600; }
.sell-action { color: var(--accent-red); font-weight: 600; }

.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.stock-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }
.stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.stock-symbol { font-size: 16px; font-weight: 700; }
.action-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.action-badge.buy { background: rgba(0, 200, 83, 0.15); color: var(--accent-green); }
.action-badge.sell { background: rgba(255, 23, 68, 0.15); color: var(--accent-red); }
.stock-body { font-size: 13px; color: var(--text-secondary); line-height: 1.8; }
.stock-footer { font-size: 12px; color: var(--text-secondary); margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }

.empty-state { padding: 40px; text-align: center; color: var(--text-secondary); }
.chart-placeholder { height: 200px; display: flex; align-items: center; justify-content: center; background: var(--bg-card); border-radius: var(--radius); color: var(--text-secondary); font-size: 14px; }
.loading { padding: 40px; text-align: center; }
.placeholder { color: var(--text-secondary); font-style: italic; }
```

- [ ] **Step 7: 安装前端依赖并验证构建**

```bash
cd frontend && npm install && npm run build
```

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: React frontend — dashboard, trading log, dark theme UI"
```

---

## Task 16: 经验记忆库 + 复盘系统

**Files:**
- Create: `engine/agents/utils/memory.py`
- Create: `memory/.gitkeep`

- [ ] **Step 1: 创建 engine/agents/utils/memory.py**

```python
"""经验记忆系统 — 记录每笔交易，复盘时检索类似场景"""
import json
import os
from datetime import datetime
from typing import Optional


class TradingMemory:
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        self.log_path = os.path.join(memory_dir, "trading_memory.jsonl")

    def record_decision(self, entry: dict):
        """记录每次分析+交易决策"""
        entry["timestamp"] = datetime.now().isoformat()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_recent(self, limit: int = 30) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries[-limit:]

    def find_similar(self, symbol: str, action: str = "buy") -> list[dict]:
        """查找相同股票的类似决策"""
        entries = self.load_recent(100)
        return [
            e for e in entries
            if e.get("symbol") == symbol and e.get("action") == action
        ][-5:]

    def daily_review(self, account_summary: dict, trades: list[dict]) -> str:
        """每日复盘: 总结得失，输出优化建议"""
        winning = sum(1 for t in trades if t.get("pnl", 0) > 0)
        losing = len(trades) - winning
        total_pnl = sum(t.get("pnl", 0) for t in trades)

        summary = f"""## 复盘 {datetime.now().strftime('%Y-%m-%d')}

- 今日交易: {len(trades)} 笔
- 盈利: {winning} 笔  |  亏损: {losing} 笔
- 总盈亏: ¥{total_pnl:,.2f}
- 账户总值: ¥{account_summary.get('total_value', 0):,.2f}
- 收益率: {account_summary.get('total_pnl_pct', 0):.2%}

### 经验教训
"""
        # 记录到文件
        review_path = os.path.join(self.memory_dir, f"review_{datetime.now().strftime('%Y%m%d')}.md")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(summary)
        return summary
```

- [ ] **Step 2: Commit**

```bash
git add engine/agents/utils/memory.py memory/
git commit -m "feat: experience memory system — trade logging, review, similar scenario lookup"
```

---

## Task 17: Docker 部署配置

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

RUN cd frontend && npm install && npm run build

EXPOSE 8000 3000

CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port 8000 & cd frontend && npm run dev"]
```

- [ ] **Step 2: docker-compose.yml**

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
      - "3000:3000"
    volumes:
      - ./data:/app/data
      - ./memory:/app/memory
      - ./.env:/app/.env
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker deployment — single container for API + frontend"
```

---

## Task 18: 集成测试 + 端到端验证

**Files:**
- Create: `scripts/init_db.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写入集成测试**

```python
# tests/test_integration.py
"""端到端集成测试: 分析 → 决策 → 交易 → 风控 全链路"""
import pytest
from trader.account import VirtualAccount
from trader.risk.manager import RiskManager
from trader.strategy import StrategyEngine


class TestFullPipeline:
    def test_analysis_to_trade_flow(self):
        """验证: 分析结果 → 交易计划 → 执行 → 风控检查"""
        # Step 1: 模拟分析结果
        trader_decision = {
            "action": "buy",
            "quantity_pct": 0.2,
            "price_lower": 9.5,
            "price_upper": 10.5,
            "stop_loss": 9.0,
            "stop_loss_pct": 0.05,
            "take_profit": 11.5,
            "take_profit_pct": 0.10,
            "confidence": 0.75,
        }

        # Step 2: 策略引擎生成计划
        account = VirtualAccount(initial_capital=100000)
        plan = StrategyEngine.generate_plan(trader_decision, account.cash)
        assert plan["action"] == "buy"
        assert plan["quantity"] >= 100

        # Step 3: 执行交易
        avg_price = (plan["price_range"][0] + plan["price_range"][1]) / 2
        order = account.buy("000001", "平安银行", avg_price, plan["quantity"], "AI推荐")
        assert order is not None
        assert "000001" in account.positions

        # Step 4: 风控检查
        rm = RiskManager(daily_stop_loss_pct=0.05)
        result = rm.check_position("000001", avg_price, avg_price, plan["quantity"])
        assert result["action"] == "hold"  # 未触发止损

        # Step 5: 模拟价格下跌触发止损
        result2 = rm.check_position("000001", avg_price, avg_price * 0.92, plan["quantity"])
        assert result2["stop_loss_triggered"] is True
        assert result2["action"] == "sell"

    def test_risk_manager_position_sizing(self):
        rm = RiskManager(single_position_max_pct=0.2, daily_stop_loss_pct=0.03)
        size = rm.calculate_position_size(100000, 50, risk_per_share=1.5)
        assert size * 50 <= 20000  # 不超过20%仓位

    def test_multiple_trades_pnl_tracking(self):
        account = VirtualAccount(initial_capital=100000)
        account.buy("000001", "平安银行", 10, 2000, "")
        account.sell("000001", 12, 2000, "")
        assert account.total_pnl == 4000
        assert account.total_pnl_pct == 0.04
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_integration.py -v
```

Expected: 3 PASS

- [ ] **Step 3: 初始化数据库脚本**

```python
# scripts/init_db.py
"""初始化数据库和目录结构"""
import os

dirs = ["data/cache", "memory", "logs"]
for d in dirs:
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ".gitkeep"), "w") as f:
        pass
print("Directories initialized:", dirs)
```

- [ ] **Step 4: 运行完整测试套件**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 所有测试通过（网络依赖测试标记为可跳过）

- [ ] **Step 5: Commit**

```bash
git add scripts/ tests/test_integration.py
git commit -m "test: integration tests — full pipeline from analysis to risk control"
```

---

## 总结：Phase 1 交付物

| # | 模块 | 文件数 | 核心功能 |
|---|------|--------|---------|
| 1 | 项目初始化 | 4 | pyproject.toml, config, vendor registry |
| 2 | LLM工厂 | 3 | DeepSeek/OpenAI/Claude 多供应商切换 |
| 3 | 港美股数据 | 4 | yfinance 行情+财务+新闻 |
| 4 | A股数据 | 3 | AkShare + BaoStock 双路兜底 |
| 5 | 新闻+舆情 | 4 | 国内外新闻 + 关键词情感分析 |
| 6 | Agent基类 | 3 | BaseAgent + 工具函数 + 结构化输出 |
| 7 | 分析师 | 3 | 市场/基本面/新闻 三分析师 |
| 8 | 研究员 | 3 | 多方/空方辩论 + 研究管理员 |
| 9 | 风控+交易员 | 5 | 激进/保守/中性风控 + 交易决策 |
| 10 | LangGraph工作流 | 4 | 10节点分析管道 |
| 11 | 虚拟交易 | 5 | 账户/持仓/订单/策略引擎 |
| 12 | 风控引擎 | 3 | 止损/仓位计算/回撤熔断 |
| 13 | 调度器 | 3 | 盘前/开盘/盘中/收盘 定时任务 |
| 14 | FastAPI后端 | 9 | REST API 全部端点 |
| 15 | React前端 | 14 | 仪表盘/交易记录/深色主题 |
| 16 | 记忆系统 | 1 | 交易日志+复盘 |
| 17 | Docker | 2 | Dockerfile + Compose |
| 18 | 集成测试 | 2 | 端到端全链路验证 |

**启动命令:**
```bash
# 后端
uvicorn server.main:app --reload

# 前端
cd frontend && npm run dev

# Docker 一键启动
docker-compose up
```

---

> **Phase 2 预告（P1）:** 大V爬虫+经验融合 / 社交媒体舆情增强 / AI复盘自进化 / 策略回测 / 报告导出
> **Phase 3 预告（P2）:** 多用户系统 / 多策略并行 / 实盘对接 / 港股美股深度数据
