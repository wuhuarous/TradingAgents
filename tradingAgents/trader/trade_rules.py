"""Trading microstructure rules for simulation and backtests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from tradingAgents.utils.timezone import CN_TZ


@dataclass(frozen=True)
class TradeCosts:
    gross_amount: float
    commission: float
    transfer_fee: float
    stamp_duty: float
    total_fee: float
    cash_delta: float


def a_share_limit_pct(symbol: str, name: str = "") -> float:
    """Return the daily price limit ratio for common A-share simulation."""
    normalized = (name or "").upper()
    if symbol.startswith(("300", "301", "688")):
        return 0.20
    if symbol.startswith(("8", "4", "9")):
        return 0.30
    if "ST" in normalized or "*ST" in normalized:
        return 0.05
    return 0.10


def is_limit_up(symbol: str, price: float, prev_close: float, name: str = "", tolerance: float = 0.002) -> bool:
    if price <= 0 or prev_close <= 0:
        return False
    return price >= prev_close * (1 + a_share_limit_pct(symbol, name)) * (1 - tolerance)


def is_limit_down(symbol: str, price: float, prev_close: float, name: str = "", tolerance: float = 0.002) -> bool:
    if price <= 0 or prev_close <= 0:
        return False
    return price <= prev_close * (1 - a_share_limit_pct(symbol, name)) * (1 + tolerance)


def can_buy_at_price(market: str, symbol: str, price: float, prev_close: float = 0, name: str = "") -> bool:
    return not (market == "a_stock" and is_limit_up(symbol, price, prev_close, name))


def can_sell_at_price(market: str, symbol: str, price: float, prev_close: float = 0, name: str = "") -> bool:
    return not (market == "a_stock" and is_limit_down(symbol, price, prev_close, name))


def china_trade_date(value: datetime | None = None):
    """Return the China trading calendar date for a timestamp.

    Database timestamps in this project are naive UTC by default. When a
    timestamp has no timezone, treat it as UTC before converting to Shanghai.
    """
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CN_TZ).date()


def is_same_china_trade_date(created_at: datetime | None, as_of: datetime | None = None) -> bool:
    if created_at is None:
        return False
    return china_trade_date(created_at) == china_trade_date(as_of)


def is_suspended_or_untradable(price: float, volume: float = 0, amount: float = 0) -> bool:
    """Best-effort suspension/no-trade guard for live simulation.

    Real suspension data should come from exchange status fields when available.
    In the current quote feeds, price<=0 or both volume and amount missing are
    the most reliable generic signals that the symbol should not be traded.
    """
    if price <= 0:
        return True
    return float(volume or 0) <= 0 and float(amount or 0) <= 0


def max_order_quantity_by_volume(
    volume: float,
    participation_pct: float,
    market: str = "a_stock",
    lot_size: int = 100,
) -> int:
    """Cap simulated order size by today's observed volume."""
    if participation_pct <= 0:
        return 0
    max_qty = int(float(volume or 0) * participation_pct)
    if market == "a_stock":
        return max_qty // lot_size * lot_size
    return max_qty


def compute_trade_costs(
    action: str,
    market: str,
    price: float,
    quantity: float,
    commission_rate: float = 0.0003,
    min_commission: float = 5.0,
    transfer_fee_rate: float = 0.00001,
    stamp_duty_rate: float = 0.0005,
) -> TradeCosts:
    """Compute cash impact.

    A-share assumptions:
    - commission: both sides, configurable, minimum 5 RMB
    - transfer fee: both sides, 0.001% by amount
    - stamp duty: sell side only, 0.05% by amount
    Non-A markets currently use commission only in this project.
    """
    gross = max(float(price or 0) * float(quantity or 0), 0.0)
    if gross <= 0:
        return TradeCosts(0, 0, 0, 0, 0, 0)

    commission = max(gross * commission_rate, min_commission)
    transfer_fee = gross * transfer_fee_rate if market == "a_stock" else 0.0
    stamp_duty = gross * stamp_duty_rate if market == "a_stock" and action.lower() == "sell" else 0.0
    total_fee = commission + transfer_fee + stamp_duty
    cash_delta = -(gross + total_fee) if action.lower() == "buy" else gross - total_fee
    return TradeCosts(
        gross_amount=round(gross, 6),
        commission=round(commission, 6),
        transfer_fee=round(transfer_fee, 6),
        stamp_duty=round(stamp_duty, 6),
        total_fee=round(total_fee, 6),
        cash_delta=round(cash_delta, 6),
    )
