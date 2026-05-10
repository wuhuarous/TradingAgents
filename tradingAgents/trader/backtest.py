"""Baseline backtest engine.

This intentionally starts with a price-only momentum baseline. It avoids
using current fundamentals or current news in historical simulations, so the
result is a realistic benchmark instead of a look-ahead-biased demo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.trader.strategy.short_term_100 import ShortTerm100Strategy
from tradingAgents.trader.trade_rules import a_share_limit_pct, compute_trade_costs

SHORT_TERM_BACKTEST_MAX_SYMBOLS = 60


@dataclass
class BacktestConfig:
    strategy: str = "baseline_momentum"
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
    short_min_score: float = 80.0
    short_exit_score: float = 55.0
    max_holding_days: int = 20


class BaselineMomentumBacktester:
    strategy_name = "baseline_momentum"

    def run(self, config: BacktestConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        run_id = f"bt{started_at.strftime('%Y%m%d%H%M%S%f')}"
        symbols, universe_warnings = _backtest_universe(config)
        provider = _provider_for(config.market)
        mkt = Market(config.market)
        warnings: list[str] = list(universe_warnings)

        local_histories, local_warnings = _load_clickhouse_histories(symbols, config)
        warnings.extend(local_warnings)
        histories: dict[str, pd.Series] = {}
        volumes: dict[str, pd.Series] = {}
        names: dict[str, str] = {}
        for symbol, name in symbols:
            if symbol in local_histories:
                df = local_histories[symbol]
                close = _close_series(df)
                if len(close) >= config.lookback_long + 5:
                    histories[symbol] = close
                    volume = _volume_series(df)
                    if not volume.empty:
                        volumes[symbol] = volume.reindex(close.index).fillna(0)
                    names[symbol] = name

        fetch_external = len(histories) < max(config.top_n, 2)
        external_symbols = [(symbol, name) for symbol, name in symbols if symbol not in histories]
        if histories and external_symbols and not fetch_external:
            warnings.append(f"本次回测优先使用本地 ClickHouse 日线，覆盖 {len(histories)}/{len(symbols)} 只；未覆盖标的未走外部慢接口。")

        for symbol, name in (external_symbols if fetch_external else []):
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


class ShortTerm100BacktestStrategy:
    """Daily backtest for the short-term 100-point model.

    Signals are calculated with data up to the previous trading day and are
    executed on the current trading day. This keeps the implementation clear of
    future data while still using the same scoring logic as live simulation.
    """

    strategy_name = "short_term_100"

    def __init__(self, scorer: ShortTerm100Strategy | None = None):
        self.scorer = scorer or ShortTerm100Strategy()

    def run(self, config: BacktestConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        run_id = f"bt{started_at.strftime('%Y%m%d%H%M%S%f')}"
        symbols, universe_warnings = _backtest_universe(config)
        provider = _provider_for(config.market)
        mkt = Market(config.market)
        warnings: list[str] = list(universe_warnings)
        histories, local_warnings = _load_clickhouse_histories(symbols, config)
        warnings.extend(local_warnings)
        names: dict[str, str] = {}
        for symbol, name in symbols:
            if symbol in histories:
                names[symbol] = name

        fetch_external = len(histories) < max(config.top_n, 2)
        external_symbols = [(symbol, name) for symbol, name in symbols if symbol not in histories]
        if histories and external_symbols and not fetch_external:
            warnings.append(f"本次回测优先使用本地 ClickHouse 日线，覆盖 {len(histories)}/{len(symbols)} 只；未覆盖标的未走外部慢接口。")

        for symbol, name in (external_symbols if fetch_external else []):
            try:
                df = _normalize_ohlcv(provider.get_historical(symbol, mkt, period=config.period))
                if len(df) < config.lookback_long + 5:
                    warnings.append(f"{symbol} 历史行情不足，已跳过")
                    continue
                histories[symbol] = df
                names[symbol] = name
            except Exception as exc:
                warnings.append(f"{symbol} 历史行情获取失败: {str(exc)[:80]}")

        return self.run_on_histories(config, histories, names=names, warnings=warnings, run_id=run_id, started_at=started_at)

    def run_on_histories(
        self,
        config: BacktestConfig,
        histories: dict[str, pd.DataFrame],
        names: dict[str, str] | None = None,
        warnings: list[str] | None = None,
        run_id: str | None = None,
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        started_at = started_at or datetime.utcnow()
        run_id = run_id or f"bt{started_at.strftime('%Y%m%d%H%M%S%f')}"
        names = names or {symbol: symbol for symbol in histories}
        warnings = list(warnings or [])

        normalized = {
            symbol: _normalize_ohlcv(df)
            for symbol, df in histories.items()
            if df is not None and not df.empty
        }
        normalized = {
            symbol: df
            for symbol, df in normalized.items()
            if len(df) >= config.lookback_long + 5
        }
        anomaly_scores = {
            symbol: score
            for symbol, df in normalized.items()
            if (score := _history_short_term_anomaly_score(df, symbol)) > 0
        }
        anomaly_symbols = set(anomaly_scores)
        if len(anomaly_symbols) >= max(config.top_n, 2):
            dropped = len(normalized) - len(anomaly_symbols)
            if dropped > 0:
                warnings.append(f"短线规则预筛排除 {dropped} 只全周期无涨停/倍量标的，避免无异动股票参与回测。")
            normalized = {symbol: df for symbol, df in normalized.items() if symbol in anomaly_symbols}
        if len(normalized) > SHORT_TERM_BACKTEST_MAX_SYMBOLS:
            keep_symbols = {
                symbol
                for symbol, _ in sorted(
                    anomaly_scores.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:SHORT_TERM_BACKTEST_MAX_SYMBOLS]
            }
            normalized = {symbol: df for symbol, df in normalized.items() if symbol in keep_symbols}
            warnings.append(
                f"交互式短线回测按异动强度选取前 {SHORT_TERM_BACKTEST_MAX_SYMBOLS} 只；全量严谨验证请使用离线/Qlib 实验。"
            )
        if len(normalized) < max(config.top_n, 2):
            finished_at = datetime.utcnow()
            return {
                "run_id": run_id,
                "strategy": self.strategy_name,
                "market": config.market,
                "period": config.period,
                "status": "failed",
                "initial_cash": config.initial_cash,
                "final_value": config.initial_cash,
                "params": _params(config, self.strategy_name),
                "metrics": _empty_metrics(),
                "warnings": warnings + ["可用历史行情标的不足，无法完成短线 100 分回测"],
                "trades": [],
                "equity_curve": [],
                "started_at": started_at,
                "finished_at": finished_at,
            }

        close_frame = pd.DataFrame({symbol: df["close"] for symbol, df in normalized.items()}).sort_index()
        close_frame = close_frame.dropna(how="all").ffill()
        volume_frame = pd.DataFrame({symbol: df["volume"] for symbol, df in normalized.items()}).reindex(close_frame.index).fillna(0)
        if len(close_frame) < config.lookback_long + 5:
            finished_at = datetime.utcnow()
            return {
                "run_id": run_id,
                "strategy": self.strategy_name,
                "market": config.market,
                "period": config.period,
                "status": "failed",
                "initial_cash": config.initial_cash,
                "final_value": config.initial_cash,
                "params": _params(config, self.strategy_name),
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
        position_plans: dict[str, dict[str, Any]] = {}
        trades: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []
        peak = config.initial_cash
        prev_value = config.initial_cash

        for trade_i, (trade_date, row) in enumerate(close_frame.iterrows()):
            signal_i = trade_i - 1
            if signal_i >= config.lookback_long:
                signal_date = close_frame.index[signal_i]
                signal_scores = self._score_signal_day(
                    normalized,
                    signal_date,
                    forced_symbols=set(positions.keys()),
                )
                cash, positions, lots = _short_term_rebalance(
                    cash=cash,
                    positions=positions,
                    lots=lots,
                    position_plans=position_plans,
                    signal_scores=signal_scores,
                    prices=row.to_dict(),
                    price_frame=close_frame.iloc[: trade_i + 1],
                    volume_frame=volume_frame.iloc[: trade_i + 1],
                    names=names,
                    date=trade_date,
                    trades=trades,
                    config=config,
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
                "date": _to_datetime(trade_date),
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
        return {
            "run_id": run_id,
            "strategy": self.strategy_name,
            "market": config.market,
            "period": config.period,
            "status": "success",
            "initial_cash": config.initial_cash,
            "final_value": final_value,
            "params": _params(config, self.strategy_name),
            "metrics": _metrics(equity_curve, trades, config.initial_cash),
            "warnings": warnings,
            "trades": trades,
            "equity_curve": equity_curve,
            "started_at": started_at,
            "finished_at": finished_at,
        }

    def _score_signal_day(
        self,
        histories: dict[str, pd.DataFrame],
        signal_date: Any,
        forced_symbols: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        forced_symbols = forced_symbols or set()
        scores: dict[str, dict[str, Any]] = {}
        for symbol, df in histories.items():
            if signal_date not in df.index:
                continue
            signal_pos = df.index.get_loc(signal_date)
            if isinstance(signal_pos, slice) or signal_pos < 1:
                continue
            if symbol not in forced_symbols and not _short_term_candidate_prefilter(df, int(signal_pos), symbol):
                continue
            hist = df.iloc[:signal_pos]
            quote_row = df.iloc[signal_pos]
            quote = {
                "symbol": symbol,
                "price": _safe_price(quote_row.get("close")),
                "close": _safe_price(hist["close"].iloc[-1]) if not hist.empty else 0,
                "high": _safe_price(quote_row.get("high")),
                "low": _safe_price(quote_row.get("low")),
                "volume": _safe_price(quote_row.get("volume")),
                "market_cap": _safe_price(quote_row.get("market_cap")),
            }
            score = self.scorer.score(hist, quote, fundamentals={})
            if score.get("score", 0) > 0:
                scores[symbol] = score
        return scores


def _short_term_candidate_prefilter(df: pd.DataFrame, signal_pos: int, symbol: str) -> bool:
    """Cheap anomaly gate before running the full 100-point scorer."""
    if signal_pos < 1:
        return False
    window = df.iloc[max(0, signal_pos - 31): signal_pos + 1]
    if window.empty:
        return False
    close = pd.to_numeric(window.get("close"), errors="coerce").dropna()
    if len(close) < 2:
        return False
    limit_up_pct = 0.195 if str(symbol).startswith(("300", "301", "688")) else 0.095
    if bool(close.pct_change().tail(30).ge(limit_up_pct).any()):
        return True

    volume = pd.to_numeric(window.get("volume"), errors="coerce").dropna()
    if len(volume) < 6:
        return False
    avg_vol = float(volume.iloc[:-1].tail(30).mean() or 0)
    if avg_vol <= 0:
        return False
    return float(volume.tail(30).max() or 0) >= avg_vol * 2


def _history_short_term_anomaly_score(df: pd.DataFrame, symbol: str) -> float:
    score = 0.0
    close = pd.to_numeric(df.get("close"), errors="coerce").dropna()
    if len(close) >= 2:
        limit_up_pct = 0.195 if str(symbol).startswith(("300", "301", "688")) else 0.095
        returns = close.pct_change()
        limit_count = int(returns.ge(limit_up_pct).sum())
        score += limit_count * 100
        recent_high_ret = float(returns.tail(60).max() or 0)
        score += max(recent_high_ret, 0) * 100
    volume = pd.to_numeric(df.get("volume"), errors="coerce").dropna()
    if len(volume) < 6:
        return score
    avg_vol = volume.rolling(30, min_periods=5).mean().shift(1)
    ratio = volume / avg_vol.replace(0, pd.NA)
    max_ratio = float(ratio.replace([pd.NA], 0).fillna(0).max() or 0)
    if max_ratio >= 2:
        score += min(max_ratio, 10) * 10
    return score


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


def _short_term_rebalance(
    cash: float,
    positions: dict[str, float],
    lots: dict[str, list[tuple[datetime, float]]],
    position_plans: dict[str, dict[str, Any]],
    signal_scores: dict[str, dict[str, Any]],
    prices: dict[str, Any],
    price_frame: pd.DataFrame,
    volume_frame: pd.DataFrame,
    names: dict[str, str],
    date,
    trades: list[dict[str, Any]],
    config: BacktestConfig,
) -> tuple[float, dict[str, float], dict[str, list[tuple[datetime, float]]]]:
    trade_date = _to_datetime(date)

    for symbol in list(positions.keys()):
        price = _safe_price(prices.get(symbol))
        held_qty = positions.get(symbol, 0)
        if price <= 0 or held_qty <= 0:
            continue
        score = signal_scores.get(symbol, {})
        reason = _short_term_sell_reason(price, position_plans.get(symbol, {}), score, trade_date, config)
        if not reason:
            continue
        if _is_suspended(price_frame, volume_frame, symbol, config):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, held_qty, 0, 0, "suspension_or_no_volume"))
            continue
        qty = _available_qty_for_backtest(lots, symbol, trade_date, config)
        if qty <= 0:
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, held_qty, 0, 0, "t1_blocked"))
            continue
        qty = min(qty, held_qty)
        qty = _round_quantity(_cap_qty_by_volume(volume_frame, symbol, qty, config), config.market)
        if qty <= 0:
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL_BLOCKED", price, held_qty, 0, 0, "volume_participation_blocked"))
            continue
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
            position_plans.pop(symbol, None)
        trades.append(_trade(date, symbol, names.get(symbol, symbol), "SELL", deal_price, qty, amount, fee, reason))

    total_value = cash + sum(
        qty * _safe_price(prices.get(symbol))
        for symbol, qty in positions.items()
    )

    for symbol in list(positions.keys()):
        score = signal_scores.get(symbol)
        price = _safe_price(prices.get(symbol))
        if not score or price <= 0:
            continue
        if not _short_term_should_add(positions, symbol, price, total_value, score, position_plans.get(symbol, {}), config):
            continue
        if _is_suspended(price_frame, volume_frame, symbol, config):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "suspension_or_no_volume"))
            continue
        if _is_blocked_by_limit(price_frame, symbol, "BUY"):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "limit_up_blocked"))
            continue
        add_ratio = float(score.get("add_position_ratio") or score.get("trade_plan", {}).get("add_position_ratio") or 0)
        budget = min(cash, total_value * add_ratio)
        cash = _short_term_buy(
            cash,
            positions,
            lots,
            position_plans,
            symbol,
            names.get(symbol, symbol),
            price,
            budget,
            "ADD",
            "short_term_add",
            score,
            volume_frame,
            trade_date,
            trades,
            config,
        )

    total_value = cash + sum(
        qty * _safe_price(prices.get(symbol))
        for symbol, qty in positions.items()
    )
    ranked = sorted(
        (
            (symbol, score)
            for symbol, score in signal_scores.items()
            if float(score.get("score") or 0) >= config.short_min_score and symbol not in positions
            and not score.get("exit_signal")
        ),
        key=lambda item: float(item[1].get("score") or 0),
        reverse=True,
    )
    free_slots = max(config.top_n - len(positions), 0)
    for symbol, score in ranked[:free_slots]:
        price = _safe_price(prices.get(symbol))
        if price <= 0:
            continue
        if _is_suspended(price_frame, volume_frame, symbol, config):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "suspension_or_no_volume"))
            continue
        if _is_blocked_by_limit(price_frame, symbol, "BUY"):
            trades.append(_trade(date, symbol, names.get(symbol, symbol), "BUY_BLOCKED", price, 0, 0, 0, "limit_up_blocked"))
            continue
        position_ratio = min(
            float(score.get("initial_position_ratio") or score.get("trade_plan", {}).get("position_ratio") or 0),
            config.max_position_ratio,
        )
        if position_ratio <= 0:
            continue
        budget = min(cash, total_value * position_ratio)
        cash = _short_term_buy(
            cash,
            positions,
            lots,
            position_plans,
            symbol,
            names.get(symbol, symbol),
            price,
            budget,
            "BUY",
            "short_term_score_in",
            score,
            volume_frame,
            trade_date,
            trades,
            config,
        )

    return cash, positions, lots


def _short_term_buy(
    cash: float,
    positions: dict[str, float],
    lots: dict[str, list[tuple[datetime, float]]],
    position_plans: dict[str, dict[str, Any]],
    symbol: str,
    name: str,
    price: float,
    budget: float,
    action: str,
    reason: str,
    score: dict[str, Any],
    volume_frame: pd.DataFrame,
    trade_date: datetime,
    trades: list[dict[str, Any]],
    config: BacktestConfig,
) -> float:
    if budget <= 0 or cash <= 0:
        return cash
    deal_price = _deal_price(price, "BUY", config)
    qty = _quantity_from_budget(budget, deal_price, config.market)
    qty = _round_quantity(_cap_qty_by_volume(volume_frame, symbol, qty, config), config.market)
    if qty <= 0:
        trades.append(_trade(trade_date, symbol, name, "BUY_BLOCKED", price, 0, 0, 0, "volume_participation_blocked"))
        return cash
    gross = qty * deal_price
    fee = _fee(gross, config, "BUY")
    if gross + fee > cash:
        qty = _quantity_from_budget(cash - config.min_fee, deal_price, config.market)
        qty = _round_quantity(_cap_qty_by_volume(volume_frame, symbol, qty, config), config.market)
        gross = qty * deal_price
        fee = _fee(gross, config, "BUY")
    if qty <= 0 or gross + fee > cash:
        return cash
    cash -= gross + fee
    positions[symbol] = positions.get(symbol, 0) + qty
    lots.setdefault(symbol, []).append((trade_date, qty))
    existing = position_plans.get(symbol, {})
    position_plans[symbol] = {
        "entry_date": existing.get("entry_date") or trade_date,
        "entry_price": existing.get("entry_price") or deal_price,
        "entry_score": existing.get("entry_score") or score.get("score", 0),
        "last_score": score.get("score", 0),
        "stop_loss": max(float(existing.get("stop_loss") or 0), float(score.get("stop_loss") or 0)),
        "take_profit": max(float(existing.get("take_profit") or 0), float(score.get("take_profit") or 0)),
        "key_level": float(score.get("key_level") or 0),
    }
    trades.append(_trade(trade_date, symbol, name, action, deal_price, qty, gross, fee, reason))
    return cash


def _short_term_sell_reason(
    price: float,
    plan: dict[str, Any],
    score: dict[str, Any],
    trade_date: datetime,
    config: BacktestConfig,
) -> str:
    stop_loss = float(plan.get("stop_loss") or 0)
    take_profit = float(plan.get("take_profit") or 0)
    if stop_loss > 0 and price <= stop_loss:
        return "short_stop_loss"
    if take_profit > 0 and price >= take_profit:
        return "short_take_profit"
    if score and score.get("exit_signal"):
        for signal in score.get("sell_signals") or []:
            if signal.get("severity") == "exit":
                return f"short_{signal.get('key') or 'exit_signal'}"
        return "short_exit_signal"
    entry_price = float(plan.get("entry_price") or 0)
    key_level = float(score.get("key_level") or plan.get("key_level") or 0)
    if entry_price > 0 and key_level > 0 and price / entry_price - 1 >= 0.06 and price < key_level * 0.995:
        return "short_profit_protect"
    if score and float(score.get("score") or 0) < config.short_exit_score:
        return "short_score_faded"
    entry_date = plan.get("entry_date")
    if isinstance(entry_date, datetime) and config.max_holding_days > 0:
        if (trade_date.date() - entry_date.date()).days >= config.max_holding_days:
            return "short_max_holding_days"
    return ""


def _short_term_should_add(
    positions: dict[str, float],
    symbol: str,
    price: float,
    total_value: float,
    score: dict[str, Any],
    plan: dict[str, Any],
    config: BacktestConfig,
) -> bool:
    if price <= 0 or total_value <= 0:
        return False
    short_score = float(score.get("score") or 0)
    add_ratio = float(score.get("add_position_ratio") or score.get("trade_plan", {}).get("add_position_ratio") or 0)
    if score.get("exit_signal") or short_score < max(90, config.short_min_score) or add_ratio <= 0:
        return False
    stop_loss = float(plan.get("stop_loss") or score.get("stop_loss") or 0)
    if stop_loss > 0 and price <= stop_loss:
        return False
    key_level = float(score.get("key_level") or plan.get("key_level") or 0)
    if key_level > 0 and price < key_level:
        return False
    entry_price = float(plan.get("entry_price") or 0)
    if entry_price > 0 and price / entry_price - 1 < 0.015:
        return False
    current_value = positions.get(symbol, 0) * price
    return current_value / total_value < min(0.45, config.max_position_ratio + add_ratio)


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
    outcomes = _trade_outcomes(trades)
    return {
        "total_return": round(float(total_return), 6),
        "annual_return": round(float(annual_return), 6),
        "max_drawdown": round(float(max_drawdown), 6),
        "sharpe": round(float(sharpe), 4),
        "win_rate": round(outcomes["win_rate"], 4),
        "profit_factor": round(outcomes["profit_factor"], 4),
        "trade_count": len(trades),
        "sell_count": len(sells),
        "days": len(values),
    }


def _trade_win_rate(trades: list[dict[str, Any]]) -> float:
    return _trade_outcomes(trades)["win_rate"]


def _trade_outcomes(trades: list[dict[str, Any]]) -> dict[str, float]:
    lots: dict[str, list[tuple[float, float]]] = {}
    wins = 0
    sells = 0
    gross_profit = 0.0
    gross_loss = 0.0
    for trade in trades:
        symbol = trade["symbol"]
        if trade["action"] in ("BUY", "ADD"):
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
            pnl = trade["price"] * matched - cost
            if pnl > 0:
                wins += 1
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)
    return {
        "win_rate": wins / sells if sells else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0),
    }


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["close", "high", "low", "volume", "market_cap"])
    source = df.copy()
    if "日期" in source.columns:
        source.index = pd.to_datetime(source["日期"])
    else:
        source.index = pd.to_datetime(source.index)
    close = _column_series(source, "Close", "close", "收盘")
    high = _column_series(source, "High", "high", "最高")
    low = _column_series(source, "Low", "low", "最低")
    volume = _column_series(source, "Volume", "volume", "成交量")
    market_cap = _column_series(source, "market_cap", "总市值", "市值")
    result = pd.DataFrame({
        "close": close,
        "high": high if not high.empty else close,
        "low": low if not low.empty else close,
        "volume": volume if not volume.empty else pd.Series(0, index=close.index),
        "market_cap": market_cap if not market_cap.empty else pd.Series(0, index=close.index),
    }).sort_index()
    return result.dropna(subset=["close"])


def _column_series(df: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in df.columns:
            series = pd.to_numeric(df[name], errors="coerce")
            series.index = pd.to_datetime(df.index)
            return series.dropna()
    return pd.Series(dtype="float64")


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


def _params(config: BacktestConfig, strategy_name: str = "baseline_momentum") -> dict[str, Any]:
    strategy_note = (
        "短线 100 分日线回测，逐日计算信号并下一交易日执行；复用模拟交易短线评分，已计入交易约束。"
        if strategy_name == "short_term_100"
        else "价格动量基线回测，不使用当前财务/新闻；已计入佣金、最低佣金、A股过户费、卖出印花税、滑点、基础涨跌停、T+1、停牌/无成交和成交量参与上限。"
    )
    return {
        "strategy": strategy_name,
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
        "short_min_score": config.short_min_score,
        "short_exit_score": config.short_exit_score,
        "max_holding_days": config.max_holding_days,
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
            "no_look_ahead": True,
        },
        "note": strategy_note,
    }


def _empty_metrics() -> dict[str, float]:
    return {
        "total_return": 0.0,
        "annual_return": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "trade_count": 0,
        "sell_count": 0,
        "days": 0,
    }


def _provider_for(market: str):
    if market == "a_stock":
        return AStockProvider()
    return YFinanceProvider()


def _backtest_universe(config: BacktestConfig) -> tuple[list[tuple[str, str]], list[str]]:
    local_symbols = _clickhouse_kline_universe(config)
    if local_symbols:
        warnings = []
        if len(local_symbols) < config.universe_limit:
            warnings.append(f"本地日线仅覆盖 {len(local_symbols)}/{config.universe_limit} 只，回测先使用已入库标的；请先同步/导出更多日线后再做全市场验证。")
        return local_symbols, warnings
    return get_universe(config.market, role="all", limit=config.universe_limit), []


def _clickhouse_kline_universe(config: BacktestConfig) -> list[tuple[str, str]]:
    if config.market != "a_stock":
        return []
    try:
        from tradingAgents.data.database.connection import get_ch_client

        ch = get_ch_client()
        rows = ch.query(f"""
            SELECT symbol
            FROM (
                SELECT symbol, max(date) AS latest_date, count() AS row_count
                FROM kline_daily
                GROUP BY symbol
                HAVING row_count >= {int(config.lookback_long + 5)}
                ORDER BY latest_date DESC, symbol ASC
                LIMIT {int(max(config.universe_limit, 1))}
            )
        """).result_rows
        return [(str(row[0]), str(row[0])) for row in rows if row and row[0]]
    except Exception:
        return []


def _load_clickhouse_histories(
    symbols: list[tuple[str, str]],
    config: BacktestConfig,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Load local A-share daily bars for interactive backtests.

    External historical quote APIs are the slowest and least stable part of
    running a backtest.  When the project has already synced daily bars into
    ClickHouse, use them first and only fall back to external providers when
    local coverage is too small to run the strategy.
    """
    if config.market != "a_stock" or not symbols:
        return {}, []
    try:
        from tradingAgents.data.database.connection import get_ch_client

        ch = get_ch_client()
        max_date_rows = ch.query("SELECT max(date) FROM kline_daily").result_rows
        max_date = max_date_rows[0][0] if max_date_rows and max_date_rows[0] else None
        if not max_date:
            return {}, []

        days = _period_trading_days(config.period)
        start_date = max_date - timedelta(days=max(days * 2, 90))
        frames: list[pd.DataFrame] = []
        requested = [symbol for symbol, _ in symbols]
        for chunk in _chunks(requested, 500):
            in_sql = ", ".join(_sql_quote(symbol) for symbol in chunk)
            if not in_sql:
                continue
            df = ch.query_df(f"""
                SELECT
                    symbol,
                    date,
                    anyLast(open) AS open,
                    anyLast(high) AS high,
                    anyLast(low) AS low,
                    anyLast(close) AS close,
                    anyLast(volume) AS volume
                FROM kline_daily
                WHERE symbol IN ({in_sql})
                  AND date >= toDate('{start_date.isoformat()}')
                GROUP BY symbol, date
                ORDER BY symbol, date
            """)
            if df is not None and not df.empty:
                frames.append(df)
        if not frames:
            return {}, []

        all_rows = pd.concat(frames, ignore_index=True)
        histories: dict[str, pd.DataFrame] = {}
        for symbol, group in all_rows.groupby("symbol"):
            source = group.sort_values("date").tail(days).copy()
            source.index = pd.to_datetime(source["date"])
            hist = pd.DataFrame({
                "open": pd.to_numeric(source["open"], errors="coerce"),
                "high": pd.to_numeric(source["high"], errors="coerce"),
                "low": pd.to_numeric(source["low"], errors="coerce"),
                "close": pd.to_numeric(source["close"], errors="coerce"),
                "volume": pd.to_numeric(source["volume"], errors="coerce").fillna(0),
                "market_cap": 0.0,
            }, index=source.index).dropna(subset=["close"])
            if len(hist) >= config.lookback_long + 5:
                histories[str(symbol)] = hist
        return histories, []
    except Exception as exc:
        return {}, [f"ClickHouse 日线读取失败，已回退外部行情: {str(exc)[:120]}"]


def _period_trading_days(period: str) -> int:
    return {"3mo": 66, "6mo": 132, "1y": 252}.get(period, 132)


def _chunks(values: list[str], size: int):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _sql_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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


def _quantity_from_budget(budget: float, price: float, market: str) -> float:
    if budget <= 0 or price <= 0:
        return 0.0
    return _round_quantity(budget / price, market)


def _round_quantity(qty: float, market: str) -> float:
    if qty <= 0:
        return 0.0
    if market == "a_stock":
        return float(int(qty // 100) * 100)
    return float(qty)


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
