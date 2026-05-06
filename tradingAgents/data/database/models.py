"""SQLAlchemy ORM models for PostgreSQL — accounts, positions, orders, trading plans"""
import enum
from datetime import datetime
from sqlalchemy import Boolean, String, Float, Integer, DateTime, Text, Enum as SAEnum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderAction(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class PlanStatus(str, enum.Enum):
    pending = "pending"
    executed = "executed"
    cancelled = "cancelled"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    initial_capital: Mapped[float] = mapped_column(Float, default=1_000_000)
    cash: Mapped[float] = mapped_column(Float, default=1_000_000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer)
    avg_cost: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    action: Mapped[OrderAction] = mapped_column(SAEnum(OrderAction))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    cost: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TradingPlan(Base):
    __tablename__ = "trading_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    price: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DataEvent(Base):
    __tablename__ = "data_events"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    source: Mapped[str] = mapped_column(String(120), default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict] = mapped_column(JSON)
    stored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StockUniverse(Base):
    __tablename__ = "stock_universe"
    __table_args__ = (
        UniqueConstraint("market", "symbol", name="uq_stock_universe_market_symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    exchange: Mapped[str] = mapped_column(String(40), default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(80), default="config")
    market_cap: Mapped[float] = mapped_column(Float, default=0)
    avg_turnover: Mapped[float] = mapped_column(Float, default=0)
    liquidity_rank: Mapped[int] = mapped_column(Integer, default=0)
    quality_seed_score: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockUniverseSyncRun(Base):
    __tablename__ = "stock_universe_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="success")
    total: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    source: Mapped[str] = mapped_column(String(60), default="manual")
    cash: Mapped[float] = mapped_column(Float, default=0)
    positions_value: Mapped[float] = mapped_column(Float, default=0)
    total_value: Mapped[float] = mapped_column(Float, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FactorScore(Base):
    __tablename__ = "factor_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    strategy: Mapped[str] = mapped_column(String(80), default="quality_momentum")
    market: Mapped[str] = mapped_column(String(20), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(20), default="")
    risk_level: Mapped[str] = mapped_column(String(30), default="")
    price: Mapped[float] = mapped_column(Float, default=0)
    change_pct: Mapped[float] = mapped_column(Float, default=0)
    final_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    growth_score: Mapped[float] = mapped_column(Float, default=0)
    valuation_score: Mapped[float] = mapped_column(Float, default=0)
    momentum_score: Mapped[float] = mapped_column(Float, default=0)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    liquidity_score: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    fundamentals: Mapped[dict] = mapped_column(JSON, default=dict)
    technical: Mapped[dict] = mapped_column(JSON, default=dict)
    sentiment: Mapped[dict] = mapped_column(JSON, default=dict)
    trade_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    data_quality_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DataSourceQuality(Base):
    __tablename__ = "data_source_quality"
    __table_args__ = (
        UniqueConstraint("source", "category", name="uq_data_source_quality_source_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="")
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    reliability_score: Mapped[float] = mapped_column(Float, default=0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class NewsItemRecord(Base):
    __tablename__ = "news_items"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "dedupe_key", name="uq_news_items_market_symbol_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(120), default="", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="", index=True)
    url: Mapped[str] = mapped_column(Text, default="")
    dedupe_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0)
    source_weight: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketQuoteSnapshot(Base):
    __tablename__ = "market_quote_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(120), default="", index=True)
    asset_type: Mapped[str] = mapped_column(String(30), default="stock", index=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    open: Mapped[float] = mapped_column(Float, default=0)
    high: Mapped[float] = mapped_column(Float, default=0)
    low: Mapped[float] = mapped_column(Float, default=0)
    close: Mapped[float] = mapped_column(Float, default=0)
    change_pct: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[float] = mapped_column(Float, default=0)
    turnover: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FinancialSnapshot(Base):
    __tablename__ = "financial_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    source: Mapped[str] = mapped_column(String(120), default="", index=True)
    fiscal_period: Mapped[str] = mapped_column(String(40), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    strategy: Mapped[str] = mapped_column(String(80), default="baseline_momentum", index=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    period: Mapped[str] = mapped_column(String(20), default="1y")
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    initial_cash: Mapped[float] = mapped_column(Float, default=1_000_000)
    final_value: Mapped[float] = mapped_column(Float, default=0)
    total_return: Mapped[float] = mapped_column(Float, default=0)
    annual_return: Mapped[float] = mapped_column(Float, default=0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0)
    sharpe: Mapped[float] = mapped_column(Float, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    trade_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0)
    fee: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacktestEquityCurve(Base):
    __tablename__ = "backtest_equity_curve"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    trade_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    cash: Mapped[float] = mapped_column(Float, default=0)
    positions_value: Mapped[float] = mapped_column(Float, default=0)
    total_value: Mapped[float] = mapped_column(Float, default=0)
    daily_return: Mapped[float] = mapped_column(Float, default=0)
    drawdown: Mapped[float] = mapped_column(Float, default=0)
    positions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StrategyExperiment(Base):
    __tablename__ = "strategy_experiments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    engine: Mapped[str] = mapped_column(String(60), default="local_research_baseline", index=True)
    strategy: Mapped[str] = mapped_column(String(80), default="baseline_momentum", index=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    period: Mapped[str] = mapped_column(String(20), default="1y")
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    train_range: Mapped[dict] = mapped_column(JSON, default=dict)
    valid_range: Mapped[dict] = mapped_column(JSON, default=dict)
    test_range: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    best_trial_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StrategyParamTrial(Base):
    __tablename__ = "strategy_param_trials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trial_id: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    experiment_id: Mapped[str] = mapped_column(String(50), index=True)
    backtest_run_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    engine: Mapped[str] = mapped_column(String(60), default="local_research_baseline", index=True)
    strategy: Mapped[str] = mapped_column(String(80), default="baseline_momentum", index=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    train_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    valid_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    test_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0, index=True)
    data_coverage: Mapped[float] = mapped_column(Float, default=0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StrategyLeaderboard(Base):
    __tablename__ = "strategy_leaderboard"
    __table_args__ = (
        UniqueConstraint("market", "strategy", "trial_id", name="uq_strategy_leaderboard_trial"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    strategy: Mapped[str] = mapped_column(String(80), default="baseline_momentum", index=True)
    engine: Mapped[str] = mapped_column(String(60), default="local_research_baseline", index=True)
    experiment_id: Mapped[str] = mapped_column(String(50), index=True)
    trial_id: Mapped[str] = mapped_column(String(60), index=True)
    backtest_run_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    score: Mapped[float] = mapped_column(Float, default=0, index=True)
    annual_return: Mapped[float] = mapped_column(Float, default=0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0)
    sharpe: Mapped[float] = mapped_column(Float, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0)
    test_annual_return: Mapped[float] = mapped_column(Float, default=0)
    test_max_drawdown: Mapped[float] = mapped_column(Float, default=0)
    test_sharpe: Mapped[float] = mapped_column(Float, default=0)
    data_coverage: Mapped[float] = mapped_column(Float, default=0)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class QlibDataExportRun(Base):
    __tablename__ = "qlib_data_export_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    export_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(20), default="", index=True)
    source: Mapped[str] = mapped_column(String(80), default="clickhouse_kline_daily", index=True)
    target_dir: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    calendar_count: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
