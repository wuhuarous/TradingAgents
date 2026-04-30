"""虚拟账户 — 资金管理 + 交易执行"""
from datetime import datetime
from typing import Optional


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
            p.get("current_price", 0) * p.get("quantity", 0)
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
            "price": price, "quantity": sell_qty, "revenue": revenue,
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
