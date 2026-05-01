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
        reason="触及止损线" if triggered else "",
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
    if avg_cost > 0 and (current_price / avg_cost - 1) >= take_profit_pct:
        return True
    return False
