"""Short-term 100-point scoring model.

The model is intentionally deterministic and data-local. It can be used by
live simulation with realtime quotes, and by backtests with a historical quote
constructed from the signal day only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ShortTerm100Config:
    small_cap_billion: float = 100.0
    watch_threshold: float = 70.0
    pilot_threshold: float = 80.0
    aggressive_threshold: float = 90.0
    pilot_initial_ratio: float = 0.22
    aggressive_initial_ratio: float = 0.30
    pilot_add_ratio: float = 0.15
    aggressive_add_ratio: float = 0.20
    volume_stall_ratio: float = 1.6
    trend_break_buffer: float = 0.985


class ShortTerm100Strategy:
    """Score the user's short-term strength model on a 100-point scale."""

    def __init__(self, config: ShortTerm100Config | None = None):
        self.config = config or ShortTerm100Config()

    def score(self, hist: pd.DataFrame, quote: Any, fundamentals: dict[str, float] | None = None) -> dict[str, Any]:
        fundamentals = fundamentals or {}
        close = _series(hist, "收盘", "Close", "close")
        volume = _series(hist, "成交量", "Volume", "volume")
        high = _series(hist, "最高", "High", "high")
        low = _series(hist, "最低", "Low", "low")

        price = _quote_number(quote, "price")
        prev_close = _quote_number(quote, "close", "prev_close")
        current_volume = _quote_number(quote, "volume")
        current_high = _quote_number(quote, "high", default=price)
        current_low = _quote_number(quote, "low", default=price)
        market_cap = _quote_number(quote, "market_cap")
        symbol = str(_quote_value(quote, "symbol", default="") or "")

        components: list[dict[str, Any]] = []
        reasons: list[str] = []
        warnings: list[str] = []

        def add(key: str, label: str, points: int, passed: bool, detail: str = "") -> None:
            components.append({
                "key": key,
                "label": label,
                "points": points,
                "earned": points if passed else 0,
                "passed": passed,
                "detail": detail,
            })
            if passed:
                reasons.append(f"短线加分: {label}{'，' + detail if detail else ''}")

        if close.empty or price <= 0:
            return self._empty("短线数据不足，不能按进攻模型交易")

        combined_close = pd.concat([close, pd.Series([price])], ignore_index=True)
        combined_volume = (
            pd.concat([volume, pd.Series([current_volume])], ignore_index=True)
            if not volume.empty
            else pd.Series([current_volume])
        )
        combined_high = (
            pd.concat([high, pd.Series([current_high])], ignore_index=True)
            if not high.empty
            else combined_close
        )
        combined_low = (
            pd.concat([low, pd.Series([current_low])], ignore_index=True)
            if not low.empty
            else combined_close
        )

        pct = combined_close.pct_change().fillna(0)
        recent_returns = pct.tail(30)
        limit_up_pct = 0.195 if symbol.startswith(("300", "301", "688")) else 0.095
        limit_mask = recent_returns >= limit_up_pct
        has_limit_up = bool(limit_mask.any())
        limit_indices = list(limit_mask[limit_mask].index)
        limit_idx = int(limit_indices[-1]) if limit_indices else None
        limit_low = float(combined_low.iloc[limit_idx]) if limit_idx is not None and limit_idx < len(combined_low) else 0
        held_limit_low = bool(limit_low and price >= limit_low)

        avg_vol_30 = (
            float(combined_volume.tail(31).iloc[:-1].mean())
            if len(combined_volume) >= 31
            else float(combined_volume.mean() or 0)
        )
        max_recent_vol_ratio = float((combined_volume.tail(30) / avg_vol_30).max()) if avg_vol_30 else 0
        has_double_volume = max_recent_vol_ratio >= 2

        high_20_prev = float(combined_high.iloc[:-1].tail(20).max()) if len(combined_high) > 1 else price
        high_60_prev = float(combined_high.iloc[:-1].tail(60).max()) if len(combined_high) > 1 else price
        low_20_prev = float(combined_low.iloc[:-1].tail(20).min()) if len(combined_low) > 1 else price
        range_20 = (high_20_prev / low_20_prev - 1) if low_20_prev else 0
        breakout = price >= high_20_prev * 0.995 or price >= high_60_prev * 0.99
        sideways_breakout = range_20 <= 0.18 and breakout

        ma5 = float(combined_close.tail(5).mean())
        ma10 = float(combined_close.tail(10).mean()) if len(combined_close) >= 10 else ma5
        pullback_volume = False
        if len(combined_close) >= 8 and len(combined_volume) >= 8:
            last_3_ret = combined_close.iloc[-1] / combined_close.iloc[-4] - 1 if combined_close.iloc[-4] else 0
            vol_3 = float(combined_volume.tail(3).mean())
            vol_10 = float(combined_volume.tail(10).mean()) if len(combined_volume) >= 10 else vol_3
            pullback_volume = -0.08 <= last_3_ret <= 0.03 and vol_3 <= vol_10 * 0.85 and price >= ma10 * 0.98

        latest_ret = (price / prev_close - 1) if prev_close else 0
        rel_strength = _short_market_resilience(combined_close)
        close_position = (price - current_low) / (current_high - current_low) if current_high > current_low else 1
        stand_key_level = price >= max(ma5, ma10) and close_position >= 0.55

        small_cap = 0 < market_cap <= self.config.small_cap_billion
        if market_cap <= 0:
            pb = fundamentals.get("pb", 0)
            small_cap = 0 < pb <= 8 and price < 80
            warnings.append("市值字段缺失，小市值项用估值/价格作弱替代")

        add("limit_up_30d", "30 天内有涨停", 15, has_limit_up)
        add("double_volume_30d", "30 天内有倍量", 10, has_double_volume, f"最高量比 {max_recent_vol_ratio:.1f}x" if max_recent_vol_ratio else "")
        add("small_cap", "市值 100 亿以内", 10, small_cap, f"市值 {market_cap:.1f} 亿" if market_cap else "")
        add("hold_limit_low", "涨停后未跌破涨停日最低价", 15, has_limit_up and held_limit_low)
        add("breakout", "横盘突破或突破前高", 15, breakout or sideways_breakout)
        add("market_resilience", "大盘跌它不跌", 15, rel_strength)
        add("pullback_absorption", "回调缩量、有承接", 10, pullback_volume)
        add("late_key_level", "下午 2 点后仍站稳关键位", 10, stand_key_level)

        score = sum(item["earned"] for item in components)
        if latest_ret >= limit_up_pct:
            warnings.append("当前接近涨停，模型只允许观察，不追涨买入")
        if close_position < 0.35:
            warnings.append("当前价格接近日内低位，承接不足")

        buy_tier = "watch"
        initial_ratio = 0.0
        add_ratio = 0.0
        if score >= self.config.aggressive_threshold:
            buy_tier = "aggressive"
            initial_ratio = self.config.aggressive_initial_ratio
            add_ratio = self.config.aggressive_add_ratio
        elif score >= self.config.pilot_threshold:
            buy_tier = "pilot"
            initial_ratio = self.config.pilot_initial_ratio
            add_ratio = self.config.pilot_add_ratio
        elif score >= self.config.watch_threshold:
            buy_tier = "watch"
            initial_ratio = 0.0

        stop_base = limit_low if limit_low and held_limit_low else min(ma10, price * 0.94)
        stop_loss = min(price * 0.94, stop_base * 0.995) if stop_base > 0 else price * 0.94
        take_profit = price * (1.12 if buy_tier == "pilot" else 1.18 if buy_tier == "aggressive" else 1.10)
        key_level = max(ma5, ma10)
        sell_signals, risk_flags = _exit_signals(
            price=price,
            prev_close=prev_close,
            current_high=current_high,
            current_low=current_low,
            current_volume=current_volume,
            combined_close=combined_close,
            combined_high=combined_high,
            combined_volume=combined_volume,
            ma10=ma10,
            key_level=key_level,
            limit_low=limit_low,
            volume_stall_ratio=self.config.volume_stall_ratio,
            trend_break_buffer=self.config.trend_break_buffer,
        )
        exit_reasons = [signal["label"] for signal in sell_signals if signal.get("severity") == "exit"]
        exit_signal = bool(exit_reasons)
        if exit_signal:
            warnings.append("出现短线退出信号: " + "；".join(exit_reasons[:2]))
        warnings.extend(flag["label"] for flag in risk_flags[:2])

        return {
            "score": round(float(score), 1),
            "components": components,
            "reasons": reasons,
            "warnings": warnings,
            "sell_signals": sell_signals,
            "risk_flags": risk_flags,
            "exit_signal": exit_signal,
            "exit_reason": "；".join(exit_reasons),
            "buy_tier": buy_tier,
            "initial_position_ratio": initial_ratio,
            "add_position_ratio": add_ratio,
            "stop_loss": round(stop_loss, 3),
            "take_profit": round(take_profit, 3),
            "key_level": round(key_level, 3),
            "close_position": round(close_position, 3),
            "trade_plan": {
                "entry": round(price, 3),
                "stop_loss": round(stop_loss, 3),
                "take_profit": round(take_profit, 3),
                "position_ratio": round(initial_ratio, 4),
                "entry_mode": buy_tier,
                "add_position_ratio": round(add_ratio, 4),
                "add_condition": "放量突破关键位且不跌破首次买入止损线" if add_ratio > 0 else "",
                "exit_rules": [
                    "跌破涨停日低点/关键均线立即退出",
                    "放量滞涨或突破失败退出",
                    "盈利后跌破关键位先保护利润",
                ],
                "sell_signals": sell_signals,
            },
        }

    def _empty(self, warning: str) -> dict[str, Any]:
        return {
            "score": 0,
            "components": [],
            "reasons": [],
            "warnings": [warning],
            "sell_signals": [],
            "risk_flags": [],
            "exit_signal": False,
            "exit_reason": "",
            "buy_tier": "none",
            "initial_position_ratio": 0,
            "add_position_ratio": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "key_level": 0,
            "close_position": 0,
            "trade_plan": {
                "entry": 0,
                "stop_loss": 0,
                "take_profit": 0,
                "position_ratio": 0,
                "entry_mode": "none",
                "add_position_ratio": 0,
                "exit_rules": [],
                "sell_signals": [],
            },
        }


def _short_market_resilience(close: pd.Series) -> bool:
    if close is None or len(close) < 8:
        return False
    ret_5 = close.iloc[-1] / close.iloc[-6] - 1 if close.iloc[-6] else 0
    drawdown_5 = close.iloc[-1] / close.tail(6).max() - 1 if close.tail(6).max() else 0
    return ret_5 >= -0.015 and drawdown_5 >= -0.05


def _exit_signals(
    *,
    price: float,
    prev_close: float,
    current_high: float,
    current_low: float,
    current_volume: float,
    combined_close: pd.Series,
    combined_high: pd.Series,
    combined_volume: pd.Series,
    ma10: float,
    key_level: float,
    limit_low: float,
    volume_stall_ratio: float,
    trend_break_buffer: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sell_signals: list[dict[str, Any]] = []
    risk_flags: list[dict[str, Any]] = []

    def add_signal(key: str, label: str, detail: str = "", severity: str = "exit") -> None:
        sell_signals.append({
            "key": key,
            "label": label,
            "detail": detail,
            "severity": severity,
        })

    def add_risk(key: str, label: str, detail: str = "") -> None:
        risk_flags.append({
            "key": key,
            "label": label,
            "detail": detail,
            "severity": "watch",
        })

    if price <= 0:
        return sell_signals, risk_flags

    latest_ret = price / prev_close - 1 if prev_close else 0
    close_position = (price - current_low) / (current_high - current_low) if current_high > current_low else 1
    vol_10 = float(combined_volume.tail(10).mean()) if len(combined_volume) >= 3 else 0
    vol_20 = float(combined_volume.tail(20).mean()) if len(combined_volume) >= 3 else vol_10
    volume_ratio = current_volume / vol_10 if vol_10 > 0 else 0

    if limit_low > 0 and price < limit_low * 0.995:
        add_signal("limit_low_lost", "跌破涨停日最低价", f"涨停低点 {limit_low:.3f}")

    if ma10 > 0 and price < ma10 * trend_break_buffer and latest_ret <= -0.005 and close_position < 0.55:
        add_signal("ma10_break", "跌破 10 日关键均线", f"MA10 {ma10:.3f}")

    if (
        volume_ratio >= volume_stall_ratio
        and -0.01 <= latest_ret <= 0.02
        and close_position < 0.55
    ):
        add_signal("volume_stall", "放量滞涨", f"当日量比 {volume_ratio:.1f}x")

    if len(combined_high) >= 21:
        high_20_prev = float(combined_high.iloc[:-1].tail(20).max())
        failed_breakout = (
            high_20_prev > 0
            and current_high >= high_20_prev * 0.995
            and price < high_20_prev * 0.98
            and close_position < 0.45
            and volume_ratio >= 1.15
        )
        if failed_breakout:
            add_signal("failed_breakout", "突破前高失败且收在低位", f"前高 {high_20_prev:.3f}")

    if len(combined_close) >= 4 and len(combined_high) >= 4 and vol_20 > 0:
        three_day_ret = combined_close.iloc[-1] / combined_close.iloc[-4] - 1 if combined_close.iloc[-4] else 0
        high_not_lifted = combined_high.iloc[-1] <= combined_high.iloc[-4:-1].max() * 1.005
        avg_3_volume = float(combined_volume.tail(3).mean())
        if -0.015 <= three_day_ret <= 0.025 and high_not_lifted and avg_3_volume >= vol_20 * 1.25:
            add_signal("three_bar_stall", "三日放量但高点未抬高", f"3 日涨幅 {three_day_ret * 100:.1f}%")

    if key_level > 0 and price < key_level and not sell_signals:
        add_risk("key_level_lost", "未站稳短线关键位", f"关键位 {key_level:.3f}")
    if latest_ret >= 0.07 and volume_ratio >= 2 and close_position < 0.7:
        add_risk("chase_risk", "高位放量但收盘位置不强，追涨风险偏高", f"当日量比 {volume_ratio:.1f}x")

    return sell_signals, risk_flags


def _series(df: pd.DataFrame, *names: str) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for name in names:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").dropna()
    return pd.Series(dtype=float)


def _quote_value(quote: Any, key: str, default: Any = 0) -> Any:
    if isinstance(quote, dict):
        return quote.get(key, default)
    return getattr(quote, key, default)


def _quote_number(quote: Any, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = _quote_value(quote, key, None)
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            continue
    return float(default or 0)
