from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from tradingAgents.trader.backtest import BacktestConfig, ShortTerm100BacktestStrategy
from tradingAgents.trader.strategy.short_term_100 import ShortTerm100Strategy


def _short_hist(days: int = 70) -> pd.DataFrame:
    start = datetime(2026, 1, 1)
    rows = []
    for i in range(days):
        close = 10.0
        volume = 1000
        if i == 25:
            close = 11.0
            volume = 3000
        elif i > 25:
            close = 11.15 + min(i - 26, 8) * 0.05
            volume = 1400 if i < 36 else 900
        rows.append({
            "日期": start + timedelta(days=i),
            "收盘": close,
            "最高": close * 1.01,
            "最低": close * 0.99,
            "成交量": volume,
            "market_cap": 80,
        })
    return pd.DataFrame(rows).set_index("日期")


def _flat_hist(days: int = 70) -> pd.DataFrame:
    start = datetime(2026, 1, 1)
    return pd.DataFrame(
        {
            "日期": [start + timedelta(days=i) for i in range(days)],
            "收盘": [10.0] * days,
            "最高": [10.1] * days,
            "最低": [9.9] * days,
            "成交量": [1000] * days,
            "market_cap": [80] * days,
        }
    ).set_index("日期")


def test_short_term_100_score_outputs_components_and_trade_plan():
    hist = _short_hist().iloc[:25]
    quote = SimpleNamespace(
        symbol="000001",
        price=11.0,
        close=10.0,
        high=11.11,
        low=10.89,
        volume=3000,
        market_cap=80,
    )

    result = ShortTerm100Strategy().score(hist, quote, fundamentals={})

    assert result["score"] >= 80
    assert result["components"]
    assert result["reasons"]
    assert result["trade_plan"]["entry"] == 11.0
    assert result["trade_plan"]["position_ratio"] > 0
    assert "sell_signals" in result
    assert "exit_rules" in result["trade_plan"]


def test_short_term_100_emits_exit_signal_for_volume_stall():
    hist = _short_hist().iloc[:40]
    prev_close = float(hist["收盘"].iloc[-1])
    quote = SimpleNamespace(
        symbol="000001",
        price=prev_close * 1.002,
        close=prev_close,
        high=prev_close * 1.035,
        low=prev_close * 0.99,
        volume=3200,
        market_cap=80,
    )

    result = ShortTerm100Strategy().score(hist, quote, fundamentals={})

    assert result["exit_signal"] is True
    assert any(signal["key"] == "volume_stall" for signal in result["sell_signals"])


def test_short_term_backtest_executes_signal_on_next_day_without_future_data():
    histories = {
        "000001": _short_hist(),
        "000002": _flat_hist(),
    }
    config = BacktestConfig(
        strategy="short_term_100",
        market="a_stock",
        period="3mo",
        initial_cash=100000,
        universe_limit=2,
        top_n=1,
        lookback_long=20,
        lookback_short=5,
        max_volume_participation_pct=1.0,
    )

    result = ShortTerm100BacktestStrategy().run_on_histories(
        config,
        histories,
        names={"000001": "强势样本", "000002": "普通样本"},
    )

    buys = [trade for trade in result["trades"] if trade["action"] == "BUY"]
    assert result["status"] == "success"
    assert buys
    assert buys[0]["symbol"] == "000001"
    assert buys[0]["date"].date() > histories["000001"].index[25].date()
    assert "profit_factor" in result["metrics"]
