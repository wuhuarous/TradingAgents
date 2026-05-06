"""Baseline backtest engine.

This intentionally starts with a price-only momentum baseline. It avoids
using current fundamentals or current news in historical simulations, so the
result is a realistic benchmark instead of a look-ahead-biased demo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.trader.trade_rules import a_share_limit_pct, compute_trade_costs


@dataclass
class BacktestConfig:
    market: str = "a_stock"
    period: str = "1y"
    initial_cash: float = 1_000_000
    universe_limit: int = 200
    top_n: int = 5
    rebalance_days: int = 20
    lookback_short: int = 20
    lookback_long: int = 60
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    min_fee: float = 5.0
    max_position_ratio: float = 0.20
    max_volume_participation_pct: float = 0.05


class BaselineMomentumBacktester:
    strategy_name = "baseline_momentum"

    def run(self, config: BacktestConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        run_id = f"bt{started_at.strftime('%Y%m%d%H%M%S%f')}"
        symbols = get_universe(config.market, role="all", limit=config.universe_limit)
        provider = _provider_for(config.market)
        mkt = Market(config.market)
        warnings: list[str] = []

        histories: dict[str, pd.Series] = {}
        volumes: dict[str, pd.Series] = {}
        names: dict[str, str] = {}
        for symbol, name in symbols:
            try:
                df = provider.get_historical(symbol, mkt, period=config.period)
                close = _close_series(df)
                if len(close) < config.lookback_long + 5:
                    warnings.append(f"{symbol} 历史行情不足，已跳过")
                    continue
                histories[symbol] = close
                volume = _volume_series(df)
                if not volume.empty:
                    volumes[symbol] = volume.reindex(close.index).fillna(0)
                names[symbol] = name
            except Exception as exc:
                warnings.append(f"{symbol} 历史行情获取失败: {str(exc)[:80]}")

        if len(histories) < max(config.top_n, 2):
            finished_at = datetime.utcnow()
            return {
                "run_id": run_id,
                "strategy": self.strategy_name,
                "market": config.market,
                "period": config.period,
                "status": "failed",
                "initial_cash": config.initial_cash,
                "final_value": config.initial_cash,
                "params": _params(config),
                "metrics": _empty_metrics(),
                "warnings": warnings + ["可用历史行情标的不足，无法完成回测"],
                "trades": [],
                "equity_curve": [],
                "started_at": started_at,
                "finished_at": finished_at,
            }

        prices = pd.DataFrame(histories).sort_index().ffill().dropna(how="all")
        prices = prices.dropna(axis=1, thresh=max(config.lookback_long + 5, int(len(prices) * 0.55))).ffill()
        volume_frame = pd.DataFrame(volumes).reindex(prices.index).fillna(0) if volumes else pd.DataFrame(index=prices.index)
        if len(prices) < config.lookback_long + 5:
            finished_at = datetime.utcnow()
            return {
                "run_id": run_id,
                "strategy": self.strategy_name,
                "market": config.market,
                "period": config.period,
                "status": "failed",
                "initial_cash": config.initial_cash,
                "final_value": config.initial_cash,
                "params": _params(config),
                "metrics": _empty_metrics(),
                "warnings": warnings + ["合并后的历史行情长度不足"],
                "trades": [],
                "equity_curve": [],
                "started_at": started_at,
                "finished_at": finished_at,
            }

        cash = float(config.initial_cash)
        positions: dict[str, float] = {}
        lots: dict[str, list[tuple[datetime, float]]] = {}
        trades: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []
        peak = config.initial_cash
        prev_value = config.initial_cash

        for i, (date, row) in enumerate(prices.iterrows()):
            if i >= config.lookback_long and (i - config.lookback_long) % config.rebalance_days == 0:
                target_symbols = _select_targets(prices.iloc[:i], config)
                trade_prices = row.to_dict()
                cash, positions, lots = _rebalance(
                    cash,
                    positions,
                    lots,
                    target_symbols,
                    prices.iloc[: i + 1],
                    volume_frame.iloc[: i + 1],
                    trade_prices,
                    names,
                    date,
                    trades,
                    config,
                )

            positions_value = sum(
                qty * _safe_price(row.get(symbol))
                for symbol, qty in positions.items()
                if _safe_price(row.get(symbol)) > 0
            )
            total_value = cash + positions_value
            peak = max(peak, total_value)
            daily_return = total_value / prev_value - 1 if prev_value else 0
            drawdown = total_value / peak - 1 if peak else 0
            equity_curve.append({
                "date": _to_datetime(date),
                "cash": round(cash, 2),
                "positions_value": round(positions_value, 2),
                "total_value": round(total_value, 2),
                "daily_return": round(daily_return, 6),
                "drawdown": round(drawdown, 6),
                "positions": {
                    symbol: round(qty, 4)
                    for symbol, qty in positions.items()
                    if qty > 0
                },
            })
            prev_value = total_value

        final_value = equity_curve[-1]["total_value"] if equity_curve else config.initial_cash
        finished_at = datetime.utcnow()
        metrics = _metrics(equity_curve, trades, config.initial_cash)
        return {
            "run_id": run_id,
            "strategy": self.strategy_name,
            "market": config.market,
            "period": config.period,
            "status": "success",
            "initial_cash": config.initial_cash,
            "final_value": final_value,
            "params": _params(config),
            "metrics": metrics,
            "warnings": warnings,
            "trades": trades,
            "equity_curve": equity_curve,
            "started_at": started_at,
            "finished_at": finished_at,
        }


def _select_targets(prices: pd.DataFrame, config: BacktestConfig) -> list[str]:
    scores: list[tuple[str, float]] = []
    for symbol in prices.columns:
        series = prices[symbol].dropna()
        if len(series) < config.lookback_long + 1:
            continue
        short_ret = series.iloc[-1] / series.iloc[-config.lookback_short] - 1
        long_ret = series.iloc[-1] / series.iloc[-config.lookback_long] - 1
        vol = series.pct_change().tail(config.lookback_short).std()
        if not math.isfinite(short_ret) or not math.isfinite(long_ret):
            continue
        score = short_ret * 0.55 + long_ret * 0.35 - (float(vol or 0) * 0.75)
        scores.append((symbol, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, score in scores[: config.top_n] if score > 0]


def _rebalance(
    cash: float,
    positions: dict[str, float],
    lots: dict[str, list[tuple[datetime, float]]],
    target_symbols: list[str],
    price_frame: pd.DataFrame,
    volume_frame: pd.DataFrame,
    prices: dict[str, Any],
    names: dict[str, str],
    date,
    trades: list[dict[str, Any]],
    config: BacktestConfig,
) -> tuple[float, dict[str, float], dict[str, list[tuple[datetime, float]]]]:
    trade_date = _to_datetime(date)
    for symbol in list(positions.keys()):
        if symbol in target_symbols:
            continue
        price = _safe_price(prices.get(symbol))
        held_qty = positions.get(symbol, 0)
        if price <= 0 or held_qty <= 0:
            continue
        if _is_suspended(price_frame, volume_frame, symbol, config):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, held_qty, 0, 0, "suspension_or_no_volume"))
            continue
        qty = _available_qty_for_backtest(lots, symbol, trade_date, config)
        if qty <= 0:
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, held_qty, 0, 0, "t1_blocked"))
            continue
        qty = min(qty, held_qty)
        capped_qty = _cap_qty_by_volume(volume_frame, symbol, qty, config)
        if capped_qty <= 0:
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, qty, 0, 0, "volume_participation_blocked"))
            continue
        qty = capped_qty
        if _is_blocked_by_limit(price_frame, symbol, "SELL"):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, qty, 0, 0, "limit_down_blocked"))
            continue
        deal_price = _deal_price(price, "SELL", config)
        amount = deal_price * qty
        fee = _fee(amount, config, "SELL")
        cash += amount - fee
        positions[symbol] = max(held_qty - qty, 0)
        _consume_lots(lots, symbol, qty)
        if positions[symbol] <= 1e-8:
            positions.pop(symbol, None)
            lots.pop(symbol, None)
        trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL", deal_price, qty, amount, fee, "rebalance_out"))

    current_value = cash + sum(
        qty * _safe_price(prices.get(symbol))
        for symbol, qty in positions.items()
    )
    if not target_symbols or current_value <= 0:
        return cash, positions, lots

    target_value = min(current_value / len(target_symbols), current_value * config.max_position_ratio)
    for symbol in target_symbols:
        price = _safe_price(prices.get(symbol))
        if price <= 0:
            continue
        if _is_suspended(price_frame, volume_frame, symbol, config):
            action = "BUY_BLOCKED" if symbol not in positions else "SELL_BLOCKED"
            trades.append(_trade(date, symbol, names.get(symbol, symbol), action, price, 0, 0, 0, "suspension_or_no_volume"))
            continue
        current_qty = positions.get(symbol, 0)
        current_amount = current_qty * price
        diff_value = target_value - current_amount
        if abs(diff_value) < max(100, target_value * 0.02):
            continue
        if diff_value > 0:
            if _is_blocked_by_limit(price_frame, symbol, "BUY"):
                trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "limit_up_blocked"))
                continue
            buy_amount = min(diff_value, cash)
            if buy_amount <= 0:
                continue
            deal_price = _deal_price(price, "BUY", config)
            fee = _fee(buy_amount, config, "BUY")
            qty = max((buy_amount - fee) / deal_price, 0)
            qty = _cap_qty_by_volume(volume_frame, symbol, qty, config)
            if qty <= 0:
                trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "volume_participation_blocked"))
                continue
            gross = qty * deal_price
            fee = _fee(gross, config, "BUY")
            cash -= gross + fee
            positions[symbol] = current_qty + qty
            lots.setdefault(symbol, []).append((trade_date, qty))
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY", deal_price, qty, gross, fee, "momentum_rank_in"))
        else:
            sell_amount = min(abs(diff_value), current_amount)
            qty = min(sell_amount / price, current_qty)
            if qty <= 0:
                continue
            available_qty = _available_qty_for_backtest(lots, symbol, trade_date, config)
            if available_qty <= 0:
                trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, current_qty, 0, 0, "t1_blocked"))
                continue
            qty = min(qty, available_qty)
            capped_qty = _cap_qty_by_volume(volume_frame, symbol, qty, config)
            if capped_qty <= 0:
                trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, qty, 0, 0, "volume_participation_blocked"))
                continue
            qty = capped_qty
            if _is_blocked_by_limit(price_frame, symbol, "SELL"):
                trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, qty, 0, 0, "limit_down_blocked"))
                continue
            deal_price = _deal_price(price, "SELL", config)
            amount = qty * deal_price
            fee = _fee(amount, config, "SELL")
            cash += amount - fee
            remaining = current_qty - qty
            _consume_lots(lots, symbol, qty)
            if remaining <= 1e-8:
                positions.pop(symbol, None)
                lots.pop(symbol, None)
            else:
                positions[symbol] = remaining
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL", deal_price, qty, amount, fee, "rebalance_trim"))

    return cash, positions, lots


def _metrics(equity_curve: list[dict[str, Any]], trades: list[dict[str, Any]], initial_cash: float) -> dict[str, float]:
    if not equity_curve:
        return _empty_metrics()
    values = pd.Series([point["total_value"] for point in equity_curve], dtype="float64")
    returns = values.pct_change().dropna()
    total_return = values.iloc[-1] / initial_cash - 1
    years = max(len(values) / 252, 1 / 252)
    annual_return = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1
    max_drawdown = min(point["drawdown"] for point in equity_curve)
    sharpe = 0.0
    if len(returns) > 2 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * math.sqrt(252))
    sells = [trade for trade in trades if trade["action"] == "SELL"]
    win_rate = _trade_win_rate(trades)
    return {
        "total_return": round(float(total_return), 6),
        "annual_return": round(float(annual_return), 6),
        "max_drawdown": round(float(max_drawdown), 6),
        "sharpe": round(float(sharpe), 4),
        "win_rate": round(win_rate, 4),
        "trade_count": len(trades),
        "sell_count": len(sells),
        "days": len(values),
    }


def _trade_win_rate(trades: list[dict[str, Any]]) -> float:
    lots: dict[str, list[tuple[float, float]]] = {}
    wins = 0
    sells = 0
    for trade in trades:
        symbol = trade["symbol"]
        if trade["action"] == "BUY":
            lots.setdefault(symbol, []).append((trade["price"], trade["quantity"]))
            continue
        if trade["action"] != "SELL":
            continue
        qty_to_match = trade["quantity"]
        cost = 0.0
        matched = 0.0
        queue = lots.get(symbol, [])
        while queue and qty_to_match > 1e-8:
            buy_price, buy_qty = queue.pop(0)
            take = min(buy_qty, qty_to_match)
            cost += take * buy_price
            matched += take
            qty_to_match -= take
            if buy_qty > take:
                queue.insert(0, (buy_price, buy_qty - take))
        if matched > 0:
            sells += 1
            if trade["price"] * matched > cost:
                wins += 1
    return wins / sells if sells else 0.0


def _close_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    for column in ("Close", "close", "收盘"):
        if column in df.columns:
            series = pd.to_numeric(df[column], errors="coerce")
            series.index = pd.to_datetime(df.index)
            return series.dropna()
    if "日期" in df.columns and "收盘" in df.columns:
        series = pd.to_numeric(df["收盘"], errors="coerce")
        series.index = pd.to_datetime(df["日期"])
        return series.dropna()
    return pd.Series(dtype="float64")


def _volume_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    for column in ("Volume", "volume", "成交量"):
        if column in df.columns:
            series = pd.to_numeric(df[column], errors="coerce")
            series.index = pd.to_datetime(df.index)
            return series.fillna(0)
    if "日期" in df.columns and "成交量" in df.columns:
        series = pd.to_numeric(df["成交量"], errors="coerce")
        series.index = pd.to_datetime(df["日期"])
        return series.fillna(0)
    return pd.Series(dtype="float64")


def _trade(date, symbol: str, name: str, action: str, price: float, quantity: float, amount: float, fee: float, reason: str) -> dict[str, Any]:
    return {
        "date": _to_datetime(date),
        "symbol": symbol,
        "name": name,
        "action": action,
        "price": round(price, 4),
        "quantity": round(quantity, 4),
        "amount": round(amount, 2),
        "fee": round(fee, 2),
        "reason": reason,
    }


def _params(config: BacktestConfig) -> dict[str, Any]:
    return {
        "universe_limit": config.universe_limit,
        "top_n": config.top_n,
        "rebalance_days": config.rebalance_days,
        "lookback_short": config.lookback_short,
        "lookback_long": config.lookback_long,
        "fee_rate": config.fee_rate,
        "slippage_rate": config.slippage_rate,
        "min_fee": config.min_fee,
        "max_position_ratio": config.max_position_ratio,
        "max_volume_participation_pct": config.max_volume_participation_pct,
        "constraints": {
            "fee": True,
            "slippage": True,
            "min_fee": True,
            "stamp_duty_sell": True,
            "transfer_fee": True,
            "limit_up_down": config.market == "a_stock",
            "t_plus_1": config.market == "a_stock",
            "suspension": True,
            "volume_participation": True,
        },
        "note": "价格动量基线回测，不使用当前财务/新闻；已计入佣金、最低佣金、A股过户费、卖出印花税、滑点、基础涨跌停、T+1、停牌/无成交和成交量参与上限。",
    }


def _empty_metrics() -> dict[str, float]:
    return {
        "total_return": 0.0,
        "annual_return": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "win_rate": 0.0,
        "trade_count": 0,
        "sell_count": 0,
        "days": 0,
    }


def _provider_for(market: str):
    if market == "a_stock":
        return AStockProvider()
    return YFinanceProvider()


def _safe_price(value: Any) -> float:
    try:
        price = float(value or 0)
        if math.isfinite(price):
            return price
    except (TypeError, ValueError):
        pass
    return 0.0


def _fee(amount: float, config: BacktestConfig, action: str) -> float:
    if amount <= 0:
        return 0.0
    costs = compute_trade_costs(
        action,
        config.market,
        1,
        amount,
        commission_rate=config.fee_rate,
        min_commission=config.min_fee,
    )
    return costs.total_fee


def _deal_price(price: float, action: str, config: BacktestConfig) -> float:
    slip = max(config.slippage_rate, 0)
    if action.upper() == "BUY":
        return price * (1 + slip)
    return price * (1 - slip)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return pd.to_datetime(value).to_pydatetime().replace(tzinfo=None)


def _is_blocked_by_limit(price_frame: pd.DataFrame, symbol: str, action: str) -> bool:
    if symbol not in price_frame.columns or len(price_frame) < 2:
        return False
    current = _safe_price(price_frame[symbol].iloc[-1])
    prev = _safe_price(price_frame[symbol].iloc[-2])
    if current <= 0 or prev <= 0:
        return True
    daily_return = current / prev - 1
    limit = a_share_limit_pct(symbol)
    if action.upper() == "BUY":
        return daily_return >= limit * 0.995
    return daily_return <= -limit * 0.995


def _is_suspended(price_frame: pd.DataFrame, volume_frame: pd.DataFrame, symbol: str, config: BacktestConfig) -> bool:
    if config.market != "a_stock":
        return False
    if symbol not in price_frame.columns:
        return True
    price = _safe_price(price_frame[symbol].iloc[-1])
    if price <= 0:
        return True
    if volume_frame.empty or symbol not in volume_frame.columns:
        return False
    return _safe_price(volume_frame[symbol].iloc[-1]) <= 0


def _cap_qty_by_volume(volume_frame: pd.DataFrame, symbol: str, qty: float, config: BacktestConfig) -> float:
    if qty <= 0 or config.max_volume_participation_pct <= 0:
        return 0.0
    if config.market != "a_stock" or volume_frame.empty or symbol not in volume_frame.columns:
        return qty
    max_qty = _safe_price(volume_frame[symbol].iloc[-1]) * config.max_volume_participation_pct
    if max_qty <= 0:
        return 0.0
    return min(qty, max_qty)


def _available_qty_for_backtest(
    lots: dict[str, list[tuple[datetime, float]]],
    symbol: str,
    trade_date: datetime,
    config: BacktestConfig,
) -> float:
    symbol_lots = lots.get(symbol, [])
    if config.market != "a_stock":
        return sum(qty for _, qty in symbol_lots)
    return sum(qty for bought_at, qty in symbol_lots if bought_at.date() < trade_date.date())


def _consume_lots(lots: dict[str, list[tuple[datetime, float]]], symbol: str, qty: float) -> None:
    remaining = qty
    updated: list[tuple[datetime, float]] = []
    for bought_at, lot_qty in lots.get(symbol, []):
        if remaining <= 1e-8:
            updated.append((bought_at, lot_qty))
            continue
        take = min(lot_qty, remaining)
        remaining -= take
        left = lot_qty - take
        if left > 1e-8:
            updated.append((bought_at, left))
    if updated:
        lots[symbol] = updated
    else:
        lots.pop(symbol, None)
